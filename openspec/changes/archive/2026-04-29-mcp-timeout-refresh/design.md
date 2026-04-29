## Context

当前 MCP `call_tool` 超时为单一 `asyncio.wait_for(coro, timeout=120s)` —— 一道无论服务器是否仍在活跃工作都会在 120 秒后杀死协程的硬墙。MCP 协议支持工具执行期间的 `notifications/progress`，且 `_patched_mcp_call` 已生成自定义 `progressToken` 并嵌入请求 `meta`。然而，SDK 的 `session._progress_callbacks` 字典上未注册 `progress_callback`，因此传入的进度通知被静默丢弃。

即使进度通知在 MCP 客户端层被正确处理（通过 `_call_with_timeout_refresh`），该信号也不会传递到 Agent 层。Agent 有一个 300s 的看门狗定时器，仅在 `self.print()` 被调用时重置。当 MCP 工具执行时间较长但持续发送进度通知时，Agent 的 `print()` 不会被调用，看门狗就会因 "no output" 触发中断 —— 尽管工具实际上在正常工作。

两条代码路径调用 MCP 工具：
1. **`StatefulClient.call_tool`**（通过 `_call_with_timeout`）—— 由有状态客户端管理器使用
2. **`_patched_mcp_call`**（猴子补丁到 `MCPToolFunction.__call__`）—— 由 Agent 通过 agentscope 框架使用

两条路径都需要超时刷新机制，且都需要将进度信号传递到 Agent 看门狗。

## Goals / Non-Goals

**Goals:**
- 将扁平超时替换为按通知的超时刷新
- 注册进度回调，使服务器通知重置倒计时
- 提供硬性 `max_total_timeout` 上限，防止无限延长
- MCP 进度通知同时刷新 Agent 看门狗，防止长运行工具被错误中断
- 保持完全向后兼容（无进度 = 与当前相同的 120s 超时）
- 在所有路径中清理注入的回调（正常返回、异常、取消）

**Non-Goals:**
- 修改 MCP SDK 的内部 `_progress_callbacks` 机制或 `send_request` 逻辑
- 支持 `list_tools` 或 `initialize` 调用的进度通知
- 将进度通知转发到 Agent 或控制台 UI（仅用于重置看门狗，不展示进度内容）
- 修改 `progressToken` 格式（保持 `{tenant_id}@{uuid4()}`）

## Decisions

### D1: Inject into `session._progress_callbacks` directly rather than passing `progress_callback` to `call_tool`

**Choice:** Manually inject `session._progress_callbacks[custom_token] = callback` and clean up in `finally`.

**Rationale:** The SDK's `call_tool(progress_callback=...)` auto-generates its own `progressToken` using the internal integer `request_id`, overwriting any `meta.progressToken` we set. Since `_patched_mcp_call` already uses a custom `{tenant_id}@{uuid4()}` token (which the server may depend on), we cannot use the SDK's auto-injection without changing the token format. Manual injection preserves the custom token while still getting the SDK's `_receive_loop` to dispatch notifications to our callback.

**Alternative considered:** Pass `progress_callback` to `session.call_tool()` and remove the manual `meta.progressToken`. Rejected because it changes the token format (breaks server compatibility) and the SDK still uses integer `request_id` as the dict key, not our custom string token.

### D2: `asyncio.Event` + loop instead of chaining `wait_for` calls

**Choice:** Create a single `asyncio.Event`, run the tool coroutine as a `Task`, and loop on `progress_event.wait()` with per-notification timeout. Each notification sets the event, clears it, and the loop continues. If `wait_for` times out or the task completes, the loop exits.

**Rationale:** Simpler than managing multiple `wait_for` chains. The event is set by the progress callback (which runs in the SDK's `_receive_loop`), and the main loop just watches it. A single `task.done()` check after each iteration handles normal completion.

**Alternative considered:** Use `asyncio.Queue` to pass notification events. Rejected — adds complexity for no benefit since we only need a signal (event received), not the notification data.

### D3: Fallback to `_call_with_timeout` when no progress token

**Choice:** When `progress_event` is `None` (no `progressToken` in `meta`), delegate to existing `_call_with_timeout`. This preserves exact current behavior for callers that don't use progress tokens.

### D4: Config constants with `EnvVarLoader`

**Choice:** Two new constants following the existing pattern:
- `MCP_PER_NOTIFICATION_TIMEOUT` (env: `SWE_MCP_PER_NOTIFICATION_TIMEOUT`, default 120.0, min 10.0)
- `MCP_MAX_TOTAL_TIMEOUT` (env: `SWE_MCP_MAX_TOTAL_TIMEOUT`, default 0.0, min 0.0)

`max_total_timeout=0` means no hard ceiling (fully backward compatible).

### D5: 进度通知刷新 Agent 看门狗 —— 通过 `on_progress_callback` 回调

**Choice:** 在 `_call_with_timeout_refresh` 和 MCP 调用链中增加 `on_progress_callback` 参数。`StatefulClientBase` 增加 `on_progress_callback` 属性，Agent 在 `register_mcp_clients()` 时将 `self._reset_watchdog` 设置到各 MCP 客户端上。收到进度通知时，除了设置 `progress_event` 刷新 MCP 层超时外，同时调用 `on_progress_callback()` 刷新 Agent 看门狗。

**Rationale:** 最小侵入方案 —— 不修改看门狗机制本身，仅通过回调将 MCP 进度信号传递到看门狗重置入口。`_reset_watchdog` 是同步方法，在 `_on_progress`（async）中直接调用即可。`StatefulClientBase` 上的属性使得 Agent 可以在注册时设置，而无需修改 MCP 工具函数的签名。

**Alternative considered:** 在 Agent 的 `_acting` 方法中定期检查进度状态。Rejected —— 需要修改 agentscope 框架层，且轮询方案不如回调及时。

**Alternative considered:** 将 `on_progress_callback` 作为 `call_tool` 的参数传递。Rejected —— `call_tool` 是 MCP SDK 的接口，不应为 Agent 层需求修改其签名；且 `_patched_mcp_call` 通过 `MCPToolFunction.__call__` 调用，无法从 Agent 层透传参数到 `call_tool`。

## Risks / Trade-offs

- **[Protected access to `_progress_callbacks`]** → The SDK's `_progress_callbacks` is a private attribute. If the SDK changes its internal structure, this injection will break. **Mitigation:** Pin SDK version; add a startup check that `hasattr(session, '_progress_callbacks')` and log a warning if absent, falling back to non-refresh timeout.

- **[Callback cleanup on cancellation]** → If the task is cancelled externally, the `finally` block must still run to clean up the injected callback. **Mitigation:** `try/finally` in both `call_tool` methods and `_patched_mcp_call` guarantees cleanup regardless of exit path.

- **[Event not set before task completes]** → If the tool returns a result before any notification is sent, `progress_event.wait()` would time out while the task is already done. **Mitigation:** Check `task.done()` at the top of each loop iteration before waiting.

- **[Notification storm]** → A malicious or buggy server could send progress notifications very frequently, preventing timeout indefinitely. **Mitigation:** `MCP_MAX_TOTAL_TIMEOUT` provides a hard ceiling; operators can set it to enforce a maximum.

- **[看门狗回调安全性]** → `_reset_watchdog` 是同步方法，在 async `_on_progress` 回调中直接调用。`_reset_watchdog` 只做 `self._start_watchdog()`，内部创建 `asyncio.Task`，不涉及阻塞 I/O，在 async 上下文中直接调用是安全的。 **Mitigation:** 回调仅调用同步方法创建 Task，无 await，无阻塞。
