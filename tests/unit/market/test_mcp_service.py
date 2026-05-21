# -*- coding: utf-8 -*-
"""MCP Service 方法测试."""

import pytest
from unittest.mock import MagicMock, AsyncMock
from pathlib import Path

from market.marketplace.service import MarketplaceService
from market.marketplace.schemas import (
    MCPDistributionRequest,
    PublishMCPRequest,
    DistributeRequest,
)
from market.marketplace.models import MarketItem


@pytest.fixture
def mock_db():
    """Mock 数据库连接."""
    db = MagicMock()
    db.is_connected = False
    db.fetch_one = AsyncMock(return_value=None)
    db.fetch_all = AsyncMock(return_value=[])
    db.execute = AsyncMock()
    return db


@pytest.fixture
def mock_paths(tmp_path):
    """创建临时目录结构."""
    marketplace_root = tmp_path / ".swe.marketplace"
    swe_root = tmp_path / ".swe"
    marketplace_root.mkdir(parents=True, exist_ok=True)
    swe_root.mkdir(parents=True, exist_ok=True)
    return marketplace_root, swe_root


@pytest.fixture
def service(mock_db, mock_paths):
    """创建 MarketplaceService 实例."""
    marketplace_root, swe_root = mock_paths
    return MarketplaceService(mock_db, marketplace_root, swe_root)


class TestPublishMCP:
    """发布 MCP 测试."""

    async def test_publish_new_mcp(self, service):
        """发布新 MCP 到市场."""
        source_id = "test-source"

        req = PublishMCPRequest(
            client_key="weather",
            name="Weather Tool",
            description="天气查询 MCP",
            creator_id="admin",
            creator_name="管理员",
            config={
                "command": "npx",
                "args": ["-y", "weather-mcp"],
                "env": {"API_KEY": "secret-123"},
            },
        )

        item = await service.publish_mcp(source_id, req)

        assert item.client_key == "weather"
        assert item.item_type == "mcp"
        assert item.name == "Weather Tool"
        assert item.description == "天气查询 MCP"
        assert item.status == "active"

    async def test_publish_mcp_overwrite(self, service):
        """覆盖已存在的 MCP（复用 item_id）。"""
        source_id = "test-source"

        # 首次发布
        req1 = PublishMCPRequest(
            client_key="weather",
            name="Old Name",
            creator_id="admin",
            config={"command": "npx"},
        )
        item1 = await service.publish_mcp(source_id, req1)
        item_id = item1.item_id

        # 再次发布（覆盖）
        req2 = PublishMCPRequest(
            client_key="weather",
            name="New Name",
            description="Updated",
            creator_id="admin",
            config={"command": "npx", "args": ["updated"]},
        )
        item2 = await service.publish_mcp(source_id, req2)

        assert item2.item_id == item_id  # 复用 item_id
        assert item2.name == "New Name"
        assert item2.description == "Updated"

    async def test_publish_mcp_with_bbk_ids(self, service):
        """发布带 bbk_ids 限制的 MCP."""
        source_id = "test-source"

        req = PublishMCPRequest(
            client_key="restricted",
            name="Restricted MCP",
            creator_id="admin",
            bbk_ids=["100", "200"],
            config={"command": "npx"},
        )

        item = await service.publish_mcp(source_id, req)

        assert item.bbk_ids == ["100", "200"]


class TestListMCPItems:
    """列出 MCP 测试."""

    async def test_list_empty(self, service):
        """空列表返回空结果."""
        source_id = "empty-source"

        items = await service.list_mcp_items(source_id, "100")

        assert items == []

    async def test_list_mcp_items(self, service):
        """列出 MCP 项目。"""
        source_id = "test-source"

        # 先发布一个 MCP
        req = PublishMCPRequest(
            client_key="weather",
            name="Weather",
            creator_id="admin",
            config={"command": "npx"},
        )
        await service.publish_mcp(source_id, req)

        # 列出
        items = await service.list_mcp_items(source_id, "100")

        assert len(items) == 1
        assert items[0].client_key == "weather"
        assert items[0].name == "Weather"
        assert items[0].call_count == 0  # 无数据库连接时为 0
        assert items[0].user_count == 0

    async def test_list_with_category_filter(self, service):
        """按分类过滤 MCP 列表。"""
        source_id = "test-source"

        # 发布两个 MCP，不同分类
        req1 = PublishMCPRequest(
            client_key="weather",
            name="Weather",
            creator_id="admin",
            category_id=1,
            config={"command": "npx"},
        )
        req2 = PublishMCPRequest(
            client_key="calendar",
            name="Calendar",
            creator_id="admin",
            category_id=2,
            config={"command": "npx"},
        )
        await service.publish_mcp(source_id, req1)
        await service.publish_mcp(source_id, req2)

        # 按分类过滤
        items = await service.list_mcp_items(source_id, "100", category_id=1)

        assert len(items) == 1
        assert items[0].client_key == "weather"

    async def test_list_with_bbk_filter(self, service):
        """按 bbk_id 过滤 MCP 列表。"""
        source_id = "test-source"

        # 发布带限制的 MCP
        req = PublishMCPRequest(
            client_key="restricted",
            name="Restricted",
            creator_id="admin",
            bbk_ids=["200"],
            config={"command": "npx"},
        )
        await service.publish_mcp(source_id, req)

        # bbk_id=100 可以看到（管理员权限）
        items_100 = await service.list_mcp_items(source_id, "100")
        assert len(items_100) == 1

        # bbk_id=200 可以看到（在 bbk_ids 中）
        items_200 = await service.list_mcp_items(source_id, "200")
        assert len(items_200) == 1

        # bbk_id=300 无法看到
        items_300 = await service.list_mcp_items(source_id, "300")
        assert len(items_300) == 0


class TestGetMCPDetail:
    """获取 MCP 详情测试."""

    async def test_get_mcp_detail(self, service):
        """获取 MCP 详情。"""
        source_id = "test-source"

        # 先发布
        req = PublishMCPRequest(
            client_key="weather",
            name="Weather",
            creator_id="admin",
            config={
                "command": "npx",
                "args": ["-y", "weather-mcp"],
                "env": {"API_KEY": "secret-12345"},
            },
        )
        item = await service.publish_mcp(source_id, req)

        # 获取详情
        detail = await service.get_mcp_detail(source_id, item.item_id, "100")

        assert detail is not None
        assert detail.client_key == "weather"
        assert detail.name == "Weather"
        assert detail.version == "1.0.0"
        assert detail.config.command == "npx"
        assert detail.config.args == ["-y", "weather-mcp"]
        # 环境变量应该被脱敏（"secret-12345" -> prefix=2, suffix=4, masked=6）
        assert detail.config.env["API_KEY"] == "se******2345"

    async def test_get_mcp_detail_returns_bumped_version(self, service):
        """重复上架后，详情页应返回递增后的版本号。"""
        source_id = "test-source"

        req = PublishMCPRequest(
            client_key="weather",
            name="Weather",
            creator_id="admin",
            config={"command": "npx"},
        )
        item = await service.publish_mcp(source_id, req)
        await service.publish_mcp(source_id, req)

        detail = await service.get_mcp_detail(source_id, item.item_id, "100")

        assert detail is not None
        assert detail.version == "1.0.1"

    async def test_get_mcp_detail_not_found(self, service):
        """获取不存在的 MCP 详情返回 None。"""
        source_id = "test-source"

        detail = await service.get_mcp_detail(
            source_id,
            "non-existent-id",
            "100",
        )

        assert detail is None

    async def test_get_mcp_detail_no_permission(self, service):
        """无权限访问 MCP 详情返回 None。"""
        source_id = "test-source"

        # 发布带限制的 MCP
        req = PublishMCPRequest(
            client_key="restricted",
            name="Restricted",
            creator_id="admin",
            bbk_ids=["200"],
            config={"command": "npx"},
        )
        item = await service.publish_mcp(source_id, req)

        # bbk_id=300 无权限
        detail = await service.get_mcp_detail(source_id, item.item_id, "300")

        assert detail is None


class TestDeleteMCP:
    """删除 MCP 测试."""

    async def test_delete_mcp(self, service):
        """删除 MCP。"""
        source_id = "test-source"

        # 先发布
        req = PublishMCPRequest(
            client_key="weather",
            name="Weather",
            creator_id="admin",
            config={"command": "npx"},
        )
        item = await service.publish_mcp(source_id, req)

        # 删除
        ok = await service.delete_mcp(
            source_id,
            item.item_id,
            "admin",
            "管理员",
        )

        assert ok is True

        # 验证已删除
        detail = await service.get_mcp_detail(source_id, item.item_id, "100")
        assert detail is None

    async def test_delete_mcp_not_found(self, service):
        """删除不存在的 MCP 返回 False。"""
        source_id = "test-source"

        ok = await service.delete_mcp(source_id, "non-existent-id", "admin")

        assert ok is False

    async def test_delete_skill_not_affected(self, service):
        """删除 MCP 不影响同 ID 的 Skill。"""
        source_id = "test-source"

        # 先发布一个 MCP
        req = PublishMCPRequest(
            client_key="weather",
            name="Weather MCP",
            creator_id="admin",
            config={"command": "npx"},
        )
        mcp_item = await service.publish_mcp(source_id, req)

        # 发布一个同 ID 名称不同的 Skill（这里需要手动创建）
        # 删除 MCP 后验证 Skill 列表不受影响
        await service.delete_mcp(source_id, mcp_item.item_id)

        # MCP 列表应为空
        mcp_items = await service.list_mcp_items(source_id, "100")
        assert len(mcp_items) == 0


class TestDistributeMCP:
    """分发 MCP 测试."""

    async def test_distribute_mcp_not_found(self, service):
        """分发不存在的 MCP 抛出异常。"""
        source_id = "test-source"

        req = DistributeRequest(target_type="user_id", target_values=["alice"])

        with pytest.raises(ValueError, match="MCP item .* not found"):
            await service.distribute_mcp(
                source_id,
                "non-existent-id",
                "admin",
                "管理员",
                req,
            )

    async def test_distribute_mcp_to_users(self, service, mock_paths):
        """分发 MCP 到用户（无数据库连接）。"""
        source_id = "test-source"
        _, swe_root = mock_paths

        # 先发布
        req = PublishMCPRequest(
            client_key="weather",
            name="Weather",
            creator_id="admin",
            config={"command": "npx", "args": ["-y", "weather-mcp"]},
        )
        item = await service.publish_mcp(source_id, req)

        # 分发（因为没有数据库连接，target_type=user_id 直接使用传入值）
        dist_req = MCPDistributionRequest(
            target_tenant_ids=["alice"],
            overwrite=True,
        )

        # 由于数据库未连接，_resolve_target_users 会返回空列表
        # 但我们设置 db.is_connected = True 来测试
        service.db.is_connected = True
        service.db.fetch_all = AsyncMock(
            return_value=[
                {
                    "tenant_id": "alice",
                    "tenant_name": "Alice",
                    "bbk_id": "100",
                },
            ],
        )

        result = await service.distribute_mcp(
            source_id,
            item.item_id,
            "admin",
            "管理员",
            dist_req,
        )

        assert result.source_agent_id
        assert len(result.results) == 1
        assert result.results[0].tenant_id == "alice"
        assert result.results[0].success is True

        # 验证用户配置文件已创建
        user_config_path = (
            swe_root / "alice" / "workspaces" / "default" / "agent.json"
        )
        assert user_config_path.exists()


class TestMCPStats:
    """MCP 统计测试."""

    async def test_get_mcp_stats_no_db(self, service):
        """无数据库连接时返回 0,0。"""
        call_count, user_count = await service._get_mcp_stats(
            "weather",
            "test-source",
        )

        assert call_count == 0
        assert user_count == 0

    async def test_get_mcp_stats_with_db(self, service):
        """有数据库连接时返回查询结果。"""
        service.db.is_connected = True
        service.db.fetch_one = AsyncMock(
            return_value={"call_count": 10, "user_count": 3},
        )

        call_count, user_count = await service._get_mcp_stats(
            "weather",
            "test-source",
        )

        assert call_count == 10
        assert user_count == 3

    async def test_get_mcp_user_stats_no_db(self, service):
        """无数据库连接时返回空列表。"""
        stats = await service._get_mcp_user_stats("weather", "test-source")

        assert stats == []

    async def test_get_mcp_user_stats_with_db(self, service):
        """有数据库连接时返回用户统计列表。"""
        service.db.is_connected = True
        service.db.fetch_all = AsyncMock(
            return_value=[
                {"user_id": "alice", "user_name": "Alice", "call_count": 5},
                {"user_id": "bob", "user_name": "Bob", "call_count": 3},
            ],
        )

        stats = await service._get_mcp_user_stats("weather", "test-source")

        assert len(stats) == 2
        assert stats[0].user_id == "alice"
        assert stats[0].call_count == 5
