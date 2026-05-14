# -*- coding: utf-8 -*-
"""market 内置的 MCP stateful client。"""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import AsyncExitStack
from datetime import timedelta
from typing import Any, Literal

import httpx
from mcp import ClientSession
from mcp.client.sse import sse_client
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.client.streamable_http import streamable_http_client

logger = logging.getLogger(__name__)

MCP_CALL_TIMEOUT = float(os.environ.get("SWE_MCP_CALL_TIMEOUT", "120"))
MCP_PER_NOTIFICATION_TIMEOUT = float(
    os.environ.get("SWE_MCP_PER_NOTIFICATION_TIMEOUT", "120"),
)
MCP_MAX_TOTAL_TIMEOUT = float(
    os.environ.get("SWE_MCP_MAX_TOTAL_TIMEOUT", "0"),
)


async def _call_with_timeout(
    coro,
    timeout: float,
    operation: str,
    client_name: str,
):
    """对 MCP 调用增加统一超时保护。"""
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except asyncio.TimeoutError:
        logger.error(
            "MCP client '%s' %s timed out after %.0fs",
            client_name,
            operation,
            timeout,
        )
        raise


async def _call_with_timeout_refresh(
    coro,
    per_notification_timeout: float,
    max_total_timeout: float | None,
    operation: str,
    client_name: str,
    progress_event: asyncio.Event | None = None,
    on_progress_callback=None,
):
    """收到进度通知时刷新超时窗口。"""
    if progress_event is None:
        return await _call_with_timeout(
            coro,
            per_notification_timeout,
            operation,
            client_name,
        )

    task = asyncio.ensure_future(coro)
    loop = asyncio.get_running_loop()
    task.add_done_callback(lambda _task: progress_event.set())
    deadline = loop.time() + max_total_timeout if max_total_timeout else None

    try:
        while not task.done():
            try:
                await asyncio.wait_for(
                    progress_event.wait(),
                    timeout=per_notification_timeout,
                )
                progress_event.clear()
                if on_progress_callback is not None:
                    on_progress_callback()
            except asyncio.TimeoutError:
                task.cancel()
                logger.error(
                    "MCP client '%s' %s timed out after %.0fs "
                    "(no progress notification)",
                    client_name,
                    operation,
                    per_notification_timeout,
                )
                raise

            if deadline and loop.time() > deadline:
                task.cancel()
                logger.error(
                    "MCP client '%s' %s exceeded max total timeout %.0fs",
                    client_name,
                    operation,
                    max_total_timeout,
                )
                raise asyncio.TimeoutError()

        return task.result()
    except asyncio.CancelledError:
        task.cancel()
        raise
    except asyncio.TimeoutError:
        raise
    except Exception:
        task.cancel()
        raise


class StdIOStatefulClient:
    """stdio MCP client。"""

    def __init__(
        self,
        name: Any,
        command: Any,
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
        cwd: str | None = None,
        encoding: str = "utf-8",
        encoding_error_handler: Literal[
            "strict",
            "ignore",
            "replace",
        ] = "strict",
    ) -> None:
        if not isinstance(name, str):
            raise TypeError(f"name must be str, got {type(name).__name__}")
        if not isinstance(command, str):
            raise TypeError(
                f"command must be str, got {type(command).__name__}",
            )

        self.name = name
        self.server_params = StdioServerParameters(
            command=command,
            args=args or [],
            env=env,
            cwd=cwd,
            encoding=encoding,
            encoding_error_handler=encoding_error_handler,
        )
        self._lifecycle_task: asyncio.Task | None = None
        self._reload_event = asyncio.Event()
        self._ready_event = asyncio.Event()
        self._stop_event = asyncio.Event()
        self.session: ClientSession | None = None
        self.is_connected = False
        self._cached_tools = None
        self.on_progress_callback = None

    async def _run_lifecycle(self) -> None:
        """在同一任务内完成 connect / close 生命周期。"""
        while not self._stop_event.is_set():
            try:
                async with AsyncExitStack() as stack:
                    read_stream, write_stream = (
                        await stack.enter_async_context(
                            stdio_client(self.server_params),
                        )
                    )
                    self.session = ClientSession(read_stream, write_stream)
                    await stack.enter_async_context(self.session)
                    await self.session.initialize()
                    self.is_connected = True
                    self._ready_event.set()

                    while (
                        not self._reload_event.is_set()
                        and not self._stop_event.is_set()
                    ):
                        await asyncio.sleep(0.1)

                    self.session = None
                    self.is_connected = False
                    self._cached_tools = None

                    if self._reload_event.is_set():
                        self._reload_event.clear()
                        self._ready_event.clear()
            except Exception as exc:
                logger.error(
                    "Error in MCP client lifecycle for %s: %s",
                    self.name,
                    exc,
                    exc_info=True,
                )
                self.session = None
                self.is_connected = False
                self._cached_tools = None
                self._ready_event.clear()
                await asyncio.sleep(1)

    async def connect(self, timeout: float = 30.0) -> None:
        """连接 MCP 服务器。"""
        if self.is_connected:
            raise RuntimeError(
                f"MCP client '{self.name}' is already connected. "
                f"Call close() before connecting again.",
            )

        self._stop_event.clear()
        self._lifecycle_task = asyncio.create_task(self._run_lifecycle())
        try:
            await asyncio.wait_for(self._ready_event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            self._stop_event.set()
            if self._lifecycle_task:
                await self._lifecycle_task
            raise

    async def close(self, ignore_errors: bool = True) -> None:
        """关闭 MCP 连接。"""
        if not self.is_connected:
            if not ignore_errors:
                raise RuntimeError(
                    f"MCP client '{self.name}' is not connected. "
                    f"Call connect() before closing.",
                )
            return

        try:
            self._stop_event.set()
            if self._lifecycle_task:
                await self._lifecycle_task
                self._lifecycle_task = None
        except Exception:
            if not ignore_errors:
                raise

    async def reload(self, timeout: float = 30.0) -> None:
        """重连当前 MCP 客户端。"""
        if not self.is_connected:
            raise RuntimeError(
                f"MCP client '{self.name}' is not connected. "
                f"Call connect() first.",
            )

        self._reload_event.set()
        await asyncio.wait_for(self._ready_event.wait(), timeout=timeout)

    async def list_tools(self, timeout: float = MCP_CALL_TIMEOUT):
        """获取服务端工具列表。"""
        self._validate_connection()
        result = await _call_with_timeout(
            self.session.list_tools(),
            timeout=timeout,
            operation="list_tools",
            client_name=self.name,
        )
        self._cached_tools = result.tools
        return result.tools

    async def call_tool(
        self,
        name: str,
        arguments: dict | None = None,
        meta: dict[str, Any] | None = None,
    ):
        """调用服务端工具。"""
        self._validate_connection()

        progress_event = asyncio.Event()
        progress_token = None

        if meta and "progressToken" in meta:
            progress_token = meta["progressToken"]

            async def _on_progress(_progress, _total, _message):
                progress_event.set()
                if self.on_progress_callback is not None:
                    self.on_progress_callback()

            self.session._progress_callbacks[progress_token] = _on_progress

        try:
            return await _call_with_timeout_refresh(
                self.session.call_tool(name, arguments or {}, meta=meta),
                per_notification_timeout=MCP_PER_NOTIFICATION_TIMEOUT,
                max_total_timeout=MCP_MAX_TOTAL_TIMEOUT or None,
                operation=f"call_tool({name})",
                client_name=self.name,
                progress_event=progress_event if progress_token else None,
                on_progress_callback=self.on_progress_callback,
            )
        finally:
            if progress_token:
                self.session._progress_callbacks.pop(progress_token, None)

    def _validate_connection(self) -> None:
        """校验 session 是否已建立。"""
        if not self.is_connected:
            raise RuntimeError(
                f"MCP client '{self.name}' is not connected. "
                f"Call connect() first.",
            )
        if not self.session:
            raise RuntimeError(
                f"MCP client '{self.name}' session is not initialized. "
                f"Call connect() first.",
            )


class HttpStatefulClient:
    """HTTP / SSE MCP client。"""

    def __init__(
        self,
        name: Any,
        transport: Any,
        url: Any,
        headers: dict[str, str] | None = None,
        timeout: float = 30,
        sse_read_timeout: float = 60 * 5,
        **client_kwargs: Any,
    ) -> None:
        if not isinstance(name, str):
            raise TypeError(f"name must be str, got {type(name).__name__}")
        if not isinstance(transport, str):
            raise TypeError(
                f"transport must be str, got {type(transport).__name__}",
            )
        if transport not in ["streamable_http", "sse"]:
            raise ValueError(
                "transport must be 'streamable_http' or 'sse', "
                f"got {transport!r}",
            )
        if not isinstance(url, str):
            raise TypeError(f"url must be str, got {type(url).__name__}")

        self.name = name
        self.transport = transport
        self.url = url
        self.headers = headers
        self.timeout = timeout
        self.sse_read_timeout = sse_read_timeout
        self.client_kwargs = client_kwargs
        self._lifecycle_task: asyncio.Task | None = None
        self._reload_event = asyncio.Event()
        self._ready_event = asyncio.Event()
        self._stop_event = asyncio.Event()
        self.session: ClientSession | None = None
        self.is_connected = False
        self._cached_tools = None
        self.on_progress_callback = None

    async def _run_lifecycle(self) -> None:
        """在同一任务内完成 connect / close 生命周期。"""
        while not self._stop_event.is_set():
            try:
                async with AsyncExitStack() as stack:
                    if self.transport == "streamable_http":
                        timeout_seconds = (
                            self.timeout.total_seconds()
                            if isinstance(self.timeout, timedelta)
                            else self.timeout
                        )
                        sse_read_timeout_seconds = (
                            self.sse_read_timeout.total_seconds()
                            if isinstance(self.sse_read_timeout, timedelta)
                            else self.sse_read_timeout
                        )
                        http_client = httpx.AsyncClient(
                            headers=self.headers or {},
                            timeout=httpx.Timeout(
                                connect=timeout_seconds,
                                read=sse_read_timeout_seconds,
                                write=timeout_seconds,
                                pool=timeout_seconds,
                            ),
                            **self.client_kwargs,
                        )
                        await stack.enter_async_context(http_client)
                        read_stream, write_stream, _ = (
                            await stack.enter_async_context(
                                streamable_http_client(
                                    url=self.url,
                                    http_client=http_client,
                                ),
                            )
                        )
                    else:
                        read_stream, write_stream = (
                            await stack.enter_async_context(
                                sse_client(
                                    url=self.url,
                                    headers=self.headers,
                                    timeout=self.timeout,
                                    sse_read_timeout=self.sse_read_timeout,
                                    **self.client_kwargs,
                                ),
                            )
                        )

                    self.session = ClientSession(read_stream, write_stream)
                    await stack.enter_async_context(self.session)
                    await self.session.initialize()
                    self.is_connected = True
                    self._ready_event.set()

                    while (
                        not self._reload_event.is_set()
                        and not self._stop_event.is_set()
                    ):
                        await asyncio.sleep(0.1)

                    self.session = None
                    self.is_connected = False
                    self._cached_tools = None

                    if self._reload_event.is_set():
                        self._reload_event.clear()
                        self._ready_event.clear()
            except Exception as exc:
                logger.error(
                    "Error in MCP client lifecycle for %s: %s",
                    self.name,
                    exc,
                    exc_info=True,
                )
                self.session = None
                self.is_connected = False
                self._cached_tools = None
                self._ready_event.clear()
                await asyncio.sleep(1)

    async def connect(self, timeout: float = 30.0) -> None:
        """连接 MCP 服务器。"""
        if self.is_connected:
            raise RuntimeError(
                f"MCP client '{self.name}' is already connected. "
                f"Call close() before connecting again.",
            )

        self._stop_event.clear()
        self._lifecycle_task = asyncio.create_task(self._run_lifecycle())
        try:
            await asyncio.wait_for(self._ready_event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            self._stop_event.set()
            if self._lifecycle_task:
                await self._lifecycle_task
            raise

    async def close(self, ignore_errors: bool = True) -> None:
        """关闭 MCP 连接。"""
        if not self.is_connected:
            if not ignore_errors:
                raise RuntimeError(
                    f"MCP client '{self.name}' is not connected. "
                    f"Call connect() before closing.",
                )
            return

        try:
            self._stop_event.set()
            if self._lifecycle_task:
                await self._lifecycle_task
                self._lifecycle_task = None
        except Exception:
            if not ignore_errors:
                raise

    async def list_tools(self, timeout: float = MCP_CALL_TIMEOUT):
        """获取服务端工具列表。"""
        self._validate_connection()
        result = await _call_with_timeout(
            self.session.list_tools(),
            timeout=timeout,
            operation="list_tools",
            client_name=self.name,
        )
        self._cached_tools = result.tools
        return result.tools

    async def call_tool(
        self,
        name: str,
        arguments: dict | None = None,
        meta: dict[str, Any] | None = None,
    ):
        """调用服务端工具。"""
        self._validate_connection()

        progress_event = asyncio.Event()
        progress_token = None

        if meta and "progressToken" in meta:
            progress_token = meta["progressToken"]

            async def _on_progress(_progress, _total, _message):
                progress_event.set()
                if self.on_progress_callback is not None:
                    self.on_progress_callback()

            self.session._progress_callbacks[progress_token] = _on_progress

        try:
            return await _call_with_timeout_refresh(
                self.session.call_tool(name, arguments or {}, meta=meta),
                per_notification_timeout=MCP_PER_NOTIFICATION_TIMEOUT,
                max_total_timeout=MCP_MAX_TOTAL_TIMEOUT or None,
                operation=f"call_tool({name})",
                client_name=self.name,
                progress_event=progress_event if progress_token else None,
                on_progress_callback=self.on_progress_callback,
            )
        finally:
            if progress_token:
                self.session._progress_callbacks.pop(progress_token, None)

    def _validate_connection(self) -> None:
        """校验 session 是否已建立。"""
        if not self.is_connected:
            raise RuntimeError(
                f"MCP client '{self.name}' is not connected. "
                f"Call connect() first.",
            )
        if not self.session:
            raise RuntimeError(
                f"MCP client '{self.name}' session is not initialized. "
                f"Call connect() first.",
            )
