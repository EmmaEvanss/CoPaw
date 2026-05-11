## 1. P0: Zhaohu 通道字段页面可配置化

- [x] 1.1 在 `console/src/pages/Control/Channels/components/constants.ts` 的 `CHANNEL_LABELS` 中新增 `zhaohu: "Zhaohu"`
- [x] 1.2 在 `console/src/pages/Control/Channels/components/ChannelDrawer.tsx` 的 `renderBuiltinExtraFields` 中新增 `case "zhaohu":` 分支，渲染 `robot_open_id`（Input）、`client_id`（Input）、`client_secret`（Input.Password），三个字段均 `required`
- [x] 1.3 验证 Console → 通道 → Zhaohu → drawer 显示三个字段，`client_secret` 遮蔽显示
- [x] 1.4 验证保存后 `agent.json` 正确写入并热重载生效

## 2. P1: 通道配置分发 API

- [x] 2.1 在 `src/swe/app/routers/config.py` 新增 `ChannelDistributionRequest` 和 `ChannelDistributionTenantResult` Pydantic 模型
- [x] 2.2 实现 `POST /config/channels/{channel_name}/distribute` 端点：读取源租户通道配置、按 fields 过滤、对每个目标租户写入（非覆盖模式保护已有值）、触发热重载、返回 per-tenant 结果
- [x] 2.3 复用 `mcp.py` 中 `_validate_target_tenant_id`、`TenantInitializer.ensure_seeded_bootstrap`、`schedule_agent_reload` 等基础设施

## 3. P1: Console 分发 UI

- [x] 3.1 在 `console/src/api/modules/channel.ts` 新增 `distributeChannelConfig()` 方法
- [x] 3.2 在 `ChannelDrawer.tsx` 的 zhaohu 分支 drawer footer 新增"分发到租户"按钮，点击弹出 Modal（目标租户 Select mode="tags" + 覆盖 Switch + 确认提交）
- [x] 3.3 验证分发流程：default 租户配置 → 分发到目标租户 → `agent.json` 更新 → 热重载

## 4. P2: is_tenant_source 便捷方法

- [x] 4.1 在 `src/swe/app/workspace/tenant_init_source_store.py` 的 `TenantInitSourceStore` 类新增 `is_tenant_source(tenant_id, expected_source_id)` 方法
- [x] 4.2 新增模块级便捷函数 `is_tenant_source(tenant_id, expected_source_id)`，内部调用 store 实例方法，store 为 None 时返回 False
- [x] 4.3 编写单元测试验证：RMASSIST 租户返回 True、非 RMASSIST 返回 False、无 DB 返回 False

## 5. P2: CronManager 按 source 控制跳转链接

- [x] 5.1 修改 `src/swe/app/crons/manager.py` 的 `_push_task_success_notification`，在拼接 `link_url` 前调用 `is_tenant_source(creator_id, "RMASSIST")`，仅 RMASSIST 时设置 `link_url` 和 `link_text`
- [x] 5.2 验证：RMASSIST 租户通知包含链接，非 RMASSIST 通知不包含链接

## 6. P2: ZhaohuChannel 卡片按 source 控制跳转链接

- [x] 6.1 修改 `_build_task_initiated_card` 新增 `include_link: bool = True` 参数，`include_link=False` 时不调用 `_build_claw_url`、不渲染跳转链接 content 块
- [x] 6.2 修改 `_build_task_progress_card` 新增 `include_link: bool = True` 参数，`include_link=False` 时不生成 `result_url`、不渲染"查看结果"按钮
- [x] 6.3 修改 `_handle_task_assignment` 调用处，根据 `is_tenant_source(sap_id, "RMASSIST")` 传入 `include_link`
- [x] 6.4 修改 `_run_task_llm_and_notify` 调用处，根据 `is_tenant_source(user_id, "RMASSIST")` 传入 `include_link`
- [x] 6.5 修改 `_query_task_progress` 调用处，根据 `is_tenant_source(user_id, "RMASSIST")` 传入 `include_link`
- [x] 6.6 验证：RMASSIST 租户卡片包含链接，非 RMASSIST 卡片不包含链接，无 source 记录不包含链接
