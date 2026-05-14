## ADDED Requirements

### Requirement: Hook runtime SHALL emit supported agent lifecycle events
The system SHALL provide a unified hook runtime that can emit
`SessionStart`, `UserPromptSubmit`, `PreToolUse`, `PostToolUse`,
`PostToolUseFailure`, and `Stop` events with a structured HookContext.

#### Scenario: Runner emits user prompt event before normal processing
- **WHEN** an agent request contains a user prompt
- **THEN** the system SHALL emit `UserPromptSubmit` before command dispatch and agent reasoning
- **AND** matched hooks SHALL be able to block or enrich the prompt before it is processed

#### Scenario: Tool execution emits pre and post tool events
- **WHEN** an agent requests a tool call
- **THEN** the system SHALL emit `PreToolUse` before executing the tool
- **AND** the system SHALL emit `PostToolUse` after a successful tool execution
- **AND** the system SHALL emit `PostToolUseFailure` after a failed tool execution

#### Scenario: Runner emits stop event before ending the turn
- **WHEN** the agent has produced a final assistant response for the turn
- **THEN** the system SHALL emit `Stop` before treating the turn as complete

### Requirement: HookContext SHALL include tenant, session, agent, and event data
The system SHALL pass each handler a HookContext JSON object containing
common runtime identity fields and event-specific payload fields.

#### Scenario: Common fields are present for every event
- **WHEN** any supported hook event is emitted
- **THEN** HookContext SHALL include `session_id`, `transcript_path`, `cwd`, `hook_event_name`, `tenant_id`, `effective_tenant_id`, `user_id`, `agent_id`, and `channel`
- **AND** HookContext SHALL include `permission_mode`, `effort.level`, `agent_type`, `source_id`, `workspace_dir`, `chat_id`, and `turn_id` when available

#### Scenario: Optional enum fields use bounded values
- **WHEN** HookContext includes `permission_mode`
- **THEN** the value SHALL be one of `default`, `plan`, `acceptEdits`, `auto`, `dontAsk`, or `bypassPermissions`
- **AND** when HookContext includes `effort.level`, the value SHALL be one of `low`, `medium`, `high`, `xhigh`, or `max`

#### Scenario: Session start fields are present
- **WHEN** `SessionStart` is emitted
- **THEN** HookContext SHALL include `source` with one of `startup`, `resume`, `clear`, or `compact`
- **AND** HookContext SHALL include `model` when the active model is known

#### Scenario: User prompt field is present
- **WHEN** `UserPromptSubmit` is emitted
- **THEN** HookContext SHALL include the submitted `prompt`

#### Scenario: Tool fields are present for tool events
- **WHEN** `PreToolUse`, `PostToolUse`, or `PostToolUseFailure` is emitted
- **THEN** HookContext SHALL include `tool_name` and `tool_input`
- **AND** `PreToolUse` SHALL include `tool_use_id` when the tool call id is available
- **AND** post-tool events SHALL include tool output or error data when available

### Requirement: Tenant hook config SHALL be isolated by effective tenant
The system SHALL load hook definitions from the current effective tenant
configuration and SHALL NOT use hook definitions from another tenant.

#### Scenario: Tenant has its own hook config
- **WHEN** tenant `alice` and tenant `bob` define different hook handlers
- **THEN** requests running under tenant `alice` SHALL resolve only tenant `alice` hook handlers
- **AND** requests running under tenant `bob` SHALL resolve only tenant `bob` hook handlers

#### Scenario: Missing tenant hook config
- **WHEN** the current tenant has no enabled hook configuration
- **THEN** the hook runtime SHALL produce an empty execution plan
- **AND** existing agent behavior SHALL continue unchanged

### Requirement: Session hook overlay SHALL be dynamically resolved at event boundaries
The system SHALL support session-scoped hook overlays that are reloaded when
each hook event starts and applied to that event's execution plan.

#### Scenario: Session disables a tenant hook for the next event
- **WHEN** a session overlay disables a tenant-defined hook before an event starts
- **THEN** the disabled hook SHALL be omitted from that event's execution plan

#### Scenario: Overlay changes do not affect in-flight event execution
- **WHEN** a hook event has already resolved its execution plan
- **AND** the session overlay is changed while handlers are running
- **THEN** the in-flight event SHALL continue using its original execution plan
- **AND** the overlay change SHALL apply only to later events

#### Scenario: Expired overlay is ignored
- **WHEN** a session overlay entry has an `expires_at` value earlier than the event start time
- **THEN** the system SHALL ignore that overlay entry

### Requirement: Hook matcher SHALL select handlers by event and optional filters
The system SHALL execute only handlers whose configured event and matcher
criteria match the emitted HookContext.

#### Scenario: Tool matcher limits pre-tool hook execution
- **WHEN** a `PreToolUse` hook is configured with a matcher for `execute_shell_command`
- **AND** the emitted event is for `read_file`
- **THEN** the system SHALL NOT execute that handler

#### Scenario: Event mismatch prevents handler execution
- **WHEN** a handler is configured for `UserPromptSubmit`
- **AND** the emitted event is `Stop`
- **THEN** the system SHALL NOT execute that handler

### Requirement: Hook configuration SHALL use event matcher groups
The system SHALL model hook configuration as event names containing matcher
groups, where each matcher group contains one or more handlers.

#### Scenario: Event contains matcher groups
- **WHEN** tenant configuration defines hooks for `PreToolUse`
- **THEN** the configuration SHALL allow one or more matcher groups under `PreToolUse`
- **AND** each matcher group SHALL contain a `hooks` list of handlers

#### Scenario: Unsupported handler type is rejected
- **WHEN** tenant configuration defines a handler type other than `command` or `http` in the MVP
- **THEN** the system SHALL reject the handler configuration during validation

### Requirement: Hook handlers SHALL support common configuration fields
The system SHALL support common handler fields for `if`, `timeout`,
`statusMessage`, and `once`.

#### Scenario: If condition prevents handler execution
- **WHEN** a handler has an `if` condition
- **AND** the condition evaluates false against the HookContext using the supported expression subset
- **THEN** the system SHALL NOT execute that handler

#### Scenario: Handler timeout overrides default
- **WHEN** a handler has a configured `timeout`
- **THEN** the system SHALL use that timeout for the handler execution

#### Scenario: Once handler executes once per session scope
- **WHEN** a handler has `once=true`
- **AND** the same handler has already executed for the same effective tenant, user, session, and event
- **THEN** the system SHALL omit that handler from later execution plans for that scope

#### Scenario: Status message is preserved for user-visible blocking
- **WHEN** a handler has `statusMessage`
- **AND** that handler contributes to a blocking or ask decision
- **THEN** the system SHALL preserve the status message for the event consumer when user-visible feedback is needed

### Requirement: Command handlers SHALL receive HookContext on stdin
The system SHALL support `command` hook handlers that execute a configured
local command with HookContext JSON written to stdin.

#### Scenario: Command handler validates command parameters
- **WHEN** a `command` handler is configured
- **THEN** the handler configuration SHALL include a command string or command argv representation
- **AND** optional shell selection SHALL be validated against the shells supported by the current platform
- **AND** command `async` and `asyncRewake` behavior SHALL NOT be enabled in the MVP

#### Scenario: Command handler returns JSON result on success
- **WHEN** a command hook exits with code `0`
- **AND** stdout contains a valid HookResult JSON object
- **THEN** the system SHALL parse stdout as that handler's HookResult

#### Scenario: Command handler exits with blocking code
- **WHEN** a command hook exits with code `2`
- **THEN** the system SHALL treat the handler result as blocking for blockable events
- **AND** the system SHALL NOT parse stdout as a successful HookResult for that execution
- **AND** the blocking reason SHALL include stderr or configured fallback text

#### Scenario: Command handler fails with other non-zero code
- **WHEN** a command hook exits with a non-zero code other than `2`
- **THEN** the system SHALL treat the handler as failed
- **AND** the event outcome SHALL follow the handler's configured `fail_policy`

### Requirement: HTTP handlers SHALL receive HookContext as POST JSON
The system SHALL support `http` hook handlers that POST HookContext JSON to a
tenant-configured endpoint and normalize the response into HookResult.

#### Scenario: HTTP handler validates request parameters
- **WHEN** an `http` handler is configured
- **THEN** the handler configuration SHALL include a URL
- **AND** any configured headers SHALL be resolved from tenant-scoped configuration or secrets
- **AND** any configured `allowedEnvVars` SHALL be resolved only from explicitly allowed environment variable names

#### Scenario: HTTP handler returns successful JSON result
- **WHEN** an HTTP hook returns a `2xx` status
- **AND** the response body contains a valid HookResult JSON object
- **THEN** the system SHALL parse the response body as that handler's HookResult

#### Scenario: HTTP handler returns blocking status
- **WHEN** an HTTP hook returns status `409` or `422`
- **THEN** the system SHALL treat the handler result as blocking when no explicit HookResult body is provided

#### Scenario: HTTP handler times out
- **WHEN** an HTTP hook does not return within its configured timeout
- **THEN** the system SHALL treat the handler as failed
- **AND** the event outcome SHALL follow the handler's configured `fail_policy`

### Requirement: HookResult SHALL support structured decisions and context updates
The system SHALL normalize Claude-style handler output into an internal event
result while preserving common output fields and event-specific
`hookSpecificOutput`.

#### Scenario: Common output fields are parsed
- **WHEN** a successful handler returns JSON with `continue`, `stopReason`, `suppressOutput`, or `systemMessage`
- **THEN** the system SHALL parse and preserve those common output fields

#### Scenario: Continue false preserves stop reason
- **WHEN** a handler returns `continue=false`
- **AND** the handler also returns `stopReason`
- **THEN** the system SHALL use the stop reason when constructing the internal stop decision

#### Scenario: Event-specific hook output identifies its event
- **WHEN** a handler returns `hookSpecificOutput`
- **THEN** the system SHALL preserve the event name inside that structure for traceability

#### Scenario: Handler injects additional context
- **WHEN** a handler returns `hookSpecificOutput.additionalContext`
- **THEN** the system SHALL preserve the context with the handler id
- **AND** the applicable runtime path SHALL make the additional context available to the next model turn or current event consumer

#### Scenario: User prompt submit returns session title
- **WHEN** a `UserPromptSubmit` handler returns `hookSpecificOutput.sessionTitle`
- **THEN** the system SHALL preserve the session title update for the event consumer

#### Scenario: Pre-tool handler returns permission decision
- **WHEN** a `PreToolUse` handler returns `hookSpecificOutput.permissionDecision`
- **THEN** the system SHALL map `allow`, `deny`, or `ask` into the internal merged event decision
- **AND** the system SHALL preserve `hookSpecificOutput.permissionDecisionReason` when provided
- **AND** the MVP SHALL reject or ignore `defer` because external resume is out of scope

#### Scenario: Handler replaces tool input
- **WHEN** a `PreToolUse` handler returns `hookSpecificOutput.updatedInput`
- **AND** no other handler returns `hookSpecificOutput.updatedInput`
- **THEN** the system SHALL replace the entire tool input before executing the tool
- **AND** the system SHALL NOT treat `updatedInput` as a patch or deep merge

#### Scenario: Top-level block decision is parsed
- **WHEN** a block-style event handler returns top-level `decision="block"` with a `reason`
- **THEN** the system SHALL map that output into an internal blocking event decision

### Requirement: Hook decisions SHALL be merged deterministically
The system SHALL merge parallel handler results using a deterministic priority
order independent of handler completion order.

#### Scenario: Blocking decision wins over allow
- **WHEN** one matched handler returns `allow`
- **AND** another matched handler returns `deny` or `block`
- **THEN** the merged event decision SHALL be blocking

#### Scenario: Continue false stops the event
- **WHEN** any matched handler returns `continue=false`
- **THEN** the merged event result SHALL stop the current hook event flow
- **AND** the stop SHALL take precedence over other decisions

#### Scenario: Multiple updated inputs conflict
- **WHEN** more than one matched handler returns `hookSpecificOutput.updatedInput`
- **THEN** the system SHALL NOT apply any returned updated input
- **AND** the merged event result SHALL block the event with an input update conflict reason

#### Scenario: Duplicate handlers are deduplicated within one event plan
- **WHEN** the same effective handler is matched more than once for a single event plan
- **THEN** the system SHALL execute it at most once for that event plan
- **AND** the deduplication identity SHALL include tenant id, event name, matcher group, handler id, handler type, and handler target

### Requirement: Hook decisions SHALL be applied according to event semantics
The system SHALL apply merged hook decisions according to the emitted event
type and SHALL NOT use event-specific behavior on unrelated events.

#### Scenario: User prompt is blocked
- **WHEN** `UserPromptSubmit` produces a merged `deny` or `block` decision
- **THEN** the system SHALL reject the prompt before normal command dispatch and agent reasoning

#### Scenario: Pre-tool use is denied
- **WHEN** `PreToolUse` produces a merged `deny` or `block` decision
- **THEN** the system SHALL NOT execute the requested tool call
- **AND** the agent SHALL receive a structured tool result or message explaining the denial

#### Scenario: Post-tool use cannot roll back side effects
- **WHEN** `PostToolUse` produces a blocking decision
- **THEN** the system SHALL NOT attempt to roll back the completed tool side effects
- **AND** the system SHALL expose the blocking reason to subsequent agent processing

#### Scenario: Stop is blocked
- **WHEN** `Stop` produces a merged blocking decision
- **THEN** the system SHALL prevent the turn from being treated as complete
- **AND** the system SHALL provide the blocking reason as continuation context when continuation is supported

### Requirement: Hook runtime SHALL preserve tenant security boundaries
The system SHALL enforce tenant isolation for hook scripts, working
directories, HTTP endpoints, and secrets.

#### Scenario: Command hook cwd escapes tenant workspace
- **WHEN** a command hook configuration requests a working directory outside the current tenant workspace boundary
- **THEN** the system SHALL reject the hook execution before starting the command

#### Scenario: Session overlay references another tenant hook
- **WHEN** a session overlay references a hook id that is not defined for the current effective tenant
- **THEN** the system SHALL ignore or reject that overlay entry
- **AND** the system SHALL NOT load hook configuration from the other tenant

#### Scenario: HTTP secret remains tenant scoped
- **WHEN** an HTTP hook uses configured headers or secrets
- **THEN** the system SHALL resolve those values only from the current tenant secret scope
- **AND** the system SHALL NOT persist resolved secret values into session state or hook results

### Requirement: Hook failures SHALL follow explicit fail policy
The system SHALL apply a configured fail policy when a handler fails to start,
times out, returns invalid output, or raises an execution error.

#### Scenario: Fail policy allows event to continue
- **WHEN** a handler fails
- **AND** its `fail_policy` is `allow`
- **THEN** the system SHALL log the failure
- **AND** the event SHALL continue unless another handler blocks it

#### Scenario: Fail policy blocks event
- **WHEN** a handler fails
- **AND** its `fail_policy` is `block`
- **THEN** the merged event decision SHALL block the event with a hook failure reason
