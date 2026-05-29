## MODIFIED Requirements

### Requirement: Hook runtime SHALL emit supported agent lifecycle events
The system SHALL provide a unified hook runtime that can emit
`SessionStart`, `UserPromptSubmit`, `PreToolUse`, `PostToolUse`,
`PostToolUseFailure`, `BeforeStop`, and `Stop` events with a structured
HookContext.

#### Scenario: Runner emits user prompt event before normal processing
- **WHEN** an agent request contains a user prompt
- **THEN** the system SHALL emit `UserPromptSubmit` before command dispatch and agent reasoning
- **AND** matched hooks SHALL be able to block or enrich the prompt before it is processed

#### Scenario: Tool execution emits pre and post tool events
- **WHEN** an agent requests a tool call
- **THEN** the system SHALL emit `PreToolUse` before executing the tool
- **AND** the system SHALL emit `PostToolUse` after a successful tool execution
- **AND** the system SHALL emit `PostToolUseFailure` after a failed tool execution

#### Scenario: Runner emits before stop event before final stop
- **WHEN** the agent has produced a candidate assistant response for the turn
- **THEN** the system SHALL emit `BeforeStop` before emitting `Stop`
- **AND** matched hooks SHALL be able to allow completion or block stopping with a reason

#### Scenario: Runner emits stop event before ending the turn
- **WHEN** the agent has produced a final assistant response for the turn
- **AND** completion has not been blocked by `BeforeStop`
- **THEN** the system SHALL emit `Stop` before treating the turn as complete

## ADDED Requirements

### Requirement: BeforeStop SHALL act as a completion gate
The system SHALL treat `BeforeStop` as a completion gate that decides whether
the agent may stop after producing a candidate assistant response.

#### Scenario: BeforeStop allows normal completion
- **WHEN** matched `BeforeStop` handlers return `decision="allow"`
- **THEN** the system SHALL continue to the existing `Stop` event path
- **AND** the turn SHALL remain eligible for normal completion

#### Scenario: BeforeStop blocks stopping and continues the agent
- **WHEN** a matched `BeforeStop` handler returns `decision="block"` with a non-empty `reason`
- **THEN** the system SHALL NOT emit `Stop` for that candidate response
- **AND** the system SHALL convert the block reason into an internal follow-up instruction
- **AND** the agent SHALL continue execution in the same request when automatic continuation budget remains

#### Scenario: BeforeStop block re-enters the completion lifecycle
- **WHEN** `BeforeStop` blocks stopping and automatic continuation budget remains
- **THEN** the next agent turn SHALL run through the same completion lifecycle as the original turn
- **AND** the next candidate response SHALL be eligible for post-turn validation, `BeforeStop`, and `Stop`
- **AND** the previous blocked candidate response SHALL NOT run `Stop`

#### Scenario: Completion side effects wait for BeforeStop
- **WHEN** a candidate assistant response has been produced
- **AND** `BeforeStop` has not yet allowed completion
- **THEN** the system SHALL NOT treat the candidate as final for pending validation storage, suggestions, final model-output indexing, trace completion, or QA extraction
- **AND** those side effects SHALL only run after `BeforeStop` allows completion or after the task is explicitly marked incomplete

#### Scenario: BeforeStop block uses event-specific semantics
- **WHEN** a matched `BeforeStop` handler returns `decision="block"`
- **THEN** the system SHALL interpret the block as "do not stop yet"
- **AND** the system SHALL NOT treat the block as a final user-visible denial while continuation budget remains

#### Scenario: BeforeStop does not hide candidate response
- **WHEN** the agent has streamed a candidate assistant response
- **AND** `BeforeStop` later blocks stopping
- **THEN** the system SHALL keep the already streamed response visible
- **AND** the system SHALL stream any later continuation output normally

### Requirement: BeforeStop SHALL support only allow and block decisions
The system SHALL constrain first-version `BeforeStop` handler outcomes to
`allow` and `block` decisions.

#### Scenario: BeforeStop allow is accepted
- **WHEN** a matched `BeforeStop` handler returns `decision="allow"` with a non-empty `reason`
- **THEN** the system SHALL treat the handler as allowing completion

#### Scenario: BeforeStop block is accepted
- **WHEN** a matched `BeforeStop` handler returns `decision="block"` with a non-empty `reason`
- **THEN** the system SHALL treat the handler as blocking stop and requesting continuation

#### Scenario: BeforeStop unsupported decisions are blocking configuration or runtime errors
- **WHEN** a matched `BeforeStop` handler returns `decision="deny"`, `permissionDecision="ask"`, top-level `continue=false`, `hookSpecificOutput.updatedInput`, `hookSpecificOutput.sessionTitle`, or `hookSpecificOutput.additionalContext`
- **THEN** the system SHALL NOT apply those event-specific behaviors to `BeforeStop`
- **AND** the event outcome SHALL follow the handler failure or unsupported-output policy used by the hook runtime

#### Scenario: BeforeStop output validation does not change other events
- **WHEN** a handler on `Stop`, `PreToolUse`, or `UserPromptSubmit` returns output supported by that event
- **THEN** the system SHALL preserve the existing event semantics for that output
- **AND** `BeforeStop`-specific unsupported-output validation SHALL NOT reject that output on unrelated events

### Requirement: BeforeStop SHALL be bounded and re-entry safe
The system SHALL prevent `BeforeStop` completion-gate continuations from
recursing or looping indefinitely.

#### Scenario: stop hook active guard prevents re-entry
- **WHEN** the runner is already executing the stop hook path
- **AND** another stop boundary is reached before that path completes
- **THEN** the system SHALL NOT recursively emit `BeforeStop`
- **AND** the system SHALL allow the active stop path to finish according to its current decision

#### Scenario: stop hook active guard is scoped to the active stop path
- **WHEN** `BeforeStop` blocks stopping and schedules a gate-driven follow-up
- **THEN** the runner SHALL clear the re-entry guard before starting that follow-up turn
- **AND** the follow-up candidate response SHALL be eligible to emit `BeforeStop`

#### Scenario: BeforeStop continuation budget is enforced
- **WHEN** `BeforeStop` returns `block` after the configured automatic continuation budget is exhausted
- **THEN** the system SHALL stop automatic continuation
- **AND** the system SHALL surface the latest block reason to the user
- **AND** the system SHALL mark the task as incomplete

#### Scenario: BeforeStop budget counts only gate-driven continuations
- **WHEN** post-turn validation performs its own automatic continuation
- **THEN** the system SHALL NOT count that continuation against the `BeforeStop` continuation budget
- **AND** `BeforeStop` SHALL maintain its own continuation count for gate-driven follow-ups

#### Scenario: Aggregate automatic continuation budget is enforced
- **WHEN** post-turn validation follow-ups and `BeforeStop` follow-ups both occur in the same request
- **THEN** the system SHALL enforce an aggregate automatic continuation cap for the request
- **AND** the system SHALL stop automatic continuation and mark the task incomplete when the aggregate cap is exhausted