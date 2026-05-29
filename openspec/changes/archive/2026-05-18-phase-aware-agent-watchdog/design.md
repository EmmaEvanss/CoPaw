## Context

`SWEAgent` currently starts a watchdog for each `reply()` and resets it from
`SWEAgent.print()`. This means the watchdog observes user-visible output, not
internal progress. AgentScope calls `print()` after model stream chunks and
after tool response chunks, so a long internal phase can appear silent even
when work is still progressing.

The built-in `write_file` path is synchronous and normally fast. If it blocks
inside `file.write()`, the event loop is also blocked and the watchdog cannot
reliably fire at the configured threshold. Therefore a 5-minute watchdog
interruption attributed to `write_file` is more likely caused by a silent async
phase around model output, tool dispatch, MCP/skill execution, replay, or
another await point. The fix should make the watchdog phase-aware and make
timeout diagnostics identify the phase before we add narrow tool-specific
workarounds.

## Goals / Non-Goals

**Goals:**

- Separate Agent liveness from user-visible output.
- Preserve fast interruption for real silent stalls in reasoning and
  summarizing phases.
- Prevent tool execution from being cancelled solely because no UI output was
  produced.
- Keep tool execution bounded through existing subsystem timeouts, new
  per-tool hard limits where needed, and the global query timeout.
- Record enough structured diagnostics to distinguish model, tool, approval,
  replay, and filesystem-write slow paths.
- Add tests that reproduce the previous false-positive class and protect the
  real-stall interruption behavior.

**Non-Goals:**

- Do not redesign AgentScope tool execution.
- Do not make built-in file writes asynchronous unless instrumentation proves
  local file I/O is the bottleneck.
- Do not change frontend APIs or approval UI behavior.
- Do not remove global query timeout enforcement.
- Do not log tool input contents or file contents.

## Decisions

### Decision: Track explicit Agent run phases

Add a small phase-state model on `SWEAgent`, updated through context-manager
style helpers around known phase boundaries:

- `reasoning`
- `acting`
- `tool_execution`
- `tool_guard`
- `approval_replay`
- `summarizing`
- `idle`
- `unknown`

The state should include `phase`, `started_at`, `last_activity_at`,
`tool_name`, `tool_call_id`, and a free-form `reason` field for diagnostics.
`SWEAgent.print()` should still update activity, but phase transitions and
selected internal checkpoints must also update it.

Alternative considered: keep the current output-only timer and increase
`SWE_AGENT_WATCHDOG_TIMEOUT`. This was rejected because it weakens real stall
detection and still does not identify the stalled phase.

### Decision: Use phase-specific watchdog policy

Replace the one-shot sleep watchdog with a loop that periodically checks the
current phase and policy:

- Reasoning and summarizing phases remain idle-sensitive and may cancel the
  reply task after `SWE_AGENT_WATCHDOG_TIMEOUT` of no internal activity.
- Tool execution phases are not cancelled only because the UI is silent.
- Tool execution phases must be bounded by existing tool/subsystem timeouts,
  a configurable tool hard timeout, or the global query timeout.
- Unknown phases default to conservative idle detection and log enough context
  to classify future gaps.

Alternative considered: pause the watchdog entirely during tools. This was
rejected because unbounded custom skill tools or unexpected await points could
still hang until only the global query timeout fires.

### Decision: Add explicit tool hard-timeout coverage only where needed

Existing bounded paths should keep their own limits:

- MCP tools use `SWE_MCP_CALL_TIMEOUT`.
- LLM calls use `SWE_LLM_CALL_TIMEOUT` and `SWE_LLM_STREAM_STALL_TIMEOUT`.
- Shell and file-search tools already contain operation-specific timeouts.

For generic local tool execution paths that lack a hard timeout, introduce a
configurable tool execution hard limit. The default should be higher than the
idle watchdog and lower than or equal to the query timeout. The hard timeout
error must include tool name, tool call id, phase duration, and configured
limit. A tool hard timeout is a tool failure, not an Agent idle interruption.

Alternative considered: make `write_file` async and rely on watchdog resets
from progress events. This was rejected for the first implementation because
the current evidence does not show built-in file I/O is the root cause.

### Decision: Instrument built-in file writes without changing semantics

Add debug/info-level timing around built-in `write_file` and `append_file`
operations:

- path after tenant-boundary resolution
- content byte length
- duration for path resolution, open, write, and close
- total duration

Do not log `content`. This instrumentation confirms or disproves whether
filesystem I/O is the slow phase in production without changing write
semantics.

### Decision: Improve watchdog diagnostics before behavior broadening

When the watchdog cancels a run or emits a warning, logs must include:

- session id, user id, agent id when available
- current phase
- phase start time and duration
- last internal activity time and silence duration
- tool name and tool call id when available
- configured threshold and cancellation policy

This makes the next incident attributable to a phase rather than to the last
visible UI event.

## Risks / Trade-offs

- Tool execution may run longer than before when silent but valid.
  Mitigation: enforce tool hard timeouts and keep global query timeout as the
  outer wall-clock guard.
- A generic hard timeout could cancel a legitimate long-running custom tool.
  Mitigation: make the limit configurable and log the exact policy that caused
  cancellation.
- More logging can expose sensitive paths or tool metadata.
  Mitigation: log resolved paths and sizes only where already operationally
  visible; never log file contents or secret values.
- Phase-state bugs could leave the Agent in the wrong policy.
  Mitigation: use context managers with `finally` restoration and focused unit
  tests for nested/exception paths.
- Synchronous blocking file I/O can still block the event loop.
  Mitigation: instrument first; only move to chunked/threaded writes if data
  proves local I/O is a real production bottleneck.

## Migration Plan

1. Add phase-state helpers and diagnostics with no behavior change except
   richer logs.
2. Change watchdog cancellation policy by phase.
3. Add or wire tool hard-timeout policy for unbounded local tool paths.
4. Add file-write timing instrumentation.
5. Run targeted unit tests for watchdog behavior and existing relevant tests.
6. Roll back by restoring output-based cancellation while keeping diagnostic
   logs if the new policy causes unexpected long-running tasks.

## Open Questions

- What default should the generic local tool hard timeout use? Recommended:
  greater than `SWE_AGENT_WATCHDOG_TIMEOUT` and less than or equal to
  `SWE_QUERY_TIMEOUT_SECONDS`, with an environment variable override.
- Should slow file-write logs be emitted at `info` only when duration exceeds
  a threshold, or always at `debug`? Recommended: always `debug`, `warning`
  above a configurable slow threshold.
