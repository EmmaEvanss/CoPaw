# -*- coding: utf-8 -*-
"""Integration tests for my-mcp CRUD workflow."""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware

from swe.config.config import MCPClientConfig, MCPConfig


@pytest.fixture
def test_app():
    """Create a FastAPI app with the my-mcp router."""
    from swe.app.routers.my_mcp import router

    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(test_app):
    """Create a TestClient for the my-mcp router."""
    return TestClient(test_app)


@pytest.fixture
def client_with_manager():
    """Create a TestClient with manager middleware."""
    from swe.app.routers.my_mcp import router

    class ManagerMiddleware(BaseHTTPMiddleware):
        """Middleware that sets request.state.manager = True."""

        async def dispatch(self, request, call_next):
            request.state.manager = True
            return await call_next(request)

    app = FastAPI()
    app.add_middleware(ManagerMiddleware)
    app.include_router(router)
    return TestClient(app)


@pytest.fixture
def mock_workspace():
    """Create a mock workspace."""
    ws = MagicMock()
    ws.agent_id = "test-agent"
    ws.tenant_id = "test-tenant"
    return ws


class TestMyMCPFullWorkflow:
    """完整的 CRUD 流程集成测试."""

    # pylint: disable=too-many-statements
    def test_full_crud_workflow(self, client, mock_workspace):
        """验证完整的 CRUD 流程：创建 -> 详情 -> 更新 -> 启停 -> 删除."""
        # 初始化空 MCP 配置
        mcp_config = MCPConfig(clients={})
        agent_config = MagicMock()
        agent_config.mcp = mcp_config

        # ===== Step 1: 创建 MCP =====
        with patch(
            "swe.app.routers.my_mcp.get_agent_and_config_for_request",
            return_value=(mock_workspace, agent_config),
        ):
            with patch("swe.app.routers.my_mcp.save_agent_config"):
                with patch("swe.app.routers.my_mcp.schedule_agent_reload"):
                    create_response = client.post(
                        "/my-mcp",
                        json={
                            "client_key": "test-tool",
                            "name": "Test Tool",
                            "description": "A test MCP client",
                            "transport": "stdio",
                            "command": "npx",
                            "args": ["-y", "test-mcp-server"],
                            "env": {"API_KEY": "secret-key-12345"},
                        },
                    )
                    assert create_response.status_code == 201
                    create_data = create_response.json()
                    assert create_data["client_key"] == "test-tool"
                    assert create_data["name"] == "Test Tool"
                    assert create_data["source"] == ""  # 我创建的
                    assert (
                        create_data["env"]["API_KEY"] == "se**********2345"
                    )  # 脱敏（前2+后4，中间遮盖）

        # 模拟创建后的状态
        created_client = MCPClientConfig(
            name="Test Tool",
            description="A test MCP client",
            transport="stdio",
            command="npx",
            args=["-y", "test-mcp-server"],
            env={"API_KEY": "secret-key-12345"},
            source="",
            created_at="2026-04-30T10:00:00Z",
            updated_at="2026-04-30T10:00:00Z",
        )
        mcp_config.clients["test-tool"] = created_client

        # ===== Step 2: 获取列表 =====
        with patch(
            "swe.app.routers.my_mcp.get_agent_and_config_for_request",
            return_value=(mock_workspace, agent_config),
        ):
            list_response = client.get("/my-mcp")
            assert list_response.status_code == 200
            list_data = list_response.json()
            assert len(list_data) == 1
            assert list_data[0]["client_key"] == "test-tool"
            assert list_data[0]["name"] == "Test Tool"

        # ===== Step 3: 获取详情 =====
        with patch(
            "swe.app.routers.my_mcp.get_agent_and_config_for_request",
            return_value=(mock_workspace, agent_config),
        ):
            detail_response = client.get("/my-mcp/test-tool")
            assert detail_response.status_code == 200
            detail_data = detail_response.json()
            assert detail_data["client_key"] == "test-tool"
            assert detail_data["command"] == "npx"
            assert (
                detail_data["env"]["API_KEY"] == "se**********2345"
            )  # 脱敏展示

        # ===== Step 4: 更新 MCP =====
        with patch(
            "swe.app.routers.my_mcp.get_agent_and_config_for_request",
            return_value=(mock_workspace, agent_config),
        ):
            with patch("swe.app.routers.my_mcp.save_agent_config"):
                with patch("swe.app.routers.my_mcp.schedule_agent_reload"):
                    update_response = client.put(
                        "/my-mcp/test-tool",
                        json={
                            "name": "Updated Tool",
                            "description": "Updated description",
                        },
                    )
                    assert update_response.status_code == 200
                    update_data = update_response.json()
                    assert update_data["name"] == "Updated Tool"

        # 模拟更新后的状态
        created_client.name = "Updated Tool"
        created_client.description = "Updated description"

        # ===== Step 5: 启停 MCP =====
        with patch(
            "swe.app.routers.my_mcp.get_agent_and_config_for_request",
            return_value=(mock_workspace, agent_config),
        ):
            with patch("swe.app.routers.my_mcp.save_agent_config"):
                with patch("swe.app.routers.my_mcp.schedule_agent_reload"):
                    toggle_response = client.patch("/my-mcp/test-tool/toggle")
                    assert toggle_response.status_code == 200
                    toggle_data = toggle_response.json()
                    assert (
                        toggle_data["enabled"] is False
                    )  # 从 True 变为 False

        # ===== Step 6: 再次启停（恢复启用） =====
        created_client.enabled = False
        with patch(
            "swe.app.routers.my_mcp.get_agent_and_config_for_request",
            return_value=(mock_workspace, agent_config),
        ):
            with patch("swe.app.routers.my_mcp.save_agent_config"):
                with patch("swe.app.routers.my_mcp.schedule_agent_reload"):
                    toggle_response2 = client.patch("/my-mcp/test-tool/toggle")
                    assert toggle_response2.status_code == 200
                    toggle_data2 = toggle_response2.json()
                    assert (
                        toggle_data2["enabled"] is True
                    )  # 从 False 变为 True

        # ===== Step 7: 删除 MCP =====
        created_client.enabled = True
        with patch(
            "swe.app.routers.my_mcp.get_agent_and_config_for_request",
            return_value=(mock_workspace, agent_config),
        ):
            with patch("swe.app.routers.my_mcp.save_agent_config"):
                with patch("swe.app.routers.my_mcp.schedule_agent_reload"):
                    delete_response = client.delete("/my-mcp/test-tool")
                    assert delete_response.status_code == 200

        # ===== Step 8: 验证删除成功 =====
        mcp_config.clients = {}
        with patch(
            "swe.app.routers.my_mcp.get_agent_and_config_for_request",
            return_value=(mock_workspace, agent_config),
        ):
            # 列表应为空
            list_response2 = client.get("/my-mcp")
            assert list_response2.status_code == 200
            assert list_response2.json() == []

            # 详情应返回 404
            detail_response2 = client.get("/my-mcp/test-tool")
            assert detail_response2.status_code == 404


class TestDistributedMCPWorkflow:
    """市场分发 MCP 的特殊流程测试."""

    def test_distributed_mcp_cannot_modify_sensitive_fields(
        self,
        client,
        mock_workspace,
    ):
        """市场分发的 MCP 禁止修改敏感字段."""
        # 创建一个市场分发的 MCP
        distributed_client = MCPClientConfig(
            name="Distributed Tool",
            command="npx",
            args=["-y", "distributed-mcp"],
            source="marketplace:item-uuid-123",
            market_client_key="distributed-tool",
            distributed_by="admin-user",
        )
        mcp_config = MCPConfig(
            clients={"distributed-tool": distributed_client},
        )
        agent_config = MagicMock()
        agent_config.mcp = mcp_config

        # 尝试修改 command（敏感字段）- 应返回 403
        with patch(
            "swe.app.routers.my_mcp.get_agent_and_config_for_request",
            return_value=(mock_workspace, agent_config),
        ):
            update_response = client.put(
                "/my-mcp/distributed-tool",
                json={"command": "new-command"},
            )
            assert update_response.status_code == 403
            assert "Cannot modify" in update_response.json()["detail"]

        # 修改 name（非敏感字段）- 应成功
        with patch(
            "swe.app.routers.my_mcp.get_agent_and_config_for_request",
            return_value=(mock_workspace, agent_config),
        ):
            with patch("swe.app.routers.my_mcp.save_agent_config"):
                with patch("swe.app.routers.my_mcp.schedule_agent_reload"):
                    update_response2 = client.put(
                        "/my-mcp/distributed-tool",
                        json={"name": "New Name"},
                    )
                    assert update_response2.status_code == 200
                    assert update_response2.json()["name"] == "New Name"

    def test_distributed_mcp_can_toggle_and_delete(
        self,
        client,
        mock_workspace,
    ):
        """市场分发的 MCP 可以启停和删除."""
        distributed_client = MCPClientConfig(
            name="Distributed Tool",
            command="npx",
            source="marketplace:item-uuid-123",
            enabled=True,
        )
        mcp_config = MCPConfig(
            clients={"distributed-tool": distributed_client},
        )
        agent_config = MagicMock()
        agent_config.mcp = mcp_config

        # 启停操作应成功
        with patch(
            "swe.app.routers.my_mcp.get_agent_and_config_for_request",
            return_value=(mock_workspace, agent_config),
        ):
            with patch("swe.app.routers.my_mcp.save_agent_config"):
                with patch("swe.app.routers.my_mcp.schedule_agent_reload"):
                    toggle_response = client.patch(
                        "/my-mcp/distributed-tool/toggle",
                    )
                    assert toggle_response.status_code == 200
                    assert toggle_response.json()["enabled"] is False

        # 删除操作应成功
        with patch(
            "swe.app.routers.my_mcp.get_agent_and_config_for_request",
            return_value=(mock_workspace, agent_config),
        ):
            with patch("swe.app.routers.my_mcp.save_agent_config"):
                with patch("swe.app.routers.my_mcp.schedule_agent_reload"):
                    delete_response = client.delete("/my-mcp/distributed-tool")
                    assert delete_response.status_code == 200


class TestMultipleMCPWorkflow:
    """多 MCP 操作流程测试."""

    def test_create_multiple_and_batch_publish(
        self,
        client_with_manager,
        mock_workspace,
    ):
        """创建多个 MCP 并批量发布."""
        client = client_with_manager
        mcp_config = MCPConfig(clients={})
        agent_config = MagicMock()
        agent_config.mcp = mcp_config

        # 创建多个 MCP
        clients_to_create = [
            {
                "client_key": "weather",
                "name": "Weather Tool",
                "command": "npx",
                "args": ["-y", "weather-mcp"],
            },
            {
                "client_key": "search",
                "name": "Search Tool",
                "command": "npx",
                "args": ["-y", "search-mcp"],
            },
            {
                "client_key": "calendar",
                "name": "Calendar Tool",
                "command": "npx",
                "args": ["-y", "calendar-mcp"],
            },
        ]

        for client_data in clients_to_create:
            with patch(
                "swe.app.routers.my_mcp.get_agent_and_config_for_request",
                return_value=(mock_workspace, agent_config),
            ):
                with patch("swe.app.routers.my_mcp.save_agent_config"):
                    with patch("swe.app.routers.my_mcp.schedule_agent_reload"):
                        response = client.post("/my-mcp", json=client_data)
                        assert response.status_code == 201

                        # 模拟创建后的状态
                        mcp_config.clients[client_data["client_key"]] = (
                            MCPClientConfig(
                                name=client_data["name"],
                                command=client_data["command"],
                                args=client_data["args"],
                                source="",
                            )
                        )

        # 验证列表包含所有 MCP
        with patch(
            "swe.app.routers.my_mcp.get_agent_and_config_for_request",
            return_value=(mock_workspace, agent_config),
        ):
            list_response = client.get("/my-mcp")
            assert list_response.status_code == 200
            list_data = list_response.json()
            assert len(list_data) == 3

        # 批量发布（需要管理员权限）
        # 直接使用 headers 设置 manager 标识
        # Mock httpx.AsyncClient for market service calls
        mock_market_response = MagicMock()
        mock_market_response.status_code = 201
        mock_market_response.json.return_value = {
            "item_id": "test-market-item-uuid",
        }

        mock_http_client = AsyncMock()
        mock_http_client.post = AsyncMock(return_value=mock_market_response)
        mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
        mock_http_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_http_client):
            with patch(
                "swe.app.routers.my_mcp.get_agent_and_config_for_request",
                return_value=(mock_workspace, agent_config),
            ):
                publish_response = client.post(
                    "/my-mcp/publish",
                    json={"client_keys": ["weather", "search", "calendar"]},
                    headers={"X-Manager": "true"},
                )
                assert publish_response.status_code == 200
                publish_data = publish_response.json()
                assert len(publish_data["results"]) == 3
                for result in publish_data["results"]:
                    assert result["success"] is True
