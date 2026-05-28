# -*- coding: utf-8 -*-
"""MCP progress token scope namespace regression tests."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from agentscope.message import TextBlock
from agentscope.tool import ToolResponse

from swe.app import mcp as app_mcp
from swe.constant import TRUNCATION_NOTICE_MARKER
from swe.config.context import tenant_context


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


def test_truncate_tool_response_text_blocks_only_touches_text_blocks() -> None:
    """外部工具文本块截断应保留非文本块与 metadata。"""
    response = ToolResponse(
        content=[
            TextBlock(type="text", text="line-1\n" * 400),
            {"type": "image", "source": {"type": "url", "url": "file://x"}},
        ],
        metadata={"source": "demo"},
        stream=True,
        is_last=True,
    )

    truncated = app_mcp._truncate_tool_response_text_blocks(
        response,
        max_bytes=1000,
    )

    assert truncated.metadata == {"source": "demo"}
    assert truncated.stream is True
    assert truncated.is_last is True
    assert truncated.content[1] == response.content[1]
    assert TRUNCATION_NOTICE_MARKER in truncated.content[0]["text"]
