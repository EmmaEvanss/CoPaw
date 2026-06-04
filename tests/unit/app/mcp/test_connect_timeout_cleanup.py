# -*- coding: utf-8 -*-
"""Tests for MCP connect timeout cleanup on hanging startup."""

from __future__ import annotations

import asyncio
import time
from contextlib import asynccontextmanager

import pytest

from swe.app.mcp.stateful_client import (
    HttpStatefulClient,
    StdIOStatefulClient,
)


@asynccontextmanager
async def _hanging_context_manager(*args, **kwargs):
    """模拟底层 transport 启动阶段卡住，直到被取消。"""
    del args, kwargs
    await asyncio.sleep(3600)
    yield None


@pytest.mark.asyncio
async def test_http_connect_timeout_cleans_up_hanging_lifecycle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import swe.app.mcp.stateful_client as stateful_client_module

    monkeypatch.setattr(
        stateful_client_module,
        "streamable_http_client",
        _hanging_context_manager,
    )

    client = HttpStatefulClient(
        name="demo",
        transport="streamable_http",
        url="https://mcp.example.test/stream",
        headers=None,
    )

    started_at = time.perf_counter()
    with pytest.raises(asyncio.TimeoutError):
        await client.connect(timeout=0.05)

    elapsed = time.perf_counter() - started_at
    assert elapsed < 0.2
    assert client._lifecycle_task is None or client._lifecycle_task.done()
    assert client.session is None
    assert client.is_connected is False


@pytest.mark.asyncio
async def test_stdio_connect_timeout_cleans_up_hanging_lifecycle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import mcp.client.stdio as mcp_stdio

    monkeypatch.setattr(
        mcp_stdio,
        "stdio_client",
        _hanging_context_manager,
    )

    client = StdIOStatefulClient(
        name="demo",
        command="python",
        args=["-c", "print('never reached')"],
        env=None,
        cwd=None,
    )

    started_at = time.perf_counter()
    with pytest.raises(asyncio.TimeoutError):
        await client.connect(timeout=0.05)

    elapsed = time.perf_counter() - started_at
    assert elapsed < 0.2
    assert client._lifecycle_task is None or client._lifecycle_task.done()
    assert client.session is None
    assert client.is_connected is False
