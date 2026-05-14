## ADDED Requirements

### Requirement: Hook configuration SHALL support prompt handlers
The system SHALL support a `prompt` hook handler type in tenant, agent, and skill hook configuration.

#### Scenario: Tenant prompt handler config is accepted
- **WHEN** tenant hook configuration defines a handler with `type="prompt"` and a non-empty `prompt`
- **AND** the handler is configured under `SessionStart`, `UserPromptSubmit`, `PreToolUse`, or `Stop`
- **THEN** the system SHALL parse the handler as a prompt hook handler
- **AND** the handler SHALL retain common fields including `if`, `timeout`, `statusMessage`, `once`, and `failPolicy`

#### Scenario: Agent prompt handler config is accepted
- **WHEN** agent hook configuration defines a handler with `type="prompt"` and a non-empty `prompt`
- **AND** the handler is configured under a supported prompt hook event
- **THEN** the system SHALL parse the handler as a prompt hook handler

#### Scenario: Skill prompt handler config is accepted
- **WHEN** a skill `hooks/hooks.json` defines a handler with `type="prompt"` and a non-empty `prompt`
- **AND** the handler is configured under a supported prompt hook event
- **THEN** the system SHALL load the prompt handler into session hook state
- **AND** the loaded handler id SHALL be namespaced using the existing skill hook id namespace rules

#### Scenario: Empty prompt handler rules are rejected
- **WHEN** hook configuration defines a handler with `type="prompt"`
- **AND** the `prompt` value is missing or empty after trimming whitespace
- **THEN** the system SHALL reject the handler configuration during validation

#### Scenario: Prompt handler override fields are rejected
- **WHEN** hook configuration defines a handler with `type="prompt"`
- **AND** the handler includes model/provider routing fields such as `model`, `provider`, `providerId`, `baseUrl`, or prompt template/file reference fields
- **THEN** the system SHALL reject the handler configuration during validation
- **AND** the system SHALL NOT silently ignore those fields

#### Scenario: Prompt handler defaults to fail closed
- **WHEN** hook configuration defines a handler with `type="prompt"`
- **AND** the handler omits `failPolicy`
- **THEN** the parsed handler SHALL use `failPolicy="block"`

#### Scenario: Prompt handler dedupe includes business rules
- **WHEN** two matched prompt handlers share the same handler id, event, group, and type
- **AND** their `prompt` business rules differ
- **THEN** the resolver SHALL NOT deduplicate them as the same handler target

### Requirement: Prompt handlers SHALL only be valid on blockable events
The system SHALL allow prompt handlers only on events where a blocking decision can still affect execution.

#### Scenario: Prompt handler is valid on SessionStart
- **WHEN** hook configuration defines a `prompt` handler under `SessionStart`
- **THEN** the system SHALL accept the handler configuration

#### Scenario: Prompt handler is valid on UserPromptSubmit
- **WHEN** hook configuration defines a `prompt` handler under `UserPromptSubmit`
- **THEN** the system SHALL accept the handler configuration

#### Scenario: Prompt handler is valid on PreToolUse
- **WHEN** hook configuration defines a `prompt` handler under `PreToolUse`
- **THEN** the system SHALL accept the handler configuration

#### Scenario: Prompt handler is valid on Stop
- **WHEN** hook configuration defines a `prompt` handler under `Stop`
- **THEN** the system SHALL accept the handler configuration

#### Scenario: Prompt handler is rejected on PostToolUse
- **WHEN** hook configuration defines a `prompt` handler under `PostToolUse`
- **THEN** the system SHALL reject the handler configuration during validation

#### Scenario: Prompt handler is rejected on PostToolUseFailure
- **WHEN** hook configuration defines a `prompt` handler under `PostToolUseFailure`
- **THEN** the system SHALL reject the handler configuration during validation

### Requirement: Prompt handlers SHALL use the current tenant active model
The system SHALL execute prompt handlers through the current effective tenant's active model and SHALL NOT allow handler-level model overrides.

#### Scenario: Prompt handler uses effective tenant model
- **WHEN** a prompt handler is executed for a request under effective tenant `alice`
- **THEN** the model call SHALL use tenant `alice` provider configuration and active model
- **AND** the handler SHALL NOT read provider configuration from another tenant
- **AND** the executor SHALL bind tenant, user, source, and workspace context from the HookContext before creating or invoking the model
- **AND** the model factory call SHALL preserve the current agent identity when `context.agent_id` is present

#### Scenario: Handler-level model field is rejected
- **WHEN** hook configuration defines a `prompt` handler with a model or provider override field
- **THEN** the system SHALL reject the handler configuration during validation

#### Scenario: Missing active model follows fail policy
- **WHEN** a prompt handler is executed
- **AND** the current effective tenant has no usable active model configuration
- **THEN** the handler SHALL fail
- **AND** the event outcome SHALL follow the handler's configured `failPolicy`

### Requirement: Prompt handlers SHALL assemble model input with fixed layers
The system SHALL construct prompt handler model input using a platform-owned scaffold before and after the hook business rules.

#### Scenario: Model input preserves fixed layer order
- **WHEN** a prompt handler is executed
- **THEN** the model input SHALL include the platform fixed scaffold before the configured hook business rules
- **AND** the model input SHALL include the runtime HookContext JSON after the hook business rules
- **AND** the model input SHALL include structured output constraints after the runtime HookContext JSON

#### Scenario: HookContext is injected as JSON data
- **WHEN** a prompt handler is executed
- **THEN** the system SHALL serialize a prompt-safe copy of `HookContext.to_handler_payload()` as JSON for the runtime context layer
- **AND** the prompt-safe copy SHALL redact fields covered by the existing hook payload redaction rules
- **AND** the platform scaffold SHALL instruct the model to treat HookContext values as data rather than instructions

#### Scenario: Stop prompt handler receives assistant response
- **WHEN** a prompt handler is executed for `Stop`
- **THEN** the runtime context layer SHALL include the assistant response being finalized
- **AND** the handler SHALL NOT be expected to infer final-answer content from `prompt` or `transcript_path` alone

#### Scenario: Prompt field is treated as business rules
- **WHEN** a prompt handler has a configured `prompt`
- **THEN** the system SHALL include that text only in the hook business rules layer
- **AND** the system SHALL NOT treat that text as the full final model prompt

### Requirement: Prompt handler output SHALL be judgment-only JSON
The system SHALL accept only structured judgment output from prompt handler model responses.

#### Scenario: Allow output is parsed
- **WHEN** the prompt handler model response is a JSON object with exactly `decision="allow"` and a non-empty string `reason`
- **THEN** the handler result SHALL map to `HookDecision.ALLOW`
- **AND** the handler result reason SHALL equal the returned reason

#### Scenario: Deny output is parsed
- **WHEN** the prompt handler model response is a JSON object with exactly `decision="deny"` and a non-empty string `reason`
- **THEN** the handler result SHALL map to `HookDecision.DENY`
- **AND** the handler result reason SHALL equal the returned reason

#### Scenario: Block output is parsed
- **WHEN** the prompt handler model response is a JSON object with exactly `decision="block"` and a non-empty string `reason`
- **THEN** the handler result SHALL map to `HookDecision.BLOCK`
- **AND** the handler result reason SHALL equal the returned reason

#### Scenario: Full HookOutput fields are rejected
- **WHEN** the prompt handler model response contains unsupported fields such as `hookSpecificOutput`, `updatedInput`, `additionalContext`, `sessionTitle`, `systemMessage`, or `continue`
- **THEN** the handler SHALL treat the output as invalid
- **AND** the event outcome SHALL follow the handler's configured `failPolicy`

#### Scenario: Invalid model output follows fail policy
- **WHEN** the prompt handler model response is not valid JSON
- **OR** the response is not a JSON object
- **OR** the response omits `decision` or `reason`
- **OR** the response contains fields other than `decision` and `reason`
- **OR** the response uses a decision other than `allow`, `deny`, or `block`
- **OR** the response reason is not a string
- **OR** the response reason is empty after trimming whitespace
- **THEN** the handler SHALL fail
- **AND** the event outcome SHALL follow the handler's configured `failPolicy`

### Requirement: Prompt handlers SHALL use existing execution and merge semantics
The system SHALL execute prompt handlers as part of the existing hook runtime event plan.

#### Scenario: Prompt handlers execute concurrently with other handlers
- **WHEN** an event plan contains matched `command`, `http`, and `prompt` handlers
- **THEN** the system SHALL execute the matched handlers using the existing concurrent hook execution model

#### Scenario: Prompt handler timeout is enforced
- **WHEN** a prompt handler does not return a model result within its configured timeout
- **THEN** the handler SHALL fail with a timeout failure
- **AND** the event outcome SHALL follow the handler's configured `failPolicy`

#### Scenario: Prompt handler timeout covers streaming extraction
- **WHEN** a prompt handler model call returns a streaming response
- **AND** consuming the stream does not complete within the handler timeout
- **THEN** the handler SHALL fail with a timeout failure
- **AND** the runtime SHALL close or cancel the stream when supported

#### Scenario: Prompt decision participates in deterministic merge
- **WHEN** one matched prompt handler returns `allow`
- **AND** another matched handler returns `deny` or `block`
- **THEN** the merged result SHALL follow the existing hook decision priority rules
- **AND** merge order SHALL remain independent of handler completion order

#### Scenario: Prompt handler once semantics are preserved
- **WHEN** a prompt handler has `once=true`
- **AND** the same handler has already executed for the same effective tenant, user, session, and event
- **THEN** the system SHALL omit that handler from later execution plans for that scope
