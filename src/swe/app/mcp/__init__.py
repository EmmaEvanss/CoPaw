# -*- coding: utf-8 -*-
"""MCP (Model Context Protocol) client management module.

This module provides hot-reloadable MCP client management,
completely independent from other app components.

It also provides drop-in replacements for AgentScope's MCP clients
that solve the CPU leak issue caused by cross-task context manager exits.
"""

import asyncio
from dataclasses import replace
import logging
from pathlib import Path
import re
import time
import uuid
from typing import Any

from agentscope.mcp._client_base import MCPClientBase
from agentscope.mcp._mcp_function import MCPToolFunction
from agentscope.tool import ToolResponse
from mcp import ClientSession as _CS
from ...agents.tools.utils import truncate_text_output
from ...config.context import get_current_effective_tenant_id
from ...constant import (
    MCP_MAX_TOTAL_TIMEOUT,
    MCP_PER_NOTIFICATION_TIMEOUT,
    TRUNCATION_NOTICE_MARKER,
    WORKING_DIR,
)
from ...config.context import (
    get_current_tool_result_retention_days,
    get_current_workspace_dir,
)

from .manager import MCPClientManager
from .stateful_client import (
    HttpStatefulClient,
    StdIOStatefulClient,
    _call_with_timeout_refresh,
)
from .watcher import MCPConfigWatcher

logger = logging.getLogger(__name__)

_EXTERNAL_TOOL_OUTPUT_DIR = Path("memory") / "external_tool_output"


# ---------------------------------------------------------------------------
# Helpers extracted from _patched_mcp_call to keep the main function flat.
# ---------------------------------------------------------------------------


def _build_on_progress(progress_event, progress_queue, watchdog_cb):
    """Return an ``_on_progress`` callback that resets the watchdog,
    sets *progress_event*, and enqueues the notification for the
    frontend-facing generator."""

    async def _on_progress(_progress, _total, _message):
        progress_event.set()
        if watchdog_cb is not None:
            watchdog_cb()
        await progress_queue.put((_progress, _total, _message))

    return _on_progress


def _truncate_text_block_output(
    text: str,
    max_bytes: int,
    *,
    tool_name: str,
) -> str:
    """按字节裁剪外部工具文本块，并保留可续读的完整文本文件。"""
    if not text or max_bytes <= 0:
        return text

    original_text = text.split(TRUNCATION_NOTICE_MARKER, 1)[0]
    original_bytes = original_text.encode("utf-8")
    if len(original_bytes) <= max_bytes:
        return text

    saved_path = _persist_external_tool_output_text(tool_name, original_text)
    if saved_path is None:
        logger.warning(
            "skip truncating external tool output because persistence failed: "
            "tool=%s",
            tool_name,
        )
        return text

    total_lines = max(len(original_text.splitlines()), 1)
    return truncate_text_output(
        original_text,
        start_line=1,
        total_lines=total_lines,
        max_bytes=max_bytes,
        file_path=saved_path,
    )


def _truncate_tool_response_text_blocks(
    response: Any,
    max_bytes: int | None,
    *,
    tool_name: str,
) -> Any:
    """仅裁剪 ToolResponse 中的文本块，保留其他块和 metadata。"""
    if max_bytes is None:
        return response

    if isinstance(response.content, str):
        truncated_text = _truncate_text_block_output(
            response.content,
            max_bytes,
            tool_name=tool_name,
        )
        if truncated_text == response.content:
            return response
        return _replace_response_content(response, truncated_text)

    if not isinstance(response.content, list):
        return response

    next_content = []
    changed = False
    for block in response.content:
        next_block, block_changed = _truncate_response_text_block(
            block,
            max_bytes,
            tool_name=tool_name,
        )
        changed = changed or block_changed
        next_content.append(next_block)

    if not changed:
        return response
    return _replace_response_content(response, next_content)


def _replace_response_content(response: Any, content: Any) -> Any:
    """按响应对象类型回填新的 content，保留其余字段。"""
    if isinstance(response, ToolResponse):
        return replace(response, content=content)
    if hasattr(response, "model_copy"):
        return response.model_copy(update={"content": content})
    return response


def _truncate_response_text_block(
    block: Any,
    max_bytes: int,
    *,
    tool_name: str,
) -> tuple[Any, bool]:
    """统一裁剪 dict / 模型对象里的文本块。"""
    if isinstance(block, dict):
        if block.get("type") != "text":
            return block, False
        text = block.get("text")
        if not isinstance(text, str):
            return block, False
        truncated_text = _truncate_text_block_output(
            text,
            max_bytes,
            tool_name=tool_name,
        )
        if truncated_text == text:
            return block, False
        return {**block, "text": truncated_text}, True

    if getattr(block, "type", None) != "text":
        return block, False
    text = getattr(block, "text", None)
    if not isinstance(text, str):
        return block, False

    truncated_text = _truncate_text_block_output(
        text,
        max_bytes,
        tool_name=tool_name,
    )
    if truncated_text == text:
        return block, False
    if hasattr(block, "model_copy"):
        return block.model_copy(update={"text": truncated_text}), True
    try:
        return replace(block, text=truncated_text), True
    except TypeError:
        return block, False


def _launch_call_tool(
    session,
    tool_name: str,
    kwargs: dict,
    timeout,
    meta: dict,
    per_timeout: float,
    max_total: float | None,
    progress_event: asyncio.Event,
    watchdog_cb,
    progress_queue: asyncio.Queue,
) -> asyncio.Task:
    """Fire ``call_tool`` as a background task.

    When done the task puts either the ``CallToolResult`` or the raised
    exception into *progress_queue*.
    """

    async def _run():
        try:
            coro = session.call_tool(
                tool_name,
                arguments=kwargs,
                read_timeout_seconds=timeout,
                meta=meta,
            )
            result = await _call_with_timeout_refresh(
                coro,
                per_timeout,
                max_total,
                f"call_tool({tool_name})",
                tool_name,
                progress_event,
                on_progress_callback=watchdog_cb,
            )
            await progress_queue.put(result)
        except Exception as exc:
            await progress_queue.put(exc)

    return asyncio.ensure_future(_run())


async def _drain_progress(
    progress_queue,
    tool_name,
    result_box,
    external_tool_output_max_bytes: int | None,
):
    """Yield intermediate ``ToolResponse`` chunks from *progress_queue*.

    The final ``CallToolResult`` is appended to *result_box* (a one-element
    list) so the caller can retrieve it after the generator is exhausted.
    """
    while True:
        item = await progress_queue.get()
        if isinstance(item, Exception):
            raise item
        if isinstance(item, ToolResponse):
            yield _truncate_tool_response_text_blocks(
                item,
                external_tool_output_max_bytes,
                tool_name=tool_name,
            )
        elif isinstance(item, tuple):
            _p, _t, msg = item
            yield _truncate_tool_response_text_blocks(
                ToolResponse(
                    content=msg or f"tool '{tool_name}' running",
                    stream=True,
                    is_last=False,
                ),
                external_tool_output_max_bytes,
                tool_name=tool_name,
            )
        else:
            result_box.append(item)
            return


async def _call_with_progress(
    session,
    tool_name: str,
    kwargs: dict,
    timeout,
    meta: dict,
    per_timeout: float,
    max_total: float | None,
    progress_event: asyncio.Event,
    watchdog_cb,
    progress_queue: asyncio.Queue,
    wrap_tool_result: bool,
    external_tool_output_max_bytes: int | None = None,
):
    """Run ``call_tool`` in a background task, yield all chunks.

    Yields intermediate progress ``ToolResponse`` chunks while the tool
    executes, then yields the final result (or wrapped result).
    """
    task = _launch_call_tool(
        session,
        tool_name,
        kwargs,
        timeout,
        meta,
        per_timeout,
        max_total,
        progress_event,
        watchdog_cb,
        progress_queue,
    )
    result_box: list = []
    try:
        async for chunk in _drain_progress(
            progress_queue,
            tool_name,
            result_box,
            external_tool_output_max_bytes,
        ):
            yield chunk
    finally:
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass

    # Yield the final result.
    res = result_box[0]
    if wrap_tool_result:
        as_content = MCPClientBase._convert_mcp_content_to_as_blocks(
            res.content,
        )
        yield _truncate_tool_response_text_blocks(
            ToolResponse(
                content=as_content,
                metadata=res.meta,
                stream=True,
                is_last=True,
            ),
            external_tool_output_max_bytes,
            tool_name=tool_name,
        )
    else:
        yield _truncate_tool_response_text_blocks(
            res,
            external_tool_output_max_bytes,
            tool_name=tool_name,
        )


def _persist_external_tool_output_text(
    tool_name: str,
    text: str,
) -> str | None:
    """把完整外部工具文本落到当前工作区，供 read_file 续读。"""
    try:
        base_dir = get_current_workspace_dir() or WORKING_DIR
        output_dir = base_dir / _EXTERNAL_TOOL_OUTPUT_DIR
        output_dir.mkdir(parents=True, exist_ok=True)
        _cleanup_expired_external_tool_output_files(
            output_dir,
            get_current_tool_result_retention_days(),
        )
        file_name = (
            f"{_sanitize_external_tool_name(tool_name)}-"
            f"{uuid.uuid4().hex[:12]}.txt"
        )
        file_path = output_dir / file_name
        file_path.write_text(text, encoding="utf-8")
        return str(file_path.relative_to(base_dir))
    except Exception:
        logger.warning(
            "failed to persist external tool output for recovery: tool=%s",
            tool_name,
            exc_info=True,
        )
        return None


def _cleanup_expired_external_tool_output_files(
    output_dir: Path,
    retention_days: int | None,
) -> None:
    """按共享 retention_days 清理过期的外部工具输出文件。"""
    if (
        retention_days is None
        or retention_days <= 0
        or not output_dir.exists()
    ):
        return
    expire_before = time.time() - (retention_days * 24 * 60 * 60)
    for path in output_dir.glob("*.txt"):
        try:
            if path.stat().st_mtime < expire_before:
                path.unlink()
        except FileNotFoundError:
            continue
        except Exception:
            logger.debug(
                "failed to cleanup expired external tool output: %s",
                path,
                exc_info=True,
            )


def _sanitize_external_tool_name(tool_name: str) -> str:
    """把工具名收敛为适合文件名的 ASCII 片段。"""
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "-", tool_name).strip("-")
    return cleaned or "tool"


# ---------------------------------------------------------------------------
# Monkey-patch
# ---------------------------------------------------------------------------

# Monkey-patch MCPToolFunction.__call__ to auto-inject _meta with progressToken.
# progressToken is generated from X-Tenant-Id (from request context) + UUID,
# and forwarded as meta to the MCP SDK's ClientSession.call_tool.
#
# This is an **async generator** so that call_tool_function() dispatches it
# through _async_generator_wrapper.  Each yielded ToolResponse triggers
# ReActAgent._acting -> self.print(), which pushes events into the agent
# message queue and ultimately to the frontend SSE stream.  Without this,
# the entire call_tool() duration produces zero frontend-visible events.
#
# NOTE: We bypass the original __call__ entirely because its signature
# (`**kwargs`) would swallow `meta` into the arguments dict instead of
# passing it as a keyword-only param to `session.call_tool(meta=...)`.
_original_mcp_call = MCPToolFunction.__call__


async def _patched_mcp_call(self: MCPToolFunction, **kwargs: Any):  # type: ignore[override]
    from ..source_system_config import (
        resolve_external_tool_output_truncation_config,
    )

    kwargs.pop("_meta", None)

    scope_id = get_current_effective_tenant_id() or "default"
    progress_token = f"{scope_id}@{uuid.uuid4()}"
    meta = {"progressToken": progress_token}

    progress_event = asyncio.Event()
    progress_queue: asyncio.Queue = asyncio.Queue()
    watchdog_cb = getattr(self, "on_progress_callback", None)
    on_progress = _build_on_progress(
        progress_event,
        progress_queue,
        watchdog_cb,
    )

    per_timeout = MCP_PER_NOTIFICATION_TIMEOUT
    max_total = MCP_MAX_TOTAL_TIMEOUT or None
    external_tool_output_truncation = (
        resolve_external_tool_output_truncation_config()
    )

    # Common keyword arguments for _call_with_progress.
    call_kw = {
        "tool_name": self.name,
        "kwargs": kwargs,
        "timeout": self.timeout,
        "meta": meta,
        "per_timeout": per_timeout,
        "max_total": max_total,
        "progress_event": progress_event,
        "watchdog_cb": watchdog_cb,
        "progress_queue": progress_queue,
        "wrap_tool_result": self.wrap_tool_result,
        "external_tool_output_max_bytes": (
            external_tool_output_truncation.max_bytes
            if external_tool_output_truncation.enabled
            else None
        ),
    }

    if self.client_gen:
        async with self.client_gen() as cli:
            read_stream, write_stream = cli[0], cli[1]
            async with _CS(read_stream, write_stream) as session:
                await session.initialize()
                session._progress_callbacks[progress_token] = on_progress
                try:
                    async for chunk in _call_with_progress(session, **call_kw):
                        yield chunk
                finally:
                    await asyncio.sleep(0.1)
                    session._progress_callbacks.pop(progress_token, None)
    else:
        session = self.session
        session._progress_callbacks[progress_token] = on_progress
        try:
            async for chunk in _call_with_progress(session, **call_kw):
                yield chunk
        finally:
            await asyncio.sleep(0.1)
            session._progress_callbacks.pop(progress_token, None)


MCPToolFunction.__call__ = _patched_mcp_call  # type: ignore[method-assign]

__all__ = [
    "HttpStatefulClient",
    "MCPClientManager",
    "MCPConfigWatcher",
    "StdIOStatefulClient",
]
