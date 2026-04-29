# 应用市场后端基础设施计划（2a）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 market 服务中实现数据库连接层、文件系统工具和分类 API，为业务层（计划2b）提供基础设施。

**Architecture:** market 服务已有骨架（`market/src/market/`），复用主服务的 `DatabaseConnection` 模式（aiomysql 连接池），文件系统工具封装市场目录（`~/.swe.marketplace/`）和用户技能目录（`~/.swe/<user_id>/`）的读写操作。数据库配置已在 `market/src/market/config/constant.py` 中定义（`MARKET_DB_*` 环境变量）。

**Tech Stack:** Python 3.10+, FastAPI, aiomysql, pydantic, pytest-asyncio

---

## 文件结构

| 文件 | 操作 | 说明 |
|------|------|------|
| `market/pyproject.toml` | Modify | 新增 aiomysql、pydantic 依赖 |
| `market/src/market/database/__init__.py` | Create | 导出 DatabaseConnection |
| `market/src/market/database/connection.py` | Create | 复用主服务模式的异步连接池 |
| `market/src/market/app/_app.py` | Modify | lifespan 中初始化/关闭数据库连接 |
| `market/src/market/app/deps.py` | Create | FastAPI 依赖注入：get_db() |
| `market/src/market/marketplace/__init__.py` | Create | 空 |
| `market/src/market/marketplace/fs.py` | Create | 文件系统工具：市场目录读写、用户技能目录写入 |
| `market/src/market/marketplace/models.py` | Create | Pydantic 模型：MarketItem, CategoryItem |
| `market/src/market/app/routers/categories.py` | Create | GET /api/marketplace/categories |
| `market/src/market/app/routers/__init__.py` | Modify | 注册 categories router |
| `tests/unit/marketplace/test_fs.py` | Create | 文件系统工具单元测试 |
| `tests/unit/marketplace/test_categories.py` | Create | 分类 API 单元测试 |

---

### Task 1: 新增依赖并实现数据库连接层

**Files:**
- Modify: `market/pyproject.toml`
- Create: `market/src/market/database/__init__.py`
- Create: `market/src/market/database/connection.py`
- Modify: `market/src/market/app/_app.py`
- Create: `market/src/market/app/deps.py`

- [ ] **Step 1: 写失败测试**

创建 `market/tests/unit/test_database.py`：

```python
# -*- coding: utf-8 -*-
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_database_connection_is_connected_false_before_connect():
    from market.database.connection import DatabaseConnection
    from market.database.connection import DatabaseConfig
    config = DatabaseConfig(host="localhost", port=3306, user="root",
                            password="", database="test")
    db = DatabaseConnection(config)
    assert db.is_connected is False


@pytest.mark.asyncio
async def test_get_db_dependency_returns_connection():
    from market.app.deps import get_db
    # get_db should be a callable that returns a DatabaseConnection
    assert callable(get_db)
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd "D:\Vibe Coding\CoPaw1.0.0\CoPaw\market"
python -m pytest tests/unit/test_database.py -v
```

预期：ImportError（模块不存在）

- [ ] **Step 3: 新增依赖到 pyproject.toml**

修改 `market/pyproject.toml`，在 dependencies 中新增：

```toml
dependencies = [
    "fastapi>=0.100.0",
    "uvicorn>=0.23.0",
    "click>=8.0.0",
    "pyyaml>=6.0",
    "aiomysql>=0.2.0",
    "pydantic>=2.0.0",
]
```

- [ ] **Step 4: 创建数据库连接模块**

创建 `market/src/market/database/__init__.py`：

```python
# -*- coding: utf-8 -*-
from .connection import DatabaseConfig, DatabaseConnection

__all__ = ["DatabaseConfig", "DatabaseConnection"]
```

创建 `market/src/market/database/connection.py`（完整内容）：

```python
# -*- coding: utf-8 -*-
"""异步 MySQL 连接池，复用主服务模式."""
import logging
from contextlib import asynccontextmanager
from typing import Any, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

try:
    import aiomysql
    AIOMYSQL_AVAILABLE = True
except ImportError:
    AIOMYSQL_AVAILABLE = False
    logger.debug("aiomysql not installed, database features will be unavailable")


class DatabaseConfig(BaseModel):
    host: str = Field(default="localhost")
    port: int = Field(default=3306)
    user: str = Field(default="root")
    password: str = Field(default="")
    database: str = Field(default="swe")
    min_connections: int = Field(default=2)
    max_connections: int = Field(default=10)
    charset: str = Field(default="utf8mb4")


class DatabaseConnection:
    def __init__(self, config: DatabaseConfig):
        self.config = config
        self._pool: Optional[Any] = None
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected and self._pool is not None

    async def connect(self) -> None:
        if not AIOMYSQL_AVAILABLE:
            raise RuntimeError("aiomysql is not installed")
        if self._pool is not None:
            return
        try:
            self._pool = await aiomysql.create_pool(
                host=self.config.host,
                port=self.config.port,
                user=self.config.user,
                password=self.config.password,
                db=self.config.database,
                charset=self.config.charset,
                minsize=self.config.min_connections,
                maxsize=self.config.max_connections,
                autocommit=True,
            )
            self._connected = True
            logger.info("DB pool created: %s:%s/%s",
                        self.config.host, self.config.port, self.config.database)
        except Exception as e:
            logger.error("Failed to create DB pool: %s", e)
            self._connected = False
            raise

    async def close(self) -> None:
        if self._pool is not None:
            self._pool.close()
            await self._pool.wait_closed()
            self._pool = None
            self._connected = False

    @asynccontextmanager
    async def acquire(self):
        if self._pool is None:
            raise RuntimeError("Database not connected")
        async with self._pool.acquire() as conn:
            yield conn

    async def execute(self, query: str, params: Optional[tuple] = None) -> int:
        async with self.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, params)
                return cur.rowcount

    async def execute_many(self, query: str, params_list: list[tuple]) -> int:
        if not params_list:
            return 0
        async with self.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.executemany(query, params_list)
                return cur.rowcount

    async def fetch_one(self, query: str, params: Optional[tuple] = None) -> Optional[dict]:
        async with self.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(query, params)
                row = await cur.fetchone()
                return dict(row) if row else None

    async def fetch_all(self, query: str, params: Optional[tuple] = None) -> list[dict]:
        async with self.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(query, params)
                rows = await cur.fetchall()
                return [dict(row) for row in rows] if rows else []
```

- [ ] **Step 5: 创建依赖注入模块**

创建 `market/src/market/app/deps.py`：

```python
# -*- coding: utf-8 -*-
"""FastAPI 依赖注入."""
from typing import Annotated
from fastapi import Depends, Request
from ..database.connection import DatabaseConnection


def get_db(request: Request) -> DatabaseConnection:
    """从 app.state 获取数据库连接."""
    return request.app.state.db


DbDep = Annotated[DatabaseConnection, Depends(get_db)]
```

- [ ] **Step 6: 修改 _app.py，在 lifespan 中初始化数据库**

修改 `market/src/market/app/_app.py`：

```python
# -*- coding: utf-8 -*-
from contextlib import asynccontextmanager
import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ..__version__ import __version__
from ..config.constant import (
    DOCS_ENABLED, CORS_ORIGINS,
    DB_HOST, DB_PORT, DB_USER, DB_ACCESS, DB_NAME, DB_MIN_CONN, DB_MAX_CONN,
)
from ..database.connection import DatabaseConfig, DatabaseConnection
from .routers import api_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(fastapi_app: FastAPI):
    logger.info("Market service starting up...")
    logger.info(f"Environment: {os.environ.get('MARKET_ENV', 'prd')}")

    # 初始化数据库连接
    db_config = DatabaseConfig(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_ACCESS,
        database=DB_NAME,
        min_connections=DB_MIN_CONN,
        max_connections=DB_MAX_CONN,
    )
    db = DatabaseConnection(db_config)
    if DB_HOST:
        try:
            await db.connect()
        except Exception as e:
            logger.warning("DB connection failed (non-fatal): %s", e)
    fastapi_app.state.db = db

    yield

    await db.close()
    logger.info("Market service shutting down...")


app = FastAPI(
    title="Market",
    description="应用市场服务",
    version=__version__,
    lifespan=lifespan,
    docs_url="/docs" if DOCS_ENABLED else None,
    redoc_url="/redoc" if DOCS_ENABLED else None,
    openapi_url="/openapi.json" if DOCS_ENABLED else None,
)

if CORS_ORIGINS:
    origins = [o.strip() for o in CORS_ORIGINS.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(api_router, prefix="/api")
```

- [ ] **Step 7: 运行测试确认通过**

```bash
cd "D:\Vibe Coding\CoPaw1.0.0\CoPaw\market"
python -m pytest tests/unit/test_database.py -v
```

预期：2 passed

- [ ] **Step 8: Commit**

```bash
git add market/pyproject.toml market/src/market/database/ market/src/market/app/_app.py market/src/market/app/deps.py market/tests/unit/test_database.py
git commit -m "feat(marketplace): add database connection layer to market service"
```

---

### Task 2: 实现文件系统工具和数据模型

**Files:**
- Create: `market/src/market/marketplace/__init__.py`
- Create: `market/src/market/marketplace/models.py`
- Create: `market/src/market/marketplace/fs.py`
- Create: `market/tests/unit/marketplace/__init__.py`
- Create: `market/tests/unit/marketplace/test_fs.py`

- [ ] **Step 1: 写失败测试**

创建 `market/tests/unit/marketplace/__init__.py`（空文件）

创建 `market/tests/unit/marketplace/test_fs.py`：

```python
# -*- coding: utf-8 -*-
import json
import pytest
from pathlib import Path


def test_get_marketplace_dir(tmp_path):
    from market.marketplace.fs import get_marketplace_dir
    result = get_marketplace_dir(tmp_path, "source_a")
    assert result == tmp_path / "source_a"


def test_get_index_path(tmp_path):
    from market.marketplace.fs import get_index_path
    result = get_index_path(tmp_path, "source_a")
    assert result == tmp_path / "source_a" / "index.json"


def test_load_index_returns_empty_when_not_exists(tmp_path):
    from market.marketplace.fs import load_index
    result = load_index(tmp_path, "source_a")
    assert result == []


def test_save_and_load_index(tmp_path):
    from market.marketplace.fs import save_index, load_index
    from market.marketplace.models import MarketItem
    item = MarketItem(
        item_id="uuid-1",
        item_type="skill",
        name="test_skill",
        description="desc",
        version="1.0.0",
        creator_id="user1",
        creator_name="User One",
        category_id=None,
        bbk_ids=[],
        status="active",
    )
    save_index(tmp_path, "source_a", [item])
    loaded = load_index(tmp_path, "source_a")
    assert len(loaded) == 1
    assert loaded[0].name == "test_skill"


def test_get_skill_dir_in_marketplace(tmp_path):
    from market.marketplace.fs import get_skill_dir
    result = get_skill_dir(tmp_path, "source_a", "item-123")
    assert result == tmp_path / "source_a" / "skills" / "item-123"


def test_get_user_skills_dir(tmp_path):
    from market.marketplace.fs import get_user_skills_dir
    result = get_user_skills_dir(tmp_path, "user1", "agent1")
    assert result == tmp_path / "user1" / "workspaces" / "agent1" / "skills"
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd "D:\Vibe Coding\CoPaw1.0.0\CoPaw\market"
python -m pytest tests/unit/marketplace/test_fs.py -v
```

预期：ImportError

- [ ] **Step 3: 创建数据模型**

创建 `market/src/market/marketplace/__init__.py`（空文件）

创建 `market/src/market/marketplace/models.py`：

```python
# -*- coding: utf-8 -*-
"""应用市场数据模型."""
from __future__ import annotations
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class MarketItem(BaseModel):
    """市场条目（index.json 中的单条记录）."""
    item_id: str
    item_type: str = "skill"
    name: str
    description: str = ""
    version: str = "1.0.0"
    creator_id: str
    creator_name: str = ""
    category_id: Optional[int] = None
    bbk_ids: list[str] = Field(default_factory=list)
    status: str = "active"
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class CategoryItem(BaseModel):
    """分类条目."""
    id: int
    source_id: str
    name: str
    sort_order: int = 0
    created_at: Optional[datetime] = None


class SkillManifest(BaseModel):
    """用户本地技能 skill.json 扩展字段."""
    source: str = "customized"
    distributed_by: Optional[str] = None
    received_version: Optional[str] = None
```

- [ ] **Step 4: 创建文件系统工具**

创建 `market/src/market/marketplace/fs.py`：

```python
# -*- coding: utf-8 -*-
"""市场文件系统工具.

市场目录结构：
  <marketplace_root>/<source_id>/index.json
  <marketplace_root>/<source_id>/skills/<item_id>/skill.json
  <marketplace_root>/<source_id>/skills/<item_id>/SKILL.md

用户技能目录：
  <swe_root>/<user_id>/workspaces/<agent_id>/skills/<skill_name>/
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Optional

from .models import MarketItem

logger = logging.getLogger(__name__)

DEFAULT_AGENT_ID = "default"


def get_marketplace_dir(marketplace_root: Path, source_id: str) -> Path:
    return marketplace_root / source_id


def get_index_path(marketplace_root: Path, source_id: str) -> Path:
    return get_marketplace_dir(marketplace_root, source_id) / "index.json"


def get_skill_dir(marketplace_root: Path, source_id: str, item_id: str) -> Path:
    return get_marketplace_dir(marketplace_root, source_id) / "skills" / item_id


def get_user_skills_dir(
    swe_root: Path,
    user_id: str,
    agent_id: str = DEFAULT_AGENT_ID,
) -> Path:
    return swe_root / user_id / "workspaces" / agent_id / "skills"


def load_index(marketplace_root: Path, source_id: str) -> list[MarketItem]:
    """读取市场索引，不存在时返回空列表."""
    path = get_index_path(marketplace_root, source_id)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return [MarketItem(**item) for item in data.get("items", [])]
    except Exception as e:
        logger.error("Failed to load index %s: %s", path, e)
        return []


def save_index(
    marketplace_root: Path,
    source_id: str,
    items: list[MarketItem],
) -> None:
    """原子写入市场索引."""
    path = get_index_path(marketplace_root, source_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {"items": [item.model_dump() for item in items]}
    _atomic_write_json(path, data)


def _atomic_write_json(path: Path, data: dict) -> None:
    """原子写入 JSON 文件，防止并发损坏."""
    dir_ = path.parent
    dir_.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=dir_, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def copy_skill_to_user(
    marketplace_root: Path,
    source_id: str,
    item_id: str,
    swe_root: Path,
    user_id: str,
    skill_name: str,
    distributed_by: str,
    version: str,
    agent_id: str = DEFAULT_AGENT_ID,
) -> None:
    """将市场技能复制到用户工作目录，并写入分发元数据."""
    src_dir = get_skill_dir(marketplace_root, source_id, item_id)
    dst_dir = get_user_skills_dir(swe_root, user_id, agent_id) / skill_name
    dst_dir.mkdir(parents=True, exist_ok=True)

    # 复制 SKILL.md
    src_skill_md = src_dir / "SKILL.md"
    if src_skill_md.exists():
        (dst_dir / "SKILL.md").write_bytes(src_skill_md.read_bytes())

    # 读取原始 skill.json，合并分发元数据后写入
    src_skill_json = src_dir / "skill.json"
    skill_data: dict = {}
    if src_skill_json.exists():
        try:
            skill_data = json.loads(src_skill_json.read_text(encoding="utf-8"))
        except Exception:
            pass

    skill_data["source"] = f"marketplace:{item_id}"
    skill_data["distributed_by"] = distributed_by
    skill_data["received_version"] = version

    _atomic_write_json(dst_dir / "skill.json", skill_data)
```

- [ ] **Step 5: 运行测试确认通过**

```bash
cd "D:\Vibe Coding\CoPaw1.0.0\CoPaw\market"
python -m pytest tests/unit/marketplace/test_fs.py -v
```

预期：6 passed

- [ ] **Step 6: Commit**

```bash
git add market/src/market/marketplace/ market/tests/unit/marketplace/
git commit -m "feat(marketplace): add filesystem utilities and data models"
```

---

### Task 3: 实现分类 API

**Files:**
- Create: `market/src/market/app/routers/categories.py`
- Modify: `market/src/market/app/routers/__init__.py`
- Create: `market/tests/unit/marketplace/test_categories.py`

- [ ] **Step 1: 写失败测试**

创建 `market/tests/unit/marketplace/test_categories.py`：

```python
# -*- coding: utf-8 -*-
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient


def _make_app(mock_db):
    from fastapi import FastAPI
    from market.app.routers.categories import router
    from market.app.deps import get_db
    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.dependency_overrides[get_db] = lambda: mock_db
    return app


def test_get_categories_returns_list():
    mock_db = AsyncMock()
    mock_db.is_connected = True
    mock_db.fetch_all = AsyncMock(return_value=[
        {"id": 1, "source_id": "src_a", "name": "数据分析", "sort_order": 0, "created_at": None},
        {"id": 2, "source_id": "src_a", "name": "报表", "sort_order": 1, "created_at": None},
    ])
    app = _make_app(mock_db)
    client = TestClient(app)
    response = client.get("/api/marketplace/categories", headers={"X-Source-Id": "src_a"})
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["name"] == "数据分析"


def test_get_categories_missing_source_id_returns_400():
    mock_db = AsyncMock()
    mock_db.is_connected = True
    app = _make_app(mock_db)
    client = TestClient(app)
    response = client.get("/api/marketplace/categories")
    assert response.status_code == 400


def test_get_categories_db_not_connected_returns_503():
    mock_db = MagicMock()
    mock_db.is_connected = False
    app = _make_app(mock_db)
    client = TestClient(app)
    response = client.get("/api/marketplace/categories", headers={"X-Source-Id": "src_a"})
    assert response.status_code == 503
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd "D:\Vibe Coding\CoPaw1.0.0\CoPaw\market"
python -m pytest tests/unit/marketplace/test_categories.py -v
```

预期：ImportError

- [ ] **Step 3: 实现分类路由**

创建 `market/src/market/app/routers/categories.py`：

```python
# -*- coding: utf-8 -*-
"""分类 API."""
from fastapi import APIRouter, Header, HTTPException
from typing import Optional
from ...app.deps import DbDep
from ...marketplace.models import CategoryItem

router = APIRouter()


@router.get("/marketplace/categories", response_model=list[CategoryItem])
async def get_categories(
    db: DbDep,
    x_source_id: Optional[str] = Header(default=None, alias="X-Source-Id"),
):
    """获取当前 source-id 下的分类列表，按 sort_order 升序."""
    if not x_source_id:
        raise HTTPException(status_code=400, detail="X-Source-Id header is required")
    if not db.is_connected:
        raise HTTPException(status_code=503, detail="Database unavailable")

    rows = await db.fetch_all(
        "SELECT id, source_id, name, sort_order, created_at "
        "FROM swe_marketplace_categories "
        "WHERE source_id = %s ORDER BY sort_order ASC",
        (x_source_id,),
    )
    return [CategoryItem(**row) for row in rows]
```

- [ ] **Step 4: 注册路由**

修改 `market/src/market/app/routers/__init__.py`：

```python
# -*- coding: utf-8 -*-
from fastapi import APIRouter

from .health import router as health_router
from .categories import router as categories_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(categories_router, tags=["marketplace"])
```

- [ ] **Step 5: 运行测试确认通过**

```bash
cd "D:\Vibe Coding\CoPaw1.0.0\CoPaw\market"
python -m pytest tests/unit/marketplace/ -v
```

预期：9 passed（6 fs + 3 categories）

- [ ] **Step 6: Commit**

```bash
git add market/src/market/app/routers/categories.py market/src/market/app/routers/__init__.py market/tests/unit/marketplace/test_categories.py
git commit -m "feat(marketplace): add categories API endpoint"
```

---

## 自检

**Spec 覆盖：**
- [x] 数据库连接层（aiomysql 连接池，lifespan 初始化）— Task 1
- [x] FastAPI 依赖注入 get_db() — Task 1
- [x] 文件系统工具（市场目录读写、用户技能目录写入、原子写入）— Task 2
- [x] Pydantic 模型（MarketItem, CategoryItem, SkillManifest）— Task 2
- [x] `GET /api/marketplace/categories`（X-Source-Id 过滤，sort_order 排序）— Task 3

**占位符扫描：** 无 TBD/TODO，所有代码完整。

**类型一致性：**
- `MarketItem` 在 Task 2 定义，Task 3 的 `fs.py` 使用，一致
- `CategoryItem` 在 Task 2 定义，Task 3 的路由 response_model 使用，一致
- `DbDep` 在 Task 1 的 `deps.py` 定义，Task 3 的路由使用，一致
