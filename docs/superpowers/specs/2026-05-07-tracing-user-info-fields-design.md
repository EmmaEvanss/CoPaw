# Tracing 模块添加 user_name 和 bbk_id 字段设计文档

## 背景

当前 `swe_tracing_traces` 和 `swe_tracing_spans` 两张表仅记录了 `user_id`，无法直观识别用户身份和所属机构。为提升数据可读性和查询效率，需要增加 `user_name`（用户姓名）和 `bbk_id`（分行编号）两个字段。

## 目标

- 为 tracing 模块添加 `user_name` 和 `bbk_id` 字段
- 数据来源为请求头传递（`X-User-Name` 和 `X-Bbk-Id`）
- 两张表均冗余存储新字段，与现有 `user_id` 策略保持一致

## 数据流设计

```
请求头(X-User-Name, X-Bbk-Id)
  → tenant_identity 中间件解析
  → AgentRequest 传递
  → AgentRunner 提取
  → TraceManager.start_trace()
  → TraceStore.create_trace() / create_span()
  → 数据库写入
```

## 修改模块清单

### 1. 数据库迁移

**文件：** 新建 `scripts/sql/tracing_user_info_migration.sql`

**内容：**
```sql
-- 为 swe_tracing_traces 表添加字段
ALTER TABLE swe_tracing_traces
ADD COLUMN user_name VARCHAR(128) DEFAULT NULL COMMENT '用户姓名',
ADD COLUMN bbk_id VARCHAR(64) DEFAULT NULL COMMENT '分行编号';

-- 为 swe_tracing_spans 表添加字段（冗余存储）
ALTER TABLE swe_tracing_spans
ADD COLUMN user_name VARCHAR(128) DEFAULT NULL COMMENT '用户姓名（冗余）',
ADD COLUMN bbk_id VARCHAR(64) DEFAULT NULL COMMENT '分行编号（冗余）';

-- 添加索引以支持按 user_name 和 bbk_id 查询
ALTER TABLE swe_tracing_traces ADD INDEX idx_user_name (user_name);
ALTER TABLE swe_tracing_traces ADD INDEX idx_bbk_id (bbk_id);
ALTER TABLE swe_tracing_spans ADD INDEX idx_bbk_id (bbk_id);
```

### 2. 请求解析

**文件：** `src/swe/app/middleware/tenant_identity.py`

**修改位置：** `_resolve_request_identity` 方法（约第126-128行）

**修改内容：**
- 解析 `X-User-Name` 请求头
- 解析 `X-Bbk-Id` 请求头
- 将新字段存入 request.state 或通过其他方式传递给下游

### 3. Pydantic 模型

**文件：** `src/swe/tracing/models.py`

**修改的模型类：**

| 模型类 | 位置 | 新增字段 |
|--------|------|----------|
| `Span` | 第34-95行 | `user_name: str | None`, `bbk_id: str | None` |
| `Trace` | 第97-156行 | `user_name: str | None`, `bbk_id: str | None` |
| `UserListItem` | 第382-390行 | `user_name: str | None`, `bbk_id: str | None` |
| `TraceListItem` | 第393-408行 | `user_name: str | None`, `bbk_id: str | None` |
| `UserMessageItem` | 第443-456行 | `user_name: str | None`, `bbk_id: str | None` |

### 4. 存储层

**文件：** `src/swe/tracing/store.py`

**修改的方法：**

| 方法 | 位置 | 修改内容 |
|------|------|----------|
| `create_trace()` | 第113-151行 | INSERT SQL 添加 `user_name`, `bbk_id` 字段 |
| `update_trace()` | 第153-191行 | UPDATE SQL 添加 `user_name`, `bbk_id` 字段 |
| `create_span()` | 第225-266行 | INSERT SQL 添加 `user_name`, `bbk_id` 字段 |
| `batch_create_spans()` | 第320-368行 | 批量 INSERT 添加 `user_name`, `bbk_id` 字段 |
| `_row_to_trace()` | 第2411-2436行 | 行转模型添加 `user_name`, `bbk_id` 映射 |
| `_row_to_span()` | 第2438-2463行 | 行转模型添加 `user_name`, `bbk_id` 映射 |
| `get_users()` | 第779-891行 | 查询返回 `user_name`, `bbk_id` |
| `get_traces()` | 第1087-1171行 | 查询返回 `user_name`, `bbk_id` |
| `get_user_messages()` | 第1610-1708行 | 查询返回 `user_name`, `bbk_id` |

### 5. 管理层

**文件：** `src/swe/tracing/manager.py`

**修改内容：**

| 类/方法 | 位置 | 修改内容 |
|---------|------|----------|
| `TraceContext` | 第28-95行 | 添加 `user_name` 和 `bbk_id` 属性 |
| `start_trace()` | 第246-299行 | 添加 `user_name` 和 `bbk_id` 参数，传递给 store |
| `emit_span()` | 第431-511行 | 添加 `user_name` 和 `bbk_id` 参数 |
| `emit_llm_input()` | 第623-657行 | 传递 `user_name` 和 `bbk_id` |
| `emit_tool_call_start()` | 第681-754行 | 传递 `user_name` 和 `bbk_id` |
| `emit_skill_invocation()` | 第796-830行 | 传递 `user_name` 和 `bbk_id` |

### 6. 钩子层

**文件：** `src/swe/agents/hooks/tracing.py`

**修改内容：**

| 方法 | 位置 | 修改内容 |
|------|------|----------|
| `TracingHook.__init__()` | 第25-52行 | 添加 `user_name` 和 `bbk_id` 参数 |
| 所有 `on_*` 方法 | 各处 | 传递 `user_name` 和 `bbk_id` 到 manager |

### 7. Runner 层

**文件：** `src/swe/app/runner/runner.py`

**修改位置：** `query_handler` 方法（约第534-564行）

**修改内容：**
- 从 request 或 request.state 提取 `user_name` 和 `bbk_id`
- 传递给 `TraceManager.start_trace()`
- 传递给 `TracingHook` 初始化

### 8. 前端 API 类型

**文件：** `console/src/api/modules/tracing.ts`

**修改的接口：**

| 接口 | 位置 | 新增字段 |
|------|------|----------|
| `UserListItem` | 第82-88行 | `user_name?: string`, `bbk_id?: string` |
| `TraceListItem` | 第90-103行 | `user_name?: string`, `bbk_id?: string` |
| `Trace` | 第142-158行 | `user_name?: string`, `bbk_id?: string` |
| `Span` | 第160-176行 | `user_name?: string`, `bbk_id?: string` |
| `UserMessageItem` | 第242-253行 | `user_name?: string`, `bbk_id?: string` |

### 9. 前端展示

**文件：** `console/src/pages/Analytics/BusinessOverview/index.tsx`

**修改内容：**
- `UserRow` 类型定义添加 `user_name` 和 `bbk_id`
- 用户列表渲染优先显示 `user_name`，若无则显示 `user_id`
- 可选：添加 `bbk_id` 列展示

## 兼容性考虑

- 新字段默认为 `NULL`，不影响现有数据
- 请求头缺失时，字段值为 `None`/`NULL`，不阻塞流程
- 前端展示兼容处理：`user_name` 缺失时回退显示 `user_id`

## 测试要点

1. **数据库迁移：** 执行 SQL 脚本后表结构正确
2. **请求解析：** 中间件正确解析并传递请求头
3. **数据写入：** trace 和 span 记录包含新字段
4. **API 查询：** 返回数据包含新字段
5. **前端展示：** 正确显示 user_name 和 bbk_id
6. **兼容性：** 请求头缺失时不影响正常运行

## 实施顺序

1. 执行数据库迁移脚本
2. 修改后端代码（按依赖顺序：中间件 → models → store → manager → hooks → runner）
3. 修改前端代码（API 类型 → 展示组件）
4. 验证测试