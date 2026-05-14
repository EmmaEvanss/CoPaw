# 应用市场业务层计划（2b）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 market 服务中实现 MarketplaceService 和完整的市场 API（上架/下架/列表/详情/分发）以及我的技能 API（我创建的/我接收的），并写入操作日志。

**Architecture:** MarketplaceService 封装所有业务逻辑（文件系统读写 + 数据库日志），路由层只做参数校验和权限检查。分发时按 target_type 展开用户列表（查 swe_tenant_init_source），逐用户调用 copy_skill_to_user 并写一条 swe_marketplace_operation_logs 记录。统计数据（调用次数/用户量）从 swe_tracing_spans 实时查询。

**Tech Stack:** Python 3.10+, FastAPI, aiomysql, pydantic v2, pytest-asyncio

---

## 文件结构

| 文件 | 操作 | 说明 |
|------|------|------|
| `market/src/market/marketplace/service.py` | Create | MarketplaceService：上架/下架/列表/详情/分发/我的技能 |
| `market/src/market/marketplace/schemas.py` | Create | API 请求/响应 Pydantic 模型 |
| `market/src/market/app/routers/skills_market.py` | Create | 管理员 API：POST/DELETE/distribute |
| `market/src/market/app/routers/skills_browse.py` | Create | 用户 API：GET list/detail/mine/received |
| `market/src/market/app/routers/__init__.py` | Modify | 注册两个新 router |
| `market/tests/unit/marketplace/test_service.py` | Create | MarketplaceService 单元测试 |
| `market/tests/unit/marketplace/test_skills_market.py` | Create | 管理员 API 单元测试 |
| `market/tests/unit/marketplace/test_skills_browse.py` | Create | 用户 API 单元测试 |

---

### Task 1: 实现 API 请求/响应模型

**Files:**
- Create: `market/src/market/marketplace/schemas.py`
- Create: `market/tests/unit/marketplace/test_schemas.py`

- [ ] **Step 1: 写失败测试**

创建 `market/tests/unit/marketplace/test_schemas.py`：

```python
# -*- coding: utf-8 -*-
def test_publish_request_defaults():
    from market.marketplace.schemas import PublishSkillRequest
    req = PublishSkillRequest(
        name="my_skill",
        description="desc",
        creator_id="user1",
        creator_name="User One",
        skill_json={"name": "my_skill"},
        skill_md="# My Skill",
    )
    assert req.category_id is None
    assert req.bbk_ids == []


def test_distribute_request_all():
    from market.marketplace.schemas import DistributeRequest
    req = DistributeRequest(target_type="all", target_values=[])
    assert req.target_type == "all"


def test_distribute_request_rejects_invalid_type():
    from market.marketplace.schemas import DistributeRequest
    import pytest
    with pytest.raises(Exception):
        DistributeRequest(target_type="invalid", target_values=[])


def test_market_skill_response_fields():
    from market.marketplace.schemas import MarketSkillResponse
    r = MarketSkillResponse(
        item_id="id1",
        name="skill",
        description="",
        version="1.0.0",
        creator_id="u1",
        creator_name="U",
        category_id=None,
        bbk_ids=[],
        status="active",
        created_at=None,
        updated_at=None,
        call_count=0,
        user_count=0,
    )
    assert r.item_id == "id1"
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd "D:\Vibe Coding\CoPaw1.0.0\CoPaw\market"
PYTHONPATH=src python -m pytest tests/unit/marketplace/test_schemas.py -v
```

预期：ImportError

- [ ] **Step 3: 创建 schemas.py**

创建 `market/src/market/marketplace/schemas.py`：

```python
# -*- coding: utf-8 -*-
"""API 请求/响应模型."""
from __future__ import annotations

from typing import Literal, Optional
from pydantic import BaseModel, Field


class PublishSkillRequest(BaseModel):
    """上架技能请求体."""
    name: str
    description: str = ""
    creator_id: str
    creator_name: str = ""
    category_id: Optional[int] = None
    bbk_ids: list[str] = Field(default_factory=list)
    skill_json: dict = Field(default_factory=dict)
    skill_md: str = ""


class DistributeRequest(BaseModel):
    """分发技能请求体."""
    target_type: Literal["all", "bbk_id", "user_id"]
    target_values: list[str] = Field(default_factory=list)


class MarketSkillResponse(BaseModel):
    """市场技能列表/详情响应."""
    item_id: str
    name: str
    description: str
    version: str
    creator_id: str
    creator_name: str
    category_id: Optional[int]
    bbk_ids: list[str]
    status: str
    created_at: Optional[str]
    updated_at: Optional[str]
    call_count: int = 0
    user_count: int = 0


class SkillUserStat(BaseModel):
    """技能详情页调用客户明细."""
    user_id: str
    user_name: str
    call_count: int


class MarketSkillDetail(MarketSkillResponse):
    """技能详情（含调用客户明细）."""
    user_stats: list[SkillUserStat] = Field(default_factory=list)


class MySkillItem(BaseModel):
    """我的技能列表条目."""
    skill_name: str
    source: str
    description: str = ""
    version: Optional[str] = None
    received_version: Optional[str] = None
    distributed_by: Optional[str] = None
    is_received: bool = False
    has_update: bool = False


class DistributeResponse(BaseModel):
    """分发结果."""
    distributed_count: int
    item_id: str
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd "D:\Vibe Coding\CoPaw1.0.0\CoPaw\market"
PYTHONPATH=src python -m pytest tests/unit/marketplace/test_schemas.py -v
```

预期：4 passed

- [ ] **Step 5: Commit**

```bash
git add market/src/market/marketplace/schemas.py market/tests/unit/marketplace/test_schemas.py
git commit -m "feat(marketplace): add API request/response schemas"
```

---

### Task 2: 实现 MarketplaceService

**Files:**
- Create: `market/src/market/marketplace/service.py`
- Create: `market/tests/unit/marketplace/test_service.py`

MarketplaceService 依赖 `DatabaseConnection`（用于日志写入和用户列表查询）和文件系统路径（marketplace_root、swe_root）。所有方法均为 async。

- [ ] **Step 1: 写失败测试**

创建 `market/tests/unit/marketplace/test_service.py`：

```python
# -*- coding: utf-8 -*-
import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock


def _make_service(tmp_path, mock_db=None):
    from market.marketplace.service import MarketplaceService
    if mock_db is None:
        mock_db = AsyncMock()
        mock_db.is_connected = True
    return MarketplaceService(
        db=mock_db,
        marketplace_root=tmp_path / "market",
        swe_root=tmp_path / "swe",
    )


@pytest.mark.asyncio
async def test_publish_skill_creates_index_entry(tmp_path):
    from market.marketplace.schemas import PublishSkillRequest
    svc = _make_service(tmp_path)
    req = PublishSkillRequest(
        name="skill_a",
        description="desc",
        creator_id="user1",
        creator_name="User One",
        skill_json={"name": "skill_a"},
        skill_md="# Skill A",
    )
    item = await svc.publish_skill("src_a", req)
    assert item.name == "skill_a"
    assert item.version == "1.0.0"
    assert item.status == "active"
    # index.json should exist
    index_path = tmp_path / "market" / "src_a" / "index.json"
    assert index_path.exists()
    data = json.loads(index_path.read_text())
    assert len(data["items"]) == 1


@pytest.mark.asyncio
async def test_publish_skill_increments_version_on_republish(tmp_path):
    from market.marketplace.schemas import PublishSkillRequest
    svc = _make_service(tmp_path)
    req = PublishSkillRequest(
        name="skill_a", description="", creator_id="u1", creator_name="",
        skill_json={}, skill_md="",
    )
    await svc.publish_skill("src_a", req)
    item2 = await svc.publish_skill("src_a", req)
    assert item2.version == "1.0.1"


@pytest.mark.asyncio
async def test_unpublish_skill_sets_inactive(tmp_path):
    from market.marketplace.schemas import PublishSkillRequest
    svc = _make_service(tmp_path)
    req = PublishSkillRequest(
        name="skill_b", description="", creator_id="u1", creator_name="",
        skill_json={}, skill_md="",
    )
    item = await svc.publish_skill("src_a", req)
    await svc.unpublish_skill("src_a", item.item_id, "u1", "User One")
    items = await svc.list_skills("src_a", user_bbk_id="100")
    assert all(i.status == "inactive" for i in items if i.item_id == item.item_id)


@pytest.mark.asyncio
async def test_list_skills_filters_by_bbk_id(tmp_path):
    from market.marketplace.schemas import PublishSkillRequest
    svc = _make_service(tmp_path)
    # skill visible to all (bbk_ids=[])
    req_all = PublishSkillRequest(
        name="skill_all", description="", creator_id="u1", creator_name="",
        skill_json={}, skill_md="", bbk_ids=[],
    )
    # skill visible only to bbk_id=200
    req_200 = PublishSkillRequest(
        name="skill_200", description="", creator_id="u1", creator_name="",
        skill_json={}, skill_md="", bbk_ids=["200"],
    )
    await svc.publish_skill("src_a", req_all)
    await svc.publish_skill("src_a", req_200)
    # bbk_id=100 (总行) sees all
    items_100 = await svc.list_skills("src_a", user_bbk_id="100")
    assert len(items_100) == 2
    # bbk_id=300 sees only skill_all (bbk_ids=[])
    items_300 = await svc.list_skills("src_a", user_bbk_id="300")
    assert len(items_300) == 1
    assert items_300[0].name == "skill_all"


@pytest.mark.asyncio
async def test_get_skill_detail_returns_item(tmp_path):
    from market.marketplace.schemas import PublishSkillRequest
    svc = _make_service(tmp_path)
    req = PublishSkillRequest(
        name="skill_c", description="", creator_id="u1", creator_name="",
        skill_json={}, skill_md="",
    )
    item = await svc.publish_skill("src_a", req)
    detail = await svc.get_skill_detail("src_a", item.item_id, user_bbk_id="100")
    assert detail is not None
    assert detail.item_id == item.item_id


@pytest.mark.asyncio
async def test_get_skill_detail_returns_none_for_unknown(tmp_path):
    svc = _make_service(tmp_path)
    detail = await svc.get_skill_detail("src_a", "nonexistent-id", user_bbk_id="100")
    assert detail is None
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd "D:\Vibe Coding\CoPaw1.0.0\CoPaw\market"
PYTHONPATH=src python -m pytest tests/unit/marketplace/test_service.py -v
```

预期：ImportError

- [ ] **Step 3: 创建 service.py**

创建 `market/src/market/marketplace/service.py`：

```python
# -*- coding: utf-8 -*-
"""应用市场业务服务."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from ..database.connection import DatabaseConnection
from .fs import (
    copy_skill_to_user,
    get_skill_dir,
    load_index,
    save_index,
)
from .models import MarketItem
from .schemas import (
    DistributeRequest,
    DistributeResponse,
    MarketSkillDetail,
    MarketSkillResponse,
    MySkillItem,
    PublishSkillRequest,
    SkillUserStat,
)

logger = logging.getLogger(__name__)

_TRACING_STATS_SQL = """
    SELECT
        COUNT(*) AS call_count,
        COUNT(DISTINCT user_id) AS user_count
    FROM swe_tracing_spans
    WHERE event_type = 'skill_invocation'
      AND skill_name = %s
      AND source_id = %s
"""

_TRACING_USER_STATS_SQL = """
    SELECT
        user_id,
        MAX(COALESCE(metadata->>'$.user_name', '')) AS user_name,
        COUNT(*) AS call_count
    FROM swe_tracing_spans
    WHERE event_type = 'skill_invocation'
      AND skill_name = %s
      AND source_id = %s
    GROUP BY user_id
    ORDER BY call_count DESC
    LIMIT 100
"""

_LOG_MARKET_OP_SQL = """
    INSERT INTO swe_marketplace_operation_logs
        (source_id, operator_id, operator_name, operation,
         item_type, item_id, item_name,
         target_user_id, target_user_name, target_bbk_id)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
"""

_QUERY_USERS_BY_SOURCE_SQL = """
    SELECT tenant_id, tenant_name, bbk_id
    FROM swe_tenant_init_source
    WHERE source_id = %s
"""

_QUERY_USERS_BY_BBK_SQL = """
    SELECT tenant_id, tenant_name, bbk_id
    FROM swe_tenant_init_source
    WHERE source_id = %s AND bbk_id IN ({placeholders})
"""


def _bump_patch(version: str) -> str:
    """Increment patch version: '1.0.0' -> '1.0.1'."""
    parts = version.split(".")
    if len(parts) == 3:
        try:
            parts[2] = str(int(parts[2]) + 1)
            return ".".join(parts)
        except ValueError:
            pass
    return version + ".1"


def _item_visible(item: MarketItem, user_bbk_id: str) -> bool:
    """Return True if item is visible to user with given bbk_id."""
    if item.status != "active":
        return False
    if user_bbk_id == "100":
        return True
    if not item.bbk_ids:
        return True
    return "100" in item.bbk_ids or user_bbk_id in item.bbk_ids


class MarketplaceService:
    def __init__(
        self,
        db: DatabaseConnection,
        marketplace_root: Path,
        swe_root: Path,
    ) -> None:
        self.db = db
        self.marketplace_root = marketplace_root
        self.swe_root = swe_root

    async def publish_skill(
        self, source_id: str, req: PublishSkillRequest
    ) -> MarketItem:
        """上架技能。同名技能已存在时递增 patch 版本号。"""
        items = load_index(self.marketplace_root, source_id)
        existing = next((i for i in items if i.name == req.name), None)

        now = datetime.now(timezone.utc).isoformat()
        if existing is not None:
            version = _bump_patch(existing.version)
            existing.version = version
            existing.description = req.description
            existing.creator_id = req.creator_id
            existing.creator_name = req.creator_name
            existing.category_id = req.category_id
            existing.bbk_ids = req.bbk_ids
            existing.status = "active"
            existing.updated_at = now
            item = existing
        else:
            item = MarketItem(
                item_id=str(uuid.uuid4()),
                item_type="skill",
                name=req.name,
                description=req.description,
                version="1.0.0",
                creator_id=req.creator_id,
                creator_name=req.creator_name,
                category_id=req.category_id,
                bbk_ids=req.bbk_ids,
                status="active",
                created_at=now,
                updated_at=now,
            )
            items.append(item)

        # Write skill files
        skill_dir = get_skill_dir(self.marketplace_root, source_id, item.item_id)
        skill_dir.mkdir(parents=True, exist_ok=True)
        import json
        (skill_dir / "skill.json").write_text(
            json.dumps(req.skill_json, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        if req.skill_md:
            (skill_dir / "SKILL.md").write_text(req.skill_md, encoding="utf-8")

        save_index(self.marketplace_root, source_id, items)

        if self.db.is_connected:
            try:
                await self.db.execute(
                    _LOG_MARKET_OP_SQL,
                    (source_id, req.creator_id, req.creator_name, "publish",
                     "skill", item.item_id, item.name,
                     None, None, None),
                )
            except Exception as e:
                logger.warning("Failed to log publish operation: %s", e)

        return item

    async def unpublish_skill(
        self,
        source_id: str,
        item_id: str,
        operator_id: str,
        operator_name: str,
    ) -> bool:
        """下架技能（设为 inactive）。返回 True 表示成功。"""
        items = load_index(self.marketplace_root, source_id)
        item = next((i for i in items if i.item_id == item_id), None)
        if item is None:
            return False
        item.status = "inactive"
        item.updated_at = datetime.now(timezone.utc).isoformat()
        save_index(self.marketplace_root, source_id, items)

        if self.db.is_connected:
            try:
                await self.db.execute(
                    _LOG_MARKET_OP_SQL,
                    (source_id, operator_id, operator_name, "unpublish",
                     "skill", item_id, item.name,
                     None, None, None),
                )
            except Exception as e:
                logger.warning("Failed to log unpublish operation: %s", e)

        return True

    async def list_skills(
        self,
        source_id: str,
        user_bbk_id: str,
        category_id: Optional[int] = None,
    ) -> list[MarketSkillResponse]:
        """列出市场技能，按 bbk_id 过滤，可选按分类过滤。"""
        items = load_index(self.marketplace_root, source_id)
        visible = [i for i in items if _item_visible(i, user_bbk_id)]
        if category_id is not None:
            visible = [i for i in visible if i.category_id == category_id]

        result = []
        for item in visible:
            call_count, user_count = await self._get_stats(item.name, source_id)
            result.append(MarketSkillResponse(
                item_id=item.item_id,
                name=item.name,
                description=item.description,
                version=item.version,
                creator_id=item.creator_id,
                creator_name=item.creator_name,
                category_id=item.category_id,
                bbk_ids=item.bbk_ids,
                status=item.status,
                created_at=item.created_at,
                updated_at=item.updated_at,
                call_count=call_count,
                user_count=user_count,
            ))
        return result

    async def get_skill_detail(
        self,
        source_id: str,
        item_id: str,
        user_bbk_id: str,
    ) -> Optional[MarketSkillDetail]:
        """获取技能详情（含调用客户明细）。"""
        items = load_index(self.marketplace_root, source_id)
        item = next((i for i in items if i.item_id == item_id), None)
        if item is None or not _item_visible(item, user_bbk_id):
            return None

        call_count, user_count = await self._get_stats(item.name, source_id)
        user_stats = await self._get_user_stats(item.name, source_id)

        return MarketSkillDetail(
            item_id=item.item_id,
            name=item.name,
            description=item.description,
            version=item.version,
            creator_id=item.creator_id,
            creator_name=item.creator_name,
            category_id=item.category_id,
            bbk_ids=item.bbk_ids,
            status=item.status,
            created_at=item.created_at,
            updated_at=item.updated_at,
            call_count=call_count,
            user_count=user_count,
            user_stats=user_stats,
        )

    async def distribute_skill(
        self,
        source_id: str,
        item_id: str,
        operator_id: str,
        operator_name: str,
        req: DistributeRequest,
    ) -> DistributeResponse:
        """分发技能到目标用户工作目录，并写操作日志。"""
        items = load_index(self.marketplace_root, source_id)
        item = next((i for i in items if i.item_id == item_id), None)
        if item is None:
            raise ValueError(f"Item {item_id} not found in source {source_id}")

        target_users = await self._resolve_target_users(source_id, req)
        count = 0
        for user in target_users:
            try:
                copy_skill_to_user(
                    marketplace_root=self.marketplace_root,
                    source_id=source_id,
                    item_id=item_id,
                    swe_root=self.swe_root,
                    user_id=user["tenant_id"],
                    skill_name=item.name,
                    distributed_by=operator_id,
                    version=item.version,
                )
                count += 1
            except Exception as e:
                logger.warning(
                    "Failed to copy skill to user %s: %s",
                    user["tenant_id"], e,
                )
                continue

            if self.db.is_connected:
                try:
                    await self.db.execute(
                        _LOG_MARKET_OP_SQL,
                        (source_id, operator_id, operator_name, "distribute",
                         "skill", item_id, item.name,
                         user["tenant_id"], user.get("tenant_name", ""),
                         user.get("bbk_id", "")),
                    )
                except Exception as e:
                    logger.warning("Failed to log distribute operation: %s", e)

        return DistributeResponse(distributed_count=count, item_id=item_id)

    async def get_my_skills(
        self,
        source_id: str,
        user_id: str,
        agent_id: str = "default",
    ) -> list[MySkillItem]:
        """获取用户技能列表（我创建的 + 我接收的）。"""
        from .fs import get_user_skills_dir
        import json as _json

        skills_dir = get_user_skills_dir(self.swe_root, user_id, agent_id)
        if not skills_dir.exists():
            return []

        market_index = load_index(self.marketplace_root, source_id)
        market_versions: dict[str, str] = {
            i.name: i.version for i in market_index if i.status == "active"
        }

        result = []
        for skill_dir in sorted(skills_dir.iterdir()):
            if not skill_dir.is_dir():
                continue
            skill_json_path = skill_dir / "skill.json"
            if not skill_json_path.exists():
                continue
            try:
                data = _json.loads(skill_json_path.read_text(encoding="utf-8"))
            except Exception:
                continue

            source = data.get("source", "customized")
            is_received = source.startswith("marketplace:")
            received_version = data.get("received_version")
            market_version = market_versions.get(skill_dir.name)
            has_update = (
                is_received
                and received_version is not None
                and market_version is not None
                and received_version != market_version
            )

            result.append(MySkillItem(
                skill_name=skill_dir.name,
                source=source,
                description=data.get("description", ""),
                version=data.get("version"),
                received_version=received_version,
                distributed_by=data.get("distributed_by"),
                is_received=is_received,
                has_update=has_update,
            ))
        return result

    async def _get_stats(
        self, skill_name: str, source_id: str
    ) -> tuple[int, int]:
        if not self.db.is_connected:
            return 0, 0
        try:
            row = await self.db.fetch_one(
                _TRACING_STATS_SQL, (skill_name, source_id)
            )
            if row:
                return int(row.get("call_count", 0)), int(row.get("user_count", 0))
        except Exception as e:
            logger.warning("Failed to fetch stats for %s: %s", skill_name, e)
        return 0, 0

    async def _get_user_stats(
        self, skill_name: str, source_id: str
    ) -> list[SkillUserStat]:
        if not self.db.is_connected:
            return []
        try:
            rows = await self.db.fetch_all(
                _TRACING_USER_STATS_SQL, (skill_name, source_id)
            )
            return [
                SkillUserStat(
                    user_id=r["user_id"],
                    user_name=r.get("user_name", ""),
                    call_count=int(r["call_count"]),
                )
                for r in rows
            ]
        except Exception as e:
            logger.warning("Failed to fetch user stats for %s: %s", skill_name, e)
        return []

    async def _resolve_target_users(
        self, source_id: str, req: DistributeRequest
    ) -> list[dict]:
        if not self.db.is_connected:
            return []
        if req.target_type == "all":
            rows = await self.db.fetch_all(
                _QUERY_USERS_BY_SOURCE_SQL, (source_id,)
            )
        elif req.target_type == "bbk_id" and req.target_values:
            placeholders = ",".join(["%s"] * len(req.target_values))
            sql = _QUERY_USERS_BY_BBK_SQL.format(placeholders=placeholders)
            rows = await self.db.fetch_all(
                sql, (source_id, *req.target_values)
            )
        elif req.target_type == "user_id" and req.target_values:
            rows = [
                {"tenant_id": uid, "tenant_name": "", "bbk_id": ""}
                for uid in req.target_values
            ]
        else:
            rows = []
        return rows
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd "D:\Vibe Coding\CoPaw1.0.0\CoPaw\market"
PYTHONPATH=src python -m pytest tests/unit/marketplace/test_service.py -v
```

预期：6 passed

- [ ] **Step 5: Commit**

```bash
git add market/src/market/marketplace/service.py market/tests/unit/marketplace/test_service.py
git commit -m "feat(marketplace): add MarketplaceService with publish/unpublish/list/detail/distribute"
```

---

### Task 3: 实现管理员 API

**Files:**
- Create: `market/src/market/app/routers/skills_market.py`
- Modify: `market/src/market/app/routers/__init__.py`
- Create: `market/tests/unit/marketplace/test_skills_market.py`

管理员 API 通过请求头 `X-Manager: true` 标识管理员身份。MarketplaceService 从 `app.state` 获取。

- [ ] **Step 1: 写失败测试**

创建 `market/tests/unit/marketplace/test_skills_market.py`：

```python
# -*- coding: utf-8 -*-
import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient


def _make_app(tmp_path):
    from fastapi import FastAPI
    from market.app.routers.skills_market import router
    from market.marketplace.service import MarketplaceService
    from market.database.connection import DatabaseConnection

    mock_db = AsyncMock(spec=DatabaseConnection)
    mock_db.is_connected = True
    mock_db.execute = AsyncMock(return_value=1)

    svc = MarketplaceService(
        db=mock_db,
        marketplace_root=tmp_path / "market",
        swe_root=tmp_path / "swe",
    )
    app = FastAPI()
    app.state.marketplace = svc
    app.include_router(router, prefix="/api")
    return app


def test_publish_skill_returns_201(tmp_path):
    app = _make_app(tmp_path)
    client = TestClient(app)
    payload = {
        "name": "skill_x",
        "description": "test",
        "creator_id": "u1",
        "creator_name": "User",
        "skill_json": {"name": "skill_x"},
        "skill_md": "# Skill X",
    }
    resp = client.post(
        "/api/marketplace/skills",
        json=payload,
        headers={"X-Source-Id": "src_a", "X-Manager": "true"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "skill_x"
    assert data["version"] == "1.0.0"


def test_publish_skill_non_manager_returns_403(tmp_path):
    app = _make_app(tmp_path)
    client = TestClient(app)
    payload = {
        "name": "skill_x", "description": "", "creator_id": "u1",
        "creator_name": "", "skill_json": {}, "skill_md": "",
    }
    resp = client.post(
        "/api/marketplace/skills",
        json=payload,
        headers={"X-Source-Id": "src_a"},
    )
    assert resp.status_code == 403


def test_unpublish_skill_returns_204(tmp_path):
    from market.marketplace.schemas import PublishSkillRequest
    import asyncio
    app = _make_app(tmp_path)
    svc = app.state.marketplace
    req = PublishSkillRequest(
        name="skill_y", description="", creator_id="u1", creator_name="",
        skill_json={}, skill_md="",
    )
    item = asyncio.get_event_loop().run_until_complete(
        svc.publish_skill("src_a", req)
    )
    client = TestClient(app)
    resp = client.delete(
        f"/api/marketplace/skills/{item.item_id}",
        headers={"X-Source-Id": "src_a", "X-Manager": "true",
                 "X-User-Id": "u1", "X-User-Name": "User"},
    )
    assert resp.status_code == 204


def test_unpublish_skill_not_found_returns_404(tmp_path):
    app = _make_app(tmp_path)
    client = TestClient(app)
    resp = client.delete(
        "/api/marketplace/skills/nonexistent-id",
        headers={"X-Source-Id": "src_a", "X-Manager": "true",
                 "X-User-Id": "u1", "X-User-Name": "User"},
    )
    assert resp.status_code == 404


def test_distribute_skill_returns_200(tmp_path):
    from market.marketplace.schemas import PublishSkillRequest
    import asyncio
    app = _make_app(tmp_path)
    svc = app.state.marketplace
    req = PublishSkillRequest(
        name="skill_z", description="", creator_id="u1", creator_name="",
        skill_json={}, skill_md="",
    )
    item = asyncio.get_event_loop().run_until_complete(
        svc.publish_skill("src_a", req)
    )
    # Mock _resolve_target_users to return one user
    svc.db.fetch_all = AsyncMock(return_value=[
        {"tenant_id": "user1", "tenant_name": "User One", "bbk_id": "200"}
    ])
    client = TestClient(app)
    resp = client.post(
        f"/api/marketplace/skills/{item.item_id}/distribute",
        json={"target_type": "all", "target_values": []},
        headers={"X-Source-Id": "src_a", "X-Manager": "true",
                 "X-User-Id": "u1", "X-User-Name": "User"},
    )
    assert resp.status_code == 200
    assert resp.json()["distributed_count"] == 1
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd "D:\Vibe Coding\CoPaw1.0.0\CoPaw\market"
PYTHONPATH=src python -m pytest tests/unit/marketplace/test_skills_market.py -v
```

预期：ImportError

- [ ] **Step 3: 实现管理员路由**

创建 `market/src/market/app/routers/skills_market.py`：

```python
# -*- coding: utf-8 -*-
"""管理员市场 API."""
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Request, status

from ...marketplace.schemas import (
    DistributeRequest,
    DistributeResponse,
    MarketSkillResponse,
    PublishSkillRequest,
)

router = APIRouter()


def _require_manager(x_manager: Optional[str]) -> None:
    if x_manager != "true":
        raise HTTPException(status_code=403, detail="Manager access required")


def _require_source_id(x_source_id: Optional[str]) -> str:
    if not x_source_id:
        raise HTTPException(status_code=400, detail="X-Source-Id header is required")
    return x_source_id


@router.post(
    "/marketplace/skills",
    response_model=MarketSkillResponse,
    status_code=status.HTTP_201_CREATED,
)
async def publish_skill(
    req: PublishSkillRequest,
    request: Request,
    x_source_id: Optional[str] = Header(default=None, alias="X-Source-Id"),
    x_manager: Optional[str] = Header(default=None, alias="X-Manager"),
):
    """上架技能（管理员）."""
    source_id = _require_source_id(x_source_id)
    _require_manager(x_manager)
    svc = request.app.state.marketplace
    item = await svc.publish_skill(source_id, req)
    return MarketSkillResponse(
        item_id=item.item_id,
        name=item.name,
        description=item.description,
        version=item.version,
        creator_id=item.creator_id,
        creator_name=item.creator_name,
        category_id=item.category_id,
        bbk_ids=item.bbk_ids,
        status=item.status,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


@router.delete(
    "/marketplace/skills/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def unpublish_skill(
    item_id: str,
    request: Request,
    x_source_id: Optional[str] = Header(default=None, alias="X-Source-Id"),
    x_manager: Optional[str] = Header(default=None, alias="X-Manager"),
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    x_user_name: Optional[str] = Header(default=None, alias="X-User-Name"),
):
    """下架技能（管理员）."""
    source_id = _require_source_id(x_source_id)
    _require_manager(x_manager)
    svc = request.app.state.marketplace
    ok = await svc.unpublish_skill(
        source_id, item_id,
        operator_id=x_user_id or "",
        operator_name=x_user_name or "",
    )
    if not ok:
        raise HTTPException(status_code=404, detail="Skill not found")


@router.post(
    "/marketplace/skills/{item_id}/distribute",
    response_model=DistributeResponse,
)
async def distribute_skill(
    item_id: str,
    req: DistributeRequest,
    request: Request,
    x_source_id: Optional[str] = Header(default=None, alias="X-Source-Id"),
    x_manager: Optional[str] = Header(default=None, alias="X-Manager"),
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    x_user_name: Optional[str] = Header(default=None, alias="X-User-Name"),
):
    """分发技能（管理员）."""
    source_id = _require_source_id(x_source_id)
    _require_manager(x_manager)
    svc = request.app.state.marketplace
    try:
        result = await svc.distribute_skill(
            source_id, item_id,
            operator_id=x_user_id or "",
            operator_name=x_user_name or "",
            req=req,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return result
```

- [ ] **Step 4: 注册路由并初始化 MarketplaceService**

读取 `market/src/market/app/routers/__init__.py`，添加：

```python
from .skills_market import router as skills_market_router
```

并在 `api_router` 中注册：

```python
api_router.include_router(skills_market_router, tags=["marketplace-admin"])
```

读取 `market/src/market/app/_app.py`，在 lifespan 中 `fastapi_app.state.db = db` 之后添加：

```python
from ..marketplace.service import MarketplaceService
from ..config.constant import WORKING_DIR

marketplace_root = Path(
    os.environ.get("MARKET_MARKETPLACE_ROOT", str(Path.home() / ".swe.marketplace"))
)
swe_root = Path(
    os.environ.get("MARKET_SWE_ROOT", str(Path.home() / ".swe"))
)
fastapi_app.state.marketplace = MarketplaceService(
    db=db,
    marketplace_root=marketplace_root,
    swe_root=swe_root,
)
```

在 `_app.py` 顶部 imports 中添加 `from pathlib import Path`（如果尚未导入）。

- [ ] **Step 5: 运行测试确认通过**

```bash
cd "D:\Vibe Coding\CoPaw1.0.0\CoPaw\market"
PYTHONPATH=src python -m pytest tests/unit/marketplace/test_skills_market.py -v
```

预期：5 passed

- [ ] **Step 6: Commit**

```bash
git add market/src/market/app/routers/skills_market.py market/src/market/app/routers/__init__.py market/src/market/app/_app.py market/tests/unit/marketplace/test_skills_market.py
git commit -m "feat(marketplace): add admin skills API (publish/unpublish/distribute)"
```

---

### Task 4: 实现用户浏览 API 和我的技能 API

**Files:**
- Create: `market/src/market/app/routers/skills_browse.py`
- Modify: `market/src/market/app/routers/__init__.py`
- Create: `market/tests/unit/marketplace/test_skills_browse.py`

- [ ] **Step 1: 写失败测试**

创建 `market/tests/unit/marketplace/test_skills_browse.py`：

```python
# -*- coding: utf-8 -*-
import asyncio
import pytest
from unittest.mock import AsyncMock
from fastapi.testclient import TestClient


def _make_app(tmp_path):
    from fastapi import FastAPI
    from market.app.routers.skills_browse import router
    from market.marketplace.service import MarketplaceService
    from market.database.connection import DatabaseConnection

    mock_db = AsyncMock(spec=DatabaseConnection)
    mock_db.is_connected = False  # no DB needed for fs-only tests

    svc = MarketplaceService(
        db=mock_db,
        marketplace_root=tmp_path / "market",
        swe_root=tmp_path / "swe",
    )
    app = FastAPI()
    app.state.marketplace = svc
    app.include_router(router, prefix="/api")
    return app


def _publish(svc, source_id, name, bbk_ids=None):
    from market.marketplace.schemas import PublishSkillRequest
    req = PublishSkillRequest(
        name=name, description="desc", creator_id="u1", creator_name="User",
        skill_json={}, skill_md="", bbk_ids=bbk_ids or [],
    )
    return asyncio.get_event_loop().run_until_complete(
        svc.publish_skill(source_id, req)
    )


def test_list_skills_returns_active_items(tmp_path):
    app = _make_app(tmp_path)
    _publish(app.state.marketplace, "src_a", "skill_1")
    _publish(app.state.marketplace, "src_a", "skill_2")
    client = TestClient(app)
    resp = client.get(
        "/api/marketplace/skills",
        headers={"X-Source-Id": "src_a", "X-Bbk-Id": "100"},
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_list_skills_missing_source_id_returns_400(tmp_path):
    app = _make_app(tmp_path)
    client = TestClient(app)
    resp = client.get("/api/marketplace/skills", headers={"X-Bbk-Id": "100"})
    assert resp.status_code == 400


def test_list_skills_filters_by_category(tmp_path):
    from market.marketplace.schemas import PublishSkillRequest
    app = _make_app(tmp_path)
    svc = app.state.marketplace
    req1 = PublishSkillRequest(
        name="skill_cat1", description="", creator_id="u1", creator_name="",
        skill_json={}, skill_md="", category_id=1,
    )
    req2 = PublishSkillRequest(
        name="skill_cat2", description="", creator_id="u1", creator_name="",
        skill_json={}, skill_md="", category_id=2,
    )
    asyncio.get_event_loop().run_until_complete(svc.publish_skill("src_a", req1))
    asyncio.get_event_loop().run_until_complete(svc.publish_skill("src_a", req2))
    client = TestClient(app)
    resp = client.get(
        "/api/marketplace/skills?category_id=1",
        headers={"X-Source-Id": "src_a", "X-Bbk-Id": "100"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["name"] == "skill_cat1"


def test_get_skill_detail_returns_200(tmp_path):
    app = _make_app(tmp_path)
    item = _publish(app.state.marketplace, "src_a", "skill_d")
    client = TestClient(app)
    resp = client.get(
        f"/api/marketplace/skills/{item.item_id}",
        headers={"X-Source-Id": "src_a", "X-Bbk-Id": "100"},
    )
    assert resp.status_code == 200
    assert resp.json()["item_id"] == item.item_id


def test_get_skill_detail_not_found_returns_404(tmp_path):
    app = _make_app(tmp_path)
    client = TestClient(app)
    resp = client.get(
        "/api/marketplace/skills/no-such-id",
        headers={"X-Source-Id": "src_a", "X-Bbk-Id": "100"},
    )
    assert resp.status_code == 404


def test_get_my_skills_returns_list(tmp_path):
    import json
    from market.marketplace.fs import get_user_skills_dir
    # Setup a skill in user dir
    skills_dir = get_user_skills_dir(tmp_path / "swe", "user1")
    skill_dir = skills_dir / "my_skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "skill.json").write_text(
        json.dumps({"source": "customized", "description": "my skill"}),
        encoding="utf-8",
    )
    app = _make_app(tmp_path)
    client = TestClient(app)
    resp = client.get(
        "/api/skills/mine",
        headers={"X-Source-Id": "src_a", "X-User-Id": "user1"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["skill_name"] == "my_skill"
    assert data[0]["is_received"] is False


def test_get_received_skills_returns_only_received(tmp_path):
    import json
    from market.marketplace.fs import get_user_skills_dir
    skills_dir = get_user_skills_dir(tmp_path / "swe", "user2")
    # created skill
    d1 = skills_dir / "created_skill"
    d1.mkdir(parents=True)
    (d1 / "skill.json").write_text(
        json.dumps({"source": "customized"}), encoding="utf-8"
    )
    # received skill
    d2 = skills_dir / "received_skill"
    d2.mkdir(parents=True)
    (d2 / "skill.json").write_text(
        json.dumps({"source": "marketplace:item-1", "received_version": "1.0.0"}),
        encoding="utf-8",
    )
    app = _make_app(tmp_path)
    client = TestClient(app)
    resp = client.get(
        "/api/skills/received",
        headers={"X-Source-Id": "src_a", "X-User-Id": "user2"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["skill_name"] == "received_skill"
    assert data[0]["is_received"] is True
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd "D:\Vibe Coding\CoPaw1.0.0\CoPaw\market"
PYTHONPATH=src python -m pytest tests/unit/marketplace/test_skills_browse.py -v
```

预期：ImportError

- [ ] **Step 3: 实现用户浏览路由**

创建 `market/src/market/app/routers/skills_browse.py`：

```python
# -*- coding: utf-8 -*-
"""用户市场浏览 API 和我的技能 API."""
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Request

from ...marketplace.schemas import (
    MarketSkillDetail,
    MarketSkillResponse,
    MySkillItem,
)

router = APIRouter()


def _require_source_id(x_source_id: Optional[str]) -> str:
    if not x_source_id:
        raise HTTPException(status_code=400, detail="X-Source-Id header is required")
    return x_source_id


@router.get("/marketplace/skills", response_model=list[MarketSkillResponse])
async def list_skills(
    request: Request,
    category_id: Optional[int] = None,
    x_source_id: Optional[str] = Header(default=None, alias="X-Source-Id"),
    x_bbk_id: Optional[str] = Header(default=None, alias="X-Bbk-Id"),
):
    """浏览市场技能列表（按 source_id + bbk_id 过滤）."""
    source_id = _require_source_id(x_source_id)
    user_bbk_id = x_bbk_id or "100"
    svc = request.app.state.marketplace
    return await svc.list_skills(source_id, user_bbk_id, category_id=category_id)


@router.get("/marketplace/skills/{item_id}", response_model=MarketSkillDetail)
async def get_skill_detail(
    item_id: str,
    request: Request,
    x_source_id: Optional[str] = Header(default=None, alias="X-Source-Id"),
    x_bbk_id: Optional[str] = Header(default=None, alias="X-Bbk-Id"),
):
    """预览技能详情."""
    source_id = _require_source_id(x_source_id)
    user_bbk_id = x_bbk_id or "100"
    svc = request.app.state.marketplace
    detail = await svc.get_skill_detail(source_id, item_id, user_bbk_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Skill not found")
    return detail


@router.get("/skills/mine", response_model=list[MySkillItem])
async def get_my_skills(
    request: Request,
    x_source_id: Optional[str] = Header(default=None, alias="X-Source-Id"),
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    agent_id: str = "default",
):
    """我创建的技能列表."""
    source_id = _require_source_id(x_source_id)
    if not x_user_id:
        raise HTTPException(status_code=400, detail="X-User-Id header is required")
    svc = request.app.state.marketplace
    all_skills = await svc.get_my_skills(source_id, x_user_id, agent_id)
    return [s for s in all_skills if not s.is_received]


@router.get("/skills/received", response_model=list[MySkillItem])
async def get_received_skills(
    request: Request,
    x_source_id: Optional[str] = Header(default=None, alias="X-Source-Id"),
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    agent_id: str = "default",
):
    """我接收的技能列表."""
    source_id = _require_source_id(x_source_id)
    if not x_user_id:
        raise HTTPException(status_code=400, detail="X-User-Id header is required")
    svc = request.app.state.marketplace
    all_skills = await svc.get_my_skills(source_id, x_user_id, agent_id)
    return [s for s in all_skills if s.is_received]
```

- [ ] **Step 4: 注册路由**

读取 `market/src/market/app/routers/__init__.py`，添加：

```python
from .skills_browse import router as skills_browse_router
```

并在 `api_router` 中注册：

```python
api_router.include_router(skills_browse_router, tags=["marketplace"])
```

- [ ] **Step 5: 运行全部测试**

```bash
cd "D:\Vibe Coding\CoPaw1.0.0\CoPaw\market"
PYTHONPATH=src python -m pytest tests/unit/marketplace/ -v
```

预期：全部通过（4 schemas + 6 service + 5 admin + 7 browse = 22 passed）

- [ ] **Step 6: Commit**

```bash
git add market/src/market/app/routers/skills_browse.py market/src/market/app/routers/__init__.py market/tests/unit/marketplace/test_skills_browse.py
git commit -m "feat(marketplace): add user browse API and my-skills API"
```

---

## 自检

**Spec 覆盖：**
- [x] `POST /api/marketplace/skills` — Task 3
- [x] `DELETE /api/marketplace/skills/{item_id}` — Task 3
- [x] `POST /api/marketplace/skills/{item_id}/distribute` — Task 3
- [x] `GET /api/marketplace/skills` — Task 4（bbk_id 过滤、分类过滤）
- [x] `GET /api/marketplace/skills/{item_id}` — Task 4（含调用客户明细）
- [x] `GET /api/skills/mine` — Task 4
- [x] `GET /api/skills/received` — Task 4（含 has_update 标记）
- [x] 版本号自动递增（同名重复上架）— Task 2 `_bump_patch`
- [x] 分发展开用户列表（all/bbk_id/user_id）— Task 2 `_resolve_target_users`
- [x] 操作日志写入 swe_marketplace_operation_logs — Task 2
- [x] 统计数据从 swe_tracing_spans 查询 — Task 2
- [x] 管理员权限校验（X-Manager: true）— Task 3
- [x] MarketplaceService 注入 app.state — Task 3 Step 4

**占位符扫描：** 无 TBD/TODO，所有代码完整。

**类型一致性：**
- `PublishSkillRequest` 在 Task 1 定义，Task 2 和 Task 3 使用，一致
- `MarketSkillResponse` / `MarketSkillDetail` 在 Task 1 定义，Task 2、3、4 使用，一致
- `MySkillItem` 在 Task 1 定义，Task 2 和 Task 4 使用，一致
- `DistributeRequest` / `DistributeResponse` 在 Task 1 定义，Task 2 和 Task 3 使用，一致
