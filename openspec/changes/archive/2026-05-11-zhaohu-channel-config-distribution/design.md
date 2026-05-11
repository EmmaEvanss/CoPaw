## Context

Zhaohu 通道的 `robot_open_id`、`client_id`、`client_secret` 是机器人级配置，当前只能通过环境变量或直接编辑 `agent.json` 设置。Console 通道管理页面 (`ChannelDrawer.tsx`) 的 `renderBuiltinExtraFields` 已有 14 个通道的渲染分支，但缺少 zhaohu。系统中已存在两套成熟的跨租户分发基础设施（MCP 分发 `mcp.py` 和模型分发 `providers.py`），可复用其模式。`swe_tenant_init_source` 表已存在，记录租户与 source 的映射关系。

## Goals / Non-Goals

**Goals:**
- P0：Console 页面可视化配置 Zhaohu 三个核心字段，敏感字段保护
- P1：通道配置按字段级分发到目标租户，非覆盖模式保护已有值
- P2：仅 RMASSIST 来源租户的通知卡片包含跳转链接

**Non-Goals:**
- 不重构现有分发基础设施，只复用模式
- 不做通道配置的全量同步（只分发指定字段）
- 不修改其他通道的渲染逻辑
- 不新增数据库表

## Decisions

### D1: 复用 MCP/Model 分发模式，在 config.py 新增分发端点

**选择**：在 `config.py` 新增 `POST /config/channels/{channel_name}/distribute`，复用 `mcp.py` 和 `providers.py` 已建立的分发模式（tenant listing、bootstrap、overwrite guard、per-tenant result）。

**替代方案**：在 `mcp.py` 扩展现有端点 → 语义不匹配，MCP 分发和通道配置分发是不同领域。

**理由**：config.py 已有通道 CRUD 端点，分发是通道配置的自然扩展。复用 `MCPDistributionRequest` → `ChannelDistributionRequest` 的模型模式，保持一致性。

### D2: 字段级分发而非通道级整体分发

**选择**：`fields` 参数可选，默认分发通道下所有字段。`overwrite=False` 时仅填充目标租户中为空/不存在的字段。

**替代方案**：始终整通道覆盖 → 风险高，可能覆盖目标租户的自定义配置（如自定义 push_url）。

**理由**：Zhaohu 三个字段是机器人级共享配置，但其他字段（push_url、oauth_url）可能租户不同。字段级分发更安全。

### D3: is_tenant_source 便捷方法放在 tenant_init_source_store.py

**选择**：在 `TenantInitSourceStore` 类上新增 `is_tenant_source(tenant_id, expected_source_id)` 方法，暴露模块级便捷函数。

**替代方案**：在每个调用点内联查询 → 代码重复，三处调用点（CronManager + ZhaohuChannel 两处）会重复相同逻辑。

**理由**：`TenantInitSourceStore` 已有 `get_sources_for_tenant` 方法，新增判断方法是自然扩展。模块级函数 `is_tenant_source` 与现有的 `get_tenant_init_source_store` 模式一致。

### D4: include_link 参数控制卡片链接渲染

**选择**：在 `_build_task_initiated_card` 和 `_build_task_progress_card` 新增 `include_link: bool = True` 参数，调用方根据 `is_tenant_source` 结果传入。

**替代方案**：在卡片构建方法内部查询 source → 卡片方法不应承担业务判断职责，违反单一职责。

**理由**：卡片构建是纯渲染逻辑，source 判断是业务逻辑，分离更清晰。`include_link=True` 默认值保证向后兼容。

## Risks / Trade-offs

- **[R1] 分发 API 权限** → 当前 config.py 端点无鉴权，依赖 K8s 网络策略。分发 API 同理，不额外加鉴权。
- **[R2] is_tenant_source 在无 DB 时的兜底** → `get_tenant_init_source_store()` 返回 None 时 `is_tenant_source` 返回 False，即无记录租户不拼接链接，符合安全兜底原则。
- **[R3] 分发期间目标租户 agent.json 并发写入** → 采用文件级写入（与 MCP 分发一致），无锁。极低概率竞争，与现有行为一致。
