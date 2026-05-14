# 运营看板查询迁移到 Monitor 服务设计

## 背景

当前运营看板的4个页面（BusinessOverview、Users、Sessions、Messages）的所有查询 API 都由 SWE 服务的 `/tracing/*` 端点提供。为了服务职责分离和更好的可维护性，需要将这些查询迁移到 Monitor 服务。

## 目标

- 将运营看板的所有查询 API 从 SWE 服务迁移到 Monitor 服务
- Monitor 服务直接访问 TraceStore（Redis）和 Elasticsearch
- 保持前端 API 调用路径不变（`/api/tracing/*`）
- SWE 服务完全移除 tracing 路由

## 架构设计

### 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        Console Frontend                          │
│  BusinessOverview / Users / Sessions / Messages 页面             │
└──────────────────────────┬──────────────────────────────────────┘
                           │ HTTP /api/tracing/*
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Monitor Service                             │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │
│  │   Routers       │  │   Services      │  │   Database      │  │
│  │  tracing.py     │──│ TracingQuery    │──│ TraceStore + ES │  │
│  │                 │  │   Service       │  │   Connection    │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                           │
                           ▼
         ┌─────────────────┴─────────────────┐
         │                                   │
    ┌────┴────┐                        ┌────┴────┐
    │  Redis  │                        │   ES    │
    │TraceStore│                       │ Messages│
    └─────────┘                        └─────────┘
```

### 目录结构

```
monitor/src/monitor/app/
├── routers/
│   ├── __init__.py          # 添加 tracing_router
│   ├── health.py
│   ├── sync.py
│   ├── cron.py
│   └── tracing.py           # 【新增】运营看板 API 路由
├── services/
│   ├── __init__.py
│   ├── cron/
│   │   ├── query_service.py
│   │   ├── sync_service.py
│   │   └── export_service.py
│   └── tracing/             # 【新增】运营看板服务
│       ├── __init__.py
│       ├── query_service.py # 核心查询服务
│       └── export_service.py# 导出服务
├── database/
│   ├── __init__.py
│   ├── config.py
│   ├── connection.py
│   ├── schema.py            # cron 表结构
│   └── tracing.py           # 【新增】TraceStore + ES 连接
└── models/
    ├── __init__.py
    ├── cron.py
    └── tracing.py           # 【新增】运营看板数据模型
```

## API 端点迁移清单

从 `src/swe/app/routers/tracing.py` 迁移的端点：

| 端点 | 方法 | 功能 | 页面使用 |
|------|------|------|----------|
| `/overview` | GET | 运营概览统计 | BusinessOverview |
| `/users` | GET | 用户列表（分页） | Users, BusinessOverview |
| `/users/{user_id}` | GET | 用户统计详情 | Users Drawer |
| `/traces` | GET | 对话列表（分页） | Sessions Drawer |
| `/traces/{trace_id}` | GET | 对话详情 | Sessions Drawer |
| `/traces/{trace_id}/timeline` | GET | 对话时间线 | Sessions Drawer |
| `/sessions` | GET | 会话列表（分页） | Sessions |
| `/sessions/{session_id}` | GET | 会话统计详情 | Sessions Drawer |
| `/user-messages` | GET | 用户消息列表 | Messages |
| `/user-messages/export` | GET | 导出用户消息 | Messages |
| `/sources` | GET | 平台来源列表 | BusinessOverview |
| `/channel-distribution` | GET | 平台分布统计 | BusinessOverview |
| `/growth-stats` | GET | 环比增长统计 | BusinessOverview |
| `/daily-trend` | GET | 日趋势数据 | BusinessOverview |
| `/models` | GET | 模型使用统计 | （保留备用） |
| `/tools` | GET | 工具使用统计 | （保留备用） |
| `/skills` | GET | 技能使用统计 | （保留备用） |
| `/mcp` | GET | MCP使用统计 | （保留备用） |

## 配置设计

### Monitor 独立环境变量

Monitor 服务使用独立的环境变量配置，不依赖 SWE 的配置：

```
# Monitor 服务环境变量
TRACE_STORE_URL=redis://redis-cluster:6379/0
ES_HOST=elasticsearch
ES_PORT=9200
ES_INDEX_PREFIX=swe_
ES_USER=
ES_PASSWORD=
```

### 配置常量

```python
# monitor/src/monitor/config/constant.py（新增）

TRACE_STORE_URL = os.environ.get("TRACE_STORE_URL", "")
ES_HOST = os.environ.get("ES_HOST", "")
ES_PORT = int(os.environ.get("ES_PORT", "9200"))
ES_INDEX_PREFIX = os.environ.get("ES_INDEX_PREFIX", "swe_")
ES_USER = os.environ.get("ES_USER", "")
ES_PASSWORD = os.environ.get("ES_PASSWORD", "")
```

## 数据层设计

### TracingConnection

```python
# monitor/src/monitor/app/database/tracing.py

class TracingConnection:
    """TraceStore 和 ES 连接管理器."""

    def __init__(self):
        self._trace_store = None
        self._es_client = None

    async def init(self):
        """初始化连接."""
        # 从环境变量读取配置
        from ...config.constant import TRACE_STORE_URL, ES_HOST, ES_PORT

    async def get_trace_store(self):
        """获取 TraceStore 实例."""

    async def get_es_client(self):
        """获取 ES Client 实例."""

    async def close(self):
        """关闭连接."""
```

## 服务层设计

### TracingQueryService

```python
# monitor/src/monitor/app/services/tracing/query_service.py

class TracingQueryService:
    """运营看板查询服务."""

    def __init__(self, tracing_conn: TracingConnection):
        self._conn = tracing_conn

    # ===== 运营概览 =====
    async def get_overview_stats(...) -> OverviewStats: ...
    async def get_growth_stats(...) -> dict: ...
    async def get_daily_trend(...) -> list[dict]: ...
    async def get_channel_distribution(...) -> dict: ...
    async def get_sources(...) -> list[str]: ...

    # ===== 用户分析 =====
    async def get_users(...) -> tuple[list[UserListItem], int]: ...
    async def get_user_stats(...) -> UserStats: ...

    # ===== 会话分析 =====
    async def get_sessions(...) -> tuple[list[SessionListItem], int]: ...
    async def get_session_stats(...) -> SessionStats: ...

    # ===== 对话分析 =====
    async def get_traces(...) -> tuple[list[TraceListItem], int]: ...
    async def get_trace_detail(...) -> Optional[TraceDetail]: ...
    async def get_trace_timeline(...) -> Optional[TraceDetailWithTimeline]: ...

    # ===== 用户消息 =====
    async def get_user_messages(...) -> tuple[list[UserMessageItem], int]: ...
```

### TracingExportService

```python
# monitor/src/monitor/app/services/tracing/export_service.py

class TracingExportService:
    """运营看板导出服务."""

    async def export_user_messages_csv(...) -> StreamingResponse: ...
    async def export_user_messages_xlsx(...) -> StreamingResponse: ...
    async def export_user_messages_json(...) -> StreamingResponse: ...
```

## 数据模型

从 `src/swe/tracing/models.py` 迁移以下模型：

- `OverviewStats` - 运营概览统计
- `ModelUsage` - 模型使用
- `ToolUsage` - 工具使用
- `SkillUsage` - 技能使用
- `MCPToolUsage` - MCP 工具使用
- `MCPServerUsage` - MCP 服务使用
- `UserListItem` - 用户列表项
- `UserStats` - 用户统计
- `SessionListItem` - 会话列表项
- `SessionStats` - 会话统计
- `TraceListItem` - 对话列表项
- `TraceDetail` - 对话详情
- `TraceDetailWithTimeline` - 对话时间线
- `UserMessageItem` - 用户消息
- `TimelineEvent` - 时间线事件

## 错误处理

| 场景 | HTTP 状态码 | 错误信息 |
|------|-------------|----------|
| TraceStore 未配置 | 503 | `TraceStore not configured` |
| ES 未配置 | 503 | `Elasticsearch not configured` |
| Trace 未找到 | 404 | `Trace not found` |
| 日期格式错误 | 400 | `Invalid date format` |
| 数据库连接失败 | 503 | `Database connection failed` |

## 前端适配

### API 配置变更

```typescript
// console/src/api/config.ts

// 新增 Monitor 服务地址配置
export const getMonitorApiUrl = (path: string) => {
  const baseUrl = process.env.MONITOR_API_URL || '/api';
  return `${baseUrl}${path}`;
};
```

### tracingApi 适配

修改 `console/src/api/modules/tracing.ts` 中的请求，指向 monitor 服务。

## 测试策略

| 测试类型 | 范围 | 工具 |
|----------|------|------|
| 单元测试 | TracingQueryService 方法 | pytest |
| 集成测试 | API 端点响应 | pytest + httpx |
| 契约测试 | 前后端 API 契约 | OpenAPI schema |

测试目录：

```
monitor/tests/
├── test_tracing_api.py      # API 集成测试
├── test_tracing_service.py  # 服务层单元测试
└── fixtures/
    └── tracing_data.py      # 测试数据
```

## 迁移计划

| 阶段 | 任务 | 产出 |
|------|------|------|
| Phase 1 | 数据层迁移 | `monitor/app/database/tracing.py` |
| Phase 2 | 模型迁移 | `monitor/app/models/tracing.py` |
| Phase 3 | 服务层迁移 | `monitor/app/services/tracing/` |
| Phase 4 | 路由层迁移 | `monitor/app/routers/tracing.py` |
| Phase 5 | 前端适配 | `console/src/api/` 修改 |
| Phase 6 | 清理 SWE | 移除 `src/swe/app/routers/tracing.py` |

### 依赖关系

```
Phase 1 (数据层)
    ↓
Phase 2 (模型层)
    ↓
Phase 3 (服务层)
    ↓
Phase 4 (路由层)
    ↓
Phase 5 (前端适配)
    ↓
Phase 6 (清理 SWE)
```

## 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 数据格式不一致 | 查询失败 | 使用相同的数据模型定义 |
| ES 连接不稳定 | 服务不可用 | 添加重试机制和降级逻辑 |
| 前后端不同步 | API 404 | OpenAPI 契约测试 |
| 环境变量遗漏 | 配置缺失 | 提供配置检查接口 |

## 验收标准

1. Monitor 服务提供所有 `/tracing/*` 端点
2. 前端运营看板4个页面正常工作
3. 导出功能（CSV/XLSX/JSON）正常工作
4. SWE 服务中移除 tracing 路由
5. 所有测试通过
