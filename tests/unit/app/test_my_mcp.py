# -*- coding: utf-8 -*-
"""Unit tests for my-mcp endpoints."""
import pytest
from unittest.mock import MagicMock, patch
from fastapi import FastAPI
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
            assert data["headers"]["Authorization"] == "Be*****************-123"

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
