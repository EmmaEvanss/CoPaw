# -*- coding: utf-8 -*-
"""MCP Schema 单元测试."""

import pytest
from market.marketplace.schemas import (
    MarketMCPItem,
    MarketMCPDetail,
    MCPConfigDetail,
    MCPUserStat,
    PublishMCPRequest,
    UploadMCPResponse,
)


def test_market_mcp_item_schema():
    """MarketMCPItem 应包含统计字段。"""
    item = MarketMCPItem(
        item_id="uuid",
        client_key="weather",
        name="Weather",
        description="desc",
        creator_id="admin",
        creator_name="Admin",
        category_id=1,
        bbk_ids=["100"],
        created_at="2026-04-29",
        updated_at="2026-04-30",
        call_count=100,
        user_count=10,
    )
    assert item.item_id == "uuid"
    assert item.client_key == "weather"
    assert item.call_count == 100


def test_market_mcp_detail_schema():
    """MarketMCPDetail 应包含 config 和 user_stats。"""
    detail = MarketMCPDetail(
        item_id="uuid",
        client_key="weather",
        name="Weather",
        description="desc",
        creator_id="admin",
        creator_name="Admin",
        category_id=1,
        bbk_ids=["100"],
        created_at=None,
        updated_at=None,
        call_count=100,
        user_count=10,
        config=MCPConfigDetail(
            transport="stdio",
            command="npx",
            args=["-y", "weather-mcp"],
        ),
        user_stats=[
            MCPUserStat(user_id="user1", user_name="User1", call_count=50),
        ],
    )
    assert detail.config.transport == "stdio"
    assert len(detail.user_stats) == 1


def test_mcp_config_detail_defaults():
    """MCPConfigDetail 默认值正确。"""
    config = MCPConfigDetail()
    assert config.transport == "stdio"
    assert config.command == ""
    assert config.env == {}
    assert config.lazy_load is False


def test_upload_mcp_response():
    """UploadMCPResponse 结构正确。"""
    success = UploadMCPResponse(success=True)
    assert success.success is True
    assert success.error is None

    fail = UploadMCPResponse(success=False, error="Invalid JSON")
    assert fail.success is False
    assert fail.error == "Invalid JSON"
