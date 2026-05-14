## MODIFIED Requirements

### Requirement: Hook configuration SHALL support prompt handlers
The system SHALL support a `prompt` hook handler type in tenant, agent, and skill hook configuration.

#### Scenario: Tenant prompt handler config is accepted
- **WHEN** tenant hook configuration defines a handler with `type="prompt"` and a non-empty `prompt`
- **AND** the handler is configured under `SessionStart`, `UserPromptSubmit`, `PreToolUse`, `BeforeStop`, or `Stop`
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

#### Scenario: Prompt handler is valid on BeforeStop
- **WHEN** hook configuration defines a `prompt` handler under `BeforeStop`
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

#### Scenario: BeforeStop prompt handler receives assistant response
- **WHEN** a prompt handler is executed for `BeforeStop`
- **THEN** the runtime context layer SHALL include the candidate assistant response being checked
- **AND** the handler SHALL NOT be expected to infer candidate-answer content from `prompt` or `transcript_path` alone

#### Scenario: Stop prompt handler receives assistant response
- **WHEN** a prompt handler is executed for `Stop`
- **THEN** the runtime context layer SHALL include the assistant response being finalized
- **AND** the handler SHALL NOT be expected to infer final-answer content from `prompt` or `transcript_path` alone

#### Scenario: Prompt field is treated as business rules
- **WHEN** a prompt handler has a configured `prompt`
- **THEN** the system SHALL include that text only in the hook business rules layer
- **AND** the system SHALL NOT treat that text as the full final model prompt

## ADDED Requirements

### Requirement: BeforeStop prompt handlers SHALL produce completion-gate judgments
The system SHALL treat prompt handler output for `BeforeStop` as a
completion-gate judgment.

#### Scenario: BeforeStop prompt allow output is parsed
- **WHEN** a `BeforeStop` prompt handler model response is a JSON object with exactly `decision="allow"` and a non-empty string `reason`
- **THEN** the handler result SHALL allow the candidate response to proceed toward `Stop`

#### Scenario: BeforeStop prompt block output is parsed
- **WHEN** a `BeforeStop` prompt handler model response is a JSON object with exactly `decision="block"` and a non-empty string `reason`
- **THEN** the handler result SHALL block stopping
- **AND** the returned reason SHALL be available to the runner for internal continuation

#### Scenario: BeforeStop prompt deny output is rejected
- **WHEN** a `BeforeStop` prompt handler model response is a JSON object with `decision="deny"`
- **THEN** the handler SHALL treat the output as invalid for `BeforeStop`
- **AND** the event outcome SHALL follow the handler's configured `failPolicy`

#### Scenario: BeforeStop prompt constraints are event-specific
- **WHEN** a prompt handler is executed for `BeforeStop`
- **THEN** the structured output constraints SHALL require `decision` to be only `allow` or `block`
- **AND** the handler SHALL reject any extra fields using the same invalid-output failure path as other prompt handler shape errors

#### Scenario: Non-BeforeStop prompt deny output remains valid
- **WHEN** a prompt handler is executed for `SessionStart`, `UserPromptSubmit`, `PreToolUse`, or `Stop`
- **AND** the model response is a JSON object with exactly `decision="deny"` and a non-empty string `reason`
- **THEN** the handler SHALL preserve the existing deny judgment semantics for that event
