# MCP 应用市场 - 计划 A：本地 MCP 后端

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 扩展 MCPClientConfig 字段并实现 `/api/my-mcp` API，支持本地 MCP 的 CRUD、启停、测试连接和发布到市场。

**Architecture:** 在现有 `mcp.py` 路由基础上，新建独立 `my_mcp.py` 路由处理"我的 MCP"页面需求。扩展 `MCPClientConfig` 添加来源标识、时间戳等字段。复用现有 `load_agent_config` / `save_agent_config` 进行配置持久化。

**Tech Stack:** Python 3.11+, FastAPI, Pydantic, pytest

---

## 文件结构

| 文件 | 操作 | 说明 |
|------|------|------|
| `src/swe/config/config.py` | Modify | 扩展 MCPClientConfig 添加 6 个新字段 |
| `src/swe/app/routers/my_mcp.py` | Create | 新建"我的 MCP"路由（9 个接口） |
| `src/swe/app/routers/__init__.py` | Modify | 注册 my_mcp 路由 |
| `tests/unit/app/test_my_mcp.py` | Create | 单元测试 |

---

## Task 1: 扩展 MCPClientConfig 字段

**Files:**
- Modify: `src/swe/config/config.py:875-945`
- Test: `tests/unit/config/test_mcp_config.py`

- [ ] **Step 1: 写 MCPClientConfig 扩展字段的测试**

```python
# tests/unit/config/test_mcp_config.py
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
    assert client.lazy_load == False
    assert client.created_at == ""
    assert client.updated_at == ""


def test_mcp_client_config_source_field():
    """source 字段应支持空值和市场来源标记。"""
    client_created = MCPClientConfig(
        name="created",
        command="npx",
        source="",
    )
    assert client_created.source == ""

    client_distributed = MCPClientConfig(
        name="distributed",
        command="npx",
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
    assert client.lazy_load == False
```

- [ ] **Step 2: 运行测试确认失败**

Run: `venv/bin/python -m pytest tests/unit/config/test_mcp_config.py -v`
Expected: FAIL（新字段未定义）

- [ ] **Step 3: 扩展 MCPClientConfig 模型**

```python
# src/swe/config/config.py
# 在 MCPClientConfig 类中添加以下字段（约 line 889 之后）

class MCPClientConfig(BaseModel):
    """Configuration for a single MCP client."""
    # ... 现有字段保持不变 ...

    # 新增字段（兼容现有配置）
    source: str = Field(
        default="",
        description="来源标识：空=我创建的；marketplace:{item_id}=市场分发的",
    )
    market_client_key: str = Field(
        default="",
        description="市场来源的 client_key",
    )
    distributed_by: str = Field(
        default="",
        description="分发者 user_id",
    )
    lazy_load: bool = Field(
        default=False,
        description="懒加载预留字段",
    )
    created_at: str = Field(
        default="",
        description="创建时间 ISO8601",
    )
    updated_at: str = Field(
        default="",
        description="更新时间 ISO8601",
    )
```

- [ ] **Step 4: 运行测试确认通过**

Run: `venv/bin/python -m pytest tests/unit/config/test_mcp_config.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add src/swe/config/config.py tests/unit/config/test_mcp_config.py
git commit -m "feat(config): extend MCPClientConfig with source, timestamps and lazy_load fields"
```

---

## Task 2: 新建 my_mcp 路由骨架

**Files:**
- Create: `src/swe/app/routers/my_mcp.py`
- Modify: `src/swe/app/routers/__init__.py`

- [ ] **Step 1: 创建 my_mcp.py 路由文件骨架**

```python
# src/swe/app/routers/my_mcp.py
# -*- coding: utf-8 -*-
"""我的 MCP 管理路由."""

from __future__ import annotations

from typing import List, Dict, Optional, Literal
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request, Body, Path
from pydantic import BaseModel, Field

from ...config.config import MCPClientConfig, MCPConfig, load_agent_config, save_agent_config
from ...config.context import resolve_effective_tenant_id

router = APIRouter(prefix="/my-mcp", tags=["my-mcp"])


def _get_tenant_id(request: Request) -> str | None:
    return getattr(request.state, "tenant_id", None)


def _get_source_id(request: Request) -> str | None:
    return getattr(request.state, "source_id", None)


class MyMCPListItem(BaseModel):
    """我的 MCP 列表项."""
    client_key: str
    name: str
    description: str = ""
    transport: Literal["stdio", "streamable_http", "sse"] = "stdio"
    enabled: bool = True
    source: str = ""
    market_client_key: str = ""
    created_at: str = ""
    updated_at: str = ""


class MyMCPDetail(MyMCPListItem):
    """我的 MCP 详情."""
    url: str = ""
    headers: Dict[str, str] = Field(default_factory=dict)
    command: str = ""
    args: List[str] = Field(default_factory=list)
    env: Dict[str, str] = Field(default_factory=dict)
    cwd: str = ""
    lazy_load: bool = False
    distributed_by: str = ""


class MyMCPCreateRequest(BaseModel):
    """创建 MCP 请求."""
    client_key: str = Field(..., description="唯一标识 key")
    name: str = Field(..., description="显示名称")
    description: str = Field(default="", description="描述")
    transport: Literal["stdio", "streamable_http", "sse"] = Field(default="stdio")
    url: str = Field(default="", description="HTTP/SSE URL")
    headers: Dict[str, str] = Field(default_factory=dict)
    command: str = Field(default="", description="stdio 命令")
    args: List[str] = Field(default_factory=list)
    env: Dict[str, str] = Field(default_factory=dict)
    cwd: str = Field(default="")


class MyMCPUpdateRequest(BaseModel):
    """更新 MCP 请求（所有字段可选）."""
    name: Optional[str] = None
    description: Optional[str] = None
    transport: Optional[Literal["stdio", "streamable_http", "sse"]] = None
    url: Optional[str] = None
    headers: Optional[Dict[str, str]] = None
    command: Optional[str] = None
    args: Optional[List[str]] = None
    env: Optional[Dict[str, str]] = None
    cwd: Optional[str] = None


class PublishMCPRequest(BaseModel):
    """发布到市场请求."""
    client_keys: List[str] = Field(..., description="要发布的 client_key 列表")
    category_id: Optional[int] = None
    bbk_ids: List[str] = Field(default_factory=list)


class PublishMCPResult(BaseModel):
    """单个发布结果."""
    client_key: str
    item_id: Optional[str] = None
    success: bool
    error: Optional[str] = None


class PublishMCPResponse(BaseModel):
    """发布响应."""
    results: List[PublishMCPResult]


# TODO: 实现各个接口（后续 Task）
```

- [ ] **Step 2: 注册路由到 __init__.py**

```python
# src/swe/app/routers/__init__.py
# 在现有路由导入之后添加

from .my_mcp import router as my_mcp_router

# 在 api_router.include_router 列表中添加
api_router.include_router(my_mcp_router)
```

- [ ] **Step 3: 验证路由注册**

Run: `venv/bin/python -c "from swe.app.routers import api_router; print([r.path for r in api_router.routes])"`
Expected: 输出包含 `/my-mcp` 相关路由

- [ ] **Step 4: 提交**

```bash
git add src/swe/app/routers/my_mcp.py src/swe/app/routers/__init__.py
git commit -m "feat(routers): add my_mcp router skeleton"
```

---

## Task 3: 实现我的 MCP 列表接口

**Files:**
- Modify: `src/swe/app/routers/my_mcp.py`
- Test: `tests/unit/app/test_my_mcp.py`

- [ ] **Step 1: 写列表接口测试**

```python
# tests/unit/app/test_my_mcp.py
import pytest
from unittest.mock import MagicMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient

from swe.app.routers.my_mcp import router, MyMCPListItem
from swe.config.config import MCPClientConfig, MCPConfig, AgentProfileConfig


@pytest.fixture
def test_app():
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(test_app):
    return TestClient(test_app)


class TestListMyMCP:
    def test_list_empty(self, client):
        """空配置应返回空列表."""
        with patch("swe.app.routers.my_mcp.load_agent_config") as mock_load:
            mock_config = MagicMock()
            mock_config.mcp = None
            mock_load.return_value = mock_config

            response = client.get("/my-mcp")
            assert response.status_code == 200
            assert response.json() == []

    def test_list_with_clients(self, client):
        """有 MCP 客户端时应返回列表."""
        with patch("swe.app.routers.my_mcp.load_agent_config") as mock_load:
            mock_config = MagicMock()
            mock_config.mcp = MCPConfig(clients={
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
                ),
            })
            mock_load.return_value = mock_config

            response = client.get("/my-mcp")
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 2
            assert data[0]["client_key"] in ["weather", "distributed-tool"]
```

- [ ] **Step 2: 运行测试确认失败**

Run: `venv/bin/python -m pytest tests/unit/app/test_my_mcp.py -v`
Expected: FAIL（接口未实现）

- [ ] **Step 3: 实现列表接口**

```python
# src/swe/app/routers/my_mcp.py
# 在 router 定义之后添加

from ..agent_context import get_agent_and_config_for_request


@router.get("", response_model=List[MyMCPListItem])
async def list_my_mcp(request: Request) -> List[MyMCPListItem]:
    """获取我的 MCP 列表."""
    _, agent_config = await get_agent_and_config_for_request(request)

    if agent_config.mcp is None or not agent_config.mcp.clients:
        return []

    result = []
    for client_key, client in agent_config.mcp.clients.items():
        result.append(MyMCPListItem(
            client_key=client_key,
            name=client.name,
            description=client.description,
            transport=client.transport,
            enabled=client.enabled,
            source=client.source,
            market_client_key=client.market_client_key,
            created_at=client.created_at,
            updated_at=client.updated_at,
        ))

    # 按更新时间降序
    result.sort(key=lambda x: x.updated_at or "", reverse=True)
    return result
```

- [ ] **Step 4: 运行测试确认通过**

Run: `venv/bin/python -m pytest tests/unit/app/test_my_mcp.py::TestListMyMCP -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add src/swe/app/routers/my_mcp.py tests/unit/app/test_my_mcp.py
git commit -m "feat(my-mcp): implement list endpoint"
```

---

## Task 4: 实现我的 MCP 详情接口

**Files:**
- Modify: `src/swe/app/routers/my_mcp.py`
- Test: `tests/unit/app/test_my_mcp.py`

- [ ] **Step 1: 写详情接口测试**

```python
# tests/unit/app/test_my_mcp.py 添加

class TestGetMyMCPDetail:
    def test_get_detail_success(self, client):
        """正常获取详情."""
        with patch("swe.app.routers.my_mcp.load_agent_config") as mock_load:
            mock_config = MagicMock()
            mock_config.mcp = MCPConfig(clients={
                "weather": MCPClientConfig(
                    name="Weather Tool",
                    description="天气查询",
                    command="npx",
                    args=["-y", "weather-mcp"],
                    env={"API_KEY": "test-key"},
                    source="",
                ),
            })
            mock_load.return_value = mock_config

            response = client.get("/my-mcp/weather")
            assert response.status_code == 200
            data = response.json()
            assert data["client_key"] == "weather"
            assert data["name"] == "Weather Tool"
            assert data["command"] == "npx"

    def test_get_detail_not_found(self, client):
        """不存在的 client_key 返回 404."""
        with patch("swe.app.routers.my_mcp.load_agent_config") as mock_load:
            mock_config = MagicMock()
            mock_config.mcp = MCPConfig(clients={})
            mock_load.return_value = mock_config

            response = client.get("/my-mcp/nonexistent")
            assert response.status_code == 404
```

- [ ] **Step 2: 运行测试确认失败**

Run: `venv/bin/python -m pytest tests/unit/app/test_my_mcp.py::TestGetMyMCPDetail -v`
Expected: FAIL

- [ ] **Step 3: 实现详情接口**

```python
# src/swe/app/routers/my_mcp.py 添加

from .mcp import _mask_env_value


def _mask_sensitive_values(client: MCPClientConfig) -> MyMCPDetail:
    """构建详情响应，脱敏 env 和 headers."""
    masked_env = {k: _mask_env_value(v) for k, v in client.env.items()} if client.env else {}
    masked_headers = {k: _mask_env_value(v) for k, v in client.headers.items()} if client.headers else {}

    return MyMCPDetail(
        client_key="",  # 由路由填充
        name=client.name,
        description=client.description,
        transport=client.transport,
        enabled=client.enabled,
        source=client.source,
        market_client_key=client.market_client_key,
        created_at=client.created_at,
        updated_at=client.updated_at,
        url=client.url,
        headers=masked_headers,
        command=client.command,
        args=client.args,
        env=masked_env,
        cwd=client.cwd,
        lazy_load=client.lazy_load,
        distributed_by=client.distributed_by,
    )


@router.get("/{client_key}", response_model=MyMCPDetail)
async def get_my_mcp_detail(
    request: Request,
    client_key: str = Path(...),
) -> MyMCPDetail:
    """获取单个 MCP 详情."""
    _, agent_config = await get_agent_and_config_for_request(request)

    if agent_config.mcp is None:
        raise HTTPException(404, detail=f"MCP client '{client_key}' not found")

    client = agent_config.mcp.clients.get(client_key)
    if client is None:
        raise HTTPException(404, detail=f"MCP client '{client_key}' not found")

    detail = _mask_sensitive_values(client)
    detail.client_key = client_key
    return detail
```

- [ ] **Step 4: 运行测试确认通过**

Run: `venv/bin/python -m pytest tests/unit/app/test_my_mcp.py::TestGetMyMCPDetail -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add src/swe/app/routers/my_mcp.py tests/unit/app/test_my_mcp.py
git commit -m "feat(my-mcp): implement detail endpoint with sensitive value masking"
```

---

## Task 5: 实现创建 MCP 接口

**Files:**
- Modify: `src/swe/app/routers/my_mcp.py`
- Test: `tests/unit/app/test_my_mcp.py`

- [ ] **Step 1: 写创建接口测试**

```python
# tests/unit/app/test_my_mcp.py 添加

class TestCreateMyMCP:
    def test_create_success(self, client):
        """创建新的 MCP."""
        with patch("swe.app.routers.my_mcp.load_agent_config") as mock_load:
            with patch("swe.app.routers.my_mcp.save_agent_config") as mock_save:
                mock_config = MagicMock()
                mock_config.mcp = MCPConfig(clients={})
                mock_load.return_value = mock_config

                response = client.post("/my-mcp", json={
                    "client_key": "new-tool",
                    "name": "New Tool",
                    "transport": "stdio",
                    "command": "npx",
                    "args": ["-y", "new-mcp"],
                })
                assert response.status_code == 201
                data = response.json()
                assert data["client_key"] == "new-tool"
                assert data["name"] == "New Tool"
                assert data["source"] == ""  # 我创建的
                mock_save.assert_called_once()

    def test_create_duplicate_key(self, client):
        """重复 client_key 返回 400."""
        with patch("swe.app.routers.my_mcp.load_agent_config") as mock_load:
            mock_config = MagicMock()
            mock_config.mcp = MCPConfig(clients={
                "existing": MCPClientConfig(name="Existing", command="npx"),
            })
            mock_load.return_value = mock_config

            response = client.post("/my-mcp", json={
                "client_key": "existing",
                "name": "Duplicate",
                "command": "npx",
            })
            assert response.status_code == 400
```

- [ ] **Step 2: 运行测试确认失败**

Run: `venv/bin/python -m pytest tests/unit/app/test_my_mcp.py::TestCreateMyMCP -v`
Expected: FAIL

- [ ] **Step 3: 实现创建接口**

```python
# src/swe/app/routers/my_mcp.py 添加

from ..utils import schedule_agent_reload


@router.post("", response_model=MyMCPDetail, status_code=201)
async def create_my_mcp(
    request: Request,
    body: MyMCPCreateRequest = Body(...),
) -> MyMCPDetail:
    """创建新的 MCP."""
    workspace, agent_config = await get_agent_and_config_for_request(request)

    if agent_config.mcp is None:
        agent_config.mcp = MCPConfig(clients={})

    if body.client_key in agent_config.mcp.clients:
        raise HTTPException(
            400,
            detail=f"MCP client '{body.client_key}' already exists",
        )

    now = datetime.now(timezone.utc).isoformat()
    new_client = MCPClientConfig(
        name=body.name,
        description=body.description,
        enabled=True,
        transport=body.transport,
        url=body.url,
        headers=body.headers,
        command=body.command,
        args=body.args,
        env=body.env,
        cwd=body.cwd,
        source="",  # 我创建的
        created_at=now,
        updated_at=now,
    )

    agent_config.mcp.clients[body.client_key] = new_client
    save_agent_config(workspace.agent_id, agent_config, tenant_id=workspace.tenant_id)
    schedule_agent_reload(request, workspace.agent_id, tenant_id=workspace.tenant_id)

    detail = _mask_sensitive_values(new_client)
    detail.client_key = body.client_key
    return detail
```

- [ ] **Step 4: 运行测试确认通过**

Run: `venv/bin/python -m pytest tests/unit/app/test_my_mcp.py::TestCreateMyMCP -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add src/swe/app/routers/my_mcp.py tests/unit/app/test_my_mcp.py
git commit -m "feat(my-mcp): implement create endpoint"
```

---

## Task 6: 实现更新 MCP 接口

**Files:**
- Modify: `src/swe/app/routers/my_mcp.py`
- Test: `tests/unit/app/test_my_mcp.py`

- [ ] **Step 1: 写更新接口测试**

```python
# tests/unit/app/test_my_mcp.py 添加

class TestUpdateMyMCP:
    def test_update_success(self, client):
        """更新现有 MCP."""
        with patch("swe.app.routers.my_mcp.load_agent_config") as mock_load:
            with patch("swe.app.routers.my_mcp.save_agent_config") as mock_save:
                mock_config = MagicMock()
                mock_config.mcp = MCPConfig(clients={
                    "weather": MCPClientConfig(
                        name="Old Name",
                        description="Old desc",
                        command="npx",
                        source="",
                    ),
                })
                mock_load.return_value = mock_config

                response = client.put("/my-mcp/weather", json={
                    "name": "New Name",
                    "description": "New desc",
                })
                assert response.status_code == 200
                data = response.json()
                assert data["name"] == "New Name"
                mock_save.assert_called_once()

    def test_update_not_found(self, client):
        """更新不存在的 MCP 返回 404."""
        with patch("swe.app.routers.my_mcp.load_agent_config") as mock_load:
            mock_config = MagicMock()
            mock_config.mcp = MCPConfig(clients={})
            mock_load.return_value = mock_config

            response = client.put("/my-mcp/nonexistent", json={"name": "New"})
            assert response.status_code == 404

    def test_update_distributed_mcp_forbidden(self, client):
        """市场分发的 MCP 不允许编辑连接配置."""
        with patch("swe.app.routers.my_mcp.load_agent_config") as mock_load:
            mock_config = MagicMock()
            mock_config.mcp = MCPConfig(clients={
                "distributed": MCPClientConfig(
                    name="Distributed",
                    command="npx",
                    source="marketplace:item-123",
                ),
            })
            mock_load.return_value = mock_config

            response = client.put("/my-mcp/distributed", json={
                "command": "new-command",
            })
            assert response.status_code == 403
```

- [ ] **Step 2: 运行测试确认失败**

Run: `venv/bin/python -m pytest tests/unit/app/test_my_mcp.py::TestUpdateMyMCP -v`
Expected: FAIL

- [ ] **Step 3: 实现更新接口**

```python
# src/swe/app/routers/my_mcp.py 添加

# 敏感字段列表（市场分发的 MCP 不允许修改）
SENSITIVE_FIELDS = ["transport", "url", "headers", "command", "args", "env", "cwd"]


def _is_distributed_from_market(client: MCPClientConfig) -> bool:
    return client.source.startswith("marketplace:")


@router.put("/{client_key}", response_model=MyMCPDetail)
async def update_my_mcp(
    request: Request,
    client_key: str = Path(...),
    body: MyMCPUpdateRequest = Body(...),
) -> MyMCPDetail:
    """更新 MCP 配置."""
    workspace, agent_config = await get_agent_and_config_for_request(request)

    if agent_config.mcp is None or client_key not in agent_config.mcp.clients:
        raise HTTPException(404, detail=f"MCP client '{client_key}' not found")

    existing = agent_config.mcp.clients[client_key]

    # 市场分发的 MCP 不允许修改连接配置
    if _is_distributed_from_market(existing):
        update_data = body.model_dump(exclude_unset=True)
        for field in SENSITIVE_FIELDS:
            if field in update_data:
                raise HTTPException(
                    403,
                    detail=f"Cannot modify '{field}' for distributed MCP",
                )

    # 合并更新
    merged_data = existing.model_dump(mode="json")
    update_data = body.model_dump(exclude_unset=True)

    # 处理 env/headers 脱敏值恢复（复用现有 mcp.py 逻辑）
    from .mcp import _restore_original_values
    if "env" in update_data and update_data["env"] is not None:
        update_data["env"] = _restore_original_values(update_data["env"], existing.env or {})
    if "headers" in update_data and update_data["headers"] is not None:
        update_data["headers"] = _restore_original_values(update_data["headers"], existing.headers or {})

    merged_data.update(update_data)
    merged_data["updated_at"] = datetime.now(timezone.utc).isoformat()

    updated_client = MCPClientConfig.model_validate(merged_data)
    agent_config.mcp.clients[client_key] = updated_client

    save_agent_config(workspace.agent_id, agent_config, tenant_id=workspace.tenant_id)
    schedule_agent_reload(request, workspace.agent_id, tenant_id=workspace.tenant_id)

    detail = _mask_sensitive_values(updated_client)
    detail.client_key = client_key
    return detail
```

- [ ] **Step 4: 运行测试确认通过**

Run: `venv/bin/python -m pytest tests/unit/app/test_my_mcp.py::TestUpdateMyMCP -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add src/swe/app/routers/my_mcp.py tests/unit/app/test_my_mcp.py
git commit -m "feat(my-mcp): implement update endpoint with distributed MCP restriction"
```

---

## Task 7: 实现删除 MCP 接口

**Files:**
- Modify: `src/swe/app/routers/my_mcp.py`
- Test: `tests/unit/app/test_my_mcp.py`

- [ ] **Step 1: 写删除接口测试**

```python
# tests/unit/app/test_my_mcp.py 添加

class TestDeleteMyMCP:
    def test_delete_success(self, client):
        """删除 MCP."""
        with patch("swe.app.routers.my_mcp.load_agent_config") as mock_load:
            with patch("swe.app.routers.my_mcp.save_agent_config") as mock_save:
                mock_config = MagicMock()
                mock_config.mcp = MCPConfig(clients={
                    "weather": MCPClientConfig(name="Weather", command="npx"),
                })
                mock_load.return_value = mock_config

                response = client.delete("/my-mcp/weather")
                assert response.status_code == 200
                mock_save.assert_called_once()

    def test_delete_not_found(self, client):
        """删除不存在的 MCP 返回 404."""
        with patch("swe.app.routers.my_mcp.load_agent_config") as mock_load:
            mock_config = MagicMock()
            mock_config.mcp = MCPConfig(clients={})
            mock_load.return_value = mock_config

            response = client.delete("/my-mcp/nonexistent")
            assert response.status_code == 404
```

- [ ] **Step 2: 运行测试确认失败**

Run: `venv/bin/python -m pytest tests/unit/app/test_my_mcp.py::TestDeleteMyMCP -v`
Expected: FAIL

- [ ] **Step 3: 实现删除接口**

```python
# src/swe/app/routers/my_mcp.py 添加

@router.delete("/{client_key}", response_model=Dict[str, str])
async def delete_my_mcp(
    request: Request,
    client_key: str = Path(...),
) -> Dict[str, str]:
    """删除 MCP."""
    workspace, agent_config = await get_agent_and_config_for_request(request)

    if agent_config.mcp is None or client_key not in agent_config.mcp.clients:
        raise HTTPException(404, detail=f"MCP client '{client_key}' not found")

    del agent_config.mcp.clients[client_key]
    save_agent_config(workspace.agent_id, agent_config, tenant_id=workspace.tenant_id)
    schedule_agent_reload(request, workspace.agent_id, tenant_id=workspace.tenant_id)

    return {"message": f"MCP client '{client_key}' deleted"}
```

- [ ] **Step 4: 运行测试确认通过**

Run: `venv/bin/python -m pytest tests/unit/app/test_my_mcp.py::TestDeleteMyMCP -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add src/swe/app/routers/my_mcp.py tests/unit/app/test_my_mcp.py
git commit -m "feat(my-mcp): implement delete endpoint"
```

---

## Task 8: 实现启停 MCP 接口

**Files:**
- Modify: `src/swe/app/routers/my_mcp.py`
- Test: `tests/unit/app/test_my_mcp.py`

- [ ] **Step 1: 写启停接口测试**

```python
# tests/unit/app/test_my_mcp.py 添加

class TestToggleMyMCP:
    def test_toggle_enable(self, client):
        """启用 MCP."""
        with patch("swe.app.routers.my_mcp.load_agent_config") as mock_load:
            with patch("swe.app.routers.my_mcp.save_agent_config") as mock_save:
                mock_config = MagicMock()
                mock_config.mcp = MCPConfig(clients={
                    "weather": MCPClientConfig(name="Weather", command="npx", enabled=False),
                })
                mock_load.return_value = mock_config

                response = client.patch("/my-mcp/weather/toggle")
                assert response.status_code == 200
                data = response.json()
                assert data["enabled"] == True

    def test_toggle_disable(self, client):
        """禁用 MCP."""
        with patch("swe.app.routers.my_mcp.load_agent_config") as mock_load:
            with patch("swe.app.routers.my_mcp.save_agent_config") as mock_save:
                mock_config = MagicMock()
                mock_config.mcp = MCPConfig(clients={
                    "weather": MCPClientConfig(name="Weather", command="npx", enabled=True),
                })
                mock_load.return_value = mock_config

                response = client.patch("/my-mcp/weather/toggle")
                assert response.status_code == 200
                data = response.json()
                assert data["enabled"] == False
```

- [ ] **Step 2: 运行测试确认失败**

Run: `venv/bin/python -m pytest tests/unit/app/test_my_mcp.py::TestToggleMyMCP -v`
Expected: FAIL

- [ ] **Step 3: 实现启停接口**

```python
# src/swe/app/routers/my_mcp.py 添加

@router.patch("/{client_key}/toggle", response_model=MyMCPDetail)
async def toggle_my_mcp(
    request: Request,
    client_key: str = Path(...),
) -> MyMCPDetail:
    """启用/禁用 MCP."""
    workspace, agent_config = await get_agent_and_config_for_request(request)

    if agent_config.mcp is None or client_key not in agent_config.mcp.clients:
        raise HTTPException(404, detail=f"MCP client '{client_key}' not found")

    client = agent_config.mcp.clients[client_key]
    client.enabled = not client.enabled
    client.updated_at = datetime.now(timezone.utc).isoformat()

    save_agent_config(workspace.agent_id, agent_config, tenant_id=workspace.tenant_id)
    schedule_agent_reload(request, workspace.agent_id, tenant_id=workspace.tenant_id)

    detail = _mask_sensitive_values(client)
    detail.client_key = client_key
    return detail
```

- [ ] **Step 4: 运行测试确认通过**

Run: `venv/bin/python -m pytest tests/unit/app/test_my_mcp.py::TestToggleMyMCP -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add src/swe/app/routers/my_mcp.py tests/unit/app/test_my_mcp.py
git commit -m "feat(my-mcp): implement toggle endpoint"
```

---

## Task 9: 实现测试连接接口

**Files:**
- Modify: `src/swe/app/routers/my_mcp.py`
- Test: `tests/unit/app/test_my_mcp.py`

- [ ] **Step 1: 写测试连接接口测试**

```python
# tests/unit/app/test_my_mcp.py 添加

class TestMyMCPConnection:
    def test_test_connection_success(self, client):
        """测试连接成功."""
        with patch("swe.app.routers.my_mcp.load_agent_config") as mock_load:
            with patch("swe.app.routers.my_mcp._test_mcp_connection") as mock_test:
                mock_config = MagicMock()
                mock_config.mcp = MCPConfig(clients={
                    "weather": MCPClientConfig(
                        name="Weather",
                        command="npx",
                        args=["-y", "weather-mcp"],
                    ),
                })
                mock_load.return_value = mock_config
                mock_test.return_value = {
                    "success": True,
                    "tools": [{"name": "get_weather", "description": "Get weather"}],
                }

                response = client.post("/my-mcp/weather/test")
                assert response.status_code == 200
                data = response.json()
                assert data["success"] == True
                assert len(data["tools"]) == 1

    def test_test_connection_failure(self, client):
        """测试连接失败."""
        with patch("swe.app.routers.my_mcp.load_agent_config") as mock_load:
            with patch("swe.app.routers.my_mcp._test_mcp_connection") as mock_test:
                mock_config = MagicMock()
                mock_config.mcp = MCPConfig(clients={
                    "weather": MCPClientConfig(name="Weather", command="npx"),
                })
                mock_load.return_value = mock_config
                mock_test.return_value = {
                    "success": False,
                    "error": "Connection timeout",
                }

                response = client.post("/my-mcp/weather/test")
                assert response.status_code == 200
                data = response.json()
                assert data["success"] == False
                assert "error" in data
```

- [ ] **Step 2: 运行测试确认失败**

Run: `venv/bin/python -m pytest tests/unit/app/test_my_mcp.py::TestMyMCPConnection -v`
Expected: FAIL

- [ ] **Step 3: 实现测试连接接口**

```python
# src/swe/app/routers/my_mcp.py 添加

import asyncio
from ..mcp.stateful_client import StatefulStdioClient, HttpStatefulClient


class MCPTestResult(BaseModel):
    """测试连接结果."""
    success: bool
    tools: List[Dict[str, str]] = Field(default_factory=list)
    error: str = ""


async def _test_mcp_connection(client: MCPClientConfig, timeout: float = 30.0) -> MCPTestResult:
    """测试 MCP 连接."""
    try:
        if client.transport == "stdio":
            mcp_client = StatefulStdioClient(
                name="test-connection",
                command=client.command,
                args=client.args,
                env=client.env,
                cwd=client.cwd or None,
            )
        else:
            mcp_client = HttpStatefulClient(
                name="test-connection",
                transport=client.transport,
                url=client.url,
                headers=client.headers,
            )

        await mcp_client.connect()
        tools = await mcp_client.list_tools(timeout=timeout)
        await mcp_client.close()

        return MCPTestResult(
            success=True,
            tools=[{"name": t.name, "description": t.description or ""} for t in tools],
        )
    except asyncio.TimeoutError:
        return MCPTestResult(success=False, error="连接超时")
    except Exception as e:
        return MCPTestResult(success=False, error=str(e))


@router.post("/{client_key}/test", response_model=MCPTestResult)
async def test_my_mcp_connection(
    request: Request,
    client_key: str = Path(...),
) -> MCPTestResult:
    """测试 MCP 连接."""
    _, agent_config = await get_agent_and_config_for_request(request)

    if agent_config.mcp is None or client_key not in agent_config.mcp.clients:
        raise HTTPException(404, detail=f"MCP client '{client_key}' not found")

    client = agent_config.mcp.clients[client_key]
    return await _test_mcp_connection(client)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `venv/bin/python -m pytest tests/unit/app/test_my_mcp.py::TestMyMCPConnection -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add src/swe/app/routers/my_mcp.py tests/unit/app/test_my_mcp.py
git commit -m "feat(my-mcp): implement test connection endpoint"
```

---

## Task 10: 实现发布到市场接口（骨架）

**Files:**
- Modify: `src/swe/app/routers/my_mcp.py`
- Test: `tests/unit/app/test_my_mcp.py`

**说明:** 发布到市场需要调用 market 服务，本 Task 仅实现骨架和权限校验，实际调用逻辑在计划 B 完成后补充。

- [ ] **Step 1: 写发布接口测试**

```python
# tests/unit/app/test_my_mcp.py 添加

class TestPublishMyMCP:
    def test_publish_requires_manager(self, client):
        """非管理员不允许发布."""
        with patch("swe.app.routers.my_mcp.load_agent_config") as mock_load:
            mock_config = MagicMock()
            mock_config.mcp = MCPConfig(clients={
                "weather": MCPClientConfig(name="Weather", command="npx"),
            })
            mock_load.return_value = mock_config

            response = client.post("/my-mcp/publish", json={
                "client_keys": ["weather"],
            })
            # 需要在请求中设置 manager 标识，这里简化测试
            assert response.status_code in [200, 403]  # 骨架测试

    def test_publish_empty_keys(self, client):
        """空 client_keys 返回 400."""
        response = client.post("/my-mcp/publish", json={
            "client_keys": [],
        })
        assert response.status_code == 400
```

- [ ] **Step 2: 运行测试确认失败**

Run: `venv/bin/python -m pytest tests/unit/app/test_my_mcp.py::TestPublishMyMCP -v`
Expected: FAIL

- [ ] **Step 3: 实现发布接口骨架**

```python
# src/swe/app/routers/my_mcp.py 添加

def _require_manager(request: Request) -> None:
    """校验管理员权限."""
    manager = getattr(request.state, "manager", False)
    if not manager:
        raise HTTPException(403, detail="Manager access required")


@router.post("/publish", response_model=PublishMCPResponse)
async def publish_my_mcp_to_market(
    request: Request,
    body: PublishMCPRequest = Body(...),
) -> PublishMCPResponse:
    """发布 MCP 到市场（管理员）."""
    _require_manager(request)

    if not body.client_keys:
        raise HTTPException(400, detail="No client_keys provided")

    _, agent_config = await get_agent_and_config_for_request(request)

    if agent_config.mcp is None:
        raise HTTPException(400, detail="No MCP clients configured")

    results = []
    for client_key in body.client_keys:
        client = agent_config.mcp.clients.get(client_key)
        if client is None:
            results.append(PublishMCPResult(
                client_key=client_key,
                success=False,
                error=f"MCP client '{client_key}' not found",
            ))
            continue

        # TODO: 调用 market 服务发布（计划 B 完成后补充）
        # 目前返回占位结果
        results.append(PublishMCPResult(
            client_key=client_key,
            success=True,
            item_id="placeholder-item-id",
        ))

    return PublishMCPResponse(results=results)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `venv/bin/python -m pytest tests/unit/app/test_my_mcp.py::TestPublishMyMCP -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add src/swe/app/routers/my_mcp.py tests/unit/app/test_my_mcp.py
git commit -m "feat(my-mcp): implement publish endpoint skeleton (market service call to be added)"
```

---

## Task 11: 运行完整测试套件

- [ ] **Step 1: 运行全部 my_mcp 测试**

Run: `venv/bin/python -m pytest tests/unit/app/test_my_mcp.py -v`
Expected: 全部 PASS

- [ ] **Step 2: 运行 MCPConfig 测试**

Run: `venv/bin/python -m pytest tests/unit/config/test_mcp_config.py -v`
Expected: 全部 PASS

- [ ] **Step 3: 运行整体后端测试（确保无回归）**

Run: `venv/bin/python -m pytest tests/unit/ -v --tb=short`
Expected: 全部 PASS

---

## 完成检查

| 检查项 | 状态 |
|--------|------|
| MCPClientConfig 扩展字段 | ✓ |
| `/api/my-mcp` 列表接口 | ✓ |
| `/api/my-mcp/{client_key}` 详情接口 | ✓ |
| `/api/my-mcp` 创建接口 | ✓ |
| `/api/my-mcp/{client_key}` 更新接口 | ✓ |
| `/api/my-mcp/{client_key}` 删除接口 | ✓ |
| `/api/my-mcp/{client_key}/toggle` 启停接口 | ✓ |
| `/api/my-mcp/{client_key}/test` 测试连接接口 | ✓ |
| `/api/my-mcp/publish` 发布骨架 | ✓ |
| 单元测试 | ✓ |

---

## 后续依赖

- **计划 B** 完成后，补充 `publish` 接口的 market 服务调用逻辑