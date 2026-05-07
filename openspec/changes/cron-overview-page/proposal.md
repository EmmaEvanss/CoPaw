## Why

目前定时任务系统存在以下问题：

1. **任务定义存储不持久** - 任务定义存储在 `jobs.json` 文件中，多实例部署时存在并发写入风险
2. **执行状态只在内存中** - `CronJobState` 只保存在内存，服务重启后丢失，无法追溯历史执行
3. **缺少全局概览视图** - 管理员无法查看所有租户/用户的定时任务状态和执行历史
4. **缺少数据导出能力** - 无法导出定时任务数据用于报表或审计

## What Changes

- 在 Monitor 模块中创建定时任务数据库表（`swe_cron_jobs` + `swe_cron_executions`）
- 在 Monitor 中实现任务定义同步 API（供 SWE 双写调用）和查询 API（供前端调用）
- 在 SWE 的 `CronManager` 中集成异步双写逻辑，任务创建/编辑/删除/执行后同步到 Monitor
- 在 Console 前端新增定时任务概览页面，支持查询、筛选、导出功能

## Capabilities

### New Capabilities

- `cron-overview`: 全局定时任务概览页面，支持查看所有租户的定时任务定义和执行历史，支持按条件筛选和导出 Excel

### Modified Capabilities

- `cron-management`: 定时任务管理功能，新增异步双写机制将任务定义和执行记录同步到 Monitor 数据库

## Impact

- 新增模块：`monitor/src/monitor/models/cron.py`、`monitor/src/monitor/services/cron/`、`monitor/src/monitor/database/`
- 新增路由：`monitor/src/monitor/app/routers/cron.py`
- 修改模块：`src/swe/app/crons/manager.py`（集成 MonitorSyncClient）
- 新增前端页面：`console/src/pages/Monitor/CronOverview/`
- 新增数据库表：`swe_cron_jobs`、`swe_cron_executions`
