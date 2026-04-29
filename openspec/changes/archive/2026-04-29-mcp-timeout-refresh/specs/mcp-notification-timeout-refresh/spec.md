## ADDED Requirements

### Requirement: Per-notification timeout refresh for call_tool
The system SHALL replace the single overall timeout for MCP `call_tool` with a per-notification timeout that resets each time a `notifications/progress` is received from the MCP server. When no progress notification arrives within `MCP_PER_NOTIFICATION_TIMEOUT` seconds, the call SHALL be cancelled and `asyncio.TimeoutError` raised.

#### Scenario: Tool sends progress notifications and completes successfully
- **WHEN** an MCP tool call is made with a `progressToken` in `meta`, and the server sends `notifications/progress` at 30s, 60s, and 90s, and returns a result at 100s
- **THEN** the timeout countdown SHALL reset at each notification (30s, 60s, 90s), the call SHALL NOT time out, and the result SHALL be returned

#### Scenario: Tool stops sending progress notifications
- **WHEN** an MCP tool call is made with a `progressToken` in `meta`, and the server sends one notification at 30s but sends no further notifications
- **THEN** the call SHALL time out at 30s + `MCP_PER_NOTIFICATION_TIMEOUT` seconds and raise `asyncio.TimeoutError`

#### Scenario: Tool completes without any progress notifications
- **WHEN** an MCP tool call is made with a `progressToken` in `meta`, and the server does not send any progress notifications but returns a result within `MCP_PER_NOTIFICATION_TIMEOUT` seconds
- **THEN** the result SHALL be returned without timeout

### Requirement: Max total timeout ceiling
The system SHALL enforce an optional hard maximum total timeout (`MCP_MAX_TOTAL_TIMEOUT`) for MCP `call_tool`. When `MCP_MAX_TOTAL_TIMEOUT` is greater than 0, the call SHALL be cancelled if the total elapsed time exceeds this value, regardless of how many progress notifications have been received. When `MCP_MAX_TOTAL_TIMEOUT` is 0 (default), no hard ceiling SHALL be enforced.

#### Scenario: Max total timeout exceeded despite ongoing notifications
- **WHEN** `MCP_MAX_TOTAL_TIMEOUT` is set to 300s, and the server continuously sends progress notifications, and the total elapsed time reaches 300s
- **THEN** the call SHALL be cancelled and `asyncio.TimeoutError` raised

#### Scenario: Max total timeout disabled (default)
- **WHEN** `MCP_MAX_TOTAL_TIMEOUT` is 0 (default), and the server continuously sends progress notifications
- **THEN** no hard ceiling SHALL be enforced; the call continues until per-notification timeout or completion

### Requirement: Progress callback injection and cleanup
The system SHALL register a progress callback in `session._progress_callbacks[progressToken]` before calling `session.call_tool`, and SHALL remove the callback in a `finally` block after the call completes or fails. The callback SHALL set an `asyncio.Event` to signal the timeout-refresh loop.

#### Scenario: Callback registered and cleaned up on success
- **WHEN** an MCP tool call completes successfully
- **THEN** the callback SHALL be present in `_progress_callbacks` during the call and removed after completion

#### Scenario: Callback cleaned up on timeout
- **WHEN** an MCP tool call times out
- **THEN** the callback SHALL be removed from `_progress_callbacks` after the timeout error is raised

#### Scenario: Callback cleaned up on cancellation
- **WHEN** an MCP tool call is cancelled externally
- **THEN** the callback SHALL be removed from `_progress_callbacks`

### Requirement: Fallback to single timeout without progress token
The system SHALL fall back to the existing `_call_with_timeout` behavior (single overall timeout) when no `progressToken` is present in the `meta` parameter.

#### Scenario: Call tool without progressToken in meta
- **WHEN** `call_tool` is called with `meta=None` or `meta` without a `progressToken` key
- **THEN** the call SHALL use the existing `_call_with_timeout` with a single overall timeout, without any per-notification refresh logic

### Requirement: Backward compatibility with non-progress servers
The system SHALL maintain identical behavior to the current implementation when the MCP server does not send progress notifications. The default `MCP_PER_NOTIFICATION_TIMEOUT` SHALL equal the current `MCP_CALL_TIMEOUT` (120s).

#### Scenario: Server does not support progress notifications
- **WHEN** an MCP tool call is made and the server never sends `notifications/progress`
- **THEN** the call SHALL time out after `MCP_PER_NOTIFICATION_TIMEOUT` seconds (default 120s), identical to current behavior

### Requirement: 进度通知刷新 Agent 看门狗
MCP 进度通知 SHALL 同时刷新 Agent 的看门狗定时器。当 `_call_with_timeout_refresh` 收到进度通知时，SHALL 调用 `on_progress_callback`（如果已设置）。`StatefulClientBase` SHALL 提供 `on_progress_callback` 属性（默认 `None`），Agent 在注册 MCP 客户端时 SHALL 将其看门狗重置方法设置为该属性。`_on_progress` 回调在设置 `progress_event` 的同时 SHALL 调用 `on_progress_callback`。

#### Scenario: MCP 进度通知刷新看门狗
- **WHEN** MCP 工具发送 `notifications/progress`，且 MCP 客户端已设置 `on_progress_callback = agent._reset_watchdog`
- **THEN** 看门狗定时器 SHALL 被重置，Agent 不会因 "no output" 被中断

#### Scenario: MCP 工具无进度通知时看门狗正常触发
- **WHEN** MCP 工具不发送进度通知，且 Agent 在 300s 内未产生任何输出
- **THEN** 看门狗 SHALL 正常触发并中断 Agent

#### Scenario: 未设置回调时不影响现有行为
- **WHEN** MCP 客户端的 `on_progress_callback` 为 `None`
- **THEN** 进度通知仅刷新 MCP 层超时，不影响 Agent 层行为

### Requirement: Configuration constants
The system SHALL provide two environment-configurable constants: `MCP_PER_NOTIFICATION_TIMEOUT` (env: `SWE_MCP_PER_NOTIFICATION_TIMEOUT`, default 120.0, minimum 10.0) and `MCP_MAX_TOTAL_TIMEOUT` (env: `SWE_MCP_MAX_TOTAL_TIMEOUT`, default 0.0, minimum 0.0).

#### Scenario: Custom per-notification timeout via environment
- **WHEN** `SWE_MCP_PER_NOTIFICATION_TIMEOUT` is set to 60.0
- **THEN** `MCP_PER_NOTIFICATION_TIMEOUT` SHALL be 60.0

#### Scenario: Custom max total timeout via environment
- **WHEN** `SWE_MCP_MAX_TOTAL_TIMEOUT` is set to 600.0
- **THEN** `MCP_MAX_TOTAL_TIMEOUT` SHALL be 600.0
