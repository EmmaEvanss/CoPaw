# -*- coding: utf-8 -*-
"""Unit tests for my-mcp endpoints."""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from swe.config.config import MCPClientConfig, MCPConfig


@pytest.fixture
def test_app():
    """Create a FastAPI app with the my-mcp router."""
    # 延迟导入以避免依赖问题
    from swe.app.routers.my_mcp import router

    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(test_app):
    """Create a TestClient for the my-mcp router."""
    return TestClient(test_app)


class TestListMyMCP:
    """Tests for GET /my-mcp endpoint."""

    def test_list_empty(self, client):
        """空配置应返回空列表."""
        # Mock workspace 和 agent_config
        mock_workspace = MagicMock()
        mock_workspace.agent_id = "default"
        mock_workspace.tenant_id = None

        mock_agent_config = MagicMock()
        mock_agent_config.mcp = None

        with patch(
            "swe.app.routers.my_mcp.get_agent_and_config_for_request",
            return_value=(mock_workspace, mock_agent_config),
        ):
            response = client.get("/my-mcp")
            assert response.status_code == 200
            assert response.json() == []

    def test_list_with_empty_clients_dict(self, client):
        """clients 为空字典时应返回空列表."""
        mock_workspace = MagicMock()
        mock_workspace.agent_id = "default"
        mock_workspace.tenant_id = None

        mock_agent_config = MagicMock()
        mock_agent_config.mcp = MCPConfig(clients={})

        with patch(
            "swe.app.routers.my_mcp.get_agent_and_config_for_request",
            return_value=(mock_workspace, mock_agent_config),
        ):
            response = client.get("/my-mcp")
            assert response.status_code == 200
            assert response.json() == []

    def test_list_with_clients(self, client):
        """有 MCP 客户端时应返回列表."""
        mock_workspace = MagicMock()
        mock_workspace.agent_id = "default"
        mock_workspace.tenant_id = None

        mock_agent_config = MagicMock()
        mock_agent_config.mcp = MCPConfig(
            clients={
                "weather": MCPClientConfig(
                    name="Weather Tool",
                    description="天气查询",
                    command="npx",
                    args=["-y", "weather-mcp"],
                    source="",
                    created_at="2026-04-29T10:00:00Z",
                    updated_at="2026-04-30T10:00:00Z",
                ),
                "distributed-tool": MCPClientConfig(
                    name="Distributed Tool",
                    command="npx",
                    source="marketplace:item-123",
                    market_client_key="distributed-tool",
                    created_at="2026-04-28T10:00:00Z",
                    updated_at="2026-04-29T10:00:00Z",
                ),
            },
        )

        with patch(
            "swe.app.routers.my_mcp.get_agent_and_config_for_request",
            return_value=(mock_workspace, mock_agent_config),
        ):
            response = client.get("/my-mcp")
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 2
            # 检查返回的 client_key 是否正确
            client_keys = [item["client_key"] for item in data]
            assert "weather" in client_keys
            assert "distributed-tool" in client_keys

    def test_list_sorted_by_updated_at(self, client):
        """列表应按更新时间降序排序."""
        mock_workspace = MagicMock()
        mock_workspace.agent_id = "default"
        mock_workspace.tenant_id = None

        mock_agent_config = MagicMock()
        mock_agent_config.mcp = MCPConfig(
            clients={
                "older": MCPClientConfig(
                    name="Older Client",
                    command="npx",
                    created_at="2026-04-01T10:00:00Z",
                    updated_at="2026-04-01T10:00:00Z",
                ),
                "newer": MCPClientConfig(
                    name="Newer Client",
                    command="npx",
                    created_at="2026-04-02T10:00:00Z",
                    updated_at="2026-04-02T10:00:00Z",
                ),
                "newest": MCPClientConfig(
                    name="Newest Client",
                    command="npx",
                    created_at="2026-04-03T10:00:00Z",
                    updated_at="2026-04-03T10:00:00Z",
                ),
            },
        )

        with patch(
            "swe.app.routers.my_mcp.get_agent_and_config_for_request",
            return_value=(mock_workspace, mock_agent_config),
        ):
            response = client.get("/my-mcp")
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 3
            # 检查排序顺序（最新的在前）
            assert data[0]["client_key"] == "newest"
            assert data[1]["client_key"] == "newer"
            assert data[2]["client_key"] == "older"

    def test_list_with_empty_updated_at(self, client):
        """updated_at 为空字符串时排序应正确处理."""
        mock_workspace = MagicMock()
        mock_workspace.agent_id = "default"
        mock_workspace.tenant_id = None

        mock_agent_config = MagicMock()
        mock_agent_config.mcp = MCPConfig(
            clients={
                "no-time": MCPClientConfig(
                    name="No Time Client",
                    command="npx",
                    created_at="",
                    updated_at="",
                ),
                "with-time": MCPClientConfig(
                    name="With Time Client",
                    command="npx",
                    created_at="2026-04-02T10:00:00Z",
                    updated_at="2026-04-02T10:00:00Z",
                ),
            },
        )

        with patch(
            "swe.app.routers.my_mcp.get_agent_and_config_for_request",
            return_value=(mock_workspace, mock_agent_config),
        ):
            response = client.get("/my-mcp")
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 2
            # 有时间的应排在前面
            assert data[0]["client_key"] == "with-time"
            assert data[1]["client_key"] == "no-time"

    def test_list_item_fields(self, client):
        """返回项应包含所有 MyMCPListItem 字段."""
        mock_workspace = MagicMock()
        mock_workspace.agent_id = "default"
        mock_workspace.tenant_id = None

        mock_agent_config = MagicMock()
        mock_agent_config.mcp = MCPConfig(
            clients={
                "test-client": MCPClientConfig(
                    name="Test Client",
                    description="A test MCP client",
                    transport="stdio",
                    enabled=True,
                    command="npx",
                    args=["-y", "test-mcp"],
                    source="local",
                    market_client_key="original-key",
                    created_at="2026-04-01T00:00:00Z",
                    updated_at="2026-04-02T00:00:00Z",
                ),
            },
        )

        with patch(
            "swe.app.routers.my_mcp.get_agent_and_config_for_request",
            return_value=(mock_workspace, mock_agent_config),
        ):
            response = client.get("/my-mcp")
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            item = data[0]
            assert item["client_key"] == "test-client"
            assert item["name"] == "Test Client"
            assert item["description"] == "A test MCP client"
            assert item["transport"] == "stdio"
            assert item["enabled"] is True
            assert item["source"] == "local"
            assert item["market_client_key"] == "original-key"
            assert item["created_at"] == "2026-04-01T00:00:00Z"
            assert item["updated_at"] == "2026-04-02T00:00:00Z"

    def test_list_with_http_transport(self, client):
        """HTTP 传输类型的客户端应正确返回."""
        mock_workspace = MagicMock()
        mock_workspace.agent_id = "default"
        mock_workspace.tenant_id = None

        mock_agent_config = MagicMock()
        mock_agent_config.mcp = MCPConfig(
            clients={
                "http-client": MCPClientConfig(
                    name="HTTP Client",
                    description="HTTP MCP client",
                    transport="streamable_http",
                    enabled=True,
                    url="https://example.com/mcp",
                    headers={"Authorization": "Bearer token"},
                    source="",
                    created_at="2026-04-01T00:00:00Z",
                    updated_at="2026-04-01T00:00:00Z",
                ),
            },
        )

        with patch(
            "swe.app.routers.my_mcp.get_agent_and_config_for_request",
            return_value=(mock_workspace, mock_agent_config),
        ):
            response = client.get("/my-mcp")
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            item = data[0]
            assert item["client_key"] == "http-client"
            assert item["transport"] == "streamable_http"


class TestGetMyMCPDetail:
    """Tests for GET /my-mcp/{client_key} endpoint."""

    def test_get_detail_success(self, client):
        """正常获取详情."""
        mock_workspace = MagicMock()
        mock_workspace.agent_id = "default"
        mock_workspace.tenant_id = None

        mock_agent_config = MagicMock()
        mock_agent_config.mcp = MCPConfig(
            clients={
                "weather": MCPClientConfig(
                    name="Weather Tool",
                    description="天气查询",
                    command="npx",
                    args=["-y", "weather-mcp"],
                    env={"API_KEY": "test-key-12345678"},
                    headers={"X-Custom": "header-value"},
                    source="",
                    created_at="2026-04-29T10:00:00Z",
                    updated_at="2026-04-30T10:00:00Z",
                ),
            },
        )

        with patch(
            "swe.app.routers.my_mcp.get_agent_and_config_for_request",
            return_value=(mock_workspace, mock_agent_config),
        ):
            response = client.get("/my-mcp/weather")
            assert response.status_code == 200
            data = response.json()
            assert data["client_key"] == "weather"
            assert data["name"] == "Weather Tool"
            assert data["description"] == "天气查询"
            assert data["command"] == "npx"
            assert data["args"] == ["-y", "weather-mcp"]
            # 检查脱敏后的 env
            assert "API_KEY" in data["env"]
            # test-key-12345678 长度 17，前2字符 + 11星号 + 后4字符
            assert data["env"]["API_KEY"] == "te***********5678"
            # 检查脱敏后的 headers
            assert "X-Custom" in data["headers"]
            # header-value 长度 12，前2字符 + 6星号 + 后4字符
            assert data["headers"]["X-Custom"] == "he******alue"

    def test_get_detail_not_found(self, client):
        """不存在的 client_key 返回 404."""
        mock_workspace = MagicMock()
        mock_workspace.agent_id = "default"
        mock_workspace.tenant_id = None

        mock_agent_config = MagicMock()
        mock_agent_config.mcp = MCPConfig(clients={})

        with patch(
            "swe.app.routers.my_mcp.get_agent_and_config_for_request",
            return_value=(mock_workspace, mock_agent_config),
        ):
            response = client.get("/my-mcp/nonexistent")
            assert response.status_code == 404
            assert "nonexistent" in response.json()["detail"]

    def test_get_detail_mcp_none(self, client):
        """MCP 配置为 None 时返回 404."""
        mock_workspace = MagicMock()
        mock_workspace.agent_id = "default"
        mock_workspace.tenant_id = None

        mock_agent_config = MagicMock()
        mock_agent_config.mcp = None

        with patch(
            "swe.app.routers.my_mcp.get_agent_and_config_for_request",
            return_value=(mock_workspace, mock_agent_config),
        ):
            response = client.get("/my-mcp/weather")
            assert response.status_code == 404

    def test_get_detail_http_transport(self, client):
        """HTTP 传输类型的详情应包含 url 和 headers."""
        mock_workspace = MagicMock()
        mock_workspace.agent_id = "default"
        mock_workspace.tenant_id = None

        mock_agent_config = MagicMock()
        mock_agent_config.mcp = MCPConfig(
            clients={
                "http-client": MCPClientConfig(
                    name="HTTP Client",
                    description="HTTP MCP client",
                    transport="streamable_http",
                    enabled=True,
                    url="https://example.com/mcp",
                    headers={"Authorization": "Bearer secret-token-123"},
                    source="marketplace:item-456",
                    market_client_key="http-tool",
                    created_at="2026-04-01T00:00:00Z",
                    updated_at="2026-04-02T00:00:00Z",
                ),
            },
        )

        with patch(
            "swe.app.routers.my_mcp.get_agent_and_config_for_request",
            return_value=(mock_workspace, mock_agent_config),
        ):
            response = client.get("/my-mcp/http-client")
            assert response.status_code == 200
            data = response.json()
            assert data["client_key"] == "http-client"
            assert data["transport"] == "streamable_http"
            assert data["url"] == "https://example.com/mcp"
            # headers 应被脱敏
            assert "Authorization" in data["headers"]
            # Bearer secret-token-123 长度 23，前2字符 + 17星号 + 后4字符
            assert (
                data["headers"]["Authorization"] == "Be*****************-123"
            )

    def test_get_detail_empty_env_headers(self, client):
        """env 和 headers 为空时应返回空字典."""
        mock_workspace = MagicMock()
        mock_workspace.agent_id = "default"
        mock_workspace.tenant_id = None

        mock_agent_config = MagicMock()
        mock_agent_config.mcp = MCPConfig(
            clients={
                "simple": MCPClientConfig(
                    name="Simple Client",
                    command="npx",
                    args=["simple"],
                    env={},
                    headers={},
                    source="",
                ),
            },
        )

        with patch(
            "swe.app.routers.my_mcp.get_agent_and_config_for_request",
            return_value=(mock_workspace, mock_agent_config),
        ):
            response = client.get("/my-mcp/simple")
            assert response.status_code == 200
            data = response.json()
            assert data["env"] == {}
            assert data["headers"] == {}

    def test_get_detail_all_fields(self, client):
        """详情应包含所有 MyMCPDetail 字段."""
        mock_workspace = MagicMock()
        mock_workspace.agent_id = "default"
        mock_workspace.tenant_id = None

        mock_agent_config = MagicMock()
        mock_agent_config.mcp = MCPConfig(
            clients={
                "full-client": MCPClientConfig(
                    name="Full Client",
                    description="完整配置测试",
                    transport="stdio",
                    enabled=True,
                    source="local",
                    market_client_key="original-key",
                    created_at="2026-04-01T00:00:00Z",
                    updated_at="2026-04-02T00:00:00Z",
                    url="",
                    headers={},
                    command="npx",
                    args=["-y", "full-mcp"],
                    env={"KEY": "value"},
                    cwd="/tmp",
                    lazy_load=True,
                    distributed_by="admin",
                ),
            },
        )

        with patch(
            "swe.app.routers.my_mcp.get_agent_and_config_for_request",
            return_value=(mock_workspace, mock_agent_config),
        ):
            response = client.get("/my-mcp/full-client")
            assert response.status_code == 200
            data = response.json()
            # MyMCPListItem 字段
            assert data["client_key"] == "full-client"
            assert data["name"] == "Full Client"
            assert data["description"] == "完整配置测试"
            assert data["transport"] == "stdio"
            assert data["enabled"] is True
            assert data["source"] == "local"
            assert data["market_client_key"] == "original-key"
            assert data["created_at"] == "2026-04-01T00:00:00Z"
            assert data["updated_at"] == "2026-04-02T00:00:00Z"
            # MyMCPDetail 扩展字段
            assert data["url"] == ""
            assert data["headers"] == {}
            assert data["command"] == "npx"
            assert data["args"] == ["-y", "full-mcp"]
            assert "KEY" in data["env"]
            assert data["cwd"] == "/tmp"
            assert data["lazy_load"] is True
            assert data["distributed_by"] == "admin"


class TestCreateMyMCP:
    """Tests for POST /my-mcp endpoint."""

    def test_create_success(self, client):
        """创建新的 MCP."""
        mock_workspace = MagicMock()
        mock_workspace.agent_id = "test-agent"
        mock_workspace.tenant_id = "test-tenant"

        mock_config = MagicMock()
        mock_config.mcp = MCPConfig(clients={})

        with patch(
            "swe.app.routers.my_mcp.get_agent_and_config_for_request",
        ) as mock_get:
            with patch(
                "swe.app.routers.my_mcp.save_agent_config",
            ) as mock_save:
                with patch(
                    "swe.app.routers.my_mcp.schedule_agent_reload",
                ) as mock_reload:
                    mock_get.return_value = (mock_workspace, mock_config)

                    response = client.post(
                        "/my-mcp",
                        json={
                            "client_key": "new-tool",
                            "name": "New Tool",
                            "transport": "stdio",
                            "command": "npx",
                            "args": ["-y", "new-mcp"],
                        },
                    )
                    assert response.status_code == 201
                    data = response.json()
                    assert data["client_key"] == "new-tool"
                    assert data["name"] == "New Tool"
                    assert data["source"] == ""  # 我创建的
                    mock_save.assert_called_once()
                    mock_reload.assert_called_once()

    def test_create_duplicate_key(self, client):
        """重复 client_key 返回 400."""
        mock_workspace = MagicMock()
        mock_workspace.agent_id = "test-agent"
        mock_workspace.tenant_id = "test-tenant"

        mock_config = MagicMock()
        mock_config.mcp = MCPConfig(
            clients={
                "existing": MCPClientConfig(name="Existing", command="npx"),
            },
        )

        with patch(
            "swe.app.routers.my_mcp.get_agent_and_config_for_request",
        ) as mock_get:
            mock_get.return_value = (mock_workspace, mock_config)

            response = client.post(
                "/my-mcp",
                json={
                    "client_key": "existing",
                    "name": "Duplicate",
                    "command": "npx",
                },
            )
            assert response.status_code == 400

    def test_create_with_all_fields(self, client):
        """创建时包含所有字段."""
        mock_workspace = MagicMock()
        mock_workspace.agent_id = "test-agent"
        mock_workspace.tenant_id = "test-tenant"

        mock_config = MagicMock()
        mock_config.mcp = MCPConfig(clients={})

        with patch(
            "swe.app.routers.my_mcp.get_agent_and_config_for_request",
        ) as mock_get:
            with patch(
                "swe.app.routers.my_mcp.save_agent_config",
            ) as mock_save:
                with patch(
                    "swe.app.routers.my_mcp.schedule_agent_reload",
                ) as mock_reload:
                    mock_get.return_value = (mock_workspace, mock_config)

                    response = client.post(
                        "/my-mcp",
                        json={
                            "client_key": "full-tool",
                            "name": "Full Tool",
                            "description": "完整配置",
                            "transport": "stdio",
                            "command": "npx",
                            "args": ["-y", "full-mcp"],
                            "env": {"API_KEY": "secret-key"},
                            "cwd": "/tmp",
                        },
                    )
                    assert response.status_code == 201
                    data = response.json()
                    assert data["client_key"] == "full-tool"
                    assert data["name"] == "Full Tool"
                    assert data["description"] == "完整配置"
                    assert data["transport"] == "stdio"
                    assert data["command"] == "npx"
                    assert data["args"] == ["-y", "full-mcp"]
                    assert data["cwd"] == "/tmp"
                    # env 应被脱敏
                    assert "API_KEY" in data["env"]
                    mock_save.assert_called_once()
                    mock_reload.assert_called_once()

    def test_create_http_transport(self, client):
        """创建 HTTP 传输类型的 MCP."""
        mock_workspace = MagicMock()
        mock_workspace.agent_id = "test-agent"
        mock_workspace.tenant_id = "test-tenant"

        mock_config = MagicMock()
        mock_config.mcp = MCPConfig(clients={})

        with patch(
            "swe.app.routers.my_mcp.get_agent_and_config_for_request",
        ) as mock_get:
            with patch(
                "swe.app.routers.my_mcp.save_agent_config",
            ) as mock_save:
                with patch(
                    "swe.app.routers.my_mcp.schedule_agent_reload",
                ) as mock_reload:
                    mock_get.return_value = (mock_workspace, mock_config)

                    response = client.post(
                        "/my-mcp",
                        json={
                            "client_key": "http-tool",
                            "name": "HTTP Tool",
                            "transport": "streamable_http",
                            "url": "https://example.com/mcp",
                            "headers": {"Authorization": "Bearer token"},
                        },
                    )
                    assert response.status_code == 201
                    data = response.json()
                    assert data["client_key"] == "http-tool"
                    assert data["transport"] == "streamable_http"
                    assert data["url"] == "https://example.com/mcp"
                    # headers 应被脱敏
                    assert "Authorization" in data["headers"]
                    mock_save.assert_called_once()
                    mock_reload.assert_called_once()

    def test_create_mcp_none(self, client):
        """MCP 配置为 None 时应自动初始化."""
        mock_workspace = MagicMock()
        mock_workspace.agent_id = "test-agent"
        mock_workspace.tenant_id = "test-tenant"

        mock_config = MagicMock()
        mock_config.mcp = None

        with patch(
            "swe.app.routers.my_mcp.get_agent_and_config_for_request",
        ) as mock_get:
            with patch(
                "swe.app.routers.my_mcp.save_agent_config",
            ) as mock_save:
                with patch(
                    "swe.app.routers.my_mcp.schedule_agent_reload",
                ) as mock_reload:
                    mock_get.return_value = (mock_workspace, mock_config)

                    response = client.post(
                        "/my-mcp",
                        json={
                            "client_key": "new-tool",
                            "name": "New Tool",
                            "command": "npx",
                        },
                    )
                    assert response.status_code == 201
                    data = response.json()
                    assert data["client_key"] == "new-tool"
                    assert data["name"] == "New Tool"
                    mock_save.assert_called_once()
                    mock_reload.assert_called_once()


class TestUpdateMyMCP:
    """Tests for PUT /my-mcp/{client_key} endpoint."""

    def test_update_success(self, client):
        """更新现有 MCP."""
        mock_workspace = MagicMock()
        mock_workspace.agent_id = "test-agent"
        mock_workspace.tenant_id = "test-tenant"

        mock_config = MagicMock()
        mock_config.mcp = MCPConfig(
            clients={
                "weather": MCPClientConfig(
                    name="Old Name",
                    description="Old desc",
                    command="npx",
                    source="",
                    created_at="2026-04-29T10:00:00Z",
                    updated_at="2026-04-29T10:00:00Z",
                ),
            },
        )

        with patch(
            "swe.app.routers.my_mcp.get_agent_and_config_for_request",
        ) as mock_get:
            with patch(
                "swe.app.routers.my_mcp.save_agent_config",
            ) as mock_save:
                with patch(
                    "swe.app.routers.my_mcp.schedule_agent_reload",
                ) as mock_reload:
                    mock_get.return_value = (mock_workspace, mock_config)

                    response = client.put(
                        "/my-mcp/weather",
                        json={
                            "name": "New Name",
                            "description": "New desc",
                        },
                    )
                    assert response.status_code == 200
                    data = response.json()
                    assert data["name"] == "New Name"
                    assert data["description"] == "New desc"
                    mock_save.assert_called_once()
                    mock_reload.assert_called_once()

    def test_update_not_found(self, client):
        """更新不存在的 MCP 返回 404."""
        mock_workspace = MagicMock()
        mock_config = MagicMock()
        mock_config.mcp = MCPConfig(clients={})

        with patch(
            "swe.app.routers.my_mcp.get_agent_and_config_for_request",
        ) as mock_get:
            mock_get.return_value = (mock_workspace, mock_config)

            response = client.put("/my-mcp/nonexistent", json={"name": "New"})
            assert response.status_code == 404
            assert "nonexistent" in response.json()["detail"]

    def test_update_mcp_none(self, client):
        """MCP 配置为 None 时返回 404."""
        mock_workspace = MagicMock()
        mock_config = MagicMock()
        mock_config.mcp = None

        with patch(
            "swe.app.routers.my_mcp.get_agent_and_config_for_request",
        ) as mock_get:
            mock_get.return_value = (mock_workspace, mock_config)

            response = client.put("/my-mcp/weather", json={"name": "New"})
            assert response.status_code == 404

    def test_update_distributed_mcp_forbidden(self, client):
        """市场分发的 MCP 不允许编辑敏感字段."""
        mock_workspace = MagicMock()
        mock_config = MagicMock()
        mock_config.mcp = MCPConfig(
            clients={
                "distributed": MCPClientConfig(
                    name="Distributed",
                    command="npx",
                    source="marketplace:item-123",
                ),
            },
        )

        with patch(
            "swe.app.routers.my_mcp.get_agent_and_config_for_request",
        ) as mock_get:
            mock_get.return_value = (mock_workspace, mock_config)

            # 尝试修改 command（敏感字段）
            response = client.put(
                "/my-mcp/distributed",
                json={
                    "command": "new-command",
                },
            )
            assert response.status_code == 403
            assert "Cannot modify" in response.json()["detail"]

    def test_update_distributed_mcp_non_sensitive_allowed(self, client):
        """市场分发的 MCP 可以修改非敏感字段（如 name, description）."""
        mock_workspace = MagicMock()
        mock_workspace.agent_id = "test-agent"
        mock_workspace.tenant_id = "test-tenant"

        mock_config = MagicMock()
        mock_config.mcp = MCPConfig(
            clients={
                "distributed": MCPClientConfig(
                    name="Distributed",
                    description="Old desc",
                    command="npx",
                    source="marketplace:item-123",
                    created_at="2026-04-29T10:00:00Z",
                    updated_at="2026-04-29T10:00:00Z",
                ),
            },
        )

        with patch(
            "swe.app.routers.my_mcp.get_agent_and_config_for_request",
        ) as mock_get:
            with patch(
                "swe.app.routers.my_mcp.save_agent_config",
            ) as mock_save:
                with patch(
                    "swe.app.routers.my_mcp.schedule_agent_reload",
                ) as mock_reload:
                    mock_get.return_value = (mock_workspace, mock_config)

                    # 修改 name 和 description（非敏感字段）
                    response = client.put(
                        "/my-mcp/distributed",
                        json={
                            "name": "New Name",
                            "description": "New desc",
                        },
                    )
                    assert response.status_code == 200
                    data = response.json()
                    assert data["name"] == "New Name"
                    assert data["description"] == "New desc"
                    mock_save.assert_called_once()
                    mock_reload.assert_called_once()

    def test_update_with_env_restore(self, client):
        """更新 env 时应恢复脱敏值."""
        mock_workspace = MagicMock()
        mock_workspace.agent_id = "test-agent"
        mock_workspace.tenant_id = "test-tenant"

        original_env = {"API_KEY": "secret-key-12345678"}
        mock_config = MagicMock()
        mock_config.mcp = MCPConfig(
            clients={
                "test-client": MCPClientConfig(
                    name="Test",
                    command="npx",
                    env=original_env,
                    source="",
                    created_at="2026-04-29T10:00:00Z",
                    updated_at="2026-04-29T10:00:00Z",
                ),
            },
        )

        with patch(
            "swe.app.routers.my_mcp.get_agent_and_config_for_request",
        ) as mock_get:
            with patch(
                "swe.app.routers.my_mcp.save_agent_config",
            ) as mock_save:
                with patch(
                    "swe.app.routers.my_mcp.schedule_agent_reload",
                ) as mock_reload:
                    mock_get.return_value = (mock_workspace, mock_config)

                    # 发送脱敏后的值（与原始值匹配）
                    # secret-key-12345678 长度19，前2字符 + 13星号 + 后4字符
                    masked_value = "se*************5678"
                    response = client.put(
                        "/my-mcp/test-client",
                        json={
                            "env": {"API_KEY": masked_value},
                        },
                    )
                    assert response.status_code == 200
                    # 验证保存了原始值（而非脱敏值）
                    saved_client = mock_save.call_args[0][1].mcp.clients[
                        "test-client"
                    ]
                    assert (
                        saved_client.env["API_KEY"] == original_env["API_KEY"]
                    )

    def test_update_all_sensitive_fields_blocked(self, client):
        """测试所有敏感字段对市场分发 MCP 都被禁止."""
        mock_workspace = MagicMock()
        mock_config = MagicMock()
        mock_config.mcp = MCPConfig(
            clients={
                "distributed": MCPClientConfig(
                    name="Distributed",
                    command="npx",
                    source="marketplace:item-123",
                ),
            },
        )

        with patch(
            "swe.app.routers.my_mcp.get_agent_and_config_for_request",
        ) as mock_get:
            mock_get.return_value = (mock_workspace, mock_config)

            # 使用有效的字段值进行测试
            test_values = {
                "transport": "stdio",  # 有效值
                "url": "https://test.com",
                "headers": {"KEY": "value"},
                "command": "test-command",
                "args": ["arg1"],
                "env": {"KEY": "value"},
                "cwd": "/test/path",
            }

            for field, value in test_values.items():
                response = client.put(
                    "/my-mcp/distributed",
                    json={field: value},
                )
                assert (
                    response.status_code == 403
                ), f"{field} should be forbidden"
                assert field in response.json()["detail"]


class TestDeleteMyMCP:
    """Tests for DELETE /my-mcp/{client_key} endpoint."""

    def test_delete_success(self, client):
        """删除 MCP."""
        mock_workspace = MagicMock()
        mock_workspace.agent_id = "test-agent"
        mock_workspace.tenant_id = "test-tenant"

        mock_config = MagicMock()
        mock_config.mcp = MCPConfig(
            clients={
                "weather": MCPClientConfig(name="Weather", command="npx"),
            },
        )

        with patch(
            "swe.app.routers.my_mcp.get_agent_and_config_for_request",
        ) as mock_get:
            with patch(
                "swe.app.routers.my_mcp.save_agent_config",
            ) as mock_save:
                with patch(
                    "swe.app.routers.my_mcp.schedule_agent_reload",
                ) as mock_reload:
                    mock_get.return_value = (mock_workspace, mock_config)

                    response = client.delete("/my-mcp/weather")
                    assert response.status_code == 200
                    mock_save.assert_called_once()
                    mock_reload.assert_called_once()

    def test_delete_not_found(self, client):
        """删除不存在的 MCP 返回 404."""
        mock_workspace = MagicMock()
        mock_config = MagicMock()
        mock_config.mcp = MCPConfig(clients={})

        with patch(
            "swe.app.routers.my_mcp.get_agent_and_config_for_request",
        ) as mock_get:
            mock_get.return_value = (mock_workspace, mock_config)

            response = client.delete("/my-mcp/nonexistent")
            assert response.status_code == 404

    def test_delete_mcp_none(self, client):
        """MCP 配置为 None 时返回 404."""
        mock_workspace = MagicMock()
        mock_config = MagicMock()
        mock_config.mcp = None

        with patch(
            "swe.app.routers.my_mcp.get_agent_and_config_for_request",
        ) as mock_get:
            mock_get.return_value = (mock_workspace, mock_config)

            response = client.delete("/my-mcp/weather")
            assert response.status_code == 404


class TestToggleMyMCP:
    """Tests for PATCH /my-mcp/{client_key}/toggle endpoint."""

    def test_toggle_enable(self, client):
        """启用 MCP（从 False 到 True）."""
        mock_workspace = MagicMock()
        mock_workspace.agent_id = "test-agent"
        mock_workspace.tenant_id = "test-tenant"

        mock_config = MagicMock()
        mock_config.mcp = MCPConfig(
            clients={
                "weather": MCPClientConfig(
                    name="Weather",
                    command="npx",
                    enabled=False,
                    created_at="2026-04-29T10:00:00Z",
                    updated_at="2026-04-29T10:00:00Z",
                ),
            },
        )

        with patch(
            "swe.app.routers.my_mcp.get_agent_and_config_for_request",
        ) as mock_get:
            with patch(
                "swe.app.routers.my_mcp.save_agent_config",
            ) as mock_save:
                with patch(
                    "swe.app.routers.my_mcp.schedule_agent_reload",
                ) as mock_reload:
                    mock_get.return_value = (mock_workspace, mock_config)

                    response = client.patch("/my-mcp/weather/toggle")
                    assert response.status_code == 200
                    data = response.json()
                    assert data["enabled"] is True
                    assert data["client_key"] == "weather"
                    mock_save.assert_called_once()
                    mock_reload.assert_called_once()

    def test_toggle_disable(self, client):
        """禁用 MCP（从 True 到 False）."""
        mock_workspace = MagicMock()
        mock_workspace.agent_id = "test-agent"
        mock_workspace.tenant_id = "test-tenant"

        mock_config = MagicMock()
        mock_config.mcp = MCPConfig(
            clients={
                "weather": MCPClientConfig(
                    name="Weather",
                    command="npx",
                    enabled=True,
                    created_at="2026-04-29T10:00:00Z",
                    updated_at="2026-04-29T10:00:00Z",
                ),
            },
        )

        with patch(
            "swe.app.routers.my_mcp.get_agent_and_config_for_request",
        ) as mock_get:
            with patch(
                "swe.app.routers.my_mcp.save_agent_config",
            ) as mock_save:
                with patch(
                    "swe.app.routers.my_mcp.schedule_agent_reload",
                ) as mock_reload:
                    mock_get.return_value = (mock_workspace, mock_config)

                    response = client.patch("/my-mcp/weather/toggle")
                    assert response.status_code == 200
                    data = response.json()
                    assert data["enabled"] is False
                    assert data["client_key"] == "weather"

    def test_toggle_not_found(self, client):
        """不存在的 MCP 返回 404."""
        mock_workspace = MagicMock()
        mock_config = MagicMock()
        mock_config.mcp = MCPConfig(clients={})

        with patch(
            "swe.app.routers.my_mcp.get_agent_and_config_for_request",
        ) as mock_get:
            mock_get.return_value = (mock_workspace, mock_config)

            response = client.patch("/my-mcp/nonexistent/toggle")
            assert response.status_code == 404
            assert "nonexistent" in response.json()["detail"]

    def test_toggle_mcp_none(self, client):
        """MCP 配置为 None 时返回 404."""
        mock_workspace = MagicMock()
        mock_config = MagicMock()
        mock_config.mcp = None

        with patch(
            "swe.app.routers.my_mcp.get_agent_and_config_for_request",
        ) as mock_get:
            mock_get.return_value = (mock_workspace, mock_config)

            response = client.patch("/my-mcp/weather/toggle")
            assert response.status_code == 404

    def test_toggle_updates_timestamp(self, client):
        """切换应更新 updated_at 时间戳."""
        mock_workspace = MagicMock()
        mock_workspace.agent_id = "test-agent"
        mock_workspace.tenant_id = "test-tenant"

        original_updated_at = "2026-04-29T10:00:00Z"
        mock_config = MagicMock()
        mock_config.mcp = MCPConfig(
            clients={
                "weather": MCPClientConfig(
                    name="Weather",
                    command="npx",
                    enabled=False,
                    created_at="2026-04-29T10:00:00Z",
                    updated_at=original_updated_at,
                ),
            },
        )

        with patch(
            "swe.app.routers.my_mcp.get_agent_and_config_for_request",
        ) as mock_get:
            with patch(
                "swe.app.routers.my_mcp.save_agent_config",
            ) as mock_save:
                with patch(
                    "swe.app.routers.my_mcp.schedule_agent_reload",
                ) as mock_reload:
                    mock_get.return_value = (mock_workspace, mock_config)

                    response = client.patch("/my-mcp/weather/toggle")
                    assert response.status_code == 200
                    data = response.json()
                    # updated_at 应被更新（不同于原始值）
                    assert data["updated_at"] != original_updated_at


class TestMyMCPConnection:
    """Tests for POST /my-mcp/{client_key}/test endpoint."""

    def test_test_connection_success(self, client):
        """测试连接成功."""
        mock_workspace = MagicMock()
        mock_config = MagicMock()
        mock_config.mcp = MCPConfig(
            clients={
                "weather": MCPClientConfig(
                    name="Weather",
                    command="npx",
                    args=["-y", "weather-mcp"],
                ),
            },
        )

        with patch(
            "swe.app.routers.my_mcp.get_agent_and_config_for_request",
        ) as mock_get:
            with patch(
                "swe.app.routers.my_mcp._test_mcp_connection",
            ) as mock_test:
                mock_get.return_value = (mock_workspace, mock_config)
                mock_test.return_value = {
                    "success": True,
                    "tools": [
                        {"name": "get_weather", "description": "Get weather"},
                    ],
                    "error": "",
                }

                response = client.post("/my-mcp/weather/test")
                assert response.status_code == 200
                data = response.json()
                assert data["success"] is True
                assert len(data["tools"]) == 1
                assert data["tools"][0]["name"] == "get_weather"

    def test_test_connection_failure(self, client):
        """测试连接失败."""
        mock_workspace = MagicMock()
        mock_config = MagicMock()
        mock_config.mcp = MCPConfig(
            clients={
                "weather": MCPClientConfig(
                    name="Weather",
                    command="npx",
                ),
            },
        )

        with patch(
            "swe.app.routers.my_mcp.get_agent_and_config_for_request",
        ) as mock_get:
            with patch(
                "swe.app.routers.my_mcp._test_mcp_connection",
            ) as mock_test:
                mock_get.return_value = (mock_workspace, mock_config)
                mock_test.return_value = {
                    "success": False,
                    "tools": [],
                    "error": "Connection timeout",
                }

                response = client.post("/my-mcp/weather/test")
                assert response.status_code == 200
                data = response.json()
                assert data["success"] is False
                assert "error" in data
                assert data["error"] == "Connection timeout"

    def test_test_connection_not_found(self, client):
        """不存在的 MCP 返回 404."""
        mock_workspace = MagicMock()
        mock_config = MagicMock()
        mock_config.mcp = MCPConfig(clients={})

        with patch(
            "swe.app.routers.my_mcp.get_agent_and_config_for_request",
        ) as mock_get:
            mock_get.return_value = (mock_workspace, mock_config)

            response = client.post("/my-mcp/nonexistent/test")
            assert response.status_code == 404
            assert "nonexistent" in response.json()["detail"]

    def test_test_connection_mcp_none(self, client):
        """MCP 配置为 None 时返回 404."""
        mock_workspace = MagicMock()
        mock_config = MagicMock()
        mock_config.mcp = None

        with patch(
            "swe.app.routers.my_mcp.get_agent_and_config_for_request",
        ) as mock_get:
            mock_get.return_value = (mock_workspace, mock_config)

            response = client.post("/my-mcp/weather/test")
            assert response.status_code == 404

    def test_test_connection_http_transport(self, client):
        """HTTP 传输类型的连接测试."""
        mock_workspace = MagicMock()
        mock_config = MagicMock()
        mock_config.mcp = MCPConfig(
            clients={
                "http-tool": MCPClientConfig(
                    name="HTTP Tool",
                    transport="streamable_http",
                    url="https://example.com/mcp",
                ),
            },
        )

        with patch(
            "swe.app.routers.my_mcp.get_agent_and_config_for_request",
        ) as mock_get:
            with patch(
                "swe.app.routers.my_mcp._test_mcp_connection",
            ) as mock_test:
                mock_get.return_value = (mock_workspace, mock_config)
                mock_test.return_value = {
                    "success": True,
                    "tools": [{"name": "query", "description": "Query data"}],
                    "error": "",
                }

                response = client.post("/my-mcp/http-tool/test")
                assert response.status_code == 200
                data = response.json()
                assert data["success"] is True
                assert len(data["tools"]) == 1


class TestPublishMyMCP:
    """Tests for POST /my-mcp/publish endpoint."""

    @pytest.fixture
    def client_with_manager(self):
        """Create a TestClient with manager middleware."""
        from starlette.middleware.base import BaseHTTPMiddleware
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

    def test_publish_requires_manager(self, client):
        """非管理员不允许发布."""
        # Mock workspace 和 config
        mock_workspace = MagicMock()
        mock_workspace.agent_id = "test-agent"
        mock_config = MagicMock()
        mock_config.mcp = MCPConfig(
            clients={
                "weather": MCPClientConfig(name="Weather", command="npx"),
            },
        )

        with patch(
            "swe.app.routers.my_mcp.get_agent_and_config_for_request",
        ) as mock_get:
            mock_get.return_value = (mock_workspace, mock_config)

            # 默认 client 没有 manager middleware，request.state.manager 为 False
            response = client.post(
                "/my-mcp/publish",
                json={"client_keys": ["weather"]},
            )
            # Without manager flag, should return 403
            assert response.status_code == 403

    def test_publish_empty_keys(self, client_with_manager):
        """空 client_keys 返回 400."""
        response = client_with_manager.post(
            "/my-mcp/publish",
            json={"client_keys": []},
        )
        assert response.status_code == 400

    def test_publish_success(self, client_with_manager):
        """发布成功（调用市场服务返回 item_id）."""
        mock_workspace = MagicMock()
        mock_workspace.agent_id = "test-agent"
        mock_config = MagicMock()
        mock_config.mcp = MCPConfig(
            clients={
                "weather": MCPClientConfig(name="Weather", command="npx"),
                "search": MCPClientConfig(name="Search", command="npx"),
            },
        )

        # Mock httpx.AsyncClient 返回成功响应
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"item_id": "mcp-weather-123"}

        # 使用 AsyncMock 模拟异步上下文管理器
        mock_http_client = AsyncMock()
        mock_http_client.post.return_value = mock_response
        mock_http_client.__aenter__.return_value = mock_http_client
        mock_http_client.__aexit__.return_value = None

        with patch(
            "swe.app.routers.my_mcp.get_agent_and_config_for_request",
        ) as mock_get:
            mock_get.return_value = (mock_workspace, mock_config)

            with patch("httpx.AsyncClient", return_value=mock_http_client):
                response = client_with_manager.post(
                    "/my-mcp/publish",
                    json={"client_keys": ["weather", "search"]},
                )

                assert response.status_code == 200
                data = response.json()
                assert "results" in data
                assert len(data["results"]) == 2
                for result in data["results"]:
                    assert result["success"] is True
                    assert result["item_id"] == "mcp-weather-123"

    def test_publish_not_found(self, client_with_manager):
        """不存在的 client_key 返回错误结果."""
        mock_workspace = MagicMock()
        mock_workspace.agent_id = "test-agent"
        mock_config = MagicMock()
        mock_config.mcp = MCPConfig(
            clients={
                "weather": MCPClientConfig(name="Weather", command="npx"),
            },
        )

        with patch(
            "swe.app.routers.my_mcp.get_agent_and_config_for_request",
        ) as mock_get:
            mock_get.return_value = (mock_workspace, mock_config)

            response = client_with_manager.post(
                "/my-mcp/publish",
                json={"client_keys": ["weather", "nonexistent"]},
            )

            assert response.status_code == 200
            data = response.json()
            assert len(data["results"]) == 2
            # nonexistent should have success=False
            for result in data["results"]:
                if result["client_key"] == "nonexistent":
                    assert result["success"] is False
                    assert "not found" in result["error"]

    def test_publish_market_error(self, client_with_manager):
        """市场服务返回错误时，结果包含错误信息."""
        mock_workspace = MagicMock()
        mock_workspace.agent_id = "test-agent"
        mock_config = MagicMock()
        mock_config.mcp = MCPConfig(
            clients={
                "weather": MCPClientConfig(name="Weather", command="npx"),
            },
        )

        # Mock httpx.AsyncClient 返回错误响应
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        mock_http_client = AsyncMock()
        mock_http_client.post.return_value = mock_response
        mock_http_client.__aenter__.return_value = mock_http_client
        mock_http_client.__aexit__.return_value = None

        with patch(
            "swe.app.routers.my_mcp.get_agent_and_config_for_request",
        ) as mock_get:
            mock_get.return_value = (mock_workspace, mock_config)

            with patch("httpx.AsyncClient", return_value=mock_http_client):
                response = client_with_manager.post(
                    "/my-mcp/publish",
                    json={"client_keys": ["weather"]},
                )

                assert response.status_code == 200
                data = response.json()
                assert len(data["results"]) == 1
                result = data["results"][0]
                assert result["success"] is False
                assert "Internal Server Error" in result["error"]

    def test_publish_mcp_none(self, client_with_manager):
        """MCP 配置为 None 时返回 400."""
        mock_workspace = MagicMock()
        mock_config = MagicMock()
        mock_config.mcp = None

        with patch(
            "swe.app.routers.my_mcp.get_agent_and_config_for_request",
        ) as mock_get:
            mock_get.return_value = (mock_workspace, mock_config)

            response = client_with_manager.post(
                "/my-mcp/publish",
                json={"client_keys": ["weather"]},
            )

            assert response.status_code == 400
            assert "No MCP clients" in response.json()["detail"]
