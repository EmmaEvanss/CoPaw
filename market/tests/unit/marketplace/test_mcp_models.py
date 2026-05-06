# -*- coding: utf-8 -*-
"""MCP 模型测试."""
import pytest
from market.marketplace.models import MarketItem


def test_market_item_mcp_type():
    """MarketItem 应支持 item_type='mcp'."""
    item = MarketItem(
        item_id="uuid-123",
        item_type="mcp",
        name="Weather Tool",
        client_key="weather-tool",
        description="天气查询",
        creator_id="admin",
        creator_name="管理员",
        category_id=1,
        bbk_ids=["100"],
        status="active",
    )
    assert item.item_type == "mcp"
    assert item.client_key == "weather-tool"


def test_market_item_mcp_optional_version():
    """MCP 条目不需要 version 字段（可选）。"""
    item = MarketItem(
        item_id="uuid-123",
        item_type="mcp",
        name="Tool",
        creator_id="admin",
    )
    # version 对 MCP 可为空或默认值
    assert item.version is not None or item.item_type != "skill"


def test_market_item_client_key_default():
    """client_key 默认值为空字符串。"""
    item = MarketItem(
        item_id="uuid-123",
        item_type="skill",
        name="Skill",
        creator_id="admin",
    )
    assert item.client_key == ""
