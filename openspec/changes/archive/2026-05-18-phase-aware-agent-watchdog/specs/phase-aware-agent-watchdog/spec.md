## ADDED Requirements

### Requirement: Agent watchdog SHALL evaluate liveness by current execution phase
The system SHALL track the current Agent execution phase and SHALL use that
phase, rather than only user-visible output, when deciding whether an Agent run
is stalled.

#### Scenario: Reasoning phase exceeds idle threshold
- **WHEN** an Agent is in the reasoning phase
- **AND** no internal activity is recorded for the configured watchdog idle threshold
- **THEN** the system SHALL interrupt the Agent run as a stalled reasoning phase
- **AND** the watchdog log SHALL include the reasoning phase and silence duration

#### Scenario: Tool phase is silent but still within tool hard timeout
- **WHEN** an Agent is executing a tool
- **AND** no user-visible output is produced for the configured watchdog idle threshold
- **AND** the tool has not exceeded its applicable hard timeout
- **THEN** the system SHALL NOT interrupt the Agent run solely because of output silence
- **AND** the system SHALL continue relying on the applicable tool or query timeout

#### Scenario: Unknown phase exceeds idle threshold
- **WHEN** an Agent phase is unknown
- **AND** no internal activity is recorded for the configured watchdog idle threshold
- **THEN** the system SHALL apply conservative stall handling
- **AND** the watchdog log SHALL include `unknown` as the phase for diagnosis

### Requirement: Agent phases SHALL record internal activity independently from output
The system SHALL update Agent activity timestamps for phase transitions and
selected internal checkpoints, even when no message is printed to the user.

#### Scenario: Phase transition records activity
- **WHEN** an Agent enters reasoning, acting, tool execution, approval replay, or summarizing
- **THEN** the system SHALL update the current phase
- **AND** the system SHALL update the last internal activity timestamp

#### Scenario: User-visible output records activity
- **WHEN** the Agent prints a message or tool result chunk
- **THEN** the system SHALL update the last internal activity timestamp
- **AND** the current phase SHALL remain available for diagnostics

### Requirement: Tool execution SHALL have bounded timeout semantics
The system SHALL ensure tool execution phases are bounded by an applicable
tool, subsystem, or query timeout instead of only by output-idle detection.

#### Scenario: MCP tool execution exceeds MCP timeout
- **WHEN** an MCP tool call exceeds the configured MCP call timeout
- **THEN** the system SHALL fail the tool call through the MCP timeout path
- **AND** the Agent watchdog SHALL NOT report the failure as an output-idle stall

#### Scenario: Local tool execution exceeds generic tool timeout
- **WHEN** a local tool execution path without a more specific timeout exceeds the configured generic tool hard timeout
- **THEN** the system SHALL fail that tool execution with a timeout error
- **AND** the error SHALL include the tool name and elapsed duration

#### Scenario: Query timeout remains the outer bound
- **WHEN** an Agent run exceeds the configured global query timeout
- **THEN** the system SHALL terminate the query through the existing query timeout path
- **AND** phase-aware watchdog behavior SHALL NOT extend the run beyond the global query timeout

### Requirement: Watchdog diagnostics SHALL identify the stalled phase
The system SHALL include phase and activity metadata in watchdog warning and
interruption logs.

#### Scenario: Watchdog interrupts a run
- **WHEN** the watchdog interrupts an Agent run
- **THEN** the log SHALL include the current phase, phase duration, last activity age, configured threshold, session id when available, and agent id when available
- **AND** the log SHALL include tool name and tool call id when the current phase is tool-related

#### Scenario: Tool phase remains silent past idle threshold
- **WHEN** a tool phase is silent past the watchdog idle threshold but remains within its hard timeout
- **THEN** the system SHALL log enough phase metadata to diagnose the silence
- **AND** the system SHALL NOT label the condition as an Agent output-idle interruption

### Requirement: Built-in file write diagnostics SHALL not expose file contents
The system SHALL record timing and size diagnostics for built-in file write
operations without logging written content.

#### Scenario: Built-in write_file completes
- **WHEN** the built-in `write_file` operation completes
- **THEN** the system SHALL be able to log total duration and content byte length
- **AND** the system SHALL NOT log the file content

#### Scenario: Built-in file write is slow
- **WHEN** a built-in file write operation exceeds the configured slow-write diagnostic threshold
- **THEN** the system SHALL emit a warning with the resolved path, content byte length, and timing breakdown
- **AND** the system SHALL NOT emit the file content
