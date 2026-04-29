## Why

`_call_with_timeout` 使用单一 `asyncio.wait_for(coro, timeout=120s)` 处理所有 MCP `call_tool` 调用。长时间运行的工具（如数据生成、批处理）可能超过 120s 并因 `TimeoutError` 失败，但全局提高超时值又会让真正卡住的请求无限挂起。MCP 协议已支持服务器发送 `notifications/progress`，且 `_patched_mcp_call` 已生成 `progressToken` —— 但未注册回调，进度通知被静默丢弃，无法刷新超时。

此外，即使 MCP 客户端层正确处理了进度通知的超时刷新，该信号也不会传递到 Agent 层的看门狗（watchdog）。当 MCP 工具持续发送进度通知（如"等待中"）时，Agent 的 300s 看门狗仍会因 "no output" 而触发中断，导致正在正常工作的工具调用被错误终止。

## What Changes

- 增加按通知的超时刷新：MCP 服务器每发送一条 `notifications/progress`，就重置倒计时，使报告进度的长运行工具不会触发超时，同时仍能防护真正卡住的调用。
- 增加硬性 `max_total_timeout` 上限，防止通知风暴无限延长超时。
- 通过 `session._progress_callbacks` 注入注册 `progress_callback`，使 SDK 将进度通知分发到我们的处理函数。
- 两个新的环境可配置常量：`MCP_PER_NOTIFICATION_TIMEOUT`（默认 120s）和 `MCP_MAX_TOTAL_TIMEOUT`（默认 0 = 无限制）。
- **MCP 进度通知刷新 Agent 看门狗**：在 MCP 调用链中增加 `on_progress_callback` 参数，Agent 将 `_reset_watchdog` 注册为回调，使进度通知同时刷新看门狗定时器。
- 在 `StatefulClientBase` 上增加 `on_progress_callback` 属性，Agent 注册 MCP 客户端时设置该属性。
- 向后兼容：不发送进度通知的服务器行为与当前完全一致。

## Capabilities

### New Capabilities
- `mcp-notification-timeout-refresh`: MCP `call_tool` 的按通知超时刷新 —— 每收到一条进度通知即重置超时倒计时，可配置按通知超时和最大总超时；进度通知同时刷新 Agent 看门狗定时器。

### Modified Capabilities
<!-- No existing capability specs are modified at the requirements level. -->

## Impact

- `src/swe/constant.py` — 2 new config constants
- `src/swe/app/mcp/stateful_client.py` — `_call_with_timeout_refresh` 增加 `on_progress_callback` 参数；`StatefulClientBase` 增加 `on_progress_callback` 属性；`StdIOStatefulClient.call_tool` 和 `HttpStatefulClient.call_tool` 传递回调
- `src/swe/app/mcp/__init__.py` — `_patched_mcp_call` 读取客户端回调并传递
- `src/swe/agents/react_agent.py` — `register_mcp_clients()` 设置 `client.on_progress_callback = self._reset_watchdog`
- `tests/unit/app/mcp/test_timeout_refresh.py` — 新增 `on_progress_callback` 测试
- No API or dependency changes; fully backward compatible
