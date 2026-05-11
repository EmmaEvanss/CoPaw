## MODIFIED Requirements

### Requirement: Case 2 Non-Streaming Processing
Case 2 任务分配 SHALL 使用非流式处理模式，且根据调用方传入的 `include_link` 参数决定是否在卡片中包含跳转链接。

#### Scenario: Send task initiated card with link
- **WHEN** Case 2 任务分配场景触发
- **AND** 调用方传入 `include_link=True`
- **THEN** 系统立即发送"任务已发起"卡片通知
- **AND** 卡片包含 Claw URL 可跳转查看进度

#### Scenario: Send task initiated card without link
- **WHEN** Case 2 任务分配场景触发
- **AND** 调用方传入 `include_link=False`
- **THEN** 系统立即发送"任务已发起"卡片通知
- **AND** 卡片 SHALL NOT 包含跳转链接 content 块

#### Scenario: Process task in background
- **WHEN** 任务分配开始处理
- **THEN** 系统在后台异步运行 LLM
- **AND** NOT 发送流式事件给前端

#### Scenario: Send complete result
- **WHEN** 任务处理完成
- **THEN** 系统发送完整的处理结果给用户
- **AND** 用户收到的是一条完整消息而非多条流式碎片

#### Scenario: Handle processing error
- **WHEN** 任务处理过程中发生异常
- **THEN** 系统发送错误通知给用户
- **AND** 错误通知内容为"抱歉，处理您的任务时发生错误，请稍后重试。"

### Requirement: Custom Card Templates
系统 SHALL 支持自定义卡片消息发送，且 `_build_task_initiated_card` 和 `_build_task_progress_card` 接受 `include_link` 参数控制跳转链接的渲染。

#### Scenario: Template 1 - Task initiated card with link
- **WHEN** 发送任务发起通知，且 `include_link=True`
- **THEN** 卡片内容包含任务描述和跳转链接
- **AND** 使用 OAuth Token 认证

#### Scenario: Template 1 - Task initiated card without link
- **WHEN** 发送任务发起通知，且 `include_link=False`
- **THEN** 卡片内容包含任务描述
- **AND** 卡片 SHALL NOT 包含跳转链接

#### Scenario: Template 2 - Task progress card with link
- **WHEN** 发送任务进度查询结果，且 `include_link=True`
- **THEN** 已完成任务显示"查看结果"操作按钮
- **AND** 按钮链接指向 `result_url`

#### Scenario: Template 2 - Task progress card without link
- **WHEN** 发送任务进度查询结果，且 `include_link=False`
- **THEN** 已完成任务 SHALL NOT 显示"查看结果"操作按钮
- **AND** SHALL NOT 生成 `result_url`

#### Scenario: Card send with OAuth
- **WHEN** 发送自定义卡片
- **THEN** 系统使用 OAuth Token 进行认证
- **AND** Token 通过 `bearer` 方式放在 Authorization header

### Requirement: Claw URL Generation
ZhaohuChannel 的 Claw URL 构造 SHALL 根据 `include_link` 参数决定是否生成。

#### Scenario: Build claw URL when link included
- **WHEN** `_build_task_initiated_card` 或 `_build_task_progress_card` 传入 `include_link=True`
- **AND** 需要 Card 跳转到 session 页面
- **THEN** 系统构造 URL 包含 sessionId 参数
- **AND** URL 格式为 `CMBMobileOA:///?pcSysId={sys_id}&pcParams={encoded}`

#### Scenario: Skip claw URL when link excluded
- **WHEN** `_build_task_initiated_card` 或 `_build_task_progress_card` 传入 `include_link=False`
- **THEN** 系统 SHALL NOT 调用 `_build_claw_url`
- **AND** 卡片中 SHALL NOT 包含 claw_url 相关字段

### Requirement: ZhaohuChannel 按 source 控制卡片链接
ZhaohuChannel 的任务卡片调用方 SHALL 根据租户 source_id 传入 `include_link` 参数。

#### Scenario: 任务分配时 RMASSIST 租户包含链接
- **WHEN** `_handle_task_assignment` 处理任务分配
- **AND** 租户 `source_id` 为 `RMASSIST`
- **THEN** 调用 `_build_task_initiated_card` 时 SHALL 传入 `include_link=True`

#### Scenario: 任务分配时非 RMASSIST 租户不包含链接
- **WHEN** `_handle_task_assignment` 处理任务分配
- **AND** 租户 `source_id` 不是 `RMASSIST`
- **THEN** 调用 `_build_task_initiated_card` 时 SHALL 传入 `include_link=False`

#### Scenario: LLM 通知时 RMASSIST 租户包含链接
- **WHEN** `_run_task_llm_and_notify` 发送任务完成通知
- **AND** 租户 `source_id` 为 `RMASSIST`
- **THEN** 调用 `_build_task_initiated_card` 时 SHALL 传入 `include_link=True`

#### Scenario: LLM 通知时非 RMASSIST 租户不包含链接
- **WHEN** `_run_task_llm_and_notify` 发送任务完成通知
- **AND** 租户 `source_id` 不是 `RMASSIST`
- **THEN** 调用 `_build_task_initiated_card` 时 SHALL 传入 `include_link=False`

#### Scenario: 进度查询时 RMASSIST 租户包含链接
- **WHEN** `_query_task_progress` 查询任务进度
- **AND** 租户 `source_id` 为 `RMASSIST`
- **THEN** 调用 `_build_task_progress_card` 时 SHALL 传入 `include_link=True`

#### Scenario: 进度查询时非 RMASSIST 租户不包含链接
- **WHEN** `_query_task_progress` 查询任务进度
- **AND** 租户 `source_id` 不是 `RMASSIST`
- **THEN** 调用 `_build_task_progress_card` 时 SHALL 传入 `include_link=False`
