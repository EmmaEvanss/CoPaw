## Why

多租户场景下，管理员需要将一个租户工作区中的模板文件（AGENTS.md、SOUL.md、PROFILE.md 等）批量复制到其他租户，以统一配置标准。目前只能逐个租户手动上传，效率低且容易遗漏。需要提供一种"文件分发"能力，让管理员在工作区页面选择文件后一键推送到多个目标租户。

## What Changes

- 新增后端 `FileBroadcastService` 服务类，支持将源租户工作区中指定的 MD 文件复制到多个目标租户的 default 工作区，目标租户目录不存在时自动通过 `TenantInitializer` 引导创建
- 新增两个 API 端点：`GET /workspace/broadcast/tenants`（获取可分发租户列表）和 `POST /workspace/broadcast/files`（执行文件分发）
- 后端强制要求 `overwrite=true` 并在分发前校验源文件存在性，与技能广播模式对齐
- 前端工作区页面重构：文件选择内联在页面卡片上，分发按钮在 PageHeader 区域，分发弹窗采用 MCP distribute 模式（内联 Modal + TenantTargetPicker），异步加载租户列表并排除当前租户
- 删除独立的 `FileBroadcastModal` 组件，分发逻辑内联至 `index.tsx`
- `FileItem` 组件新增 `selectable`/`broadcastSelected`/`onSelectToggle` 属性，支持可广播文件的选择交互
- 新增 4 语言 i18n 键（zh/en/ru/ja）覆盖分发流程所有文案
- 新增样式：选中卡片蓝色边框、选择按钮、橙色覆盖警告框、选中计数 badge，均含暗色模式

## Capabilities

### New Capabilities
- `file-broadcast`: 将工作区模板文件分发到指定租户，包含后端服务、API 端点、前端交互和 i18n

### Modified Capabilities

## Impact

- **后端**：`src/swe/app/routers/workspace.py`（新增 2 个端点）、`src/swe/app/workspace/file_broadcast.py`（新增服务类）
- **前端**：`console/src/pages/Agent/Workspace/` 目录下 `index.tsx`、`FileItem.tsx`、`FileListPanel.tsx`、`index.module.less` 重构/修改
- **前端 API**：`console/src/api/modules/workspace.ts`、`console/src/api/types/workspace.ts` 新增广播接口和类型
- **i18n**：`console/src/locales/` 下 zh/en/ru/ja 四个文件新增约 17 个键
- **依赖**：复用 `TenantInitializer`、`TenantTargetPicker`、`list_logical_tenant_ids()`，无新增外部依赖
