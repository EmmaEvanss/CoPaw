## Context

CoPaw 采用多租户隔离架构，每个租户拥有独立的工作区目录（`~/.swe/<tenant>/workspaces/default/`）。工作区中存放模板文件（AGENTS.md、SOUL.md 等），这些文件定义了智能体的行为和人格。当前缺少将一个租户的模板文件批量推送到其他租户的能力，管理员只能逐个上传，效率低下。

已有的分发模式可复用：
- **技能广播**（`src/swe/app/routers/skills.py`）：后端逐租户处理、`TenantInitializer` 引导、`asyncio.to_thread` 阻塞操作
- **MCP distribute**（`console/src/pages/Agent/MCP/index.tsx`）：前端页面级选择、内联 Modal、`TenantTargetPicker`、异步加载租户

## Goals / Non-Goals

**Goals:**
- 提供后端文件分发服务，支持将指定工作区文件复制到多个目标租户
- 前端交互对齐 MCP distribute 模式：页面级文件选择 → 分发按钮 → 内联弹窗选租户
- 目标租户目录不存在时自动创建（通过 `TenantInitializer`）
- 逐租户错误隔离，单个租户失败不阻塞其他租户
- 强制 `overwrite=true` 校验、源文件前置校验

**Non-Goals:**
- 不支持增量/差异同步，仅全量覆盖
- 不支持回滚（简单文件复制场景不需要，区别于 MCP 的配置写入）
- 不支持选择性覆盖（不提供 overwrite=false 选项）
- 不支持分发非 BROADCASTABLE_FILES 文件

## Decisions

### 1. 独立服务类 vs 内联路由逻辑

**选择：独立 `FileBroadcastService` 类**

理由：与技能广播模式对齐（`_broadcast_skills_to_tenant` 是独立逻辑），便于测试和复用。路由层仅负责请求校验和参数组装。

替代方案：在 `workspace.py` 路由中内联实现。被否决——逻辑较复杂（租户校验、目录初始化、逐租户复制），内联会导致路由函数过长且难以测试。

### 2. 前端交互模式：MCP distribute vs SkillPool BroadcastModal

**选择：MCP distribute 模式**

理由：文件选择适合在页面卡片上完成（用户需要看到文件内容再决定是否分发），内联 Modal 更轻量。SkillPool 的 BroadcastModal 是因为技能池有独立的选择逻辑才使用独立组件。

替代方案：独立 `FileBroadcastModal` 组件。被否决——增加了不必要的组件层级，且与 MCP distribute 模式不一致。

### 3. 可广播文件范围

**选择：白名单 `BROADCASTABLE_FILES` 元组**

当前包含：AGENTS.md、BOOTSTRAP.md、HEARTBEAT.md、MEMORY.md、PROFILE.md、SOUL.md

理由：防止意外分发日常记忆、会话数据等非模板文件，与技能广播的白名单模式一致。

### 4. 租户目录自动创建

**选择：使用 `TenantInitializer.ensure_seeded_bootstrap()`**

理由：与技能广播一致，目标租户可能首次访问，需要引导创建目录结构和基础配置。

### 5. 前端租户列表获取

**选择：打开弹窗时异步获取，调用 `GET /workspace/broadcast/tenants`**

理由：与 MCP distribute 一致，租户列表可能变化，打开时获取保证数据新鲜。排除当前租户避免自我分发。

## Risks / Trade-offs

- **[覆盖风险]** 目标租户同名文件被无条件覆盖 → 前端橙色警告框明确提示，后端强制 `overwrite=true`
- **[首次分发引导]** 目标租户目录不存在时自动 bootstrap → 通过 `bootstrapped` 字段在结果中标记，前端展示给用户
- **[并发写入]** 多个管理员同时向同一租户分发 → 当前无锁机制，依赖文件系统原子性（`shutil.copy2`），对于小 MD 文件风险可接受
- **[大文件分发]** 当前仅限 MD 文件，体积小 → 若未来扩展到大文件需增加超时和分片机制
