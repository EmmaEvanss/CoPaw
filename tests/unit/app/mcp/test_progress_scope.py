# -*- coding: utf-8 -*-
"""MCP progress token scope namespace regression tests."""

from __future__ import annotations

import os
import re
from pathlib import Path
import time
from types import SimpleNamespace

import pytest
from agentscope.message import TextBlock
from agentscope.tool import ToolResponse
from mcp.types import CallToolResult, TextContent

from swe.app import mcp as app_mcp
from swe.constant import TRUNCATION_NOTICE_MARKER
from swe.config.context import (
    set_current_tool_result_retention_days,
    tenant_context,
)


@pytest.mark.asyncio
async def test_patched_mcp_call_namespaces_progress_tokens_by_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """相同 runtime 对象在不同 scope 下也必须生成不同 progress namespace。"""
    captured_tokens: list[str] = []

    async def _fake_call_with_progress(
        _session,
        *,
        meta,
        **_kwargs,
    ):
        captured_tokens.append(meta["progressToken"])
        yield SimpleNamespace(content="done", metadata=meta, is_last=True)

    token_values = iter(["uuid-a", "uuid-b"])
    fake_tool = SimpleNamespace(
        name="demo-tool",
        timeout=5.0,
        wrap_tool_result=False,
        client_gen=None,
        session=SimpleNamespace(_progress_callbacks={}),
    )

    monkeypatch.setattr(
        app_mcp,
        "_call_with_progress",
        _fake_call_with_progress,
    )
    monkeypatch.setattr(
        app_mcp.uuid,
        "uuid4",
        lambda: next(token_values),
    )

    with tenant_context(tenant_id="tenant-a", source_id="source-a"):
        async for _chunk in app_mcp._patched_mcp_call(fake_tool, value=1):
            pass

    with tenant_context(tenant_id="tenant-a", source_id="source-b"):
        async for _chunk in app_mcp._patched_mcp_call(fake_tool, value=1):
            pass

    assert captured_tokens == [
        "dGVuYW50LWE.c291cmNlLWE@uuid-a",
        "dGVuYW50LWE.c291cmNlLWI@uuid-b",
    ]


def test_truncate_tool_response_text_blocks_only_touches_text_blocks(
    tmp_path: Path,
) -> None:
    """外部工具文本块截断应保留非文本块与 metadata。"""
    workspace_dir = tmp_path / "workspace"
    workspace_dir.mkdir()
    response = ToolResponse(
        content=[
            TextBlock(type="text", text="line-1\n" * 400),
            {"type": "image", "source": {"type": "url", "url": "file://x"}},
        ],
        metadata={"source": "demo"},
        stream=True,
        is_last=True,
    )

    with tenant_context(
        tenant_id="tenant-a",
        source_id="source-a",
        workspace_dir=workspace_dir,
    ):
        truncated = app_mcp._truncate_tool_response_text_blocks(
            response,
            max_bytes=1000,
            tool_name="demo-tool",
        )

    assert truncated.metadata == {"source": "demo"}
    assert truncated.stream is True
    assert truncated.is_last is True
    assert truncated.content[1] == response.content[1]
    assert TRUNCATION_NOTICE_MARKER in truncated.content[0]["text"]


def test_truncate_tool_response_text_blocks_handles_call_tool_result(
    tmp_path: Path,
) -> None:
    """原始 CallToolResult 的 TextContent 文本块也应走统一截断逻辑。"""
    workspace_dir = tmp_path / "workspace"
    workspace_dir.mkdir()
    response = CallToolResult(
        content=[
            TextContent(type="text", text="line-1\n" * 400),
        ],
        isError=False,
    )

    with tenant_context(
        tenant_id="tenant-a",
        source_id="source-a",
        workspace_dir=workspace_dir,
    ):
        truncated = app_mcp._truncate_tool_response_text_blocks(
            response,
            max_bytes=1000,
            tool_name="demo-tool",
        )

    assert isinstance(truncated, CallToolResult)
    assert TRUNCATION_NOTICE_MARKER in truncated.content[0].text
    assert "call `read_file` with file_path=" in truncated.content[0].text


def test_truncate_tool_response_text_blocks_persists_full_text_for_recovery(
    tmp_path: Path,
) -> None:
    """MCP 截断后的完整文本应落到可续读文件中。"""
    workspace_dir = tmp_path / "workspace"
    workspace_dir.mkdir()
    response = ToolResponse(
        content=[
            TextBlock(type="text", text="line-1\n" * 400),
        ],
        stream=True,
        is_last=True,
    )

    with tenant_context(
        tenant_id="tenant-a",
        source_id="source-a",
        workspace_dir=workspace_dir,
    ):
        set_current_tool_result_retention_days(7)
        try:
            truncated = app_mcp._truncate_tool_response_text_blocks(
                response,
                max_bytes=1000,
                tool_name="demo-tool",
            )
        finally:
            set_current_tool_result_retention_days(None)

    assert TRUNCATION_NOTICE_MARKER in truncated.content[0]["text"]
    match = re.search(
        r"file_path=([^\s]+)\s+start_line=(\d+)",
        truncated.content[0]["text"],
    )
    assert match is not None
    saved_path = workspace_dir / match.group(1)
    assert saved_path.exists()
    assert saved_path.read_text(encoding="utf-8") == "line-1\n" * 400


def test_truncate_tool_response_text_blocks_cleans_expired_saved_outputs(
    tmp_path: Path,
) -> None:
    """共享 retention_days 到期后应清理旧的外部工具输出文件。"""
    workspace_dir = tmp_path / "workspace"
    output_dir = workspace_dir / app_mcp._EXTERNAL_TOOL_OUTPUT_DIR
    output_dir.mkdir(parents=True)
    expired_file = output_dir / "expired.txt"
    expired_file.write_text("old", encoding="utf-8")
    expired_at = time.time() - (3 * 24 * 60 * 60)
    os.utime(expired_file, (expired_at, expired_at))
    response = ToolResponse(
        content=[
            TextBlock(type="text", text="line-1\n" * 400),
        ],
        stream=True,
        is_last=True,
    )

    with tenant_context(
        tenant_id="tenant-a",
        source_id="source-a",
        workspace_dir=workspace_dir,
    ):
        set_current_tool_result_retention_days(1)
        try:
            app_mcp._truncate_tool_response_text_blocks(
                response,
                max_bytes=1000,
                tool_name="demo-tool",
            )
        finally:
            set_current_tool_result_retention_days(None)

    assert not expired_file.exists()
