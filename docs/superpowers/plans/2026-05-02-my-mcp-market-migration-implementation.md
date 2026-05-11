# MyMCP 迁移到 Market 服务实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `D:\workspace\copaw1\CoPaw` 中 `MyMCP` 的全部后端能力从 `swe` 主服务迁移到 `market` 服务，使 `MyMCP` 页面只依赖 `market`，并删除 `swe` 中原有 `my_mcp.py`。

**Architecture:** 本次实现以“整体迁移 + 最小改造”为原则。直接复制 `src/swe/app/routers/my_mcp.py` 到 `market/src/market/app/routers/my_mcp.py`，最大限度复用原有请求模型、脱敏逻辑、测试连接逻辑和本地 MCP 业务规则。只替换 `market` 无法直接运行的依赖，包括 agent 配置定位、保存后 reload、以及路由注册位置。前端继续保留 `MyMCP` 页面与组件结构，只调整请求目标服务。

**Tech Stack:** FastAPI, Pydantic, Python marketplace service/fs layer, React, TypeScript, Ant Design, pytest

---

## File Structure

### Existing files to modify

- `market/src/market/app/routers/__init__.py`
  责任：注册新的 `my_mcp` 路由。
- `market/src/market/app/_app.py`
  责任：为 `my_mcp` 运行所需的共享依赖补充最小初始化能力。
- `market/src/market/app/deps.py`
  责任：补充 `my_mcp` 所需的请求上下文解析 helper（如适合放在此处）。
- `market/src/market/marketplace/service.py`
  责任：保留现有 MCP 市场服务，并允许 `my_mcp` 直接复用内部发布逻辑。
- `console/src/api/modules/myMcp.ts`
  责任：切换 `MyMCP` 请求目标到 `market` 服务。
- `console/src/api/request.ts`
  责任：如有需要，补充 `MyMCP` 请求在 `market` 服务下的错误透传兼容。

### Existing files to delete

- `src/swe/app/routers/my_mcp.py`
  责任：迁移完成后删除。

### New backend files

- `market/src/market/app/routers/my_mcp.py`
  责任：承接本地 MCP 列表、详情、创建、更新、删除、启停、草稿测试、连接测试、发布。
- `market/src/market/app/my_mcp_helpers.py`
  责任：抽取 `my_mcp` 专用上下文解析、agent 配置加载/保存、reload 触发逻辑。

### New / updated tests

- `market/tests/unit/app/routers/test_my_mcp.py`
- `market/tests/unit/app/test_my_mcp_helpers.py`

---

## Task 1: 迁移 `my_mcp.py` 到 market 并跑通基础导入

**Files:**
- Create: `market/src/market/app/routers/my_mcp.py`
- Modify: `market/src/market/app/routers/__init__.py`
- Delete later: `src/swe/app/routers/my_mcp.py`

- [ ] **Step 1: 复制 `swe` 版本的 `my_mcp.py` 到 `market`**

直接以 `src/swe/app/routers/my_mcp.py` 为基线复制，保留：

- 请求/响应 schema
- 列表/详情/创建/更新/删除/启停
- 草稿测试与详情测试
- 发布 MCP 到市场
- 敏感字段保护与掩码恢复

- [ ] **Step 2: 修正导入路径使文件可在 `market` 中导入**

重点处理：

- `swe.config.config`
- `swe.app.mcp.stateful_client`
- 脱敏恢复 helper 的导入路径
- 原来依赖 `swe.app` 相对路径的部分

- [ ] **Step 3: 在 `market` 路由注册中挂载 `my_mcp`**

要求：

- 保持接口前缀仍为 `/api/my-mcp`
- 不改前端现有调用路径

---

## Task 2: 替换 workspace / agent 上下文依赖

**Files:**
- Create: `market/src/market/app/my_mcp_helpers.py`
- Modify: `market/src/market/app/routers/my_mcp.py`
- Test: `market/tests/unit/app/test_my_mcp_helpers.py`

- [ ] **Step 1: 写失败测试，覆盖请求头解析与 agent 配置定位**

最少覆盖：

- 从 `X-User-Id` / `X-Tenant-Id` / `X-Source-Id` / `X-Agent-Id` 解析目标上下文
- 默认 agent 回退为 `default`
- source-scoped tenant 的定位逻辑保持与 `swe` 一致

- [ ] **Step 2: 在 `market` 中实现 `load_agent_config_for_request()` helper**

要求：

- 不依赖 `multi_agent_manager`
- 直接基于 header / context 定位本地 agent 配置文件
- 返回最小可用上下文对象与 agent 配置

- [ ] **Step 3: 替换原 `get_agent_and_config_for_request()` 调用**

`market` 版 `my_mcp.py` 不再依赖 `swe.app.agent_context.get_agent_and_config_for_request()`。

---

## Task 3: 在 market 中实现配置保存后的 reload

**Files:**
- Modify: `market/src/market/app/my_mcp_helpers.py`
- Modify: `market/src/market/app/routers/my_mcp.py`
- Test: `market/tests/unit/app/test_my_mcp_helpers.py`

- [ ] **Step 1: 先写 reload 调用测试与最小 smoke test**

覆盖：

- 保存成功后触发 reload
- 保存失败不触发 reload
- reload 失败不回滚配置，但要可记录

- [ ] **Step 2: 复用 `swe` 现有 reload 调用链**

要求：

- 优先直接调用 `swe` 已有 reload helper 或等价入口
- 不新增新的跨服务 HTTP 协议
- 保持异步非阻塞语义

- [ ] **Step 3: 替换原 `schedule_agent_reload()` 调用**

将 `market` 版 `my_mcp.py` 中所有 reload 调用切到 `market` helper。

---

## Task 4: 将“发布到市场”从回环 HTTP 改为内部调用

**Files:**
- Modify: `market/src/market/app/routers/my_mcp.py`
- Modify: `market/src/market/marketplace/service.py`
- Test: `market/tests/unit/app/routers/test_my_mcp.py`

- [ ] **Step 1: 写失败测试，覆盖 `/api/my-mcp/publish`**

覆盖：

- 正常读取本地 MCP 并发布成功
- 本地缺失 MCP 时逐项返回失败
- `bbk_ids` 为空与非空的处理

- [ ] **Step 2: 删除 `my_mcp` 中对本地 market HTTP 的回调**

替换为直接调用当前进程内的：

- `request.app.state.marketplace.publish_mcp(...)`

- [ ] **Step 3: 保持返回结构不变**

继续返回：

- `results[]`
- `client_key`
- `item_id`
- `success`
- `error`

---

## Task 5: 切换前端 `MyMCP` API 到 market 服务

**Files:**
- Modify: `console/src/api/modules/myMcp.ts`
- Modify: `console/src/pages/MyMCP/*`（仅在请求路径或错误提示需要时）

- [ ] **Step 1: 确认 `myMcpApi` 请求指向 market 服务**

要求：

- 所有 `/my-mcp` 请求都打到 `market`
- 不再依赖 `swe` 中旧路由

- [ ] **Step 2: 保持前端页面交互不变**

不改：

- 详情布局
- 创建/编辑弹窗
- 草稿测试
- 上架弹窗

- [ ] **Step 3: 确认错误提示继续显示真实后端错误**

避免再次退回只显示“操作失败”。

---

## Task 6: 删除 swe 旧路由并完成清理

**Files:**
- Delete: `src/swe/app/routers/my_mcp.py`
- Modify: `src/swe/app/routers/__init__.py` 或等效注册文件
- Modify: 相关测试引用

- [ ] **Step 1: 搜索所有旧 `my_mcp` 引用**

定位：

- 路由注册
- 测试导入
- 任何直接依赖 `swe.app.routers.my_mcp` 的地方

- [ ] **Step 2: 删除旧文件与注册**

要求：

- `swe` 启动不再引用旧 `my_mcp.py`
- 不保留双路由并存

- [ ] **Step 3: 确认前端与测试不再依赖旧路径**

---

## Task 7: 验证迁移后的 MyMCP 全链路

**Files / commands:**
- `market/tests/unit/app/routers/test_my_mcp.py`
- `market/tests/unit/app/test_my_mcp_helpers.py`
- 前端定向检查与必要联调

- [ ] **Step 1: 运行 Python 定向测试**

建议至少覆盖：

- 列表 / 详情
- 创建 / 更新 / 删除 / 启停
- 草稿测试 / 连接测试
- 发布
- 配置保存后的 reload 调用

- [ ] **Step 2: 运行前端定向检查**

确认：

- `MyMCP` 页能正常打开
- 创建 / 编辑 / 测试 / 上架链路不因服务迁移失效

- [ ] **Step 3: 人工验收**

至少验证：

1. 创建 MCP 后能立即生效
2. 编辑 MCP 后能 reload 生效
3. 删除 MCP 后列表刷新正常
4. 测试连接和草稿测试正常
5. 上架到市场正常
6. `swe` 中不再保留 `my_mcp.py`

---

## Notes

- 本次迁移不追求服务边界纯净，允许 `market` 直接依赖 `swe` 内部模块。
- 优先保证行为一致，不主动抽共享库。
- 如果 reload 链路无法直接复用现有 helper，再补最小适配层，不要在中途改造整套架构。
