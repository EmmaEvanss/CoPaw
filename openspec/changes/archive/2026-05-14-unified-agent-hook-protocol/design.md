## Context

Swe already has several lifecycle-specific extension points:
AgentScope instance hooks for pre-reasoning behavior, `ToolGuardMixin` for
pre-tool policy and approval replay, tracing hooks around LLM/tool spans, and
post-turn validation in the runner. These code paths are useful but each has
its own data shape and lifecycle rules.

The new hook runtime needs to provide a single protocol that can be configured
per tenant and adjusted per session. Swe is deployed in a multi-tenant model,
so hook configuration, hook scripts, remote credentials, and dynamic session
overrides must be isolated by the current effective tenant. The first
implementation is intentionally limited to `command` and `http` handlers.

## Goals / Non-Goals

**Goals:**

- Define a stable HookContext and HookResult protocol for agent lifecycle
  events, using the Claude-style parameter model in `hool_design.txt` as the
  compatibility baseline.
- Resolve hooks from tenant configuration plus session overlay at every event
  boundary.
- Run matched hook handlers concurrently using an immutable event execution
  plan.
- Support local `command` handlers and remote `http` handlers.
- Apply deterministic decision merging across handlers.
- Integrate the MVP with runner events and tool execution events without
  regressing existing Tool Guard approval behavior.
- Preserve tenant isolation for hook config, script execution, and secrets.

**Non-Goals:**

- Implement `mcp_tool`, `prompt`, or `agent` handler types.
- Implement `defer` decisions or an external SDK resume protocol.
- Replace the current Tool Guard rules and approval service in the MVP.
- Add a frontend management UI for hook configuration.
- Persist hook execution audit data beyond existing logs/tracing unless needed
  for debugging.
- Implement command `async` or `asyncRewake` behavior in the MVP.

## Decisions

### Decision 1: Add a dedicated hook runtime package

Create a dedicated package such as `src/swe/agents/hook_runtime/` containing
protocol models, config resolution, handler adapters, decision merging, and
event emission helpers.

This keeps the protocol independent from `ToolGuardMixin` while allowing the
tool guard path to call the runtime at `PreToolUse`, `PostToolUse`, and
`PostToolUseFailure`.

Alternative considered: extend `ToolGuardEngine` into a generic hook engine.
That would couple all lifecycle hooks to security-specific finding models and
approval behavior, making `SessionStart`, `UserPromptSubmit`, and `Stop`
awkward to represent.

### Decision 2: Resolve hooks at event boundaries

Each event emission resolves tenant config, agent config, and session overlay
into an immutable `EffectiveHookPlan`. The plan is used for that event only.
Session overlay changes apply to the next event, not to handlers already
running.

This gives sessions dynamic loading while avoiding nondeterministic behavior
inside a parallel hook batch.

Alternative considered: keep a long-lived hook registry on `SWEAgent`.
That would be faster but would miss session-level changes made during long
runs and would require complex invalidation.

### Decision 3: Config uses event -> matcher group -> handler

Tenant-level configuration defines hooks as event keys containing matcher
groups, and each matcher group contains one or more handlers. This mirrors the
Claude-style shape:

`HookEventName -> HookMatcherGroup[] -> HookHandler[]`.

Matcher groups have a `matcher` field and handlers share common fields:
`if`, `timeout`, `statusMessage`, and `once`. The MVP implements `command`
and `http` handler types only; unsupported handler types are rejected during
config validation rather than silently ignored.

Tenant-level configuration also defines available hook handlers, allowed
command roots, HTTP endpoints, timeouts, and fail policies. Session overlays
may enable or disable tenant-defined hooks, override approved parameters, set
expiration times, and add session-local hooks only when permitted by tenant
policy.

The session overlay must not reference hooks or secrets outside the current
effective tenant.

Alternative considered: store complete handler definitions directly in session
state. That is flexible but unsafe because any conversation could persist new
shell commands or remote endpoints without tenant-level governance.

### Decision 4: Use Claude-style HookContext envelope plus Swe metadata

Every event context includes the common envelope fields from `hool_design.txt`:

- `session_id`
- `transcript_path`
- `cwd`
- `hook_event_name`
- `permission_mode` when available
- `effort.level` when available
- `agent_id` and `agent_type` when available

`permission_mode` and `effort.level` use bounded enum values from
`hool_design.txt`; unknown values are rejected or omitted rather than passed
through as arbitrary strings.

Swe adds tenant/runtime metadata needed for isolation and traceability:
`tenant_id`, `effective_tenant_id`, `user_id`, `channel`, `source_id`,
`workspace_dir`, `chat_id`, and `turn_id` when available.

Event-specific fields are added only for relevant events. Examples:
`SessionStart` includes `source` and `model`; `UserPromptSubmit` includes
`prompt`; `PreToolUse` includes `tool_name`, `tool_input`, and `tool_use_id`;
post-tool events include `tool_response` or error details when available.

Alternative considered: use a minimal Swe-only context. That would be simpler
but would miss important interoperability fields such as `transcript_path`,
`permission_mode`, and `tool_use_id`.

### Decision 5: Normalize command and http outputs into an internal result

Handlers may return Claude-style outputs:

- `continue`
- `stopReason`
- `suppressOutput`
- `systemMessage`
- top-level `decision: "block"` for block-style events
- `hookSpecificOutput`

`hookSpecificOutput` includes `hookEventName` and may include
`additionalContext`. `PreToolUse` uses event-specific fields:
`permissionDecision`, `permissionDecisionReason`, and `updatedInput`.
`UserPromptSubmit` may include `sessionTitle`.
When `continue=false` is returned, `stopReason` is preserved as the reason for
the internal stop decision.

The runtime normalizes handler output into an internal merged event result.
This keeps the public protocol close to `hool_design.txt` while still letting
Swe apply a consistent decision merger.

Alternative considered: expose only a flattened Swe-specific HookResult with
top-level `decision`, `additionalContext`, and `updatedInput`. That would be
easier to consume but would lose event-specific semantics and create migration
work when future events are added.

### Decision 6: Keep command exit code semantics separate from JSON semantics

`command` handlers receive HookContext JSON on stdin. Exit code `0` means
success and stdout may contain JSON output. Exit code `2` means a blocking
handler result for blockable events and stdout JSON is not parsed as a
successful HookResult. Other non-zero codes are handler failures handled by
`fail_policy`.

`http` handlers receive HookContext JSON as a POST body. `2xx` responses are
successful HookResult responses. `409` and `422` map to blocking results when
no explicit HookResult is returned. Other status codes and timeouts are
handler failures handled by `fail_policy`.

Alternative considered: define separate output contracts per handler type.
That would make handler implementation harder to reason about and would
complicate decision merging.

### Decision 7: Merge decisions deterministically

Handlers may run concurrently, but merge order must be deterministic. Results
are sorted by configured handler order after completion and merged using fixed
priority:

`continue:false` > `block`/`deny` > `ask` > `allow` > `none`.

`additionalContext` is concatenated in configured handler order with handler
ids preserved. `hookSpecificOutput` is stored by handler id.

`updatedInput` is single-writer only and is treated as a replacement for the
entire event-specific input object, not as a patch or deep merge. If more than
one handler returns `updatedInput`, the runtime blocks the event with a
conflict result instead of choosing the last handler to finish.

Alternative considered: let the last completed handler win for `updatedInput`.
That is faster to implement but unsafe because parallel completion order is
nondeterministic.

### Decision 8: Deduplicate equivalent handlers per event plan

All matched hooks run concurrently, so duplicate handler definitions can cause
duplicate side effects. The resolver deduplicates equivalent handlers within a
single event plan using a stable identity derived from tenant id, event,
matcher group, handler id, handler type, and handler target.

Hook authors must still treat handlers as idempotent because different
handlers can legitimately observe the same event in parallel.

Alternative considered: execute every matched handler exactly as configured.
That is transparent but makes duplicate config mistakes dangerous.

### Decision 9: Integrate with existing Tool Guard rather than replace it

For `PreToolUse`, the hook runtime should run before or beside the current
guard decision path and produce a normalized decision. Existing Tool Guard
approval remains responsible for current risk findings, pending approval, and
approved replay. A hook `ask` decision may reuse the approval service but does
not require a frontend change in the MVP.

Alternative considered: rewrite Tool Guard fully as a hook handler. That is a
larger migration with higher regression risk and should be considered after
the runtime is stable.

### Decision 10: Command hooks use existing tenant path protections

Command hooks execute with the current tenant workspace as their default
working directory and must not run outside the effective tenant boundary.
The implementation should reuse existing tenant path boundary and Python
runtime guard patterns where practical.

HTTP hooks use tenant-scoped endpoint configuration and secret references.
Secrets are resolved at execution time and must not be copied into session
state or hook result logs.

## Risks / Trade-offs

- Handler latency can slow every event -> Use per-handler timeouts, bounded
  event budgets, and fail policies.
- Misconfigured fail-open hooks may allow risky actions -> Require explicit
  `fail_policy` defaults per event class and log failures clearly.
- Command hooks can become an execution escape hatch -> Restrict command
  paths, cwd, environment, and tenant boundary access.
- HTTP hooks can leak context to remote services -> Require tenant-owned
  endpoint configuration and keep secret/header configuration tenant-scoped.
- Session overlays can cause confusing behavior -> Apply overlays only at
  event boundaries and support expiration/reason metadata.
- Hook output can poison model context -> Treat `additionalContext` as system
  generated context with source metadata and size limits.
- Expression fields such as `if` can become an injection surface -> Use a
  restricted evaluator or a declarative subset, never arbitrary code eval.
- `once` tracking can leak across tenants or sessions -> Scope `once` state by
  effective tenant id, user id, session id, event name, and handler id.

## Migration Plan

1. Add protocol models, resolver, handler adapters, and merge logic behind a
   disabled-by-default or empty-config runtime.
2. Add config models for tenant hooks and session overlays without changing
   existing tenant config defaults.
3. Integrate events in runner and tool guard paths.
4. Add tests for no-config behavior proving existing behavior is unchanged.
5. Enable hook runtime when tenant config contains `hooks.enabled=true`.
6. Roll back by disabling `hooks.enabled` per tenant or globally.

## Open Questions

- Should session-local hook definitions be allowed in the MVP, or should the
  MVP only support enabling/disabling and parameter overrides for tenant hooks?
- Should command hook allowlists be command path based, directory based, or
  both?
- Should `ask` decisions from non-Tool Guard hooks use the same approval UI
  metadata as Tool Guard, or a generic hook approval payload?
