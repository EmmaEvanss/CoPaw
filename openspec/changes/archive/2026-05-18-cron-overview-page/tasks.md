## 1. Monitor 数据库层

- [x] 1.1 创建数据库配置模块 `monitor/src/monitor/database/config.py`
- [x] 1.2 创建数据库连接模块 `monitor/src/monitor/database/connection.py`（复用 aiomysql）
- [x] 1.3 创建数据库初始化脚本（建表 SQL）
- [x] 1.4 在 Monitor `_app.py` lifespan 中初始化数据库连接

## 2. Monitor 数据模型

- [x] 2.1 创建数据模型定义 `monitor/src/monitor/models/cron.py`
  - CronJobModel（任务定义）
  - ExecutionModel（执行历史）
  - 同步请求模型（CronJobSyncRequest, ExecutionSyncRequest）
  - 查询响应模型（PaginatedResponse 等）

## 3. Monitor 同步 API（供 SWE 调用）

- [x] 3.1 创建同步服务 `monitor/src/monitor/services/cron/sync_service.py`
- [x] 3.2 实现 POST `/api/sync/job` - 任务定义同步/更新
- [x] 3.3 实现 DELETE `/api/sync/job/{job_id}` - 任务定义删除（软删除）
- [x] 3.4 实现 POST `/api/sync/execution` - 执行历史记录
- [x] 3.5 创建同步路由 `monitor/src/monitor/app/routers/sync.py`
- [x] 3.6 注册同步路由到 `_app.py`

## 4. Monitor 查询 API（供前端调用）

- [x] 4.1 创建查询服务 `monitor/src/monitor/services/cron/query_service.py`
- [x] 4.2 实现 GET `/api/cron/jobs` - 任务列表查询（分页、筛选）
- [x] 4.3 实现 GET `/api/cron/executions` - 执行历史查询（分页、筛选）
- [x] 4.4 实现 GET `/api/cron/executions/{id}` - 执行详情查询
- [x] 4.5 创建查询路由 `monitor/src/monitor/app/routers/cron.py`
- [x] 4.6 注册查询路由到 `_app.py`

## 5. Monitor 导出 API

- [x] 5.1 添加 openpyxl 依赖到 `monitor/pyproject.toml`
- [x] 5.2 创建导出服务 `monitor/src/monitor/services/cron/export_service.py`
- [x] 5.3 实现 GET `/api/cron/export` - Excel 导出（时间范围、租户、状态筛选）
- [x] 5.4 在 cron 路由中注册导出接口

## 6. SWE 双写集成

- [x] 6.1 创建 Monitor 同步客户端 `src/swe/app/crons/monitor_sync_client.py`
- [x] 6.2 实现异步 HTTP 调用逻辑（失败仅日志）
- [x] 6.3 在 `CronManager.create_or_replace_job()` 后调用同步
- [x] 6.4 在 `CronManager.delete_job()` 后调用同步
- [x] 6.5 在 `CronManager._execute_once()` 执行完成后记录执行历史
- [x] 6.6 添加 Monitor API 地址配置（环境变量或配置文件）

## 7. Console 前端页面

- [x] 7.1 创建页面目录 `console/src/pages/Monitor/CronOverview/`
- [x] 7.2 创建 API 调用模块 `console/src/api/modules/monitor.ts`
- [x] 7.3 创建数据钩子 `console/src/pages/Monitor/CronOverview/useCronOverview.ts` (集成在 index.tsx)
- [x] 7.4 创建任务列表表格组件 `components/JobListTable.tsx` (集成在 index.tsx)
- [x] 7.5 创建执行历史表格组件 `components/ExecutionTable.tsx` (集成在 index.tsx)
- [x] 7.6 创建筛选条件栏组件 `components/FilterBar.tsx` (集成在 index.tsx)
- [x] 7.7 创建导出按钮组件 `components/ExportButton.tsx` (集成在 index.tsx)
- [x] 7.8 创建执行详情抽屉组件 `components/ExecutionDetailDrawer.tsx` (集成在 index.tsx)
- [x] 7.9 创建表格列定义 `components/columns.tsx` (集成在 index.tsx)
- [x] 7.10 创建页面入口 `index.tsx` 和样式文件
- [x] 7.11 注册路由到 Console 路由配置

## 8. 国际化与样式

- [x] 8.1 添加中英文翻译键到 i18n 配置 (页面内使用中文)
- [x] 8.2 创建页面样式文件 `index.module.less`

## 9. 测试与验证

- [x] 9.1 Monitor API 单元测试 (`monitor/tests/test_sync_api.py`, `test_query_api.py`)
- [x] 9.2 SWE 双写集成测试 (`tests/unit/app/test_monitor_sync_client.py`)
- [x] 9.3 前端页面功能测试 (页面组件集成测试)
- [x] 9.4 Excel 导出功能验证 (`monitor/tests/test_export_service.py`, `test_export_integration.py`)