# -*- coding: utf-8 -*-
"""BaseChannel 后台上下文绑定的 scope 回归测试。"""

from types import SimpleNamespace

from swe.app.channels.base import BaseChannel
from swe.config.context import encode_scope_id


def test_resolve_bound_identity_uses_payload_source_meta() -> None:
    """后台消费必须从 payload meta 还原 source，而不是只带 opaque scope。"""
    channel = object.__new__(BaseChannel)
    channel._workspace = SimpleNamespace(tenant_id="tenant-a")
    request = SimpleNamespace(source_id=None, channel_meta=None)
    payload = {"meta": {"source_id": "source-a"}}

    assert channel._resolve_bound_identity(request, payload) == (
        "tenant-a",
        "source-a",
        encode_scope_id("tenant-a", "source-a"),
    )


def test_resolve_bound_identity_decodes_workspace_scope_before_source() -> (
    None
):
    """后台消费只有 source_id 时，也必须识别 workspace 上已有的 scope。"""
    scope_id = encode_scope_id("tenant-a", "source-a")
    channel = object.__new__(BaseChannel)
    channel._workspace = SimpleNamespace(tenant_id=scope_id)
    request = SimpleNamespace(
        source_id=None,
        scope_id=None,
        channel_meta=None,
    )
    payload = {"meta": {"source_id": "source-a"}}

    assert channel._resolve_bound_identity(request, payload) == (
        "tenant-a",
        "source-a",
        scope_id,
    )
