## Why

Zhaohu 通道的 `robot_open_id`、`client_id`、`client_secret` 三个核心字段当前只能通过环境变量或直接编辑 `agent.json` 配置，前端无可视化配置入口；此外，管理员无法将配置批量分发到多个租户，且所有租户的通知卡片无条件拼接 W+/claw 跳转链接，但实际只有 `RMASSIST` 来源的租户需要该链接。

## What Changes

- **P0**：Console 通道管理页面新增 Zhaohu 渲染分支，暴露 `robot_open_id`、`client_id` 三个字段，`client_secret` 使用密码输入框保护
- **P1**：后端新增通道配置分发 API，支持将源租户的通道配置字段级分发到目标租户（非覆盖模式保护已有值），前端 ChannelDrawer 新增"分发到租户"按钮
- **P2**：根据租户 `source_id` 控制通知卡片跳转链接拼接，仅 `RMASSIST` 来源租户包含跳转链接，涉及 CronManager 和 ZhaohuChannel 三处代码

## Capabilities

### New Capabilities
- `zhaohu-channel-config-ui`: Zhaohu 通道字段在 Console 通道管理页面的可视化配置，包含敏感字段保护
- `channel-config-distribution`: 通道配置的租户级分发能力，支持字段级选择、非覆盖模式、热重载
- `source-based-link-control`: 基于租户 source_id 控制通知卡片跳转链接的拼接逻辑

### Modified Capabilities
- `zhaohu-channel-design`: 新增 `include_link` 参数控制卡片是否包含跳转链接，`_build_task_initiated_card` 和 `_build_task_progress_card` 行为变更

## Impact

- **前端**：`ChannelDrawer.tsx`、`constants.ts`、`channel.ts` API 模块
- **后端**：`config.py` 路由（新增分发端点）、`tenant_init_source_store.py`（新增 `is_tenant_source` 方法）、`crons/manager.py`（链接拼接逻辑）、`channels/zhaohu/channel.py`（卡片构建方法）
- **数据库**：无变更，配置存储在 `agent.json`，`swe_tenant_init_source` 表已存在
- **API**：新增 `POST /config/channels/{channel_name}/distribute`
