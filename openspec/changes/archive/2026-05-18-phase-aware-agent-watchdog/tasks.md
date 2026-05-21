## 1. Phase State And Diagnostics

- [x] 1.1 Add an Agent phase-state model to `SWEAgent` with phase, phase start time, last activity time, tool name, tool call id, and reason fields.
- [x] 1.2 Add context-manager style helpers to enter and restore Agent phases safely across normal completion, exceptions, and cancellation.
- [x] 1.3 Update `SWEAgent.print()` to record output activity without erasing the active phase metadata.
- [x] 1.4 Add structured watchdog diagnostic logging that includes phase, phase duration, silence duration, threshold, session id, user id, agent id, tool name, and tool call id where available.

## 2. Phase-Aware Watchdog Policy

- [x] 2.1 Replace the one-shot watchdog sleep with a periodic phase-aware watchdog loop.
- [x] 2.2 Preserve cancellation behavior for reasoning, summarizing, and unknown phases after the configured idle threshold.
- [x] 2.3 Prevent tool execution phases from being cancelled solely because no user-visible output was produced.
- [x] 2.4 Ensure the global query timeout remains the outer wall-clock bound for the full request.

## 3. Tool Execution Bounds

- [x] 3.1 Enter tool-related phases around guarded tool decisions, approval replay, and actual tool execution in `ToolGuardMixin`.
- [x] 3.2 Preserve existing MCP, LLM, shell, and file-search timeout behavior as the primary timeout paths for those subsystems.
- [x] 3.3 Add a configurable generic local tool hard-timeout path for tool executions that do not already have a more specific timeout.
- [x] 3.4 Return or log tool hard-timeout failures as tool execution failures, not Agent output-idle watchdog interruptions.

## 4. File Write Instrumentation

- [x] 4.1 Add timing and byte-size diagnostics to built-in `write_file` without changing write semantics.
- [x] 4.2 Add matching timing and byte-size diagnostics to built-in `append_file`.
- [x] 4.3 Ensure file-write diagnostics never log file contents.
- [x] 4.4 Emit slow-write warnings only when duration exceeds the configured diagnostic threshold.

## 5. Tests

- [x] 5.1 Add a unit test showing a silent reasoning phase exceeding watchdog idle threshold interrupts the Agent.
- [x] 5.2 Add a unit test showing a silent async tool phase within its hard timeout is not interrupted by output-idle watchdog policy.
- [x] 5.3 Add a unit test showing a generic local tool phase exceeding its hard timeout fails as a tool timeout.
- [x] 5.4 Add a unit test verifying watchdog logs include phase and tool metadata when interrupting.
- [x] 5.5 Add a unit test verifying built-in file-write diagnostics include size and timing but not content.

## 6. Verification

- [x] 6.1 Run the targeted watchdog and file-tool unit tests.
- [x] 6.2 Run existing tests covering runner timeout, MCP timeout, tool guard, and file tools.
- [x] 6.3 Run `gitnexus_detect_changes()` before any commit to verify affected execution flows match the expected Agent/watchdog/tool scope.
