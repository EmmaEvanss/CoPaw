## ADDED Requirements

### Requirement: Skills SHALL declare session hooks in a single hooks file
The system SHALL allow an enabled workspace skill to declare session hooks in
`hooks/hooks.json` under that skill directory.

#### Scenario: Skill hooks file is discovered when tracing is enabled
- **WHEN** a skill directory contains `hooks/hooks.json`
- **AND** the skill becomes active during an agent session
- **AND** tracing is enabled for that session
- **THEN** the system SHALL load that file as the skill's hook configuration

#### Scenario: Skill hooks file is discovered when tracing is disabled
- **WHEN** a skill directory contains `hooks/hooks.json`
- **AND** the skill becomes active during an agent session
- **AND** tracing is disabled for that session
- **THEN** the system SHALL load that file as the skill's hook configuration

#### Scenario: Missing hooks file is ignored
- **WHEN** a skill becomes active during an agent session
- **AND** the skill directory does not contain `hooks/hooks.json`
- **THEN** the system SHALL continue without loading skill hooks
- **AND** existing skill behavior SHALL remain unchanged

#### Scenario: Additional hook config files are ignored
- **WHEN** a skill directory contains hook configuration files other than
  `hooks/hooks.json`
- **THEN** the system SHALL NOT load those files as skill hook configuration

### Requirement: Skill hook files SHALL use the unified HookConfig shape
The system SHALL parse `hooks/hooks.json` using the existing unified hook
configuration shape with `enabled` and `events` fields.

#### Scenario: Complete command handler is accepted
- **WHEN** `hooks/hooks.json` defines an enabled event matcher group with a
  `command` handler
- **AND** the command handler satisfies skill script path validation
- **THEN** the system SHALL make that handler available to later hook event
  boundary resolution for the current session

#### Scenario: Complete HTTP handler is accepted
- **WHEN** `hooks/hooks.json` defines an enabled event matcher group with an
  `http` handler
- **AND** the HTTP handler URL matches the current tenant's approved skill
  hook endpoint policy
- **AND** the HTTP handler does not define literal headers or
  `allowedEnvVars`
- **THEN** the system SHALL make that handler available to later hook event
  boundary resolution for the current session
- **AND** HTTP headers and secrets SHALL continue to resolve only through
  tenant-scoped hook runtime rules

#### Scenario: HTTP handler without tenant approval is rejected
- **WHEN** `hooks/hooks.json` defines an `http` handler
- **AND** the HTTP handler URL does not match the current tenant's approved
  skill hook endpoint policy
- **THEN** the system SHALL reject that skill HTTP handler
- **AND** the rejected handler SHALL NOT be included in later event plans

#### Scenario: HTTP handler literal headers are rejected
- **WHEN** `hooks/hooks.json` defines an `http` handler with literal
  `headers`
- **THEN** the system SHALL reject that skill HTTP handler
- **AND** the rejected handler SHALL NOT be included in later event plans

#### Scenario: HTTP handler allowedEnvVars are rejected
- **WHEN** `hooks/hooks.json` defines an `http` handler with
  `allowedEnvVars`
- **THEN** the system SHALL reject that skill HTTP handler
- **AND** the rejected handler SHALL NOT be included in later event plans

#### Scenario: Invalid hook config is rejected for the skill
- **WHEN** `hooks/hooks.json` cannot be parsed as a valid hook configuration
- **THEN** the system SHALL reject that skill hook load
- **AND** the system SHALL continue the agent session without adding handlers
  from that file

### Requirement: Skill command hook scripts SHALL stay inside skill scripts
The system SHALL require command hook scripts declared by a skill hook config
to resolve under that same skill's `scripts/` directory.

#### Scenario: Argv script path under scripts is accepted
- **WHEN** a skill command hook uses `argv` and references `scripts/check.py`
- **AND** the normalized path resolves under the same skill's `scripts/`
  directory
- **AND** the normalized path exists as a regular file
- **THEN** the system SHALL allow the command handler to load
- **AND** the stored handler SHALL use the normalized script path

#### Scenario: Shell command string is rejected
- **WHEN** a skill command hook uses the shell-string `command` field
- **THEN** the system SHALL reject that command handler
- **AND** the rejected handler SHALL NOT be included in later event plans

#### Scenario: Missing script argument is rejected
- **WHEN** a skill command hook uses `argv` without a script argument under
  the same skill's `scripts/` directory
- **THEN** the system SHALL reject that command handler
- **AND** the rejected handler SHALL NOT be included in later event plans

#### Scenario: Ambiguous script arguments are rejected
- **WHEN** a skill command hook uses `argv` with more than one script argument
  under the same skill's `scripts/` directory
- **THEN** the system SHALL reject that command handler
- **AND** the rejected handler SHALL NOT be included in later event plans

#### Scenario: Script path outside scripts is rejected
- **WHEN** a skill command hook references a path outside the same skill's
  `scripts/` directory
- **THEN** the system SHALL reject that command handler
- **AND** the rejected handler SHALL NOT be included in later event plans

#### Scenario: Path traversal is rejected
- **WHEN** a skill command hook references a path that uses traversal to leave
  the same skill's `scripts/` directory
- **THEN** the system SHALL reject that command handler before execution

#### Scenario: Symlink escape is rejected
- **WHEN** a skill command hook script path resolves through a symlink outside
  the same skill's `scripts/` directory
- **THEN** the system SHALL reject that command handler before execution

#### Scenario: Missing script file is rejected
- **WHEN** a skill command hook script path resolves under the same skill's
  `scripts/` directory
- **AND** the path does not exist as a regular file
- **THEN** the system SHALL reject that command handler before execution

#### Scenario: Directory script path is rejected
- **WHEN** a skill command hook script path resolves under the same skill's
  `scripts/` directory
- **AND** the path is a directory
- **THEN** the system SHALL reject that command handler before execution

#### Scenario: Command handler literal environment is rejected
- **WHEN** a skill command hook defines literal `env` values
- **THEN** the system SHALL reject that command handler
- **AND** the rejected handler SHALL NOT be included in later event plans

### Requirement: Skill hooks SHALL be session scoped
Loaded skill hooks SHALL affect only the current session and SHALL NOT modify
tenant or agent hook configuration.

#### Scenario: Loaded hooks apply to later event boundaries
- **WHEN** a skill hook config is loaded after a skill becomes active
- **THEN** the loaded handlers SHALL be considered during later hook event
  boundary resolution in the same session
- **AND** in-flight hook events SHALL continue using their already resolved
  event plan

#### Scenario: Loaded skill hooks enable hook emission
- **WHEN** a session has loaded skill hook handlers
- **AND** tenant and agent hook configuration are disabled or empty
- **THEN** runner and tool hook event emission SHALL still resolve and execute
  the loaded skill hook handlers

#### Scenario: Loaded hooks do not affect other sessions
- **WHEN** a skill hook config is loaded in one session
- **THEN** another session for the same tenant and agent SHALL NOT receive
  those loaded skill handlers unless that other session also activates the
  skill

#### Scenario: Loaded hooks do not persist into tenant config
- **WHEN** a skill hook config is loaded in a session
- **THEN** the system SHALL NOT write those handler definitions into tenant
  configuration
- **AND** the system SHALL NOT write those handler definitions into agent
  configuration

### Requirement: Skill hook loading SHALL be idempotent
The system SHALL load each skill's hook configuration at most once per
session unless the underlying session hook state is explicitly cleared.

#### Scenario: Repeated skill activation does not duplicate handlers
- **WHEN** the same skill becomes active multiple times in one session
- **THEN** the system SHALL NOT add duplicate copies of that skill's loaded
  hook handlers to the session hook state

#### Scenario: Different skills can load independent hooks
- **WHEN** two different skills become active in one session
- **AND** both skills define `hooks/hooks.json`
- **THEN** the system SHALL load both skills' hook handlers into the session
  hook state using separate skill identities

### Requirement: Skill hook ids SHALL be namespaced
The system SHALL namespace skill-loaded matcher group ids and handler ids so
they cannot collide with tenant, agent, or other skill hooks.

#### Scenario: Handler id is namespaced
- **WHEN** a skill hook handler declares id `validate`
- **THEN** the loaded session handler id SHALL include the skill identity,
  such as `skill:<skill_name>:validate`

#### Scenario: Colliding ids from different sources remain distinct
- **WHEN** a tenant hook and a skill hook declare the same original handler id
- **THEN** both handlers SHALL remain independently addressable after skill
  hook namespacing

#### Scenario: Overlay can reference a namespaced skill hook
- **WHEN** a skill hook has been loaded into the current session
- **AND** a session overlay references the namespaced skill hook id
- **THEN** the system SHALL apply that overlay entry during later event plan
  resolution

### Requirement: Skill hook security SHALL preserve tenant boundaries
The system SHALL enforce tenant and workspace isolation when loading and
executing skill hooks.

#### Scenario: Skill hook from another tenant is not loaded
- **WHEN** a session runs under one effective tenant
- **THEN** the system SHALL NOT load a skill hook config from another tenant's
  workspace

#### Scenario: Skill HTTP secret remains tenant scoped
- **WHEN** a skill HTTP hook references a secret-backed header
- **THEN** the system SHALL resolve that secret only from the current
  effective tenant secret scope
- **AND** the system SHALL NOT persist the resolved secret into session state

#### Scenario: Command execution keeps existing tenant path protection
- **WHEN** a skill command hook is executed
- **THEN** the command execution SHALL still satisfy existing tenant workspace
  path boundary protections

#### Scenario: Skill scanner covers hook files and scripts
- **WHEN** a skill contains `hooks/hooks.json` or files under `scripts/`
- **THEN** skill import, save, and enable flows SHALL scan those files through
  the existing skill scanner policy
- **AND** a skill that fails scanning SHALL NOT be enabled for runtime hook
  loading

### Requirement: Skill hook session state SHALL be backward compatible
The system SHALL store loaded skill hook definitions in session-scoped hook
state without breaking existing sessions that only contain legacy
`hook_overlay` data.

#### Scenario: Legacy hook overlay state still loads
- **WHEN** a session state contains only legacy hook overlay fields
- **THEN** the system SHALL load that state without error
- **AND** the system SHALL treat loaded skill hook sources as empty

#### Scenario: Loaded skill hook definitions are persisted separately from overrides
- **WHEN** a skill hook config is loaded into a session
- **THEN** the system SHALL persist the loaded skill hook definitions as
  session-scoped hook sources
- **AND** the system SHALL preserve overlay entries and `once` tracking as
  separate concepts
