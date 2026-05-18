# -*- coding: utf-8 -*-
"""Zhaohu callback source-scope regression tests."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from swe.app.channels.zhaohu.channel import ZhaohuChannel
from swe.config.context import (
    encode_scope_id,
    get_current_scope_id,
    get_current_source_id,
)


def _make_channel() -> ZhaohuChannel:
    async def _noop_process(_request):
        yield  # pragma: no cover

    channel = ZhaohuChannel(
        process=_noop_process,
        enabled=True,
        push_url="https://test.push.url",
        sys_id="test_sys_id",
        robot_open_id="test_robot_open_id",
        channel_code="ZH",
        net="DMZ",
        request_timeout=15.0,
        bot_prefix="",
        custom_card_url="https://test.card.url",
        oauth_url="https://test.oauth.url",
        client_id="test_client_id",
        client_secret="test_client_secret",
    )
    channel._http = MagicMock()
    return channel


@pytest.mark.asyncio
async def test_process_callback_message_binds_explicit_source_scope() -> None:
    """Auth-exempt callback 也必须显式绑定 channel source 对应的 scope。"""
    channel = _make_channel()
    observed: dict[str, str | None] = {}

    async def _fake_query_user_info(_from_id: str) -> dict[str, str]:
        return {
            "sapId": "tenant-a",
            "ystId": "yst-user",
            "userName": "Alice",
        }

    async def _fake_route_message(
        _msg_id: str,
        _from_id: str,
        _sap_id: str,
        _yst_id: str,
        _msg_content: str,
        meta: dict,
    ) -> None:
        observed["meta_source_id"] = meta.get("source_id")
        observed["source_id"] = get_current_source_id()
        observed["scope_id"] = get_current_scope_id()

    channel._query_user_info = _fake_query_user_info
    channel._route_message = _fake_route_message

    callback_body = SimpleNamespace(
        msg_id="msg-1",
        from_id="open-id-1",
        to_id="robot-id",
        group_id=None,
        group_name=None,
        msg_type="text",
        msg_content="hello",
        timestamp=1234567890,
    )

    await channel.process_callback_message(callback_body)

    assert observed == {
        "meta_source_id": "zhaohu",
        "source_id": "zhaohu",
        "scope_id": encode_scope_id("tenant-a", "zhaohu"),
    }
