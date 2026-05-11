## Why

The current Agent watchdog treats "no user-visible output" as "the Agent is stuck". This can misclassify long internal activity, especially tool execution or model/tool-call generation phases, and its timeout logs do not identify which phase was actually silent.

This change is needed now because timeout incidents are being attributed to `write_file`, but source and runtime checks show the current built-in `write_file` is synchronous and normally fast; the system needs phase-aware evidence and interruption rules instead of a single output-based timer.

## What Changes

- Introduce phase-aware watchdog state for Agent runs, distinguishing at least reasoning, acting/tool execution, waiting for approval/replay, summarizing, and idle/unknown phases.
- Track internal activity separately from user-visible output so watchdog decisions use the current phase and last activity timestamp.
- Emit structured timeout diagnostics containing phase, tool name, tool call id, elapsed silence, last activity, and session/agent context.
- Keep existing global query timeout behavior as the outer wall-clock bound.
- Add bounded tool-phase handling: tools should not be interrupted only because no UI output was produced, but long tool phases must remain bounded by per-tool or existing subsystem timeouts.
- Add focused diagnostics for built-in file writes: content size and open/write/close durations, without logging file contents.
- Add tests proving silent async phases are handled according to phase, and normal Agent idle detection still interrupts true stalls.

## Capabilities

### New Capabilities
- `phase-aware-agent-watchdog`: Defines phase-aware Agent liveness detection, watchdog interruption rules, and timeout diagnostics.

### Modified Capabilities

None.

## Impact

- Affected backend code:
  - `src/swe/agents/react_agent.py`
  - `src/swe/agents/tool_guard_mixin.py`
  - `src/swe/agents/tools/file_io.py`
  - relevant tests under `tests/unit/agents/` or `tests/unit/app/`
- Existing environment variables remain compatible:
  - `SWE_AGENT_WATCHDOG_TIMEOUT`
  - `SWE_QUERY_TIMEOUT_SECONDS`
  - `SWE_MCP_CALL_TIMEOUT`
  - `SWE_LLM_CALL_TIMEOUT`
  - `SWE_LLM_STREAM_STALL_TIMEOUT`
- No API or frontend contract changes are required for the first implementation.
- Operational logging becomes more precise and may add new structured fields.
