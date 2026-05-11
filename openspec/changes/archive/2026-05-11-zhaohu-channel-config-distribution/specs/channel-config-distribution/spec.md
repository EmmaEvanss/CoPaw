## ADDED Requirements

### Requirement: 通道配置分发 API
系统 SHALL 提供 `POST /config/channels/{channel_name}/distribute` 端点，支持将源租户的通道配置字段分发到目标租户。

#### Scenario: 分发指定字段到目标租户
- **WHEN** 提交分发请求，指定 `fields=["robot_open_id", "client_id", "client_secret"]` 和 `target_tenant_ids=["tenant-a", "tenant-b"]`
- **THEN** 系统 SHALL 从源租户的通道配置中读取指定字段的值
- **AND** 将这些字段值写入每个目标租户的 `agent.json` 对应通道节点
- **AND** 返回每个目标租户的分发结果

#### Scenario: 非覆盖模式保护已有值
- **WHEN** 分发请求设置 `overwrite=False`
- **AND** 目标租户的某个字段已有非空值
- **THEN** 系统 SHALL NOT 覆盖该字段的已有值
- **AND** 仅填充目标租户中为空或不存在的字段

#### Scenario: 覆盖模式写入所有指定字段
- **WHEN** 分发请求设置 `overwrite=True`
- **THEN** 系统 SHALL 用源租户的值覆盖目标租户的所有指定字段，无论目标租户是否已有值

#### Scenario: 默认分发全部字段
- **WHEN** 分发请求未指定 `fields` 参数
- **THEN** 系统 SHALL 分发源租户该通道下的所有字段

#### Scenario: 分发后触发目标租户热重载
- **WHEN** 分发成功写入目标租户配置
- **THEN** 系统 SHALL 对每个成功的目标租户触发 `schedule_agent_reload`

#### Scenario: 部分租户失败不影响成功租户
- **WHEN** 分发请求包含多个目标租户
- **AND** 其中一个租户写入失败
- **THEN** 已成功的租户写入 SHALL 保持不变
- **AND** 响应 SHALL 报告每个租户的成功/失败状态

### Requirement: 分发请求模型
通道配置分发请求 SHALL 包含以下字段。

#### Scenario: 请求体结构
- **WHEN** 提交分发请求
- **THEN** 请求体 SHALL 包含 `target_tenant_ids: list[str]`（目标租户列表）
- **AND** 可选 `fields: list[str] | None`（指定分发字段，默认全部）
- **AND** `overwrite: bool`（是否覆盖，默认 False）

### Requirement: 分发响应模型
通道配置分发响应 SHALL 报告每个目标租户的分发结果。

#### Scenario: 响应体结构
- **WHEN** 分发请求完成
- **THEN** 响应 SHALL 包含 `results: list` 数组
- **AND** 每个结果 SHALL 包含 `tenant_id`、`success: bool`、`error: str | None`

### Requirement: Console 分发 UI
Console 通道管理页面 SHALL 提供通道配置分发操作入口。

#### Scenario: Zhaohu 通道 drawer 显示分发按钮
- **WHEN** 用户打开 Zhaohu 通道的 ChannelDrawer
- **THEN** drawer footer 区域 SHALL 显示"分发到租户"按钮

#### Scenario: 分发弹窗提交
- **WHEN** 用户点击"分发到租户"按钮
- **THEN** 弹出 Modal，包含目标租户 ID 输入（Select mode="tags"）和覆盖开关（Switch）
- **WHEN** 用户确认提交
- **THEN** 调用分发 API 并展示结果

### Requirement: Console 分发 API 模块
Console API 模块 SHALL 提供 `distributeChannelConfig` 方法。

#### Scenario: 调用分发 API
- **WHEN** 前端需要执行通道配置分发
- **THEN** `distributeChannelConfig(channelName, targetTenantIds, fields?, overwrite?)` SHALL 调用 `POST /config/channels/{channel_name}/distribute`
