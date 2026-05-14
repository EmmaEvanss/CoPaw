## Why

Swe currently has several hook-like mechanisms, including AgentScope
pre-reasoning hooks, tool guard approval, tracing, and post-turn validation.
These mechanisms are useful but are implemented as separate fixed code paths,
so tenants cannot define their own runtime policies and sessions cannot
dynamically adjust hook behavior.

This change introduces a unified hook protocol so tenant-scoped and
session-scoped policies can observe, enrich, or block key agent lifecycle
events through a stable contract. The MVP intentionally supports only
`command` and `http` handlers to establish the protocol without taking on
MCP, prompt, or subagent execution complexity.

## What Changes

- Add a unified Hook Runtime that emits structured event context for selected
  agent lifecycle events.
- Base hook input and output shapes on the Claude-style hook parameter design
  in `hool_design.txt`, including common envelope fields and event-specific
  `hookSpecificOutput`.
- Add tenant-scoped hook configuration and session-scoped hook overlays that
  are resolved into an immutable per-event execution plan.
- Support dynamically loaded session hook overlays by resolving hooks at each
  event boundary while keeping execution stable within the event.
- Support two handler types in the MVP:
  - `command`: run a local command with HookContext JSON on stdin.
  - `http`: POST HookContext JSON to a configured endpoint.
- Normalize handler outputs into a common HookResult contract with
  common output fields, event-specific `hookSpecificOutput`, and internal
  merged decisions.
- Model configuration as event -> matcher group -> handler, with shared
  handler fields such as `if`, `timeout`, `statusMessage`, and `once`.
- Define deterministic decision merging across parallel handlers, including
  strict single-writer replacement semantics for `updatedInput`.
- Integrate MVP events:
  - `SessionStart`
  - `UserPromptSubmit`
  - `PreToolUse`
  - `PostToolUse`
  - `PostToolUseFailure`
  - `Stop`
- Preserve existing Tool Guard behavior by adapting it to coexist with the
  new hook decision path rather than removing approvals in the MVP.
- Keep `mcp_tool`, `prompt`, `agent`, and `defer` decisions out of scope for
  the first implementation.

## Capabilities

### New Capabilities

- `unified-agent-hook-protocol`: Defines tenant-scoped and session-scoped
  hook configuration, command/http handler execution, hook event contracts,
  and deterministic hook decision application.

### Modified Capabilities

None.

## Impact

- Affected backend code:
  - `src/swe/agents/react_agent.py`
  - `src/swe/agents/tool_guard_mixin.py`
  - `src/swe/app/runner/runner.py`
  - `src/swe/app/runner/session.py`
  - `src/swe/config/config.py`
  - new hook runtime modules under `src/swe/agents/` or `src/swe/app/`
- Affected security boundaries:
  - command hooks must execute within the current tenant workspace boundary.
  - http hooks must use tenant-scoped configuration and secrets.
  - session overlays must not reference or affect another tenant's hooks.
- Affected tests:
  - unit tests for config resolution, session overlays, command/http handler
    execution, decision merging, and event integration.
  - regression tests for tenant isolation and existing tool guard approval
    behavior.
- No frontend API is required for the MVP, although future UI work may expose
  tenant/session hook management.
