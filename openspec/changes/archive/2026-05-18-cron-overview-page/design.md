## Context

项目已有完整的定时任务系统（`src/swe/app/crons/`），使用 APScheduler 进行调度，任务定义存储在 JSON 文件中。本次变更旨在：

1. 添加数据库持久化存储用于概览和追溯
2. 保持原有定时任务功能不变（双写模式）
3. 提供前端概览页面和导出功能

## Goals / Non-Goals

**Goals:**

- 在 Monitor 模块实现定时任务数据库存储和 API
- 通过异步双写机制从 SWE 同步任务定义和执行记录
- 提供前端概览页面支持查询、筛选、导出

**Non-Goals:**

- 替换 SWE 现有的 jobs.json 存储（保持双写）
- 实现 Token 使用统计（暂不需要）
- 实现历史数据定期清理（暂不清理）
- 实现分布式协调或领导选举（已有 `redis-coordinated-cron-leadership`）

## Decisions

### Decision 1: 双写模式 - 异步非阻塞

**Choice:** SWE 在任务操作成功后，异步调用 Monitor HTTP API 进行数据同步。

**Rationale:**

- Monitor 同步失败不影响 SWE 主服务的定时任务功能
- 简化实现复杂度，避免引入同步等待超时
- 适合对数据实时性要求不高的概览场景

**Alternatives considered:**

- 同步确认 + 重试：增加主服务延迟，失败可能阻塞用户操作
- 最终一致性补偿：需要额外实现定时全量同步，复杂度高

**How to apply:**

- `MonitorSyncClient` 使用 `asyncio.create_task()` 异步发送 HTTP 请求
- 失败时仅记录日志，不抛出异常

### Decision 2: 数据库存储 - VARCHAR 字段

**Choice:** 使用 VARCHAR 类型存储字符串和 JSON 数据，不使用 TEXT/JSON 类型。

**Rationale:**

- MySQL TEXT 类型有性能和索引限制
- JSON 类型在某些 MySQL 版本兼容性问题
- VARCHAR 足够存储任务元数据和执行信息

**Alternatives considered:**

- TEXT 类型：不适合索引，查询性能差
- JSON 类型：便于 JSON 查询但增加版本依赖

**How to apply:**

- `meta`、`request_input` 等字段使用 `VARCHAR(4096)`
- JSON 数据在应用层序列化/反序列化

### Decision 3: Monitor 模块独立实现

**Choice:** 在 Monitor 模块独立实现数据库和 API，不复用 SWE 的数据库配置。

**Rationale:**

- Monitor 是独立部署的服务，需要独立数据库连接
- 避免 SWE 和 Monitor 之间的数据库耦合
- 便于后续扩展监控相关功能

**How to apply:**

- 新建 `monitor/src/monitor/database/` 目录
- 数据库配置通过环境变量 `MONITOR_DB_*` 读取

### Decision 4: Excel 导出使用 openpyxl

**Choice:** 使用 openpyxl 库生成 Excel 文件。

**Rationale:**

- openpyxl 是成熟的 Python Excel 库
- 支持样式设置（表头、对齐等）
- 可直接返回 bytes 用于 HTTP 下载

**Alternatives considered:**

- xlsxwriter：功能类似，但 openpyxl 更常用
- csv 格式：不支持样式，用户体验差

**How to apply:**

- `monitor/src/monitor/services/cron/export_service.py` 使用 openpyxl
- 导出接口返回 `StreamingResponse` 直接下载

### Decision 5: 前端页面在 Monitor 菜单下

**Choice:** 在 Console 的 Monitor/Analytics 区域新增定时任务概览页面。

**Rationale:**

- 定时任务概览属于监控/运维范畴
- 与现有的 Analytics、Tracing 页面位置一致
- 不与 Control/CronJobs（用户定时任务管理）混淆

**How to apply:**

- 新增 `console/src/pages/Monitor/CronOverview/` 页面
- 路由路径 `/monitor/cron-overview`

## Risks / Trade-offs

- [双写丢失] 异步调用失败时数据可能丢失 -> 通过日志监控失败情况，必要时人工排查
- [数据库连接] Monitor 需要稳定的 MySQL 连接 -> 使用连接池 + 健康检查
- [存储增长] 执行历史持续增长不清理 -> 暂接受，后续可添加清理策略

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              整体架构                                        │
└─────────────────────────────────────────────────────────────────────────────┘

Console Frontend                    Monitor Service              SWE Service
─────────────                       ─────────────               ────────────

┌──────────────┐                    ┌──────────────┐            ┌──────────────┐
│ CronOverview │◀──── HTTP ────────▶│              │            │              │
│              │                    │  routers/    │            │  crons/      │
│  - 任务列表   │                    │    cron.py   │            │    manager   │
│  - 执行历史   │                    │              │            │              │
│  - 筛选导出   │                    │  services/   │◀── HTTP ───│  sync_client │
│              │                    │    cron/     │  (异步)    │              │
└──────────────┘                    │              │            └──────────────┘
                                    │  database/   │
                                    │              │
                                    └──────┬───────┘
                                           │
                                           ▼
                                    ┌──────────────┐
                                    │    MySQL     │
                                    │              │
                                    │ cron_jobs    │
                                    │ cron_execs   │
                                    └──────────────┘
```

## API Design

### Monitor Query APIs (供前端)

```
GET /api/cron/jobs
  Query: tenant_id, creator_user_id, status, enabled, page, page_size
  Response: { items: [], total: N, page: P, page_size: S }

GET /api/cron/executions
  Query: job_id, tenant_id, status, start_time, end_time, page, page_size
  Response: { items: [], total: N, page: P, page_size: S }

GET /api/cron/executions/{id}
  Response: ExecutionDetail

GET /api/cron/export
  Query: tenant_id, status, start_time, end_time
  Response: Excel file download
```

### Monitor Sync APIs (供 SWE 双写)

```
POST /api/sync/job
  Body: CronJobSyncRequest
  Response: { synced: true }

DELETE /api/sync/job/{job_id}
  Response: { deleted: true }

POST /api/sync/execution
  Body: ExecutionSyncRequest
  Response: { recorded: true, execution_id: N }
```

## Database Schema

详见 proposal 中的表设计，关键点：

- `swe_cron_jobs`: 任务定义表，VARCHAR 字段存储元数据
- `swe_cron_executions`: 执行历史表，支持追溯 trace_id/session_id
- 软删除使用 `deleted_at` 字段
- 索引覆盖常用查询路径（tenant_id, status, actual_time）