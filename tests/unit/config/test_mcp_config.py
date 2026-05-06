# -*- coding: utf-8 -*-
# tests/unit/config/test_mcp_config.py
"""测试 MCPClientConfig 新增字段。"""
import pytest

from swe.config.config import MCPClientConfig


def test_mcp_client_config_new_fields_defaults():
    """新字段应有默认值，兼容现有配置。"""
    client = MCPClientConfig(
        name="test-client",
        command="npx",
        args=["-y", "test-mcp"],
    )
    assert client.source == ""
    assert client.market_client_key == ""
    assert client.distributed_by == ""
    assert client.lazy_load is False
    assert client.created_at == ""
    assert client.updated_at == ""


def test_mcp_client_config_source_field():
    """source 字段应支持空值和市场来源标记。"""
    client_created = MCPClientConfig(
        name="created",
        command="npx",
        args=["-y", "created-mcp"],
        source="",
    )
    assert client_created.source == ""

    client_distributed = MCPClientConfig(
        name="distributed",
        command="npx",
        args=["-y", "distributed-mcp"],
        source="marketplace:item-uuid-123",
        market_client_key="weather-tool",
        distributed_by="admin-user",
    )
    assert client_distributed.source == "marketplace:item-uuid-123"
    assert client_distributed.market_client_key == "weather-tool"
    assert client_distributed.distributed_by == "admin-user"


def test_mcp_client_config_backward_compat():
    """加载不含新字段的 JSON 应正常工作。"""
    legacy_data = {
        "name": "legacy-client",
        "command": "npx",
        "args": ["-y", "legacy-mcp"],
        "enabled": True,
        "transport": "stdio",
    }
    client = MCPClientConfig(**legacy_data)
    assert client.name == "legacy-client"
    assert client.source == ""
    assert client.lazy_load is False


def test_mcp_client_config_timestamps():
    """时间戳字段应支持 ISO8601 格式。"""
    client = MCPClientConfig(
        name="timestamped-client",
        command="npx",
        args=["-y", "timestamped-mcp"],
        created_at="2026-04-30T10:00:00Z",
        updated_at="2026-04-30T12:30:00Z",
    )
    assert client.created_at == "2026-04-30T10:00:00Z"
    assert client.updated_at == "2026-04-30T12:30:00Z"


def test_mcp_client_config_lazy_load_field():
    """lazy_load 字段应支持 True/False。"""
    client_lazy = MCPClientConfig(
        name="lazy-client",
        command="npx",
        args=["-y", "lazy-mcp"],
        lazy_load=True,
    )
    assert client_lazy.lazy_load is True

    client_eager = MCPClientConfig(
        name="eager-client",
        command="npx",
        args=["-y", "eager-mcp"],
        lazy_load=False,
    )
    assert client_eager.lazy_load is False
