# MCP 应用市场 - 计划 B：市场 MCP 后端

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 扩展 market service 实现 `/api/market/mcp` API，支持市场 MCP 的列表、详情、上传、分发、删除和统计查询。

**Architecture:** 复用现有 market 框架，新增 MCP 相关路由、schema、fs 操作和 service 方法。沿用现有 skills market 的分类、可见范围、日志表结构。新增 MCP 专用统计查询（按 `mcp_server` 聚合）。

**Tech Stack:** Python 3.11+, FastAPI, Pydantic, pytest, MySQL

**依赖:** 计划 A（MCPClientConfig 扩展）已完成

---

## 文件结构

| 文件 | 操作 | 说明 |
|------|------|------|
| `market/src/market/marketplace/models.py` | Modify | 扩展 MarketItem 支持 MCP 条目 |
| `market/src/market/marketplace/schemas.py` | Modify | 新增 MCP 相关请求/响应模型 |
| `market/src/market/marketplace/fs.py` | Modify | 新增 MCP 目录操作函数 |
| `market/src/market/marketplace/service.py` | Modify | 新增 MCP 相关服务方法 |
| `market/src/market/app/routers/mcp_browse.py` | Create | 新建市场 MCP 浏览路由 |
| `market/src/market/app/routers/mcp_market.py` | Create | 新建市场 MCP 管理路由 |
| `market/src/market/app/routers/__init__.py` | Modify | 注册 MCP 路由 |
| `tests/unit/market/test_mcp_service.py` | Create | 单元测试 |

---

## Task 1: 扩展 MarketItem 模型

**Files:**
- Modify: `market/src/market/marketplace/models.py`
- Test: `tests/unit/market/test_mcp_models.py`

- [ ] **Step 1: 写 MarketItem MCP 扩展测试**

```python
# tests/unit/market/test_mcp_models.py
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
```

- [ ] **Step 2: 运行测试确认失败**

Run: `venv/bin/python -m pytest tests/unit/market/test_mcp_models.py -v`
Expected: FAIL（client_key 字段未定义）

- [ ] **Step 3: 扩展 MarketItem 模型**

```python
# market/src/market/marketplace/models.py
# 在 MarketItem 类中添加 client_key 字段

class MarketItem(BaseModel):
    """市场条目（index.json 中的单条记录）."""

    item_id: str
    item_type: str = "skill"  # "skill" 或 "mcp"
    name: str
    description: str = ""
    version: str = "1.0.0"  # skill 专用，MCP 可忽略
    client_key: str = ""  # MCP 专用，业务唯一键
    creator_id: str
    creator_name: str = ""
    category_id: Optional[int] = None
    bbk_ids: list[str] = Field(default_factory=list)
    status: str = "active"
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
```

- [ ] **Step 4: 运行测试确认通过**

Run: `venv/bin/python -m pytest tests/unit/market/test_mcp_models.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add market/src/market/marketplace/models.py tests/unit/market/test_mcp_models.py
git commit -m "feat(market-models): add client_key field for MCP items"
```

---

## Task 2: 新增 MCP 相关 Schema

**Files:**
- Modify: `market/src/market/marketplace/schemas.py`
- Test: `tests/unit/market/test_mcp_schemas.py`

- [ ] **Step 1: 写 MCP Schema 测试**

```python
# tests/unit/market/test_mcp_schemas.py
import pytest
from market.marketplace.schemas import (
    MarketMCPItem,
    MarketMCPDetail,
    PublishMCPRequest,
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
        config={
            "transport": "stdio",
            "command": "npx",
            "args": ["-y", "weather-mcp"],
            "env": {},
            "headers": {},
            "cwd": "",
            "url": "",
            "lazy_load": False,
        },
        user_stats=[
            {"user_id": "user1", "user_name": "User1", "call_count": 50},
        ],
    )
    assert detail.config["transport"] == "stdio"
    assert len(detail.user_stats) == 1
```

- [ ] **Step 2: 运行测试确认失败**

Run: `venv/bin/python -m pytest tests/unit/market/test_mcp_schemas.py -v`
Expected: FAIL

- [ ] **Step 3: 新增 MCP Schema**

```python
# market/src/market/marketplace/schemas.py
# 在文件末尾添加 MCP 相关模型

class MarketMCPItem(BaseModel):
    """市场 MCP 列表项."""

    item_id: str
    client_key: str
    name: str
    description: str = ""
    creator_id: str
    creator_name: str = ""
    category_id: Optional[int] = None
    bbk_ids: list[str] = Field(default_factory=list)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    call_count: int = 0
    user_count: int = 0


class MCPConfigDetail(BaseModel):
    """MCP 配置详情（用于市场详情展示）。"""
    transport: str = "stdio"
    url: str = ""
    headers: dict[str, str] = Field(default_factory=dict)
    command: str = ""
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    cwd: str = ""
    lazy_load: bool = False


class MCPUserStat(BaseModel):
    """MCP 用户统计."""
    user_id: str
    user_name: str
    call_count: int


class MarketMCPDetail(MarketMCPItem):
    """市场 MCP 详情."""
    config: MCPConfigDetail
    user_stats: list[MCPUserStat] = Field(default_factory=list)


class PublishMCPRequest(BaseModel):
    """发布 MCP 到市场请求."""
    client_key: str
    name: str
    description: str = ""
    creator_id: str
    creator_name: str = ""
    category_id: Optional[int] = None
    bbk_ids: list[str] = Field(default_factory=list)
    config: dict  # MCPClientConfig 的 dict 形式


class UploadMCPResponse(BaseModel):
    """上传 MCP 响应."""
    success: bool
    error: Optional[str] = None
```

- [ ] **Step 4: 运行测试确认通过**

Run: `venv/bin/python -m pytest tests/unit/market/test_mcp_schemas.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add market/src/market/marketplace/schemas.py tests/unit/market/test_mcp_schemas.py
git commit -m "feat(market-schemas): add MCP-related request/response models"
```

---

## Task 3: 新增 MCP 文件系统操作

**Files:**
- Modify: `market/src/market/marketplace/fs.py`
- Test: `tests/unit/market/test_mcp_fs.py`

- [ ] **Step 1: 写 MCP FS 操作测试**

```python
# tests/unit/market/test_mcp_fs.py
import pytest
from pathlib import Path
from market.marketplace.fs import (
    get_mcp_dir,
    get_mcp_config_path,
    load_mcp_config,
    save_mcp_config,
)


def test_get_mcp_dir():
    """获取 MCP 目录路径。"""
    marketplace_root = Path("/tmp/.swe.marketplace")
    source_id = "source-123"
    item_id = "item-uuid"

    mcp_dir = get_mcp_dir(marketplace_root, source_id, item_id)
    expected = marketplace_root / source_id / "mcp" / item_id
    assert mcp_dir == expected


def test_get_mcp_config_path():
    """获取 MCP 配置文件路径。"""
    marketplace_root = Path("/tmp/.swe.marketplace")
    source_id = "source-123"
    item_id = "item-uuid"

    config_path = get_mcp_config_path(marketplace_root, source_id, item_id)
    expected = marketplace_root / source_id / "mcp" / item_id / "mcp.json"
    assert config_path == expected
```

- [ ] **Step 2: 运行测试确认失败**

Run: `venv/bin/python -m pytest tests/unit/market/test_mcp_fs.py -v`
Expected: FAIL

- [ ] **Step 3: 新增 MCP FS 函数**

```python
# market/src/market/marketplace/fs.py
# 在文件末尾添加 MCP 相关函数

def get_mcp_dir(
    marketplace_root: Path,
    source_id: str,
    item_id: str,
) -> Path:
    """获取 MCP 条目目录路径."""
    _validate_path_segment(source_id, "source_id")
    _validate_path_segment(item_id, "item_id")
    return marketplace_root / source_id / "mcp" / item_id


def get_mcp_config_path(
    marketplace_root: Path,
    source_id: str,
    item_id: str,
) -> Path:
    """获取 MCP 配置文件路径."""
    return get_mcp_dir(marketplace_root, source_id, item_id) / "mcp.json"


def load_mcp_config(
    marketplace_root: Path,
    source_id: str,
    item_id: str,
) -> Optional[dict]:
    """读取 MCP 配置文件。"""
    path = get_mcp_config_path(marketplace_root, source_id, item_id)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.error("Failed to load MCP config %s: %s", path, e)
        return None


def save_mcp_config(
    marketplace_root: Path,
    source_id: str,
    item_id: str,
    config: dict,
) -> None:
    """保存 MCP 配置文件。"""
    mcp_dir = get_mcp_dir(marketplace_root, source_id, item_id)
    mcp_dir.mkdir(parents=True, exist_ok=True)
    path = mcp_dir / "mcp.json"
    _atomic_write_json(path, config)


def copy_mcp_to_user(
    marketplace_root: Path,
    source_id: str,
    item_id: str,
    swe_root: Path,
    user_id: str,
    client_key: str,
    distributed_by: str,
    agent_id: str = DEFAULT_AGENT_ID,
) -> None:
    """将市场 MCP 复制到用户本地配置。"""
    _validate_path_segment(client_key, "client_key")

    mcp_config = load_mcp_config(marketplace_root, source_id, item_id)
    if mcp_config is None:
        raise ValueError(f"MCP config not found for item {item_id}")

    # 加载用户 agent.json
    user_config_path = swe_root / user_id / "workspaces" / agent_id / "agent.json"
    user_config_path.parent.mkdir(parents=True, exist_ok=True)

    user_config: dict = {}
    if user_config_path.exists():
        try:
            user_config = json.loads(user_config_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass

    # 确保结构存在
    if "mcp" not in user_config:
        user_config["mcp"] = {"clients": {}}
    if "clients" not in user_config["mcp"]:
        user_config["mcp"]["clients"] = {}

    # 合并 MCP 配置
    config_data = mcp_config.get("config", {})
    config_data["source"] = f"marketplace:{item_id}"
    config_data["market_client_key"] = client_key
    config_data["distributed_by"] = distributed_by
    config_data["updated_at"] = datetime.now(timezone.utc).isoformat()

    user_config["mcp"]["clients"][client_key] = config_data

    _atomic_write_json(user_config_path, user_config)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `venv/bin/python -m pytest tests/unit/market/test_mcp_fs.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add market/src/market/marketplace/fs.py tests/unit/market/test_mcp_fs.py
git commit -m "feat(market-fs): add MCP directory and config operations"
```

---

## Task 4: 新增 MCP Service 方法

**Files:**
- Modify: `market/src/market/marketplace/service.py`
- Test: `tests/unit/market/test_mcp_service.py`

- [ ] **Step 1: 写 MCP Service 测试**

```python
# tests/unit/market/test_mcp_service.py
import pytest
from unittest.mock import MagicMock, AsyncMock
from pathlib import Path

from market.marketplace.service import MarketplaceService
from market.marketplace.schemas import PublishMCPRequest, DistributeRequest


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def mock_paths():
    return Path("/tmp/.swe.marketplace"), Path("/tmp/.swe")


@pytest.fixture
def service(mock_db, mock_paths):
    marketplace_root, swe_root = mock_paths
    return MarketplaceService(mock_db, marketplace_root, swe_root)


class TestMCPService:
    async def test_publish_mcp_new(self, service):
        """发布新 MCP 到市场。"""
        with pytest.mock.patch("market.marketplace.service.load_index") as mock_load:
            with pytest.mock.patch("market.marketplace.service.save_index") as mock_save:
                with pytest.mock.patch("market.marketplace.fs.save_mcp_config") as mock_save_config:
                    mock_load.return_value = []

                    req = PublishMCPRequest(
                        client_key="weather",
                        name="Weather Tool",
                        creator_id="admin",
                        config={"command": "npx", "args": ["-y", "weather-mcp"]},
                    )

                    item = await service.publish_mcp("source-123", req)
                    assert item.client_key == "weather"
                    assert item.item_type == "mcp"
                    mock_save.assert_called_once()
                    mock_save_config.assert_called_once()

    async def test_publish_mcp_overwrite(self, service):
        """覆盖已存在的 MCP（复用 item_id）。"""
        from market.marketplace.models import MarketItem

        with pytest.mock.patch("market.marketplace.service.load_index") as mock_load:
            with pytest.mock.patch("market.marketplace.service.save_index") as mock_save:
                existing_item = MarketItem(
                    item_id="existing-uuid",
                    item_type="mcp",
                    client_key="weather",
                    name="Old Name",
                    creator_id="admin",
                )
                mock_load.return_value = [existing_item]

                req = PublishMCPRequest(
                    client_key="weather",
                    name="New Name",
                    creator_id="admin",
                    config={"command": "npx"},
                )

                item = await service.publish_mcp("source-123", req)
                assert item.item_id == "existing-uuid"  # 复用
                assert item.name == "New Name"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `venv/bin/python -m pytest tests/unit/market/test_mcp_service.py -v`
Expected: FAIL

- [ ] **Step 3: 新增 MCP Service 方法**

```python
# market/src/market/marketplace/service.py
# 在 MarketplaceService 类中添加 MCP 相关方法

# MCP 专用统计 SQL
_TRACING_STATS_MCP_SQL = """
    SELECT
        COUNT(*) AS call_count,
        COUNT(DISTINCT user_id) AS user_count
    FROM swe_tracing_spans
    WHERE mcp_server = %s
      AND source_id = %s
"""

_TRACING_USER_STATS_MCP_SQL = """
    SELECT
        user_id,
        MAX(COALESCE(metadata->>'$.user_name', '')) AS user_name,
        COUNT(*) AS call_count
    FROM swe_tracing_spans
    WHERE mcp_server = %s
      AND source_id = %s
    GROUP BY user_id
    ORDER BY call_count DESC
    LIMIT 100
"""


async def publish_mcp(
    self,
    source_id: str,
    req: PublishMCPRequest,
) -> MarketItem:
    """发布 MCP 到市场。覆盖已存在条目。"""
    items = load_index(self.marketplace_root, source_id)

    # 查找已存在的 MCP（按 client_key）
    existing = next(
        (i for i in items if i.item_type == "mcp" and i.client_key == req.client_key),
        None,
    )

    now = datetime.now(timezone.utc).isoformat()
    if existing is not None:
        # 覆盖：复用 item_id
        existing.name = req.name
        existing.description = req.description
        existing.creator_id = req.creator_id
        existing.creator_name = req.creator_name
        existing.category_id = req.category_id
        existing.bbk_ids = req.bbk_ids
        existing.updated_at = now
        item = existing
    else:
        # 新建
        item = MarketItem(
            item_id=str(uuid.uuid4()),
            item_type="mcp",
            client_key=req.client_key,
            name=req.name,
            description=req.description,
            creator_id=req.creator_id,
            creator_name=req.creator_name,
            category_id=req.category_id,
            bbk_ids=req.bbk_ids,
            status="active",
            created_at=now,
            updated_at=now,
        )
        items.append(item)

    # 保存 MCP 配置文件
    mcp_config = {
        "client_key": req.client_key,
        "config": req.config,
    }
    save_mcp_config(self.marketplace_root, source_id, item.item_id, mcp_config)

    # 更新索引
    save_index(self.marketplace_root, source_id, items)

    # 记录日志
    if self.db.is_connected:
        try:
            await self.db.execute(
                _LOG_MARKET_OP_SQL,
                (
                    source_id,
                    req.creator_id,
                    req.creator_name,
                    "publish",
                    "mcp",
                    item.item_id,
                    item.name,
                    None,
                    None,
                    None,
                ),
            )
        except Exception as e:
            logger.warning("Failed to log MCP publish: %s", e)

    return item


async def list_mcp_items(
    self,
    source_id: str,
    user_bbk_id: str,
    category_id: Optional[int] = None,
) -> list[MarketMCPItem]:
    """列出市场 MCP。"""
    items = load_index(self.marketplace_root, source_id)
    mcp_items = [i for i in items if i.item_type == "mcp" and _item_visible(i, user_bbk_id)]

    if category_id is not None:
        mcp_items = [i for i in mcp_items if i.category_id == category_id]

    result = []
    for item in mcp_items:
        call_count, user_count = await self._get_mcp_stats(
            item.client_key,
            source_id,
        )
        result.append(MarketMCPItem(
            item_id=item.item_id,
            client_key=item.client_key,
            name=item.name,
            description=item.description,
            creator_id=item.creator_id,
            creator_name=item.creator_name,
            category_id=item.category_id,
            bbk_ids=item.bbk_ids,
            created_at=item.created_at,
            updated_at=item.updated_at,
            call_count=call_count,
            user_count=user_count,
        ))
    return result


async def get_mcp_detail(
    self,
    source_id: str,
    item_id: str,
    user_bbk_id: str,
) -> Optional[MarketMCPDetail]:
    """获取 MCP 详情。"""
    items = load_index(self.marketplace_root, source_id)
    item = next(
        (i for i in items if i.item_id == item_id and i.item_type == "mcp"),
        None,
    )
    if item is None or not _item_visible(item, user_bbk_id):
        return None

    # 加载 MCP 配置
    mcp_config = load_mcp_config(self.marketplace_root, source_id, item_id)
    if mcp_config is None:
        return None

    call_count, user_count = await self._get_mcp_stats(item.client_key, source_id)
    user_stats = await self._get_mcp_user_stats(item.client_key, source_id)

    from .fs import _mask_env_value
    config_data = mcp_config.get("config", {})
    masked_env = {k: _mask_env_value(v) for k, v in config_data.get("env", {}).items()}
    masked_headers = {k: _mask_env_value(v) for k, v in config_data.get("headers", {}).items()}

    return MarketMCPDetail(
        item_id=item.item_id,
        client_key=item.client_key,
        name=item.name,
        description=item.description,
        creator_id=item.creator_id,
        creator_name=item.creator_name,
        category_id=item.category_id,
        bbk_ids=item.bbk_ids,
        created_at=item.created_at,
        updated_at=item.updated_at,
        call_count=call_count,
        user_count=user_count,
        config=MCPConfigDetail(
            transport=config_data.get("transport", "stdio"),
            url=config_data.get("url", ""),
            headers=masked_headers,
            command=config_data.get("command", ""),
            args=config_data.get("args", []),
            env=masked_env,
            cwd=config_data.get("cwd", ""),
            lazy_load=config_data.get("lazy_load", False),
        ),
        user_stats=user_stats,
    )


async def distribute_mcp(
    self,
    source_id: str,
    item_id: str,
    operator_id: str,
    operator_name: str,
    req: DistributeRequest,
) -> DistributeResponse:
    """分发 MCP 到目标用户。"""
    items = load_index(self.marketplace_root, source_id)
    item = next(
        (i for i in items if i.item_id == item_id and i.item_type == "mcp"),
        None,
    )
    if item is None:
        raise ValueError(f"MCP item {item_id} not found")

    target_users = await self._resolve_target_users(source_id, req)
    count = 0

    for user in target_users:
        try:
            copy_mcp_to_user(
                marketplace_root=self.marketplace_root,
                source_id=source_id,
                item_id=item_id,
                swe_root=self.swe_root,
                user_id=user["tenant_id"],
                client_key=item.client_key,
                distributed_by=operator_id,
            )
            count += 1
        except Exception as e:
            logger.warning("Failed to distribute MCP to %s: %s", user["tenant_id"], e)
            continue

        # 记录日志
        if self.db.is_connected:
            try:
                await self.db.execute(
                    _LOG_MARKET_OP_SQL,
                    (
                        source_id,
                        operator_id,
                        operator_name,
                        "distribute",
                        "mcp",
                        item_id,
                        item.name,
                        user["tenant_id"],
                        user.get("tenant_name", ""),
                        user.get("bbk_id", ""),
                    ),
                )
            except Exception as e:
                logger.warning("Failed to log MCP distribute: %s", e)

    return DistributeResponse(distributed_count=count, item_id=item_id)


async def delete_mcp(
    self,
    source_id: str,
    item_id: str,
    operator_id: str,
    operator_name: str,
) -> bool:
    """删除市场 MCP。"""
    items = load_index(self.marketplace_root, source_id)
    item = next(
        (i for i in items if i.item_id == item_id and i.item_type == "mcp"),
        None,
    )
    if item is None:
        return False

    # 从索引移除
    items.remove(item)
    save_index(self.marketplace_root, source_id, items)

    # 删除配置文件
    mcp_dir = get_mcp_dir(self.marketplace_root, source_id, item_id)
    if mcp_dir.exists():
        import shutil
        shutil.rmtree(mcp_dir)

    # 记录日志
    if self.db.is_connected:
        try:
            await self.db.execute(
                _LOG_MARKET_OP_SQL,
                (
                    source_id,
                    operator_id,
                    operator_name,
                    "delete",
                    "mcp",
                    item_id,
                    item.name,
                    None,
                    None,
                    None,
                ),
            )
        except Exception as e:
            logger.warning("Failed to log MCP delete: %s", e)

    return True


async def _get_mcp_stats(
    self,
    client_key: str,
    source_id: str,
) -> tuple[int, int]:
    """获取 MCP 调用统计（按 mcp_server 聚合）。"""
    if not self.db.is_connected:
        return 0, 0
    try:
        row = await self.db.fetch_one(
            _TRACING_STATS_MCP_SQL,
            (client_key, source_id),
        )
        if row:
            return int(row.get("call_count", 0)), int(row.get("user_count", 0))
    except Exception as e:
        logger.warning("Failed to get MCP stats for %s: %s", client_key, e)
    return 0, 0


async def _get_mcp_user_stats(
    self,
    client_key: str,
    source_id: str,
) -> list[MCPUserStat]:
    """获取 MCP 用户统计明细。"""
    if not self.db.is_connected:
        return []
    try:
        rows = await self.db.fetch_all(
            _TRACING_USER_STATS_MCP_SQL,
            (client_key, source_id),
        )
        return [
            MCPUserStat(
                user_id=r["user_id"],
                user_name=r.get("user_name", ""),
                call_count=int(r["call_count"]),
            )
            for r in rows
        ]
    except Exception as e:
        logger.warning("Failed to get MCP user stats for %s: %s", client_key, e)
    return []
```

**注意:** 需要在文件开头导入新模块：

```python
# market/src/market/marketplace/service.py
# 添加导入

from .fs import (
    copy_skill_to_user,
    get_skill_dir,
    get_user_skills_dir,
    load_index,
    save_index,
    # 新增 MCP 相关导入
    get_mcp_dir,
    load_mcp_config,
    save_mcp_config,
    copy_mcp_to_user,
    _mask_env_value,  # 从 fs.py 移入或复用
)

from .schemas import (
    DistributeRequest,
    DistributeResponse,
    MarketSkillDetail,
    MarketSkillResponse,
    MySkillItem,
    PublishSkillRequest,
    SkillUserStat,
    # 新增 MCP 相关导入
    MarketMCPItem,
    MarketMCPDetail,
    MCPConfigDetail,
    MCPUserStat,
    PublishMCPRequest,
)
```

还需要在 `fs.py` 中添加 `_mask_env_value` 函数（复用 `src/swe/app/routers/mcp.py` 的实现）：

```python
# market/src/market/marketplace/fs.py
# 添加 _mask_env_value 函数

def _mask_env_value(value: str) -> str:
    """脱敏环境变量值（复用 swe/app/routers/mcp.py 实现）。"""
    if not value:
        return value
    length = len(value)
    if length <= 8:
        return "*" * length
    prefix_len = 3 if length > 2 and value[2] == "-" else 2
    prefix = value[:prefix_len]
    suffix = value[-4:]
    masked_len = max(length - prefix_len - 4, 4)
    return f"{prefix}{'*' * masked_len}{suffix}"
```

- [ ] **Step 4: 运行测试确认通过**

Run: `venv/bin/python -m pytest tests/unit/market/test_mcp_service.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add market/src/market/marketplace/service.py market/src/market/marketplace/fs.py tests/unit/market/test_mcp_service.py
git commit -m "feat(market-service): add MCP publish, list, detail, distribute and delete methods"
```

---

## Task 5: 新建 MCP 浏览路由

**Files:**
- Create: `market/src/market/app/routers/mcp_browse.py`
- Modify: `market/src/market/app/routers/__init__.py`

- [ ] **Step 1: 创建 MCP 浏览路由**

```python
# market/src/market/app/routers/mcp_browse.py
# -*- coding: utf-8 -*-
"""市场 MCP 浏览路由."""

from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Request

from ..marketplace.schemas import MarketMCPItem, MarketMCPDetail
from ..deps import require_source_id

router = APIRouter()


@router.get("/market/mcp", response_model=list[MarketMCPItem])
async def list_market_mcp(
    request: Request,
    category_id: Optional[int] = None,
    x_source_id: Optional[str] = Header(default=None, alias="X-Source-Id"),
    x_bbk_id: Optional[str] = Header(default=None, alias="X-Bbk-Id"),
):
    """浏览市场 MCP 列表。"""
    source_id = require_source_id(x_source_id)
    user_bbk_id = x_bbk_id or "100"
    svc = request.app.state.marketplace
    return await svc.list_mcp_items(source_id, user_bbk_id, category_id=category_id)


@router.get("/market/mcp/{item_id}", response_model=MarketMCPDetail)
async def get_market_mcp_detail(
    item_id: str,
    request: Request,
    x_source_id: Optional[str] = Header(default=None, alias="X-Source-Id"),
    x_bbk_id: Optional[str] = Header(default=None, alias="X-Bbk-Id"),
):
    """获取市场 MCP 详情。"""
    source_id = require_source_id(x_source_id)
    user_bbk_id = x_bbk_id or "100"
    svc = request.app.state.marketplace
    detail = await svc.get_mcp_detail(source_id, item_id, user_bbk_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="MCP not found")
    return detail
```

- [ ] **Step 2: 注册路由**

```python
# market/src/market/app/routers/__init__.py
# 添加导入和注册

from .mcp_browse import router as mcp_browse_router

api_router.include_router(mcp_browse_router, tags=["marketplace"])
```

- [ ] **Step 3: 验证路由注册**

Run: `venv/bin/python -c "from market.app.routers import api_router; print([r.path for r in api_router.routes])"`
Expected: 输出包含 `/market/mcp`

- [ ] **Step 4: 提交**

```bash
git add market/src/market/app/routers/mcp_browse.py market/src/market/app/routers/__init__.py
git commit -m "feat(market-routers): add MCP browse routes"
```

---

## Task 6: 新建 MCP 管理路由

**Files:**
- Create: `market/src/market/app/routers/mcp_market.py`
- Modify: `market/src/market/app/routers/__init__.py`

- [ ] **Step 1: 创建 MCP 管理路由**

```python
# market/src/market/app/routers/mcp_market.py
# -*- coding: utf-8 -*-
"""市场 MCP 管理路由（管理员）。"""

import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, File, Header, HTTPException, Request, status, UploadFile, Form

from ..marketplace.schemas import (
    DistributeRequest,
    DistributeResponse,
    MarketMCPItem,
    PublishMCPRequest,
    UploadMCPResponse,
)
from ..marketplace.models import MarketItem
from ..marketplace.fs import save_mcp_config, load_index, save_index
from ..deps import require_source_id

router = APIRouter()


def _require_manager(x_manager: Optional[str]) -> None:
    if x_manager != "true":
        raise HTTPException(status_code=403, detail="Manager access required")


@router.post(
    "/market/mcp",
    response_model=MarketMCPItem,
    status_code=status.HTTP_201_CREATED,
)
async def publish_mcp(
    req: PublishMCPRequest,
    request: Request,
    x_source_id: Optional[str] = Header(default=None, alias="X-Source-Id"),
    x_manager: Optional[str] = Header(default=None, alias="X-Manager"),
):
    """发布 MCP 到市场（管理员）。"""
    source_id = require_source_id(x_source_id)
    _require_manager(x_manager)
    svc = request.app.state.marketplace
    item = await svc.publish_mcp(source_id, req)
    return MarketMCPItem(
        item_id=item.item_id,
        client_key=item.client_key,
        name=item.name,
        description=item.description,
        creator_id=item.creator_id,
        creator_name=item.creator_name,
        category_id=item.category_id,
        bbk_ids=item.bbk_ids,
        created_at=item.created_at,
        updated_at=item.updated_at,
        call_count=0,
        user_count=0,
    )


@router.post(
    "/market/mcp/upload",
    response_model=UploadMCPResponse,
)
async def upload_mcp(
    request: Request,
    file: UploadFile = File(...),
    name: Optional[str] = Form(default=None),
    description: Optional[str] = Form(default=""),
    category_id: Optional[int] = Form(default=None),
    bbk_ids: Optional[str] = Form(default=None),  # JSON string
    x_source_id: Optional[str] = Header(default=None, alias="X-Source-Id"),
    x_manager: Optional[str] = Header(default=None, alias="X-Manager"),
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    x_user_name: Optional[str] = Header(default=None, alias="X-User-Name"),
):
    """上传 MCP 连接器文件到市场（管理员）。"""
    source_id = require_source_id(x_source_id)
    _require_manager(x_manager)

    # 解析上传文件
    if not file.filename or not file.filename.endswith(".json"):
        return UploadMCPResponse(success=False, error="Only .json files are accepted")

    try:
        content = await file.read()
        file_data = json.loads(content.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        return UploadMCPResponse(success=False, error=f"Invalid JSON: {e}")

    # 提取 client_key 和 name
    client_key = file_data.get("client_key", "")
    config = file_data.get("config", file_data)  # 支持两种格式

    if not client_key:
        # 用文件名规范化生成 client_key
        import re
        client_key = re.sub(r"[^a-zA-Z0-9_-]", "-", file.filename[:-5])

    final_name = name or config.get("name", client_key)

    # 构建发布请求
    req = PublishMCPRequest(
        client_key=client_key,
        name=final_name,
        description=description or config.get("description", ""),
        creator_id=x_user_id or "unknown",
        creator_name=x_user_name or "",
        category_id=category_id,
        bbk_ids=json.loads(bbk_ids) if bbk_ids else [],
        config=config,
    )

    svc = request.app.state.marketplace
    try:
        await svc.publish_mcp(source_id, req)
        return UploadMCPResponse(success=True)
    except Exception as e:
        return UploadMCPResponse(success=False, error=str(e))


@router.post(
    "/market/mcp/{item_id}/distribute",
    response_model=DistributeResponse,
)
async def distribute_mcp(
    item_id: str,
    req: DistributeRequest,
    request: Request,
    x_source_id: Optional[str] = Header(default=None, alias="X-Source-Id"),
    x_manager: Optional[str] = Header(default=None, alias="X-Manager"),
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    x_user_name: Optional[str] = Header(default=None, alias="X-User-Name"),
):
    """分发 MCP（管理员）。"""
    source_id = require_source_id(x_source_id)
    _require_manager(x_manager)
    svc = request.app.state.marketplace

    # 先检查条目是否存在
    items = load_index(svc.marketplace_root, source_id)
    item = next((i for i in items if i.item_id == item_id and i.item_type == "mcp"), None)
    if item is None:
        raise HTTPException(status_code=404, detail="MCP not found or already deleted")

    try:
        result = await svc.distribute_mcp(
            source_id,
            item_id,
            operator_id=x_user_id or "",
            operator_name=x_user_name or "",
            req=req,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return result


@router.delete(
    "/market/mcp/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_mcp(
    item_id: str,
    request: Request,
    x_source_id: Optional[str] = Header(default=None, alias="X-Source-Id"),
    x_manager: Optional[str] = Header(default=None, alias="X-Manager"),
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    x_user_name: Optional[str] = Header(default=None, alias="X-User-Name"),
):
    """删除市场 MCP（管理员）。"""
    source_id = require_source_id(x_source_id)
    _require_manager(x_manager)
    svc = request.app.state.marketplace

    # 先检查条目是否存在
    items = load_index(svc.marketplace_root, source_id)
    item = next((i for i in items if i.item_id == item_id and i.item_type == "mcp"), None)
    if item is None:
        raise HTTPException(status_code=404, detail="MCP not found or already deleted")

    ok = await svc.delete_mcp(
        source_id,
        item_id,
        operator_id=x_user_id or "",
        operator_name=x_user_name or "",
    )
    if not ok:
        raise HTTPException(status_code=404, detail="MCP not found")


@router.post("/market/mcp/{item_id}/test")
async def test_market_mcp(
    item_id: str,
    request: Request,
    x_source_id: Optional[str] = Header(default=None, alias="X-Source-Id"),
):
    """测试市场 MCP 连接。"""
    source_id = require_source_id(x_source_id)
    svc = request.app.state.marketplace

    # 获取 MCP 配置（使用原值）
    items = load_index(svc.marketplace_root, source_id)
    item = next((i for i in items if i.item_id == item_id and i.item_type == "mcp"), None)
    if item is None:
        raise HTTPException(status_code=404, detail="MCP not found or already deleted")

    mcp_config = load_mcp_config(svc.marketplace_root, source_id, item_id)
    if mcp_config is None:
        raise HTTPException(status_code=404, detail="MCP config not found")

    # 调用测试连接（需要导入 MCPClientConfig）
    from swe.config.config import MCPClientConfig
    from swe.app.mcp.stateful_client import StatefulStdioClient, HttpStatefulClient
    import asyncio

    config_data = mcp_config.get("config", {})
    client_config = MCPClientConfig(**config_data)

    try:
        if client_config.transport == "stdio":
            mcp_client = StatefulStdioClient(
                name="test",
                command=client_config.command,
                args=client_config.args,
                env=client_config.env,
                cwd=client_config.cwd or None,
            )
        else:
            mcp_client = HttpStatefulClient(
                name="test",
                transport=client_config.transport,
                url=client_config.url,
                headers=client_config.headers,
            )

        await mcp_client.connect()
        tools = await mcp_client.list_tools(timeout=30.0)
        await mcp_client.close()

        return {
            "success": True,
            "tools": [{"name": t.name, "description": t.description or ""} for t in tools],
        }
    except asyncio.TimeoutError:
        return {"success": False, "error": "连接超时"}
    except Exception as e:
        return {"success": False, "error": str(e)}
```

- [ ] **Step 2: 注册路由**

```python
# market/src/market/app/routers/__init__.py
# 添加导入和注册

from .mcp_market import router as mcp_market_router

api_router.include_router(mcp_market_router, tags=["marketplace-admin"])
```

- [ ] **Step 3: 提交**

```bash
git add market/src/market/app/routers/mcp_market.py market/src/market/app/routers/__init__.py
git commit -m "feat(market-routers): add MCP management routes (publish, upload, distribute, delete, test)"
```

---

## Task 7: 补充计划 A 的 publish 调用

**Files:**
- Modify: `src/swe/app/routers/my_mcp.py`

- [ ] **Step 1: 补充 publish 接口的 market 服务调用**

```python
# src/swe/app/routers/my_mcp.py
# 修改 publish_my_mcp_to_market 函数

import httpx


@router.post("/publish", response_model=PublishMCPResponse)
async def publish_my_mcp_to_market(
    request: Request,
    body: PublishMCPRequest = Body(...),
) -> PublishMCPResponse:
    """发布 MCP 到市场（管理员）。"""
    _require_manager(request)

    if not body.client_keys:
        raise HTTPException(400, detail="No client_keys provided")

    _, agent_config = await get_agent_and_config_for_request(request)

    if agent_config.mcp is None:
        raise HTTPException(400, detail="No MCP clients configured")

    source_id = _get_source_id(request)
    user_id = getattr(request.state, "user_id", "")
    user_name = getattr(request.state, "user_name", "")

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

        # 调用 market 服务发布
        try:
            market_url = "http://127.0.0.1:8090/api/market/mcp"
            publish_req = {
                "client_key": client_key,
                "name": client.name,
                "description": client.description,
                "creator_id": user_id,
                "creator_name": user_name,
                "category_id": body.category_id,
                "bbk_ids": body.bbk_ids,
                "config": client.model_dump(mode="json"),
            }

            async with httpx.AsyncClient() as http:
                resp = await http.post(
                    market_url,
                    json=publish_req,
                    headers={
                        "X-Source-Id": source_id,
                        "X-Manager": "true",
                        "X-User-Id": user_id,
                        "X-User-Name": user_name,
                    },
                    timeout=30.0,
                )

            if resp.status_code == 201:
                data = resp.json()
                results.append(PublishMCPResult(
                    client_key=client_key,
                    success=True,
                    item_id=data.get("item_id"),
                ))
            else:
                results.append(PublishMCPResult(
                    client_key=client_key,
                    success=False,
                    error=resp.text,
                ))
        except Exception as e:
            results.append(PublishMCPResult(
                client_key=client_key,
                success=False,
                error=str(e),
            ))

    return PublishMCPResponse(results=results)
```

- [ ] **Step 2: 提交**

```bash
git add src/swe/app/routers/my_mcp.py
git commit -m "feat(my-mcp): implement publish endpoint with market service integration"
```

---

## Task 8: 运行完整测试

- [ ] **Step 1: 运行 market 模块测试**

Run: `venv/bin/python -m pytest tests/unit/market/ -v`
Expected: 全部 PASS

- [ ] **Step 2: 运行整体后端测试**

Run: `venv/bin/python -m pytest tests/unit/ -v --tb=short`
Expected: 全部 PASS

---

## 完成检查

| 检查项 | 状态 |
|--------|------|
| MarketItem 扩展 client_key | ✓ |
| MCP Schema 模型 | ✓ |
| MCP FS 操作 | ✓ |
| MCP Service 方法 | ✓ |
| `/api/market/mcp` 浏览路由 | ✓ |
| `/api/market/mcp` 管理路由 | ✓ |
| MCP 统计查询 | ✓ |
| 单元测试 | ✓ |

---

## 后续依赖

- **计划 C** 将基于本计划 API 实现前端页面