## 1. Configuration Constants

- [x] 1.1 Add `MCP_PER_NOTIFICATION_TIMEOUT` constant to `src/swe/constant.py` using `EnvVarLoader.get_float("SWE_MCP_PER_NOTIFICATION_TIMEOUT", 120.0, min_value=10.0)`
- [x] 1.2 Add `MCP_MAX_TOTAL_TIMEOUT` constant to `src/swe/constant.py` using `EnvVarLoader.get_float("SWE_MCP_MAX_TOTAL_TIMEOUT", 0.0, min_value=0.0)`

## 2. Timeout Refresh Function

- [x] 2.1 Add `_call_with_timeout_refresh` async function to `src/swe/app/mcp/stateful_client.py` — implements the per-notification timeout loop using `asyncio.Event`, falls back to `_call_with_timeout` when `progress_event` is None, enforces `max_total_timeout` ceiling
- [x] 2.2 Add import for new constants (`MCP_PER_NOTIFICATION_TIMEOUT`, `MCP_MAX_TOTAL_TIMEOUT`) in `stateful_client.py`

## 3. StatefulClient call_tool Modifications

- [x] 3.1 Modify `StdIOStatefulClient.call_tool` to create `asyncio.Event`, inject `_on_progress` callback into `session._progress_callbacks[progressToken]`, call `_call_with_timeout_refresh`, and clean up in `finally`
- [x] 3.2 Modify `HttpStatefulClient.call_tool` with the same pattern as 3.1

## 4. _patched_mcp_call Modification

- [x] 4.1 Modify `_patched_mcp_call` in `src/swe/app/mcp/__init__.py` to create `asyncio.Event`, inject `_on_progress` callback into `session._progress_callbacks[progressToken]`, call `_call_with_timeout_refresh`, and clean up in `finally` for both the `client_gen` and `session` code paths
- [x] 4.2 Add imports for `_call_with_timeout_refresh`, `MCP_PER_NOTIFICATION_TIMEOUT`, `MCP_MAX_TOTAL_TIMEOUT` in `__init__.py`

## 5. Tests

- [x] 5.1 Create `tests/unit/app/mcp/test_timeout_refresh.py` with test for: notification refresh resets timeout and tool completes successfully
- [x] 5.2 Add test: no notification within per-notification timeout raises `asyncio.TimeoutError`
- [x] 5.3 Add test: no progressToken in meta falls back to `_call_with_timeout`
- [x] 5.4 Add test: `max_total_timeout` ceiling cancels call despite ongoing notifications
- [x] 5.5 Add test: `_progress_callbacks` injection and cleanup on success, timeout, and cancellation
- [x] 5.6 Add test: tool completes before any notification (task done check at loop top)

## 6. 进度通知刷新 Agent 看门狗

- [x] 6.1 在 `_call_with_timeout_refresh` 中增加 `on_progress_callback` 参数，收到进度通知后调用回调
- [x] 6.2 在 `StatefulClientBase` 上增加 `on_progress_callback` 属性（默认 `None`）
- [x] 6.3 修改 `StdIOStatefulClient.call_tool` 和 `HttpStatefulClient.call_tool`，将 `self.on_progress_callback` 传递到 `_call_with_timeout_refresh`，并在 `_on_progress` 中调用
- [x] 6.4 修改 `_patched_mcp_call`，从 `self.client` 读取 `on_progress_callback`，传递到 `_call_with_timeout_refresh`，并在 `_on_progress` 中调用
- [x] 6.5 修改 `src/swe/agents/react_agent.py` 的 `register_mcp_clients()`，设置 `client.on_progress_callback = self._reset_watchdog`
- [x] 6.6 添加测试：`on_progress_callback` 在进度通知时被调用
- [x] 6.7 添加测试：`on_progress_callback` 为 `None` 时不影响正常行为
