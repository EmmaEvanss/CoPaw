## 1. Protocol Models and Configuration

- [x] 1.1 Add hook runtime package structure with protocol models for HookEventName, bounded PermissionMode/EffortLevel enums, Claude-style HookContext envelope, event-specific inputs, common outputs, event-specific hookSpecificOutput, internal merged decision, matcher config, and fail policy.
- [x] 1.2 Extend tenant/agent configuration models with `hooks.enabled`, event matcher groups, handler definitions, common handler fields (`if`, `timeout`, `statusMessage`, `once`), command/http handler settings, and fail policies.
- [x] 1.3 Define session overlay data structures for enabling/disabling hooks, parameter overrides, expiration, reason metadata, and scoped `once` tracking.
- [x] 1.4 Add validation that session overlays can only reference hook ids available to the current effective tenant and that unsupported MVP handler types are rejected.

## 2. Hook Config Resolution

- [x] 2.1 Implement a resolver that loads tenant hook config, agent hook config, and session overlay for the current tenant/user/session scope using event -> matcher group -> handler shape.
- [x] 2.2 Implement event-boundary snapshot resolution that returns an immutable EffectiveHookPlan.
- [x] 2.3 Implement matcher filtering by event name, tool filters, restricted `if` conditions, `once` state, and equivalent handler deduplication.
- [x] 2.4 Add unit tests for tenant isolation, empty config behavior, overlay expiration, overlay disable, event/tool matcher filtering, `if`, `once`, and deduplication.

## 3. Handler Execution

- [x] 3.1 Implement command handler execution with HookContext JSON on stdin, tenant workspace cwd enforcement, timeout handling, exit-0 stdout JSON parsing, exit-2 blocking without successful JSON parsing, and other exit code failure mapping.
- [x] 3.2 Implement HTTP handler execution with POST JSON body, tenant-scoped endpoint/header/allowedEnvVars configuration, timeout handling, status mapping, and response JSON parsing.
- [x] 3.3 Implement handler failure normalization for startup errors, timeouts, invalid output, non-blocking command exit codes, and HTTP failures.
- [x] 3.4 Add unit tests for command success, command exit 2 blocking, command failure fail policies, HTTP 2xx success, HTTP 409/422 blocking, and HTTP timeout fail policies.

## 4. Decision Merging and Application

- [x] 4.1 Implement parsing from Claude-style outputs (`continue`, `stopReason`, `suppressOutput`, `systemMessage`, top-level `decision=block`, and event-specific `hookSpecificOutput`) into internal decisions.
- [x] 4.2 Implement deterministic merge priority for `continue=false`, `block`, `deny`, `ask`, `allow`, and `none`.
- [x] 4.3 Implement ordered `hookSpecificOutput.additionalContext` merge and handler-id keyed `hookSpecificOutput` preservation.
- [x] 4.4 Implement single-writer `hookSpecificOutput.updatedInput` replacement and conflict blocking for multiple updated inputs.
- [x] 4.5 Add unit tests for output parsing, merge priority, completion-order independence, additional context ordering, replacement semantics, and updated input conflicts.

## 5. Runner Event Integration

- [x] 5.1 Emit `SessionStart` with `source`, `model`, transcript path, tenant/session envelope fields when creating or preparing a request-scoped SWEAgent and apply returned additional context to the request/agent context.
- [x] 5.2 Emit `UserPromptSubmit` with `prompt` before command dispatch and normal agent reasoning, applying prompt blocks, session title output, and additional context.
- [x] 5.3 Emit `Stop` after the agent produces a final response and before the turn is treated as complete.
- [x] 5.4 Add runner integration tests proving no-config behavior is unchanged and configured hooks can block/enrich user prompt and stop events.

## 6. Tool Event Integration

- [x] 6.1 Emit `PreToolUse` from `ToolGuardMixin` with `tool_name`, `tool_input`, `tool_use_id`, and envelope fields before tool execution and before applying final tool input.
- [x] 6.2 Apply a single `hookSpecificOutput.updatedInput` replacement from `PreToolUse` before executing the tool.
- [x] 6.3 Map `hookSpecificOutput.permissionDecision` allow/deny/ask and `permissionDecisionReason` into current tool execution and approval behavior, while rejecting or ignoring `defer` in the MVP.
- [x] 6.4 Emit `PostToolUse` after successful tool execution and expose returned additional context to subsequent agent processing.
- [x] 6.5 Emit `PostToolUseFailure` after failed tool execution and expose returned additional context or blocking reason.
- [x] 6.6 Preserve existing Tool Guard denied, approval, timeout, and replay behavior when hook runtime is disabled or has no matched handlers.
- [x] 6.7 Add integration tests for pre-tool denial, updated tool input replacement, ask decision approval behavior, post-tool context injection, tool failure hook execution, and Tool Guard regression behavior.

## 7. Security and Tenant Boundary Hardening

- [x] 7.1 Enforce command hook cwd and script path boundaries under the current effective tenant workspace.
- [x] 7.2 Ensure HTTP hook headers/secrets resolve only from the current tenant secret scope and are not persisted into session state or hook results.
- [x] 7.3 Add log redaction for hook secrets, headers, and sensitive HookContext fields.
- [x] 7.4 Add regression tests for cross-tenant command path attempts, cross-tenant overlay references, and tenant-scoped HTTP secret resolution.

## 8. Documentation and Verification

- [x] 8.1 Add developer documentation or examples for tenant hook config, session overlay, command handler stdin/stdout, and HTTP handler request/response.
- [x] 8.2 Add focused pytest coverage under the relevant unit test directories for config, resolver, handlers, merge logic, runner integration, and tool integration.
- [x] 8.3 Run targeted pytest suites for hook runtime, tool guard, runner post-turn behavior, and tenant path boundaries.
- [x] 8.4 Run `openspec status --change unified-agent-hook-protocol` and ensure the change is apply-ready.
