# Tracing 模块迁移实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将运营看板的查询 API 从 SWE 服务迁移到 Monitor 服务，实现服务职责分离。

**Architecture:** Monitor 服务直接连接 MySQL 数据库（swe_tracing_traces 和 swe_tracing_spans 表）和 Elasticsearch，提供 `/api/tracing/*` 端点，前端保持 API 调用路径不变。

**Tech Stack:** Python 3.10+, FastAPI, aiomysql, elasticsearch[async], Pydantic

---

## 文件结构

迁移涉及的文件创建和修改：

```
monitor/src/monitor/
├── config/
│   └── constant.py              # 修改：添加 tracing 相关环境变量
├── app/
│   ├── database/
│   │   ├── __init__.py          # 修改：导出 TracingConnection
│   │   ├── tracing.py          # 新建：数据库连接管理
│   │   └── elasticsearch.py    # 新建：ES 客户端
│   ├── models/
│   │   ├── __init__.py          # 修改：导出 tracing 模型
│   │   └── tracing.py          # 新建：数据模型（从 SWE 复制）
│   ├── services/
│   │   ├── __init__.py          # 修改：导出 tracing 服务
│   │   └── tracing/            # 新建：服务层
│   │       ├── __init__.py
│   │       ├── query_service.py # 核心查询服务
│   │       └── export_service.py# 导出服务
│   ├── routers/
│   │   ├── __init__.py          # 修改：注册 tracing_router
│   │   └── tracing.py          # 新建：API 路由
│   └── _app.py                  # 修改：生命周期添加 tracing 连接初始化

src/swe/app/routers/
└── tracing.py                  # 最终删除
```

---

## Task 1: 添加 Tracing 环境变量配置

**Files:**
- Modify: `monitor/src/monitor/config/constant.py`

- [ ] **Step 1: 添加 tracing 数据库和 ES 环境变量**

在 `monitor/src/monitor/config/constant.py` 文件末尾添加：

```python
# ============================================================
# Tracing 数据库配置（复用 SWE 数据库）
# ============================================================

TRACING_DB_HOST = EnvVarLoader.get_str("TRACING_DB_HOST", "")
TRACING_DB_PORT = EnvVarLoader.get_int("TRACING_DB_PORT", 3306, min_value=1)
TRACING_DB_USER = EnvVarLoader.get_str("TRACING_DB_USER", "root")
TRACING_DB_ACCESS = EnvVarLoader.get_str("TRACING_DB_ACCESS", "")
TRACING_DB_NAME = EnvVarLoader.get_str("TRACING_DB_NAME", "swe")
TRACING_DB_MIN_CONN = EnvVarLoader.get_int("TRACING_DB_MIN_CONN", 2, min_value=1)
TRACING_DB_MAX_CONN = EnvVarLoader.get_int("TRACING_DB_MAX_CONN", 10, min_value=1)

# ============================================================
# Elasticsearch 配置
# ============================================================

ES_HOST = EnvVarLoader.get_str("ES_HOST", "")
ES_PORT = EnvVarLoader.get_int("ES_PORT", 9200, min_value=1)
ES_USER = EnvVarLoader.get_str("ES_USER", "")
ES_PASSWORD = EnvVarLoader.get_str("ES_PASSWORD", "")
ES_INDEX = EnvVarLoader.get_str("ES_INDEX", "swe_messages")
```

- [ ] **Step 2: Commit**

```bash
git add monitor/src/monitor/config/constant.py
git commit -m "feat(monitor): add tracing database and elasticsearch config"
```

---

## Task 2: 创建 Elasticsearch 客户端

**Files:**
- Create: `monitor/src/monitor/app/database/elasticsearch.py`
- Modify: `monitor/src/monitor/app/database/__init__.py`

- [ ] **Step 1: 创建 ES 客户端模块**

创建 `monitor/src/monitor/app/database/elasticsearch.py`：

```python
# -*- coding: utf-8 -*-
"""Elasticsearch client for Monitor service."""
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Global client singleton
_es_client: Optional["ESClient"] = None


class ESClient:
    """Async Elasticsearch client for model output queries."""

    def __init__(self, host: str, port: int, user: str = "", password: str = "", index: str = "swe_messages"):
        self._host = host
        self._port = port
        self._user = user
        self._password = password
        self._index = index
        self._es = None
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def connect(self) -> None:
        """Connect to Elasticsearch."""
        if not self._host:
            logger.info("Elasticsearch host not configured, skipping connection")
            return

        try:
            from elasticsearch import AsyncElasticsearch
        except ImportError:
            logger.warning("elasticsearch package not installed")
            return

        scheme = "https" if self._port == 443 else "http"
        hosts = [f"{scheme}://{self._host}:{self._port}"]
        kwargs: dict = {"hosts": hosts}

        if self._user and self._password:
            kwargs["basic_auth"] = (self._user, self._password)

        try:
            self._es = AsyncElasticsearch(**kwargs)
            await self._es.ping()
            self._connected = True
            logger.info("Elasticsearch connected: %s:%s", self._host, self._port)
        except Exception as e:
            logger.warning("Failed to connect to Elasticsearch: %s", e)
            self._connected = False

    async def get_message(self, trace_id: str) -> Optional[str]:
        """Get model output by trace ID.

        Args:
            trace_id: The trace ID to look up.

        Returns:
            The model_output text, or None if not found.
        """
        if not self._connected or not self._es:
            return None

        try:
            result = await self._es.get(index=self._index, id=trace_id)
            if result and result.get("found"):
                return result["_source"].get("model_output")
        except Exception:
            pass
        return None

    async def close(self) -> None:
        """Close the Elasticsearch connection."""
        if self._es:
            try:
                await self._es.close()
            except Exception as e:
                logger.warning("Failed to close ES connection: %s", e)
            finally:
                self._connected = False
                self._es = None


def get_es_client() -> Optional[ESClient]:
    """Get the global ES client instance."""
    return _es_client


async def init_es_client() -> Optional[ESClient]:
    """Initialize the global ES client."""
    global _es_client

    from ...config.constant import ES_HOST, ES_PORT, ES_USER, ES_PASSWORD, ES_INDEX

    if not ES_HOST:
        _es_client = None
        return None

    _es_client = ESClient(ES_HOST, ES_PORT, ES_USER, ES_PASSWORD, ES_INDEX)
    await _es_client.connect()
    return _es_client


async def close_es_client() -> None:
    """Close the global ES client."""
    global _es_client

    if _es_client is not None:
        await _es_client.close()
        _es_client = None
```

- [ ] **Step 2: 更新 database/__init__.py**

修改 `monitor/src/monitor/app/database/__init__.py`：

```python
# -*- coding: utf-8 -*-
"""Monitor database module."""

from .connection import DatabaseConnection, get_db_connection, init_db_connection, close_db_connection
from .elasticsearch import ESClient, get_es_client, init_es_client, close_es_client

__all__ = [
    "DatabaseConnection",
    "get_db_connection",
    "init_db_connection",
    "close_db_connection",
    "ESClient",
    "get_es_client",
    "init_es_client",
    "close_es_client",
]
```

- [ ] **Step 3: Commit**

```bash
git add monitor/src/monitor/app/database/elasticsearch.py monitor/src/monitor/app/database/__init__.py
git commit -m "feat(monitor): add elasticsearch client for tracing queries"
```

---

## Task 3: 创建 Tracing 数据库连接管理器

**Files:**
- Modify: `monitor/src/monitor/app/database/__init__.py`

- [ ] **Step 1: 创建 TracingConnection 类**

在 `monitor/src/monitor/app/database/connection.py` 文件末尾添加：

```python
# ============================================================
# Tracing Database Connection（连接 SWE 数据库）
# ============================================================

_tracing_db_connection: Optional[DatabaseConnection] = None


async def init_tracing_db_connection() -> Optional[DatabaseConnection]:
    """Initialize tracing database connection (SWE database).

    Returns:
        DatabaseConnection instance or None if not configured.
    """
    global _tracing_db_connection

    from ..config.constant import (
        TRACING_DB_HOST,
        TRACING_DB_PORT,
        TRACING_DB_USER,
        TRACING_DB_ACCESS,
        TRACING_DB_NAME,
        TRACING_DB_MIN_CONN,
        TRACING_DB_MAX_CONN,
    )

    if not TRACING_DB_HOST:
        logger.info("Tracing database not configured (TRACING_DB_HOST not set)")
        return None

    config = MonitorDatabaseConfig(
        host=TRACING_DB_HOST,
        port=TRACING_DB_PORT,
        user=TRACING_DB_USER,
        password=TRACING_DB_ACCESS,
        database=TRACING_DB_NAME,
        min_connections=TRACING_DB_MIN_CONN,
        max_connections=TRACING_DB_MAX_CONN,
    )

    _tracing_db_connection = DatabaseConnection(config)
    await _tracing_db_connection.connect()
    logger.info("Tracing database connection initialized: %s:%s/%s", config.host, config.port, config.database)
    return _tracing_db_connection


def get_tracing_db_connection() -> DatabaseConnection:
    """Get the tracing database connection.

    Raises:
        RuntimeError: If tracing database is not initialized.

    Returns:
        DatabaseConnection instance.
    """
    if _tracing_db_connection is None:
        raise RuntimeError(
            "Tracing database connection not initialized. Call init_tracing_db_connection() first."
        )
    return _tracing_db_connection


async def close_tracing_db_connection() -> None:
    """Close the tracing database connection."""
    global _tracing_db_connection

    if _tracing_db_connection is not None:
        await _tracing_db_connection.close()
        _tracing_db_connection = None
```

- [ ] **Step 2: 更新 database/__init__.py 导出**

修改 `monitor/src/monitor/app/database/__init__.py`：

```python
# -*- coding: utf-8 -*-
"""Monitor database module."""

from .connection import (
    DatabaseConnection,
    get_db_connection,
    init_db_connection,
    close_db_connection,
    init_tracing_db_connection,
    get_tracing_db_connection,
    close_tracing_db_connection,
)
from .elasticsearch import ESClient, get_es_client, init_es_client, close_es_client

__all__ = [
    "DatabaseConnection",
    "get_db_connection",
    "init_db_connection",
    "close_db_connection",
    "init_tracing_db_connection",
    "get_tracing_db_connection",
    "close_tracing_db_connection",
    "ESClient",
    "get_es_client",
    "init_es_client",
    "close_es_client",
]
```

- [ ] **Step 3: Commit**

```bash
git add monitor/src/monitor/app/database/connection.py monitor/src/monitor/app/database/__init__.py
git commit -m "feat(monitor): add tracing database connection manager"
```

---

## Task 4: 创建 Tracing 数据模型

**Files:**
- Create: `monitor/src/monitor/app/models/tracing.py`
- Modify: `monitor/src/monitor/app/models/__init__.py`

- [ ] **Step 1: 创建 tracing 模型文件**

创建 `monitor/src/monitor/app/models/tracing.py`，内容从 `src/swe/tracing/models.py` 复制所有模型定义（EventType, TraceStatus, Span, Trace, ModelUsage, ToolUsage, SkillUsage, MCPToolUsage, MCPServerUsage, DailyStats, OverviewStats, UserStats, ToolCall, TraceDetail, ToolCallInSkill, SkillCallTimeline, TimelineEvent, TraceDetailWithTimeline, UserListItem, TraceListItem, SessionListItem, SessionStats, UserMessageItem）。

模型定义与 SWE 服务完全一致，确保前端兼容。

- [ ] **Step 2: 更新 models/__init__.py**

修改 `monitor/src/monitor/app/models/__init__.py`：

```python
# -*- coding: utf-8 -*-
"""Monitor models module."""

from .cron import CronJob, CronJobCreate, CronJobUpdate, CronJobExecution
from .tracing import (
    EventType,
    TraceStatus,
    Span,
    Trace,
    ModelUsage,
    ToolUsage,
    SkillUsage,
    MCPToolUsage,
    MCPServerUsage,
    DailyStats,
    OverviewStats,
    UserStats,
    ToolCall,
    TraceDetail,
    ToolCallInSkill,
    SkillCallTimeline,
    TimelineEvent,
    TraceDetailWithTimeline,
    UserListItem,
    TraceListItem,
    SessionListItem,
    SessionStats,
    UserMessageItem,
)

__all__ = [
    # Cron models
    "CronJob",
    "CronJobCreate",
    "CronJobUpdate",
    "CronJobExecution",
    # Tracing models
    "EventType",
    "TraceStatus",
    "Span",
    "Trace",
    "ModelUsage",
    "ToolUsage",
    "SkillUsage",
    "MCPToolUsage",
    "MCPServerUsage",
    "DailyStats",
    "OverviewStats",
    "UserStats",
    "ToolCall",
    "TraceDetail",
    "ToolCallInSkill",
    "SkillCallTimeline",
    "TimelineEvent",
    "TraceDetailWithTimeline",
    "UserListItem",
    "TraceListItem",
    "SessionListItem",
    "SessionStats",
    "UserMessageItem",
]
```

- [ ] **Step 3: Commit**

```bash
git add monitor/src/monitor/app/models/tracing.py monitor/src/monitor/app/models/__init__.py
git commit -m "feat(monitor): add tracing data models"
```

---

## Task 5: 创建 Tracing 查询服务

**Files:**
- Create: `monitor/src/monitor/app/services/tracing/__init__.py`
- Create: `monitor/src/monitor/app/services/tracing/query_service.py`

- [ ] **Step 1: 创建服务目录 __init__.py**

创建 `monitor/src/monitor/app/services/tracing/__init__.py`：

```python
# -*- coding: utf-8 -*-
"""Tracing services module."""

from .query_service import TracingQueryService
from .export_service import TracingExportService

__all__ = [
    "TracingQueryService",
    "TracingExportService",
]
```

- [ ] **Step 2: 创建查询服务（第一部分：初始化和基础查询）**

创建 `monitor/src/monitor/app/services/tracing/query_service.py`：

```python
# -*- coding: utf-8 -*-
"""Tracing query service for operational dashboard."""
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Optional

from ...database import get_tracing_db_connection, DatabaseConnection
from ...models.tracing import (
    EventType,
    ModelUsage,
    MCPToolUsage,
    MCPServerUsage,
    OverviewStats,
    SessionListItem,
    SessionStats,
    SkillCallTimeline,
    SkillUsage,
    Span,
    TimelineEvent,
    ToolCallInSkill,
    ToolUsage,
    Trace,
    TraceDetail,
    TraceDetailWithTimeline,
    TraceListItem,
    TraceStatus,
    UserListItem,
    UserMessageItem,
    UserStats,
)

logger = logging.getLogger(__name__)

# 需要从统计中排除的 source_id（测试平台等）
EXCLUDED_SOURCE_IDS = ["default"]


class TracingQueryService:
    """运营看板查询服务."""

    def __init__(self, db: DatabaseConnection):
        """初始化查询服务.

        Args:
            db: 数据库连接实例
        """
        self._db = db

    @classmethod
    def get_instance(cls) -> "TracingQueryService":
        """获取服务实例（使用全局数据库连接）."""
        db = get_tracing_db_connection()
        return cls(db)

    # ===== 运营概览 =====

    async def get_overview_stats(
        self,
        source_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> OverviewStats:
        """获取运营概览统计."""
        if start_date is None:
            start_date = datetime.now() - timedelta(days=30)
        if end_date is None:
            end_date = datetime.now() + timedelta(days=1)

        total_users = await self._get_total_users(source_id, start_date, end_date)
        online_users, online_user_ids = await self._get_online_users(source_id)
        token_row = await self._get_token_stats(source_id, start_date, end_date)
        model_distribution = await self._get_model_distribution(source_id, start_date, end_date)
        top_tools = await self._get_top_tools(source_id, start_date, end_date)
        top_skills = await self._get_top_skills(source_id, start_date, end_date)
        top_mcp_tools, mcp_servers = await self._get_mcp_stats(source_id, start_date, end_date)

        return OverviewStats(
            online_users=online_users,
            online_user_ids=online_user_ids,
            total_users=total_users,
            model_distribution=model_distribution,
            total_tokens=token_row["total_tokens"] or 0 if token_row else 0,
            input_tokens=token_row["input_tokens"] or 0 if token_row else 0,
            output_tokens=token_row["output_tokens"] or 0 if token_row else 0,
            total_sessions=token_row["total_sessions"] or 0 if token_row else 0,
            total_conversations=token_row["total_traces"] or 0 if token_row else 0,
            avg_duration_ms=int(token_row["avg_duration"] or 0) if token_row and token_row["avg_duration"] else 0,
            top_tools=top_tools,
            top_skills=top_skills,
            top_mcp_tools=top_mcp_tools,
            mcp_servers=mcp_servers,
            daily_trend=[],
        )

    async def get_growth_stats(
        self,
        source_id: str,
        start_date: datetime,
        end_date: datetime,
        time_range: str = "day",
    ) -> dict[str, Any]:
        """获取环比增长统计."""
        # Calculate previous period based on time_range
        period_days = 1
        if time_range == "week":
            period_days = 7
        elif time_range == "month":
            period_days = 30
        elif time_range == "custom":
            period_days = (end_date - start_date).days

        prev_start = start_date - timedelta(days=period_days)
        prev_end = start_date - timedelta(seconds=1)

        async def get_stats(s: datetime, e: datetime) -> dict:
            if source_id == "all":
                exclude_placeholders = ", ".join(["%s"] * len(EXCLUDED_SOURCE_IDS))
                query = f"""
                    SELECT
                        COUNT(*) as calls,
                        COALESCE(SUM(total_tokens), 0) as tokens,
                        COUNT(DISTINCT session_id) as sessions,
                        COUNT(DISTINCT user_id) as users,
                        COUNT(DISTINCT source_id) as platforms,
                        AVG(duration_ms) as avg_duration
                    FROM swe_tracing_traces
                    WHERE start_time >= %s AND start_time <= %s
                      AND source_id NOT IN ({exclude_placeholders})
                      AND user_id != 'default'
                """
                row = await self._db.fetch_one(query, (s, e, *EXCLUDED_SOURCE_IDS))
            else:
                query = """
                    SELECT
                        COUNT(*) as calls,
                        COALESCE(SUM(total_tokens), 0) as tokens,
                        COUNT(DISTINCT session_id) as sessions,
                        COUNT(DISTINCT user_id) as users,
                        COUNT(DISTINCT channel) as platforms,
                        AVG(duration_ms) as avg_duration
                    FROM swe_tracing_traces
                    WHERE source_id = %s AND start_time >= %s AND start_time <= %s
                      AND user_id != 'default'
                """
                row = await self._db.fetch_one(query, (source_id, s, e))
            return {
                "calls": row["calls"] or 0,
                "tokens": row["tokens"] or 0,
                "sessions": row["sessions"] or 0,
                "users": row["users"] or 0,
                "platforms": row["platforms"] or 0,
                "avg_duration": float(row["avg_duration"] or 0),
            }

        curr = await get_stats(start_date, end_date)
        prev = await get_stats(prev_start, prev_end)

        def calc_growth(curr_val: float, prev_val: float) -> float:
            if prev_val == 0:
                return 100.0 if curr_val > 0 else 0.0
            return round(((curr_val - prev_val) / prev_val) * 100, 1)

        return {
            "callsGrowth": calc_growth(curr["calls"], prev["calls"]),
            "tokensGrowth": calc_growth(curr["tokens"], prev["tokens"]),
            "sessionGrowth": calc_growth(curr["sessions"], prev["sessions"]),
            "userGrowth": calc_growth(curr["users"], prev["users"]),
            "platformGrowth": calc_growth(curr["platforms"], prev["platforms"]),
            "avgDurationGrowth": calc_growth(curr["avg_duration"], prev["avg_duration"]),
        }

    async def get_daily_trend(
        self,
        source_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> list[dict[str, Any]]:
        """获取日趋势数据."""
        if start_date is None:
            start_date = datetime.now() - timedelta(days=30)
        if end_date is None:
            end_date = datetime.now() + timedelta(days=1)

        if source_id == "all":
            exclude_placeholders = ", ".join(["%s"] * len(EXCLUDED_SOURCE_IDS))
            query = f"""
                SELECT
                    DATE(start_time) as date,
                    COUNT(*) as calls,
                    COALESCE(SUM(total_tokens), 0) as tokens,
                    COUNT(DISTINCT user_id) as users
                FROM swe_tracing_traces
                WHERE start_time >= %s AND start_time <= %s
                  AND source_id NOT IN ({exclude_placeholders})
                  AND user_id != 'default'
                GROUP BY DATE(start_time)
                ORDER BY date
            """
            rows = await self._db.fetch_all(query, (start_date, end_date, *EXCLUDED_SOURCE_IDS))
        else:
            query = """
                SELECT
                    DATE(start_time) as date,
                    COUNT(*) as calls,
                    COALESCE(SUM(total_tokens), 0) as tokens,
                    COUNT(DISTINCT user_id) as users
                FROM swe_tracing_traces
                WHERE source_id = %s AND start_time >= %s AND start_time <= %s
                  AND user_id != 'default'
                GROUP BY DATE(start_time)
                ORDER BY date
            """
            rows = await self._db.fetch_all(query, (source_id, start_date, end_date))

        return [
            {
                "date": row["date"].strftime("%Y-%m-%d") if row["date"] else "",
                "calls": row["calls"] or 0,
                "tokens": row["tokens"] or 0,
                "users": row["users"] or 0,
            }
            for row in rows
        ]

    async def get_channel_distribution(
        self,
        source_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> dict[str, Any]:
        """获取渠道分布统计."""
        if start_date is None:
            start_date = datetime.now() - timedelta(days=30)
        if end_date is None:
            end_date = datetime.now() + timedelta(days=1)

        if source_id == "all":
            exclude_placeholders = ", ".join(["%s"] * len(EXCLUDED_SOURCE_IDS))
            query = f"""
                SELECT
                    source_id,
                    COUNT(DISTINCT user_id) as user_count,
                    COUNT(*) as call_count,
                    SUM(total_tokens) as token_count
                FROM swe_tracing_traces
                WHERE start_time >= %s AND start_time <= %s
                  AND source_id IS NOT NULL AND source_id != ''
                  AND source_id NOT IN ({exclude_placeholders})
                  AND user_id != 'default'
                GROUP BY source_id
                ORDER BY call_count DESC
            """
            rows = await self._db.fetch_all(query, (start_date, end_date, *EXCLUDED_SOURCE_IDS))
        else:
            query = """
                SELECT
                    source_id,
                    COUNT(DISTINCT user_id) as user_count,
                    COUNT(*) as call_count,
                    SUM(total_tokens) as token_count
                FROM swe_tracing_traces
                WHERE source_id = %s AND start_time >= %s AND start_time <= %s
                  AND user_id != 'default'
                GROUP BY source_id
                ORDER BY call_count DESC
            """
            rows = await self._db.fetch_all(query, (source_id, start_date, end_date))

        platform_user_dist = []
        platform_call_dist = []
        sources = []

        for row in rows:
            src_id = row["source_id"]
            sources.append(src_id)
            platform_user_dist.append({"name": src_id, "value": row["user_count"] or 0})
            platform_call_dist.append({"name": src_id, "value": row["call_count"] or 0})

        return {
            "platformUserDistribution": platform_user_dist,
            "platformCallDistribution": platform_call_dist,
            "totalPlatforms": len(sources),
        }

    async def get_sources(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> list[str]:
        """获取平台来源列表."""
        if start_date is None:
            start_date = datetime.now() - timedelta(days=30)
        if end_date is None:
            end_date = datetime.now() + timedelta(days=1)

        exclude_placeholders = ", ".join(["%s"] * len(EXCLUDED_SOURCE_IDS))
        query = f"""
            SELECT DISTINCT source_id
            FROM swe_tracing_traces
            WHERE start_time >= %s AND start_time <= %s
              AND source_id IS NOT NULL AND source_id != ''
              AND source_id NOT IN ({exclude_placeholders})
            ORDER BY source_id
        """
        rows = await self._db.fetch_all(query, (start_date, end_date, *EXCLUDED_SOURCE_IDS))
        return [row["source_id"] for row in rows]

    # ===== 用户分析 =====

    async def get_users(
        self,
        source_id: str,
        page: int = 1,
        page_size: int = 20,
        user_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        sort_by: Optional[str] = None,
    ) -> tuple[list[UserListItem], int]:
        """获取用户列表."""
        order_by = "last_active DESC"
        if sort_by == "conversations":
            order_by = "total_conversations DESC"
        elif sort_by == "last_active":
            order_by = "last_active DESC"

        if source_id == "all":
            exclude_placeholders = ", ".join(["%s"] * len(EXCLUDED_SOURCE_IDS))
            where_clauses = [f"source_id NOT IN ({exclude_placeholders})"]
            params: list[Any] = list(EXCLUDED_SOURCE_IDS)
        else:
            where_clauses = ["source_id = %s"]
            params = [source_id]

        where_clauses.append("user_id != 'default'")

        if user_id:
            where_clauses.append("user_id LIKE %s")
            params.append(f"%{user_id}%")
        if start_date:
            where_clauses.append("start_time >= %s")
            params.append(start_date)
        if end_date:
            where_clauses.append("start_time <= %s")
            params.append(end_date)

        where_sql = " AND ".join(where_clauses)

        count_query = f"SELECT COUNT(DISTINCT user_id) as total FROM swe_tracing_traces WHERE {where_sql}"
        count_row = await self._db.fetch_one(count_query, tuple(params))
        total = count_row["total"] if count_row else 0

        offset = (page - 1) * page_size
        if source_id == "all":
            query = f"""
                SELECT t.user_id,
                       COUNT(DISTINCT t.session_id) as total_sessions,
                       COUNT(*) as total_conversations,
                       SUM(t.total_tokens) as total_tokens,
                       MAX(t.start_time) as last_active,
                       (SELECT COUNT(*) FROM swe_tracing_spans s
                        WHERE s.trace_id IN (SELECT trace_id FROM swe_tracing_traces WHERE user_id = t.user_id)
                        AND s.event_type = 'skill_invocation') as total_skills,
                       (SELECT user_name FROM swe_tracing_traces t2
                        WHERE t2.user_id = t.user_id AND t2.user_name IS NOT NULL
                        ORDER BY t2.start_time DESC LIMIT 1) as user_name,
                       (SELECT bbk_id FROM swe_tracing_traces t3
                        WHERE t3.user_id = t.user_id AND t3.bbk_id IS NOT NULL
                        ORDER BY t3.start_time DESC LIMIT 1) as bbk_id
                FROM swe_tracing_traces t
                WHERE {where_sql}
                GROUP BY t.user_id
                ORDER BY {order_by}
                LIMIT %s OFFSET %s
            """
            params.extend([page_size, offset])
        else:
            query = f"""
                SELECT t.user_id,
                       COUNT(DISTINCT t.session_id) as total_sessions,
                       COUNT(*) as total_conversations,
                       SUM(t.total_tokens) as total_tokens,
                       MAX(t.start_time) as last_active,
                       (SELECT COUNT(*) FROM swe_tracing_spans s
                        WHERE s.source_id = %s
                        AND s.trace_id IN (SELECT trace_id FROM swe_tracing_traces WHERE user_id = t.user_id AND source_id = %s)
                        AND s.event_type = 'skill_invocation') as total_skills,
                       (SELECT user_name FROM swe_tracing_traces t2
                        WHERE t2.user_id = t.user_id AND t2.source_id = %s AND t2.user_name IS NOT NULL
                        ORDER BY t2.start_time DESC LIMIT 1) as user_name,
                       (SELECT bbk_id FROM swe_tracing_traces t3
                        WHERE t3.user_id = t.user_id AND t3.source_id = %s AND t3.bbk_id IS NOT NULL
                        ORDER BY t3.start_time DESC LIMIT 1) as bbk_id
                FROM swe_tracing_traces t
                WHERE {where_sql}
                GROUP BY t.user_id
                ORDER BY {order_by}
                LIMIT %s OFFSET %s
            """
            params = [source_id, source_id, source_id, source_id] + params + [page_size, offset]

        rows = await self._db.fetch_all(query, tuple(params))
        users = [
            UserListItem(
                user_id=row["user_id"],
                user_name=row["user_name"],
                bbk_id=row["bbk_id"],
                total_sessions=row["total_sessions"] or 0,
                total_conversations=row["total_conversations"] or 0,
                total_tokens=row["total_tokens"] or 0,
                total_skills=row["total_skills"] or 0,
                last_active=row["last_active"],
            )
            for row in rows
        ]
        return users, total

    async def get_user_stats(
        self,
        source_id: str,
        user_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> UserStats:
        """获取用户统计详情."""
        if start_date is None:
            start_date = datetime.now() - timedelta(days=30)
        if end_date is None:
            end_date = datetime.now()

        if source_id == "all":
            stats_query = """
                SELECT
                    COUNT(DISTINCT session_id) as total_sessions,
                    COUNT(*) as total_conversations,
                    SUM(total_input_tokens) as input_tokens,
                    SUM(total_output_tokens) as output_tokens,
                    SUM(total_tokens) as total_tokens,
                    AVG(duration_ms) as avg_duration
                FROM swe_tracing_traces
                WHERE user_id = %s AND start_time >= %s AND start_time <= %s
            """
            stats_row = await self._db.fetch_one(stats_query, (user_id, start_date, end_date))
        else:
            stats_query = """
                SELECT
                    COUNT(DISTINCT session_id) as total_sessions,
                    COUNT(*) as total_conversations,
                    SUM(total_input_tokens) as input_tokens,
                    SUM(total_output_tokens) as output_tokens,
                    SUM(total_tokens) as total_tokens,
                    AVG(duration_ms) as avg_duration
                FROM swe_tracing_traces
                WHERE source_id = %s AND user_id = %s AND start_time >= %s AND start_time <= %s
            """
            stats_row = await self._db.fetch_one(stats_query, (source_id, user_id, start_date, end_date))

        model_usage = await self._get_user_model_usage(source_id, user_id, start_date, end_date)
        tools_used = await self._get_user_tool_usage(source_id, user_id, start_date, end_date)
        skills_used = await self._get_user_skill_usage(source_id, user_id, start_date, end_date)

        return UserStats(
            user_id=user_id,
            model_usage=model_usage,
            total_tokens=stats_row["total_tokens"] or 0 if stats_row else 0,
            input_tokens=stats_row["input_tokens"] or 0 if stats_row else 0,
            output_tokens=stats_row["output_tokens"] or 0 if stats_row else 0,
            total_sessions=stats_row["total_sessions"] or 0 if stats_row else 0,
            total_conversations=stats_row["total_conversations"] or 0 if stats_row else 0,
            avg_duration_ms=int(stats_row["avg_duration"] or 0) if stats_row and stats_row["avg_duration"] else 0,
            tools_used=tools_used,
            skills_used=skills_used,
        )
```

- [ ] **Step 3: 添加私有辅助方法**

在 `query_service.py` 文件末尾继续添加私有辅助方法：

```python
    # ===== 私有辅助方法 =====

    async def _get_total_users(self, source_id: str, start_date: datetime, end_date: datetime) -> int:
        """获取用户总数."""
        if source_id == "all":
            exclude_placeholders = ", ".join(["%s"] * len(EXCLUDED_SOURCE_IDS))
            query = f"""
                SELECT COUNT(DISTINCT user_id) as total_users
                FROM swe_tracing_traces
                WHERE start_time >= %s AND start_time <= %s
                  AND source_id NOT IN ({exclude_placeholders})
                  AND user_id != 'default'
            """
            row = await self._db.fetch_one(query, (start_date, end_date, *EXCLUDED_SOURCE_IDS))
        else:
            query = """
                SELECT COUNT(DISTINCT user_id) as total_users
                FROM swe_tracing_traces
                WHERE source_id = %s AND start_time >= %s AND start_time <= %s
                  AND user_id != 'default'
            """
            row = await self._db.fetch_one(query, (source_id, start_date, end_date))
        return row["total_users"] if row else 0

    async def _get_online_users(self, source_id: str) -> tuple[int, list[str]]:
        """获取在线用户."""
        online_threshold = datetime.now() - timedelta(minutes=5)
        if source_id == "all":
            query = """
                SELECT DISTINCT user_id
                FROM swe_tracing_spans
                WHERE start_time >= %s AND user_id IS NOT NULL AND user_id != ''
            """
            rows = await self._db.fetch_all(query, (online_threshold,))
        else:
            query = """
                SELECT DISTINCT user_id
                FROM swe_tracing_spans
                WHERE source_id = %s AND start_time >= %s AND user_id IS NOT NULL AND user_id != ''
            """
            rows = await self._db.fetch_all(query, (source_id, online_threshold))
        user_ids = [row["user_id"] for row in rows if row["user_id"]]
        return len(user_ids), user_ids

    async def _get_token_stats(self, source_id: str, start_date: datetime, end_date: datetime) -> Optional[dict]:
        """获取 Token 统计."""
        if source_id == "all":
            exclude_placeholders = ", ".join(["%s"] * len(EXCLUDED_SOURCE_IDS))
            query = f"""
                SELECT
                    SUM(total_input_tokens) as input_tokens,
                    SUM(total_output_tokens) as output_tokens,
                    SUM(total_tokens) as total_tokens,
                    COUNT(*) as total_traces,
                    COUNT(DISTINCT session_id) as total_sessions,
                    AVG(duration_ms) as avg_duration
                FROM swe_tracing_traces
                WHERE start_time >= %s AND start_time <= %s
                  AND source_id NOT IN ({exclude_placeholders})
                  AND user_id != 'default'
            """
            return await self._db.fetch_one(query, (start_date, end_date, *EXCLUDED_SOURCE_IDS))
        else:
            query = """
                SELECT
                    SUM(total_input_tokens) as input_tokens,
                    SUM(total_output_tokens) as output_tokens,
                    SUM(total_tokens) as total_tokens,
                    COUNT(*) as total_traces,
                    COUNT(DISTINCT session_id) as total_sessions,
                    AVG(duration_ms) as avg_duration
                FROM swe_tracing_traces
                WHERE source_id = %s AND start_time >= %s AND start_time <= %s
                  AND user_id != 'default'
            """
            return await self._db.fetch_one(query, (source_id, start_date, end_date))

    async def _get_model_distribution(self, source_id: str, start_date: datetime, end_date: datetime) -> list[ModelUsage]:
        """获取模型分布."""
        if source_id == "all":
            exclude_placeholders = ", ".join(["%s"] * len(EXCLUDED_SOURCE_IDS))
            query = f"""
                SELECT model_name, COUNT(*) as count,
                       SUM(total_input_tokens) as input_tokens,
                       SUM(total_output_tokens) as output_tokens,
                       SUM(total_tokens) as total_tokens
                FROM swe_tracing_traces
                WHERE start_time >= %s AND start_time <= %s AND model_name IS NOT NULL
                  AND source_id NOT IN ({exclude_placeholders})
                  AND user_id != 'default'
                GROUP BY model_name
                ORDER BY count DESC
                LIMIT 10
            """
            rows = await self._db.fetch_all(query, (start_date, end_date, *EXCLUDED_SOURCE_IDS))
        else:
            query = """
                SELECT model_name, COUNT(*) as count,
                       SUM(total_input_tokens) as input_tokens,
                       SUM(total_output_tokens) as output_tokens,
                       SUM(total_tokens) as total_tokens
                FROM swe_tracing_traces
                WHERE source_id = %s AND start_time >= %s AND start_time <= %s AND model_name IS NOT NULL
                  AND user_id != 'default'
                GROUP BY model_name
                ORDER BY count DESC
                LIMIT 10
            """
            rows = await self._db.fetch_all(query, (source_id, start_date, end_date))
        return [
            ModelUsage(
                model_name=row["model_name"],
                count=row["count"] or 0,
                total_tokens=row["total_tokens"] or 0,
                input_tokens=row["input_tokens"] or 0,
                output_tokens=row["output_tokens"] or 0,
            )
            for row in rows
        ]

    async def _get_top_tools(self, source_id: str, start_date: datetime, end_date: datetime) -> list[ToolUsage]:
        """获取热门工具."""
        if source_id == "all":
            exclude_placeholders = ", ".join(["%s"] * len(EXCLUDED_SOURCE_IDS))
            query = f"""
                SELECT tool_name, COUNT(*) as count,
                       AVG(duration_ms) as avg_duration,
                       SUM(CASE WHEN error IS NOT NULL THEN 1 ELSE 0 END) as error_count
                FROM swe_tracing_spans
                WHERE start_time >= %s AND start_time <= %s
                  AND event_type = 'tool_call_end'
                  AND tool_name IS NOT NULL
                  AND mcp_server IS NULL
                  AND source_id NOT IN ({exclude_placeholders})
                  AND user_id != 'default'
                GROUP BY tool_name
                ORDER BY count DESC
                LIMIT 10
            """
            rows = await self._db.fetch_all(query, (start_date, end_date, *EXCLUDED_SOURCE_IDS))
        else:
            query = """
                SELECT tool_name, COUNT(*) as count,
                       AVG(duration_ms) as avg_duration,
                       SUM(CASE WHEN error IS NOT NULL THEN 1 ELSE 0 END) as error_count
                FROM swe_tracing_spans
                WHERE source_id = %s AND start_time >= %s AND start_time <= %s
                  AND event_type = 'tool_call_end'
                  AND tool_name IS NOT NULL
                  AND mcp_server IS NULL
                  AND user_id != 'default'
                GROUP BY tool_name
                ORDER BY count DESC
                LIMIT 10
            """
            rows = await self._db.fetch_all(query, (source_id, start_date, end_date))
        return [
            ToolUsage(
                tool_name=row["tool_name"],
                count=row["count"] or 0,
                avg_duration_ms=int(row["avg_duration"] or 0),
                error_count=row["error_count"] or 0,
            )
            for row in rows
        ]

    async def _get_top_skills(self, source_id: str, start_date: datetime, end_date: datetime) -> list[SkillUsage]:
        """获取热门技能."""
        if source_id == "all":
            exclude_placeholders = ", ".join(["%s"] * len(EXCLUDED_SOURCE_IDS))
            query = f"""
                SELECT skill_name, COUNT(*) as count,
                       AVG(duration_ms) as avg_duration
                FROM swe_tracing_spans
                WHERE start_time >= %s AND start_time <= %s
                  AND event_type = 'skill_invocation'
                  AND skill_name IS NOT NULL
                  AND source_id NOT IN ({exclude_placeholders})
                  AND user_id != 'default'
                GROUP BY skill_name
                ORDER BY count DESC
                LIMIT 10
            """
            rows = await self._db.fetch_all(query, (start_date, end_date, *EXCLUDED_SOURCE_IDS))
        else:
            query = """
                SELECT skill_name, COUNT(*) as count,
                       AVG(duration_ms) as avg_duration
                FROM swe_tracing_spans
                WHERE source_id = %s AND start_time >= %s AND start_time <= %s
                  AND event_type = 'skill_invocation'
                  AND skill_name IS NOT NULL
                  AND user_id != 'default'
                GROUP BY skill_name
                ORDER BY count DESC
                LIMIT 10
            """
            rows = await self._db.fetch_all(query, (source_id, start_date, end_date))
        return [
            SkillUsage(
                skill_name=row["skill_name"],
                count=row["count"] or 0,
                avg_duration_ms=int(row["avg_duration"] or 0),
            )
            for row in rows
        ]

    async def _get_mcp_stats(
        self, source_id: str, start_date: datetime, end_date: datetime
    ) -> tuple[list[MCPToolUsage], list[MCPServerUsage]]:
        """获取 MCP 统计."""
        if source_id == "all":
            exclude_placeholders = ", ".join(["%s"] * len(EXCLUDED_SOURCE_IDS))
            mcp_tool_query = f"""
                SELECT tool_name, mcp_server, COUNT(*) as count,
                       AVG(duration_ms) as avg_duration,
                       SUM(CASE WHEN error IS NOT NULL THEN 1 ELSE 0 END) as error_count
                FROM swe_tracing_spans
                WHERE start_time >= %s AND start_time <= %s
                  AND event_type = 'tool_call_end'
                  AND mcp_server IS NOT NULL
                  AND source_id NOT IN ({exclude_placeholders})
                  AND user_id != 'default'
                GROUP BY tool_name, mcp_server
                ORDER BY count DESC
                LIMIT 10
            """
            mcp_tool_rows = await self._db.fetch_all(query=mcp_tool_query, params=(start_date, end_date, *EXCLUDED_SOURCE_IDS))
        else:
            mcp_tool_query = """
                SELECT tool_name, mcp_server, COUNT(*) as count,
                       AVG(duration_ms) as avg_duration,
                       SUM(CASE WHEN error IS NOT NULL THEN 1 ELSE 0 END) as error_count
                FROM swe_tracing_spans
                WHERE source_id = %s AND start_time >= %s AND start_time <= %s
                  AND event_type = 'tool_call_end'
                  AND mcp_server IS NOT NULL
                  AND user_id != 'default'
                GROUP BY tool_name, mcp_server
                ORDER BY count DESC
                LIMIT 10
            """
            mcp_tool_rows = await self._db.fetch_all(query=mcp_tool_query, params=(source_id, start_date, end_date))

        top_mcp_tools = [
            MCPToolUsage(
                tool_name=row["tool_name"],
                mcp_server=row["mcp_server"],
                count=row["count"] or 0,
                avg_duration_ms=int(row["avg_duration"] or 0),
                error_count=row["error_count"] or 0,
            )
            for row in mcp_tool_rows
        ]

        # 获取 MCP 服务器统计（简化版本）
        mcp_servers = await self._get_mcp_servers(source_id, start_date, end_date)
        return top_mcp_tools, mcp_servers

    async def _get_mcp_servers(self, source_id: str, start_date: datetime, end_date: datetime) -> list[MCPServerUsage]:
        """获取 MCP 服务器统计."""
        if source_id == "all":
            exclude_placeholders = ", ".join(["%s"] * len(EXCLUDED_SOURCE_IDS))
            query = f"""
                SELECT mcp_server,
                       COUNT(DISTINCT tool_name) as tool_count,
                       COUNT(*) as total_calls,
                       AVG(duration_ms) as avg_duration,
                       SUM(CASE WHEN error IS NOT NULL THEN 1 ELSE 0 END) as error_count
                FROM swe_tracing_spans
                WHERE start_time >= %s AND start_time <= %s
                  AND event_type = 'tool_call_end'
                  AND mcp_server IS NOT NULL
                  AND source_id NOT IN ({exclude_placeholders})
                  AND user_id != 'default'
                GROUP BY mcp_server
                ORDER BY total_calls DESC
            """
            server_rows = await self._db.fetch_all(query, (start_date, end_date, *EXCLUDED_SOURCE_IDS))
        else:
            query = """
                SELECT mcp_server,
                       COUNT(DISTINCT tool_name) as tool_count,
                       COUNT(*) as total_calls,
                       AVG(duration_ms) as avg_duration,
                       SUM(CASE WHEN error IS NOT NULL THEN 1 ELSE 0 END) as error_count
                FROM swe_tracing_spans
                WHERE source_id = %s AND start_time >= %s AND start_time <= %s
                  AND event_type = 'tool_call_end'
                  AND mcp_server IS NOT NULL
                  AND user_id != 'default'
                GROUP BY mcp_server
                ORDER BY total_calls DESC
            """
            server_rows = await self._db.fetch_all(query, (source_id, start_date, end_date))

        mcp_servers = []
        for server_row in server_rows:
            server_name = server_row["mcp_server"]
            tools = await self._get_server_tools(source_id, start_date, end_date, server_name)
            mcp_servers.append(
                MCPServerUsage(
                    server_name=server_name,
                    tool_count=server_row["tool_count"] or 0,
                    total_calls=server_row["total_calls"] or 0,
                    avg_duration_ms=int(server_row["avg_duration"] or 0),
                    error_count=server_row["error_count"] or 0,
                    tools=tools,
                )
            )
        return mcp_servers

    async def _get_server_tools(
        self, source_id: str, start_date: datetime, end_date: datetime, server_name: str
    ) -> list[MCPToolUsage]:
        """获取服务器工具统计."""
        if source_id == "all":
            query = """
                SELECT tool_name, mcp_server, COUNT(*) as count,
                       AVG(duration_ms) as avg_duration,
                       SUM(CASE WHEN error IS NOT NULL THEN 1 ELSE 0 END) as error_count
                FROM swe_tracing_spans
                WHERE start_time >= %s AND start_time <= %s
                  AND event_type = 'tool_call_end'
                  AND mcp_server = %s
                GROUP BY tool_name, mcp_server
                ORDER BY count DESC
            """
            rows = await self._db.fetch_all(query, (start_date, end_date, server_name))
        else:
            query = """
                SELECT tool_name, mcp_server, COUNT(*) as count,
                       AVG(duration_ms) as avg_duration,
                       SUM(CASE WHEN error IS NOT NULL THEN 1 ELSE 0 END) as error_count
                FROM swe_tracing_spans
                WHERE source_id = %s AND start_time >= %s AND start_time <= %s
                  AND event_type = 'tool_call_end'
                  AND mcp_server = %s
                GROUP BY tool_name, mcp_server
                ORDER BY count DESC
            """
            rows = await self._db.fetch_all(query, (source_id, start_date, end_date, server_name))
        return [
            MCPToolUsage(
                tool_name=r["tool_name"],
                mcp_server=r["mcp_server"],
                count=r["count"] or 0,
                avg_duration_ms=int(r["avg_duration"] or 0),
                error_count=r["error_count"] or 0,
            )
            for r in rows
        ]

    async def _get_user_model_usage(
        self, source_id: str, user_id: str, start_date: datetime, end_date: datetime
    ) -> list[ModelUsage]:
        """获取用户模型使用."""
        if source_id == "all":
            model_query = """
                SELECT model_name, COUNT(*) as count,
                       SUM(total_input_tokens) as input_tokens,
                       SUM(total_output_tokens) as output_tokens,
                       SUM(total_tokens) as total_tokens
                FROM swe_tracing_traces
                WHERE user_id = %s AND start_time >= %s AND start_time <= %s
                      AND model_name IS NOT NULL
                GROUP BY model_name
                ORDER BY count DESC
            """
            model_rows = await self._db.fetch_all(model_query, (user_id, start_date, end_date))
        else:
            model_query = """
                SELECT model_name, COUNT(*) as count,
                       SUM(total_input_tokens) as input_tokens,
                       SUM(total_output_tokens) as output_tokens,
                       SUM(total_tokens) as total_tokens
                FROM swe_tracing_traces
                WHERE source_id = %s AND user_id = %s AND start_time >= %s AND start_time <= %s
                      AND model_name IS NOT NULL
                GROUP BY model_name
                ORDER BY count DESC
            """
            model_rows = await self._db.fetch_all(model_query, (source_id, user_id, start_date, end_date))
        return [
            ModelUsage(
                model_name=row["model_name"],
                count=row["count"],
                total_tokens=row["total_tokens"] or 0,
                input_tokens=row["input_tokens"] or 0,
                output_tokens=row["output_tokens"] or 0,
            )
            for row in model_rows
        ]

    async def _get_user_tool_usage(
        self, source_id: str, user_id: str, start_date: datetime, end_date: datetime
    ) -> list[ToolUsage]:
        """获取用户工具使用."""
        if source_id == "all":
            tool_query = """
                SELECT tool_name, COUNT(*) as count,
                       AVG(duration_ms) as avg_duration,
                       SUM(CASE WHEN error IS NOT NULL THEN 1 ELSE 0 END) as error_count
                FROM swe_tracing_spans
                WHERE user_id = %s AND start_time >= %s AND start_time <= %s
                  AND event_type = 'tool_call_end'
                  AND tool_name IS NOT NULL
                GROUP BY tool_name
                ORDER BY count DESC
            """
            tool_rows = await self._db.fetch_all(tool_query, (user_id, start_date, end_date))
        else:
            tool_query = """
                SELECT tool_name, COUNT(*) as count,
                       AVG(duration_ms) as avg_duration,
                       SUM(CASE WHEN error IS NOT NULL THEN 1 ELSE 0 END) as error_count
                FROM swe_tracing_spans
                WHERE source_id = %s AND user_id = %s AND start_time >= %s AND start_time <= %s
                  AND event_type = 'tool_call_end'
                  AND tool_name IS NOT NULL
                GROUP BY tool_name
                ORDER BY count DESC
            """
            tool_rows = await self._db.fetch_all(tool_query, (source_id, user_id, start_date, end_date))
        return [
            ToolUsage(
                tool_name=row["tool_name"],
                count=row["count"],
                avg_duration_ms=int(row["avg_duration"] or 0),
                error_count=row["error_count"] or 0,
            )
            for row in tool_rows
        ]

    async def _get_user_skill_usage(
        self, source_id: str, user_id: str, start_date: datetime, end_date: datetime
    ) -> list[SkillUsage]:
        """获取用户技能使用."""
        if source_id == "all":
            skill_query = """
                SELECT skill_name, COUNT(*) as count,
                       AVG(duration_ms) as avg_duration
                FROM swe_tracing_spans
                WHERE user_id = %s AND start_time >= %s AND start_time <= %s
                  AND event_type = 'skill_invocation'
                  AND skill_name IS NOT NULL
                GROUP BY skill_name
                ORDER BY count DESC
            """
            skill_rows = await self._db.fetch_all(skill_query, (user_id, start_date, end_date))
        else:
            skill_query = """
                SELECT skill_name, COUNT(*) as count,
                       AVG(duration_ms) as avg_duration
                FROM swe_tracing_spans
                WHERE source_id = %s AND user_id = %s AND start_time >= %s AND start_time <= %s
                  AND event_type = 'skill_invocation'
                  AND skill_name IS NOT NULL
                GROUP BY skill_name
                ORDER BY count DESC
            """
            skill_rows = await self._db.fetch_all(skill_query, (source_id, user_id, start_date, end_date))
        return [
            SkillUsage(
                skill_name=row["skill_name"],
                count=row["count"],
                avg_duration_ms=int(row["avg_duration"] or 0),
            )
            for row in skill_rows
        ]
```

- [ ] **Step 4: Commit**

```bash
git add monitor/src/monitor/app/services/tracing/
git commit -m "feat(monitor): add tracing query service"
```

---

## Task 6: 添加更多查询方法（会话和对话分析）

**Files:**
- Modify: `monitor/src/monitor/app/services/tracing/query_service.py`

- [ ] **Step 1: 添加会话和对话相关方法**

在 `query_service.py` 文件中 `TracingQueryService` 类末尾添加：

```python
    # ===== 会话分析 =====

    async def get_sessions(
        self,
        source_id: str,
        page: int = 1,
        page_size: int = 20,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> tuple[list[SessionListItem], int]:
        """获取会话列表."""
        if source_id == "all":
            where_clauses: list[str] = []
            params: list[Any] = []
        else:
            where_clauses = ["source_id = %s"]
            params = [source_id]

        if user_id:
            where_clauses.append("user_id = %s")
            params.append(user_id)
        if session_id:
            where_clauses.append("session_id LIKE %s")
            params.append(f"%{session_id}%")
        if start_date:
            where_clauses.append("start_time >= %s")
            params.append(start_date)
        if end_date:
            where_clauses.append("start_time <= %s")
            params.append(end_date)

        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

        count_query = f"SELECT COUNT(DISTINCT session_id) as total FROM swe_tracing_traces WHERE {where_sql}"
        count_row = await self._db.fetch_one(count_query, tuple(params))
        total = count_row["total"] if count_row else 0

        offset = (page - 1) * page_size
        if source_id == "all":
            query = f"""
                SELECT t.session_id,
                       t.user_id,
                       t.channel,
                       COUNT(*) as total_traces,
                       SUM(t.total_tokens) as total_tokens,
                       MIN(t.start_time) as first_active,
                       MAX(t.start_time) as last_active,
                       (SELECT COUNT(*) FROM swe_tracing_spans s
                        WHERE s.session_id = t.session_id
                        AND s.event_type = 'skill_invocation') as total_skills,
                       (SELECT t2.user_name FROM swe_tracing_traces t2
                        WHERE t2.user_id = t.user_id AND t2.user_name IS NOT NULL
                        ORDER BY t2.start_time DESC LIMIT 1) as user_name,
                       (SELECT t3.bbk_id FROM swe_tracing_traces t3
                        WHERE t3.user_id = t.user_id AND t3.bbk_id IS NOT NULL
                        ORDER BY t3.start_time DESC LIMIT 1) as bbk_id
                FROM swe_tracing_traces t
                WHERE {where_sql}
                GROUP BY t.session_id, t.user_id, t.channel
                ORDER BY last_active DESC
                LIMIT %s OFFSET %s
            """
            params.extend([page_size, offset])
        else:
            query = f"""
                SELECT t.session_id,
                       t.user_id,
                       t.channel,
                       COUNT(*) as total_traces,
                       SUM(t.total_tokens) as total_tokens,
                       MIN(t.start_time) as first_active,
                       MAX(t.start_time) as last_active,
                       (SELECT COUNT(*) FROM swe_tracing_spans s
                        WHERE s.source_id = %s
                        AND s.session_id = t.session_id
                        AND s.event_type = 'skill_invocation') as total_skills,
                       (SELECT t2.user_name FROM swe_tracing_traces t2
                        WHERE t2.user_id = t.user_id AND t2.source_id = %s AND t2.user_name IS NOT NULL
                        ORDER BY t2.start_time DESC LIMIT 1) as user_name,
                       (SELECT t3.bbk_id FROM swe_tracing_traces t3
                        WHERE t3.user_id = t.user_id AND t3.source_id = %s AND t3.bbk_id IS NOT NULL
                        ORDER BY t3.start_time DESC LIMIT 1) as bbk_id
                FROM swe_tracing_traces t
                WHERE {where_sql}
                GROUP BY t.session_id, t.user_id, t.channel
                ORDER BY last_active DESC
                LIMIT %s OFFSET %s
            """
            params = [source_id, source_id, source_id] + params + [page_size, offset]

        rows = await self._db.fetch_all(query, tuple(params))
        sessions = [
            SessionListItem(
                session_id=row["session_id"],
                user_id=row["user_id"],
                user_name=row["user_name"],
                bbk_id=row["bbk_id"],
                channel=row["channel"],
                total_traces=row["total_traces"] or 0,
                total_tokens=row["total_tokens"] or 0,
                total_skills=row["total_skills"] or 0,
                first_active=row["first_active"],
                last_active=row["last_active"],
            )
            for row in rows
        ]
        return sessions, total

    async def get_session_stats(
        self,
        source_id: str,
        session_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> SessionStats:
        """获取会话统计详情."""
        if start_date is None:
            start_date = datetime.now() - timedelta(days=30)
        if end_date is None:
            end_date = datetime.now()

        stats_row = await self._db.fetch_one(
            """
            SELECT
                user_id,
                channel,
                COUNT(*) as total_traces,
                SUM(total_input_tokens) as input_tokens,
                SUM(total_output_tokens) as output_tokens,
                SUM(total_tokens) as total_tokens,
                AVG(duration_ms) as avg_duration,
                MIN(start_time) as first_active,
                MAX(start_time) as last_active
            FROM swe_tracing_traces
            WHERE source_id = %s AND session_id = %s AND start_time >= %s AND start_time <= %s
            GROUP BY user_id, channel
            """,
            (source_id, session_id, start_date, end_date),
        )

        if not stats_row or not stats_row.get("user_id"):
            return SessionStats(session_id=session_id, user_id="", channel="")

        user_id = stats_row["user_id"]
        channel = stats_row["channel"] or ""

        model_usage = await self._db.fetch_all(
            """
            SELECT model_name, COUNT(*) as count,
                   SUM(total_input_tokens) as input_tokens,
                   SUM(total_output_tokens) as output_tokens,
                   SUM(total_tokens) as total_tokens
            FROM swe_tracing_traces
            WHERE source_id = %s AND session_id = %s AND start_time >= %s AND start_time <= %s
                  AND model_name IS NOT NULL
            GROUP BY model_name
            ORDER BY count DESC
            """,
            (source_id, session_id, start_date, end_date),
        )

        tools_used = await self._db.fetch_all(
            """
            SELECT tool_name, COUNT(*) as count,
                   AVG(duration_ms) as avg_duration,
                   SUM(CASE WHEN error IS NOT NULL THEN 1 ELSE 0 END) as error_count
            FROM swe_tracing_spans
            WHERE source_id = %s AND session_id = %s AND start_time >= %s AND start_time <= %s
              AND event_type = 'tool_call_end'
              AND tool_name IS NOT NULL
              AND mcp_server IS NULL
            GROUP BY tool_name
            ORDER BY count DESC
            """,
            (source_id, session_id, start_date, end_date),
        )

        skills_used = await self._db.fetch_all(
            """
            SELECT skill_name, COUNT(*) as count,
                   AVG(duration_ms) as avg_duration
            FROM swe_tracing_spans
            WHERE source_id = %s AND session_id = %s AND start_time >= %s AND start_time <= %s
              AND event_type = 'skill_invocation'
              AND skill_name IS NOT NULL
            GROUP BY skill_name
            ORDER BY count DESC
            """,
            (source_id, session_id, start_date, end_date),
        )

        mcp_tools_used = await self._db.fetch_all(
            """
            SELECT tool_name, mcp_server, COUNT(*) as count,
                   AVG(duration_ms) as avg_duration,
                   SUM(CASE WHEN error IS NOT NULL THEN 1 ELSE 0 END) as error_count
            FROM swe_tracing_spans
            WHERE source_id = %s AND session_id = %s AND start_time >= %s AND start_time <= %s
              AND event_type = 'tool_call_end'
              AND mcp_server IS NOT NULL
            GROUP BY tool_name, mcp_server
            ORDER BY count DESC
            """,
            (source_id, session_id, start_date, end_date),
        )

        return SessionStats(
            session_id=session_id,
            user_id=user_id,
            channel=channel,
            model_usage=[
                ModelUsage(
                    model_name=row["model_name"],
                    count=row["count"],
                    total_tokens=row["total_tokens"] or 0,
                    input_tokens=row["input_tokens"] or 0,
                    output_tokens=row["output_tokens"] or 0,
                )
                for row in model_usage
            ],
            total_tokens=stats_row["total_tokens"] or 0,
            input_tokens=stats_row["input_tokens"] or 0,
            output_tokens=stats_row["output_tokens"] or 0,
            total_traces=stats_row["total_traces"] or 0,
            avg_duration_ms=int(stats_row["avg_duration"] or 0) if stats_row and stats_row["avg_duration"] else 0,
            tools_used=[
                ToolUsage(
                    tool_name=row["tool_name"],
                    count=row["count"],
                    avg_duration_ms=int(row["avg_duration"] or 0),
                    error_count=row["error_count"] or 0,
                )
                for row in tools_used
            ],
            skills_used=[
                SkillUsage(
                    skill_name=row["skill_name"],
                    count=row["count"],
                    avg_duration_ms=int(row["avg_duration"] or 0),
                )
                for row in skills_used
            ],
            mcp_tools_used=[
                MCPToolUsage(
                    tool_name=row["tool_name"],
                    mcp_server=row["mcp_server"],
                    count=row["count"],
                    avg_duration_ms=int(row["avg_duration"] or 0),
                    error_count=row["error_count"] or 0,
                )
                for row in mcp_tools_used
            ],
            first_active=stats_row["first_active"],
            last_active=stats_row["last_active"],
        )

    # ===== 对话分析 =====

    async def get_traces(
        self,
        source_id: str,
        page: int = 1,
        page_size: int = 20,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        status: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> tuple[list[TraceListItem], int]:
        """获取对话列表."""
        if source_id == "all":
            where_clauses: list[str] = []
            params: list[Any] = []
        else:
            where_clauses = ["source_id = %s"]
            params = [source_id]

        if user_id:
            where_clauses.append("user_id = %s")
            params.append(user_id)
        if session_id:
            where_clauses.append("session_id = %s")
            params.append(session_id)
        if status:
            where_clauses.append("status = %s")
            params.append(status)
        if start_date:
            where_clauses.append("start_time >= %s")
            params.append(start_date)
        if end_date:
            where_clauses.append("start_time <= %s")
            params.append(end_date)

        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

        count_query = f"SELECT COUNT(*) as total FROM swe_tracing_traces WHERE {where_sql}"
        count_row = await self._db.fetch_one(count_query, tuple(params))
        total = count_row["total"] if count_row else 0

        offset = (page - 1) * page_size
        query = f"""
            SELECT t.trace_id, t.source_id, t.user_id, t.session_id, t.channel, t.start_time,
                   t.duration_ms, t.total_tokens, t.total_input_tokens, t.total_output_tokens,
                   t.model_name, t.status,
                   JSON_LENGTH(t.skills_used) as skills_count,
                   COALESCE(t.user_name, (
                       SELECT t2.user_name FROM swe_tracing_traces t2
                       WHERE t2.user_id = t.user_id AND t2.user_name IS NOT NULL
                       ORDER BY t2.start_time DESC LIMIT 1
                   )) as user_name,
                   COALESCE(t.bbk_id, (
                       SELECT t3.bbk_id FROM swe_tracing_traces t3
                       WHERE t3.user_id = t.user_id AND t3.bbk_id IS NOT NULL
                       ORDER BY t3.start_time DESC LIMIT 1
                   )) as bbk_id
            FROM swe_tracing_traces t
            WHERE {where_sql}
            ORDER BY t.start_time DESC
            LIMIT %s OFFSET %s
        """
        params.extend([page_size, offset])
        rows = await self._db.fetch_all(query, tuple(params))
        traces = [
            TraceListItem(
                trace_id=row["trace_id"],
                source_id=row["source_id"],
                user_id=row["user_id"],
                user_name=row["user_name"],
                bbk_id=row["bbk_id"],
                session_id=row["session_id"],
                channel=row["channel"],
                start_time=row["start_time"],
                duration_ms=row["duration_ms"],
                total_tokens=row["total_tokens"] or 0,
                total_input_tokens=row["total_input_tokens"] or 0,
                total_output_tokens=row["total_output_tokens"] or 0,
                model_name=row["model_name"],
                status=row["status"],
                skills_count=row["skills_count"] or 0,
            )
            for row in rows
        ]
        return traces, total

    async def get_trace(self, trace_id: str, source_id: Optional[str] = None) -> Optional[Trace]:
        """获取单个对话."""
        if source_id:
            query = "SELECT * FROM swe_tracing_traces WHERE trace_id = %s AND source_id = %s"
            row = await self._db.fetch_one(query, (trace_id, source_id))
        else:
            query = "SELECT * FROM swe_tracing_traces WHERE trace_id = %s"
            row = await self._db.fetch_one(query, (trace_id,))
        if row is None:
            return None
        return self._row_to_trace(row)

    async def get_spans(self, trace_id: str) -> list[Span]:
        """获取对话的所有 Span."""
        query = "SELECT * FROM swe_tracing_spans WHERE trace_id = %s ORDER BY start_time"
        rows = await self._db.fetch_all(query, (trace_id,))
        return [self._row_to_span(row) for row in rows]

    async def get_trace_detail(self, trace_id: str, source_id: Optional[str] = None) -> Optional[TraceDetail]:
        """获取对话详情."""
        trace = await self.get_trace(trace_id, source_id)
        if trace is None:
            return None

        spans = await self.get_spans(trace_id)

        llm_duration = sum(
            s.duration_ms or 0
            for s in spans
            if s.event_type in (EventType.LLM_INPUT, EventType.LLM_OUTPUT)
        )
        tool_duration = sum(
            s.duration_ms or 0
            for s in spans
            if s.event_type in (EventType.TOOL_CALL_START, EventType.TOOL_CALL_END)
        )

        tools_called = []
        tool_spans = [s for s in spans if s.event_type == EventType.TOOL_CALL_END]
        for span in tool_spans:
            tools_called.append({
                "tool_name": span.tool_name or span.name,
                "tool_input": span.tool_input,
                "tool_output": span.tool_output,
                "duration_ms": span.duration_ms,
                "error": span.error,
            })

        return TraceDetail(
            trace=trace,
            spans=spans,
            llm_duration_ms=llm_duration,
            tool_duration_ms=tool_duration,
            tools_called=tools_called,
        )

    async def get_trace_detail_with_timeline(
        self, trace_id: str, source_id: Optional[str] = None
    ) -> Optional[TraceDetailWithTimeline]:
        """获取对话详情（带时间线）."""
        trace = await self.get_trace(trace_id, source_id)
        if trace is None:
            return None

        spans = await self.get_spans(trace_id)
        timeline = self._build_timeline(spans)
        skill_invocations = self._build_skill_invocations(spans)

        llm_duration = sum(
            s.duration_ms or 0
            for s in spans
            if s.event_type in (EventType.LLM_INPUT, EventType.LLM_OUTPUT)
        )
        tool_duration = sum(
            s.duration_ms or 0
            for s in spans
            if s.event_type in (EventType.TOOL_CALL_START, EventType.TOOL_CALL_END)
        )
        skill_duration = sum(inv.duration_ms for inv in skill_invocations)

        return TraceDetailWithTimeline(
            trace=trace,
            spans=spans,
            timeline=timeline,
            skill_invocations=skill_invocations,
            llm_duration_ms=llm_duration,
            tool_duration_ms=tool_duration,
            skill_duration_ms=skill_duration,
            total_skills=len(skill_invocations),
            total_tools=len([s for s in spans if s.event_type == EventType.TOOL_CALL_END]),
            total_llm_calls=len([s for s in spans if s.event_type == EventType.LLM_INPUT]),
        )

    # ===== 用户消息 =====

    async def get_user_messages(
        self,
        source_id: str,
        page: int = 1,
        page_size: int = 20,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        query_text: Optional[str] = None,
        export: bool = False,
    ) -> tuple[list[UserMessageItem], int]:
        """获取用户消息列表."""
        if start_date is None:
            start_date = datetime.now() - timedelta(days=7)
        if end_date is None:
            end_date = datetime.now()

        if source_id == "all":
            where_clauses = ["start_time >= %s", "start_time <= %s"]
            params: list[Any] = [start_date, end_date]
        else:
            where_clauses = ["source_id = %s", "start_time >= %s", "start_time <= %s"]
            params = [source_id, start_date, end_date]

        if user_id:
            where_clauses.append("user_id = %s")
            params.append(user_id)
        if session_id:
            where_clauses.append("session_id = %s")
            params.append(session_id)
        if query_text:
            where_clauses.append("user_message LIKE %s")
            params.append(f"%{query_text}%")

        where_sql = " AND ".join(where_clauses)

        count_query = f"SELECT COUNT(*) as total FROM swe_tracing_traces WHERE {where_sql}"
        count_row = await self._db.fetch_one(count_query, tuple(params))
        total = count_row["total"] if count_row else 0

        if export:
            sql_query = f"""
                SELECT t.trace_id, t.source_id, t.user_id, t.session_id, t.channel, t.user_message,
                       t.total_input_tokens, t.total_output_tokens, t.model_name,
                       t.start_time, t.duration_ms,
                       COALESCE(t.user_name, (
                           SELECT t2.user_name FROM swe_tracing_traces t2
                           WHERE t2.user_id = t.user_id AND t2.user_name IS NOT NULL
                           ORDER BY t2.start_time DESC LIMIT 1
                       )) as user_name,
                       COALESCE(t.bbk_id, (
                           SELECT t3.bbk_id FROM swe_tracing_traces t3
                           WHERE t3.user_id = t.user_id AND t3.bbk_id IS NOT NULL
                           ORDER BY t3.start_time DESC LIMIT 1
                       )) as bbk_id
                FROM swe_tracing_traces t
                WHERE {where_sql}
                ORDER BY t.start_time DESC
            """
            rows = await self._db.fetch_all(sql_query, tuple(params))
        else:
            offset = (page - 1) * page_size
            sql_query = f"""
                SELECT t.trace_id, t.source_id, t.user_id, t.session_id, t.channel, t.user_message,
                       t.total_input_tokens, t.total_output_tokens, t.model_name,
                       t.start_time, t.duration_ms,
                       COALESCE(t.user_name, (
                           SELECT t2.user_name FROM swe_tracing_traces t2
                           WHERE t2.user_id = t.user_id AND t2.user_name IS NOT NULL
                           ORDER BY t2.start_time DESC LIMIT 1
                       )) as user_name,
                       COALESCE(t.bbk_id, (
                           SELECT t3.bbk_id FROM swe_tracing_traces t3
                           WHERE t3.user_id = t.user_id AND t3.bbk_id IS NOT NULL
                           ORDER BY t3.start_time DESC LIMIT 1
                       )) as bbk_id
                FROM swe_tracing_traces t
                WHERE {where_sql}
                ORDER BY t.start_time DESC
                LIMIT %s OFFSET %s
            """
            params.extend([page_size, offset])
            rows = await self._db.fetch_all(sql_query, tuple(params))

        messages = [
            UserMessageItem(
                trace_id=row["trace_id"],
                source_id=row["source_id"],
                user_id=row["user_id"],
                user_name=row["user_name"],
                bbk_id=row["bbk_id"],
                session_id=row["session_id"],
                channel=row["channel"],
                user_message=row["user_message"],
                input_tokens=row["total_input_tokens"] or 0,
                output_tokens=row["total_output_tokens"] or 0,
                model_name=row["model_name"],
                start_time=row["start_time"],
                duration_ms=row["duration_ms"],
            )
            for row in rows
        ]
        return messages, total

    # ===== 辅助方法 =====

    def _build_timeline(self, spans: list[Span]) -> list[TimelineEvent]:
        """构建时间线."""
        spans = sorted(spans, key=lambda s: s.start_time)

        timeline: list[TimelineEvent] = []
        skill_stack: list[TimelineEvent] = []

        for span in spans:
            if span.event_type == EventType.SKILL_INVOCATION:
                event = TimelineEvent(
                    event_type="skill_invocation",
                    span_id=span.span_id,
                    start_time=span.start_time,
                    end_time=span.end_time,
                    duration_ms=span.duration_ms or 0,
                    skill_name=span.skill_name,
                    confidence=1.0,
                    trigger_reason="declared",
                    children=[],
                )

                if skill_stack:
                    skill_stack[-1].children.append(event)
                else:
                    timeline.append(event)

                skill_stack.append(event)

            elif span.event_type == EventType.TOOL_CALL_END:
                event = TimelineEvent(
                    event_type="tool_call",
                    span_id=span.span_id,
                    start_time=span.start_time,
                    end_time=span.end_time,
                    duration_ms=span.duration_ms or 0,
                    tool_name=span.tool_name,
                    mcp_server=span.mcp_server,
                    skill_weight=None,
                    children=[],
                )

                if skill_stack:
                    skill_stack[-1].children.append(event)
                else:
                    timeline.append(event)

            elif span.event_type == EventType.LLM_INPUT:
                event = TimelineEvent(
                    event_type="llm_call",
                    span_id=span.span_id,
                    start_time=span.start_time,
                    end_time=span.end_time,
                    duration_ms=span.duration_ms or 0,
                    model_name=span.model_name,
                    input_tokens=span.input_tokens,
                    output_tokens=span.output_tokens,
                    children=[],
                )
                timeline.append(event)

        return timeline

    def _build_skill_invocations(self, spans: list[Span]) -> list[SkillCallTimeline]:
        """构建技能调用摘要."""
        skill_spans = [s for s in spans if s.event_type == EventType.SKILL_INVOCATION]

        invocations: list[SkillCallTimeline] = []
        skill_tools: dict[str, list[ToolCallInSkill]] = {}

        for span in spans:
            if span.event_type == EventType.TOOL_CALL_END and span.skill_name:
                skill_name = span.skill_name
                if skill_name not in skill_tools:
                    skill_tools[skill_name] = []

                skill_tools[skill_name].append(
                    ToolCallInSkill(
                        span_id=span.span_id,
                        tool_name=span.tool_name or "",
                        mcp_server=span.mcp_server,
                        start_time=span.start_time,
                        end_time=span.end_time,
                        duration_ms=span.duration_ms or 0,
                        status="error" if span.error else "success",
                        error=span.error,
                        skill_weight=None,
                    )
                )

        for skill_span in skill_spans:
            skill_name = skill_span.skill_name or ""
            tools = skill_tools.get(skill_name, [])

            invocations.append(
                SkillCallTimeline(
                    span_id=skill_span.span_id,
                    skill_name=skill_name,
                    start_time=skill_span.start_time,
                    end_time=skill_span.end_time,
                    duration_ms=skill_span.duration_ms or 0,
                    confidence=1.0,
                    trigger_reason="declared",
                    tools=tools,
                    total_tool_calls=len(tools),
                    tool_duration_ms=sum(t.duration_ms for t in tools),
                )
            )

        return invocations

    def _row_to_trace(self, row: dict) -> Trace:
        """转换数据库行为 Trace 模型."""
        return Trace(
            trace_id=row["trace_id"],
            source_id=row["source_id"],
            user_id=row["user_id"],
            user_name=row.get("user_name"),
            bbk_id=row.get("bbk_id"),
            session_id=row["session_id"],
            channel=row["channel"],
            start_time=row["start_time"],
            end_time=row["end_time"],
            duration_ms=row["duration_ms"],
            model_name=row["model_name"],
            total_input_tokens=row["total_input_tokens"] or 0,
            total_output_tokens=row["total_output_tokens"] or 0,
            tools_used=json.loads(row["tools_used"]) if row["tools_used"] else [],
            skills_used=json.loads(row["skills_used"]) if row["skills_used"] else [],
            status=TraceStatus(row["status"]) if row["status"] else TraceStatus.RUNNING,
            error=row["error"],
            user_message=row.get("user_message"),
        )

    def _row_to_span(self, row: dict) -> Span:
        """转换数据库行为 Span 模型."""
        return Span(
            span_id=row["span_id"],
            trace_id=row["trace_id"],
            source_id=row["source_id"],
            name=row["name"],
            event_type=EventType(row["event_type"]),
            start_time=row["start_time"],
            end_time=row["end_time"],
            duration_ms=row["duration_ms"],
            user_id=row.get("user_id") or "",
            user_name=row.get("user_name"),
            bbk_id=row.get("bbk_id"),
            session_id=row.get("session_id") or "",
            channel=row.get("channel") or "",
            model_name=row["model_name"],
            input_tokens=row["input_tokens"],
            output_tokens=row["output_tokens"],
            tool_name=row["tool_name"],
            skill_name=row["skill_name"],
            mcp_server=row.get("mcp_server"),
            tool_input=json.loads(row["tool_input"]) if row["tool_input"] else None,
            tool_output=row["tool_output"],
            error=row["error"],
        )
```

- [ ] **Step 2: Commit**

```bash
git add monitor/src/monitor/app/services/tracing/query_service.py
git commit -m "feat(monitor): add session, trace and user message query methods"
```

---

## Task 7: 创建导出服务

**Files:**
- Create: `monitor/src/monitor/app/services/tracing/export_service.py`

- [ ] **Step 1: 创建导出服务**

创建 `monitor/src/monitor/app/services/tracing/export_service.py`：

```python
# -*- coding: utf-8 -*-
"""Tracing export service for operational dashboard."""
import csv
import io
import json
import logging
from datetime import datetime
from typing import Optional

from fastapi.responses import StreamingResponse

from .query_service import TracingQueryService

logger = logging.getLogger(__name__)

_EXPORT_HEADERS = [
    "trace_id",
    "user_id",
    "session_id",
    "channel",
    "user_message",
    "input_tokens",
    "output_tokens",
    "model_name",
    "start_time",
    "duration_ms",
]


class TracingExportService:
    """运营看板导出服务."""

    def __init__(self, query_service: TracingQueryService):
        self._query_service = query_service

    @classmethod
    def get_instance(cls) -> "TracingExportService":
        """获取服务实例."""
        return cls(TracingQueryService.get_instance())

    async def export_user_messages_csv(
        self,
        source_id: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        query_text: Optional[str] = None,
    ) -> StreamingResponse:
        """导出用户消息为 CSV 格式."""
        messages, _ = await self._query_service.get_user_messages(
            source_id=source_id,
            user_id=user_id,
            session_id=session_id,
            start_date=start_date,
            end_date=end_date,
            query_text=query_text,
            export=True,
        )

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(_EXPORT_HEADERS)

        for message in messages:
            writer.writerow(self._build_export_row(message))

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=user_messages_{timestamp}.csv"},
        )

    async def export_user_messages_json(
        self,
        source_id: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        query_text: Optional[str] = None,
    ) -> StreamingResponse:
        """导出用户消息为 JSON 格式."""
        messages, _ = await self._query_service.get_user_messages(
            source_id=source_id,
            user_id=user_id,
            session_id=session_id,
            start_date=start_date,
            end_date=end_date,
            query_text=query_text,
            export=True,
        )

        data = [message.model_dump() for message in messages]
        for item in data:
            if item.get("start_time"):
                item["start_time"] = item["start_time"].isoformat()

        content = json.dumps(data, ensure_ascii=False, indent=2)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return StreamingResponse(
            iter([content]),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename=user_messages_{timestamp}.json"},
        )

    async def export_user_messages_xlsx(
        self,
        source_id: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        query_text: Optional[str] = None,
    ) -> StreamingResponse:
        """导出用户消息为 XLSX 格式."""
        try:
            from openpyxl import Workbook
            from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
            from openpyxl.utils import get_column_letter
        except ImportError:
            raise RuntimeError("openpyxl not installed. Use csv or json format.")

        messages, _ = await self._query_service.get_user_messages(
            source_id=source_id,
            user_id=user_id,
            session_id=session_id,
            start_date=start_date,
            end_date=end_date,
            query_text=query_text,
            export=True,
        )

        wb = Workbook()
        ws = wb.active
        ws.title = "User Messages"

        header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
        header_font = Font(bold=True, color="FFFFFF")
        header_alignment = Alignment(horizontal="center", vertical="center")
        thin_border = Border(
            left=Side(style="thin"),
            right=Side(style="thin"),
            top=Side(style="thin"),
            bottom=Side(style="thin"),
        )

        excel_headers = [
            "Trace ID",
            "User ID",
            "Session ID",
            "Channel",
            "User Message",
            "Input Tokens",
            "Output Tokens",
            "Model Name",
            "Start Time",
            "Duration (ms)",
        ]

        for column, header in enumerate(excel_headers, 1):
            cell = ws.cell(row=1, column=column, value=header)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_alignment
            cell.border = thin_border

        for row, message in enumerate(messages, 2):
            for column, value in enumerate(self._build_export_row(message), 1):
                cell = ws.cell(row=row, column=column, value=value)
                cell.border = thin_border
                if column == 5:
                    cell.alignment = Alignment(wrap_text=True, vertical="top")

        for column, width in enumerate([36, 20, 36, 15, 60, 12, 12, 25, 22, 12], 1):
            ws.column_dimensions[get_column_letter(column)].width = width

        excel_buffer = io.BytesIO()
        wb.save(excel_buffer)
        excel_buffer.seek(0)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return StreamingResponse(
            iter([excel_buffer.getvalue()]),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename=user_messages_{timestamp}.xlsx"},
        )

    def _build_export_row(self, message) -> list:
        """构建导出行数据."""
        return [
            message.trace_id,
            message.user_id,
            message.session_id,
            message.channel,
            message.user_message or "",
            message.input_tokens,
            message.output_tokens,
            message.model_name or "",
            message.start_time.isoformat() if message.start_time else "",
            message.duration_ms or "",
        ]
```

- [ ] **Step 2: Commit**

```bash
git add monitor/src/monitor/app/services/tracing/export_service.py
git commit -m "feat(monitor): add tracing export service"
```

---

## Task 8: 创建 API 路由

**Files:**
- Create: `monitor/src/monitor/app/routers/tracing.py`
- Modify: `monitor/src/monitor/app/routers/__init__.py`

- [ ] **Step 1: 创建路由文件**

创建 `monitor/src/monitor/app/routers/tracing.py`：

```python
# -*- coding: utf-8 -*-
"""Tracing API router for operational dashboard."""
import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Query, Request, HTTPException
from fastapi.responses import StreamingResponse

from ..database import get_tracing_db_connection, get_es_client
from ..models.tracing import (
    OverviewStats,
    SessionStats,
    TraceDetail,
    TraceDetailWithTimeline,
    UserStats,
)
from ..services.tracing import TracingQueryService, TracingExportService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tracing", tags=["tracing"])


def _parse_date(date_str: Optional[str], field_name: str, add_day: bool = False) -> Optional[datetime]:
    """解析日期字符串."""
    if not date_str:
        return None
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        if add_day:
            dt = dt + timedelta(days=1)
        return dt
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid {field_name} format") from exc


def _get_source_id(request: Request, query_source_id: Optional[str] = None) -> str:
    """获取 source_id."""
    if query_source_id:
        return query_source_id
    header_source_id = request.headers.get("X-Source-Id")
    if header_source_id:
        return header_source_id
    return "default"


@router.get("/overview", response_model=OverviewStats)
async def get_overview(
    request: Request,
    source_id: Optional[str] = Query(None, description="Source identifier, use 'all' for all platforms"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
) -> OverviewStats:
    """获取运营概览统计."""
    try:
        service = TracingQueryService.get_instance()
    except RuntimeError:
        return OverviewStats()

    actual_source_id = source_id or "all"
    start = _parse_date(start_date, "start_date")
    end = _parse_date(end_date, "end_date", add_day=True)

    return await service.get_overview_stats(actual_source_id, start, end)


@router.get("/users", response_model=dict)
async def get_users(
    request: Request,
    source_id: Optional[str] = Query(None, description="Source identifier"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Page size"),
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    sort_by: Optional[str] = Query(None, description="Sort by field"),
) -> dict:
    """获取用户列表."""
    try:
        service = TracingQueryService.get_instance()
    except RuntimeError:
        return {"items": [], "total": 0, "page": page, "page_size": page_size}

    actual_source_id = source_id or "all"
    start = _parse_date(start_date, "start_date")
    end = _parse_date(end_date, "end_date", add_day=True)

    users, total = await service.get_users(actual_source_id, page, page_size, user_id, start, end, sort_by)
    return {"items": [u.model_dump() for u in users], "total": total, "page": page, "page_size": page_size}


@router.get("/users/{user_id}", response_model=UserStats)
async def get_user_stats(
    user_id: str,
    request: Request,
    source_id: Optional[str] = Query(None, description="Source identifier"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
) -> UserStats:
    """获取用户统计详情."""
    try:
        service = TracingQueryService.get_instance()
    except RuntimeError:
        return UserStats(user_id=user_id)

    actual_source_id = _get_source_id(request, source_id)
    start = _parse_date(start_date, "start_date")
    end = _parse_date(end_date, "end_date", add_day=True)

    return await service.get_user_stats(actual_source_id, user_id, start, end)


@router.get("/traces", response_model=dict)
async def get_traces(
    request: Request,
    source_id: Optional[str] = Query(None, description="Source identifier"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Page size"),
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    session_id: Optional[str] = Query(None, description="Filter by session ID"),
    status: Optional[str] = Query(None, description="Filter by status"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
) -> dict:
    """获取对话列表."""
    try:
        service = TracingQueryService.get_instance()
    except RuntimeError:
        return {"items": [], "total": 0, "page": page, "page_size": page_size}

    actual_source_id = _get_source_id(request, source_id)
    start = _parse_date(start_date, "start_date")
    end = _parse_date(end_date, "end_date", add_day=True)

    traces, total = await service.get_traces(actual_source_id, page, page_size, user_id, session_id, status, start, end)
    return {"items": [t.model_dump() for t in traces], "total": total, "page": page, "page_size": page_size}


@router.get("/traces/{trace_id}", response_model=TraceDetail)
async def get_trace_detail(
    trace_id: str,
    request: Request,
    source_id: Optional[str] = Query(None, description="Source identifier"),
) -> TraceDetail:
    """获取对话详情."""
    try:
        service = TracingQueryService.get_instance()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail="Tracing not available") from exc

    actual_source_id = source_id if source_id else None
    detail = await service.get_trace_detail(trace_id, actual_source_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Trace not found")

    # 从 ES 查询 model_output
    try:
        es_client = get_es_client()
        if es_client and es_client.is_connected:
            model_output = await es_client.get_message(trace_id)
            if model_output:
                detail.trace.model_output = model_output
    except Exception as es_err:
        logger.warning("Failed to query model_output from ES: %s", es_err)

    return detail


@router.get("/traces/{trace_id}/timeline", response_model=TraceDetailWithTimeline)
async def get_trace_timeline(
    trace_id: str,
    request: Request,
    source_id: Optional[str] = Query(None, description="Source identifier"),
) -> TraceDetailWithTimeline:
    """获取对话时间线."""
    try:
        service = TracingQueryService.get_instance()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail="Tracing not available") from exc

    actual_source_id = source_id if source_id else None
    detail = await service.get_trace_detail_with_timeline(trace_id, actual_source_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Trace not found")

    return detail


@router.get("/sessions", response_model=dict)
async def get_sessions(
    request: Request,
    source_id: Optional[str] = Query(None, description="Source identifier"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Page size"),
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    session_id: Optional[str] = Query(None, description="Filter by session ID"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
) -> dict:
    """获取会话列表."""
    try:
        service = TracingQueryService.get_instance()
    except RuntimeError:
        return {"items": [], "total": 0, "page": page, "page_size": page_size}

    actual_source_id = _get_source_id(request, source_id)
    start = _parse_date(start_date, "start_date")
    end = _parse_date(end_date, "end_date", add_day=True)

    sessions, total = await service.get_sessions(actual_source_id, page, page_size, user_id, session_id, start, end)
    return {"items": [s.model_dump() for s in sessions], "total": total, "page": page, "page_size": page_size}


@router.get("/sessions/{session_id:path}", response_model=SessionStats)
async def get_session_stats(
    session_id: str,
    request: Request,
    source_id: Optional[str] = Query(None, description="Source identifier"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
) -> SessionStats:
    """获取会话统计详情."""
    try:
        service = TracingQueryService.get_instance()
    except RuntimeError:
        return SessionStats(session_id=session_id, user_id="", channel="")

    actual_source_id = _get_source_id(request, source_id)
    start = _parse_date(start_date, "start_date")
    end = _parse_date(end_date, "end_date", add_day=True)

    return await service.get_session_stats(actual_source_id, session_id, start, end)


@router.get("/user-messages", response_model=dict)
async def get_user_messages(
    request: Request,
    source_id: Optional[str] = Query(None, description="Source identifier"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Page size"),
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    session_id: Optional[str] = Query(None, description="Filter by session ID"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    query: Optional[str] = Query(None, description="Search in user message"),
) -> dict:
    """获取用户消息列表."""
    try:
        service = TracingQueryService.get_instance()
    except RuntimeError:
        return {"items": [], "total": 0, "page": page, "page_size": page_size}

    actual_source_id = _get_source_id(request, source_id)
    start = _parse_date(start_date, "start_date")
    end = _parse_date(end_date, "end_date", add_day=True)

    messages, total = await service.get_user_messages(actual_source_id, page, page_size, user_id, session_id, start, end, query)
    return {"items": [m.model_dump() for m in messages], "total": total, "page": page, "page_size": page_size}


@router.get("/user-messages/export")
async def export_user_messages(
    request: Request,
    source_id: Optional[str] = Query(None, description="Source identifier"),
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    session_id: Optional[str] = Query(None, description="Filter by session ID"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    query: Optional[str] = Query(None, description="Search in user message"),
    export_format: str = Query("csv", description="Export format: csv, json or xlsx", alias="format"),
) -> StreamingResponse:
    """导出用户消息."""
    try:
        export_service = TracingExportService.get_instance()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail="Tracing not available") from exc

    actual_source_id = _get_source_id(request, source_id)
    start = _parse_date(start_date, "start_date")
    end = _parse_date(end_date, "end_date", add_day=True)

    if export_format == "json":
        return await export_service.export_user_messages_json(actual_source_id, user_id, session_id, start, end, query)
    if export_format == "xlsx":
        return await export_service.export_user_messages_xlsx(actual_source_id, user_id, session_id, start, end, query)
    return await export_service.export_user_messages_csv(actual_source_id, user_id, session_id, start, end, query)


@router.get("/sources", response_model=dict)
async def get_sources(
    request: Request,
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
) -> dict:
    """获取平台来源列表."""
    try:
        service = TracingQueryService.get_instance()
    except RuntimeError:
        return {"sources": []}

    start = _parse_date(start_date, "start_date")
    end = _parse_date(end_date, "end_date", add_day=True)

    sources = await service.get_sources(start, end)
    return {"sources": sources}


@router.get("/channel-distribution", response_model=dict)
async def get_channel_distribution(
    request: Request,
    source_id: Optional[str] = Query(None, description="Source identifier"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
) -> dict:
    """获取渠道分布统计."""
    try:
        service = TracingQueryService.get_instance()
    except RuntimeError:
        return {"platformUserDistribution": [], "platformCallDistribution": [], "totalPlatforms": 0}

    actual_source_id = source_id or "all"
    start = _parse_date(start_date, "start_date")
    end = _parse_date(end_date, "end_date", add_day=True)

    return await service.get_channel_distribution(actual_source_id, start, end)


@router.get("/growth-stats", response_model=dict)
async def get_growth_stats(
    request: Request,
    source_id: Optional[str] = Query(None, description="Source identifier"),
    start_date: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: str = Query(..., description="End date (YYYY-MM-DD)"),
    time_range: str = Query("day", description="Time range: day, week, month, custom"),
) -> dict:
    """获取环比增长统计."""
    try:
        service = TracingQueryService.get_instance()
    except RuntimeError:
        return {"callsGrowth": 0, "tokensGrowth": 0, "sessionGrowth": 0, "userGrowth": 0, "platformGrowth": 0, "avgDurationGrowth": 0}

    actual_source_id = source_id or "all"
    start = _parse_date(start_date, "start_date")
    end = _parse_date(end_date, "end_date", add_day=True)

    return await service.get_growth_stats(actual_source_id, start, end, time_range)


@router.get("/daily-trend", response_model=dict)
async def get_daily_trend(
    request: Request,
    source_id: Optional[str] = Query(None, description="Source identifier"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
) -> dict:
    """获取日趋势数据."""
    try:
        service = TracingQueryService.get_instance()
    except RuntimeError:
        return {"trendData": []}

    actual_source_id = source_id or "all"
    start = _parse_date(start_date, "start_date")
    end = _parse_date(end_date, "end_date", add_day=True)

    trend = await service.get_daily_trend(actual_source_id, start, end)
    return {"trendData": trend}


@router.get("/models", response_model=dict)
async def get_model_usage(
    request: Request,
    source_id: Optional[str] = Query(None, description="Source identifier"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
) -> dict:
    """获取模型使用统计."""
    try:
        service = TracingQueryService.get_instance()
    except RuntimeError:
        return {"models": []}

    actual_source_id = _get_source_id(request, source_id)
    start = _parse_date(start_date, "start_date")
    end = _parse_date(end_date, "end_date", add_day=True)

    stats = await service.get_overview_stats(actual_source_id, start, end)
    return {"models": [m.model_dump() for m in stats.model_distribution]}


@router.get("/tools", response_model=dict)
async def get_tool_usage(
    request: Request,
    source_id: Optional[str] = Query(None, description="Source identifier"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
) -> dict:
    """获取工具使用统计."""
    try:
        service = TracingQueryService.get_instance()
    except RuntimeError:
        return {"tools": []}

    actual_source_id = _get_source_id(request, source_id)
    start = _parse_date(start_date, "start_date")
    end = _parse_date(end_date, "end_date", add_day=True)

    stats = await service.get_overview_stats(actual_source_id, start, end)
    return {"tools": [t.model_dump() for t in stats.top_tools]}


@router.get("/skills", response_model=dict)
async def get_skill_usage(
    request: Request,
    source_id: Optional[str] = Query(None, description="Source identifier"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
) -> dict:
    """获取技能使用统计."""
    try:
        service = TracingQueryService.get_instance()
    except RuntimeError:
        return {"skills": []}

    actual_source_id = _get_source_id(request, source_id)
    start = _parse_date(start_date, "start_date")
    end = _parse_date(end_date, "end_date", add_day=True)

    stats = await service.get_overview_stats(actual_source_id, start, end)
    return {"skills": [s.model_dump() for s in stats.top_skills]}


@router.get("/mcp", response_model=dict)
async def get_mcp_usage(
    request: Request,
    source_id: Optional[str] = Query(None, description="Source identifier"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
) -> dict:
    """获取 MCP 使用统计."""
    try:
        service = TracingQueryService.get_instance()
    except RuntimeError:
        return {"mcp_tools": [], "mcp_servers": []}

    actual_source_id = _get_source_id(request, source_id)
    start = _parse_date(start_date, "start_date")
    end = _parse_date(end_date, "end_date", add_day=True)

    stats = await service.get_overview_stats(actual_source_id, start, end)
    return {"mcp_tools": [t.model_dump() for t in stats.top_mcp_tools], "mcp_servers": [s.model_dump() for s in stats.mcp_servers]}
```

- [ ] **Step 2: 注册路由**

修改 `monitor/src/monitor/app/routers/__init__.py`：

```python
# -*- coding: utf-8 -*-
from fastapi import APIRouter

from .health import router as health_router
from .sync import router as sync_router
from .cron import router as cron_router
from .tracing import router as tracing_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(sync_router, tags=["sync"])
api_router.include_router(cron_router, tags=["cron"])
api_router.include_router(tracing_router, tags=["tracing"])
```

- [ ] **Step 3: Commit**

```bash
git add monitor/src/monitor/app/routers/tracing.py monitor/src/monitor/app/routers/__init__.py
git commit -m "feat(monitor): add tracing API router"
```

---

## Task 9: 更新应用生命周期

**Files:**
- Modify: `monitor/src/monitor/app/_app.py`

- [ ] **Step 1: 添加 tracing 连接初始化**

修改 `monitor/src/monitor/app/_app.py` 的 `lifespan` 函数：

```python
@asynccontextmanager
async def lifespan(fastapi_app: FastAPI):
    """应用生命周期管理."""
    logger.info("Monitor service starting up...")
    logger.info(f"Environment: {os.environ.get('MONITOR_ENV', 'prd')}")

    # Initialize database connection if configured
    if DB_HOST:
        try:
            from .database import init_db_connection
            await init_db_connection()
            logger.info("Database initialized successfully")
        except Exception as e:
            logger.warning("Database initialization failed: %s", e)
    else:
        logger.info("Database not configured (MONITOR_DB_HOST not set)")

    # Initialize tracing database connection if configured
    from ..config.constant import TRACING_DB_HOST
    if TRACING_DB_HOST:
        try:
            from .database import init_tracing_db_connection, init_es_client
            await init_tracing_db_connection()
            await init_es_client()
            logger.info("Tracing database initialized successfully")
        except Exception as e:
            logger.warning("Tracing database initialization failed: %s", e)
    else:
        logger.info("Tracing database not configured (TRACING_DB_HOST not set)")

    yield

    # Close tracing database connection on shutdown
    if TRACING_DB_HOST:
        try:
            from .database import close_tracing_db_connection, close_es_client
            await close_tracing_db_connection()
            await close_es_client()
            logger.info("Tracing database connection closed")
        except Exception as e:
            logger.warning("Failed to close tracing database connection: %s", e)

    # Close database connection on shutdown
    if DB_HOST:
        try:
            from .database import close_db_connection
            await close_db_connection()
            logger.info("Database connection closed")
        except Exception as e:
            logger.warning("Failed to close database connection: %s", e)

    logger.info("Monitor service shutting down...")
```

- [ ] **Step 2: Commit**

```bash
git add monitor/src/monitor/app/_app.py
git commit -m "feat(monitor): add tracing database initialization in app lifecycle"
```

---

## Task 10: 运行测试验证

**Files:**
- None (验证步骤)

- [ ] **Step 1: 检查 Monitor 服务启动**

```bash
cd monitor && python -m monitor.app
```

预期：服务正常启动，日志显示 tracing database initialized（如果配置了 TRACING_DB_HOST）

- [ ] **Step 2: 测试 API 端点**

```bash
curl http://localhost:9090/api/tracing/overview?source_id=all
curl http://localhost:9090/api/tracing/users?page=1&page_size=10&source_id=all
curl http://localhost:9090/api/tracing/sessions?page=1&page_size=10
```

预期：返回正确的 JSON 数据

- [ ] **Step 3: 验证导出功能**

```bash
curl "http://localhost:9090/api/tracing/user-messages/export?format=csv" -o test.csv
curl "http://localhost:9090/api/tracing/user-messages/export?format=xlsx" -o test.xlsx
curl "http://localhost:9090/api/tracing/user-messages/export?format=json" -o test.json
```

预期：生成对应的导出文件

---

## Task 11: 清理 SWE 服务的 tracing 路由

**Files:**
- Delete: `src/swe/app/routers/tracing.py`
- Modify: `src/swe/app/routers/__init__.py`

**注意：此步骤需要在前端适配完成后执行。**

- [ ] **Step 1: 从 SWE 路由中移除 tracing_router**

修改 `src/swe/app/routers/__init__.py`，删除 tracing router 的导入和注册：

```python
# 删除此行
from .tracing import router as tracing_router

# 删除此行
api_router.include_router(tracing_router, prefix="/tracing", tags=["tracing"])
```

- [ ] **Step 2: 删除 tracing 路由文件**

```bash
rm src/swe/app/routers/tracing.py
```

- [ ] **Step 3: Commit**

```bash
git add src/swe/app/routers/__init__.py
git rm src/swe/app/routers/tracing.py
git commit -m "refactor(swe): remove tracing router (migrated to Monitor service)"
```

---

## 验收标准

1. Monitor 服务提供所有 `/api/tracing/*` 端点
2. 前端运营看板 4 个页面（BusinessOverview、Users、Sessions、Messages）正常工作
3. 导出功能（CSV/XLSX/JSON）正常工作
4. SWE 服务中移除 tracing 路由
5. 所有测试通过

---

## 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 数据库连接配置错误 | 查询失败 | 提供配置检查接口，启动时验证连接 |
| ES 连接不稳定 | model_output 缺失 | 降级处理，trace detail 仍可返回 |
| 前后端 API 不同步 | 404 错误 | 前端保持 API 路径不变，OpenAPI 文档同步 |
