## ADDED Requirements

### Requirement: Zhaohu 通道字段在 Console 可视化配置
Console 通道管理页面的 ChannelDrawer SHALL 在 `renderBuiltinExtraFields` 中为 `zhaohu` 通道渲染三个配置字段：`robot_open_id`、`client_id`、`client_secret`。

#### Scenario: 选择 Zhaohu 通道时显示配置字段
- **WHEN** 用户在通道管理页面选择 `zhaohu` 通道
- **THEN** ChannelDrawer SHALL 显示 `robot_open_id`（普通输入框）、`client_id`（普通输入框）、`client_secret`（密码输入框）三个表单字段

#### Scenario: client_secret 使用密码输入框
- **WHEN** Zhaohu 通道的 `client_secret` 字段被渲染
- **THEN** 该字段 SHALL 使用 `Input.Password` 组件
- **AND** 输入内容 SHALL 被遮蔽显示

#### Scenario: robot_open_id 和 client_id 为必填字段
- **WHEN** 用户提交 Zhaohu 通道配置
- **THEN** `robot_open_id` 和 `client_id` SHALL 为必填项
- **AND** `client_secret` SHALL 为必填项

### Requirement: Zhaohu 通道标签显示
Console 通道管理页面 SHALL 为 `zhaohu` 通道提供正确的显示标签。

#### Scenario: 通道列表中显示 Zhaohu 标签
- **WHEN** `zhaohu` 通道出现在通道列表或下拉选项中
- **THEN** 显示标签 SHALL 为 "Zhaohu"

### Requirement: 保存后热重载生效
用户在 Console 保存 Zhaohu 通道配置后，配置 SHALL 写入 `agent.json` 并触发热重载。

#### Scenario: 保存配置写入 agent.json
- **WHEN** 用户填写 Zhaohu 三个字段并点击保存
- **THEN** 系统 SHALL 将 `robot_open_id`、`client_id`、`client_secret` 写入当前租户的 `agent.json` 中 `channels.zhaohu` 节点
- **AND** 系统 SHALL 触发 Agent 热重载使配置即时生效

#### Scenario: CLI 遮蔽 client_secret
- **WHEN** 通过 CLI `swe channels list` 查看 Zhaohu 通道配置
- **THEN** `client_secret` SHALL 被 `_SECRET_FIELDS` 逻辑遮蔽显示
