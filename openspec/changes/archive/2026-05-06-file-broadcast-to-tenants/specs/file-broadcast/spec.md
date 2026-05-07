## ADDED Requirements

### Requirement: File broadcast service
The system SHALL provide a `FileBroadcastService` class that copies specified workspace MD files from a source tenant to one or more target tenants' default workspace directories.

#### Scenario: Successful broadcast to multiple tenants
- **WHEN** `FileBroadcastService.broadcast()` is called with `file_names=["AGENTS.md", "SOUL.md"]` and `target_tenant_ids=["alice", "bob"]`
- **THEN** the service SHALL copy both files to `~/.swe/alice/workspaces/default/` and `~/.swe/bob/workspaces/default/`, and return a `BroadcastFilesResponse` with `results` containing two entries where `success=true`

#### Scenario: Target tenant directory does not exist
- **WHEN** a target tenant's workspace directory does not exist
- **THEN** the service SHALL invoke `TenantInitializer.ensure_seeded_bootstrap()` to create the directory structure before copying files, and set `bootstrapped=true` in the result

#### Scenario: Partial failure isolation
- **WHEN** file broadcast to tenant "alice" succeeds but broadcast to tenant "bob" fails
- **THEN** the service SHALL return a `BroadcastFilesResponse` with one result where `success=true` for "alice" and one result where `success=false` with `error` populated for "bob", and the failure SHALL NOT prevent the successful copy

### Requirement: Broadcastable files whitelist
The system SHALL restrict broadcastable files to a fixed whitelist: `AGENTS.md`, `BOOTSTRAP.md`, `HEARTBEAT.md`, `MEMORY.md`, `PROFILE.md`, `SOUL.md`.

#### Scenario: Request includes non-broadcastable file
- **WHEN** a broadcast request includes `file_names=["AGENTS.md", "secret.txt"]`
- **THEN** the system SHALL reject the request with HTTP 400 and a message indicating "secret.txt" is not broadcastable

#### Scenario: Request includes only broadcastable files
- **WHEN** a broadcast request includes `file_names=["AGENTS.md", "SOUL.md"]`
- **THEN** the system SHALL accept the request and proceed with the broadcast

### Requirement: Overwrite enforcement
The system SHALL require `overwrite=true` for all file broadcast requests.

#### Scenario: Request with overwrite=false
- **WHEN** a broadcast request includes `overwrite=false`
- **THEN** the system SHALL reject the request with HTTP 400 and the message "overwrite=true is required for file broadcast"

#### Scenario: Request with overwrite=true
- **WHEN** a broadcast request includes `overwrite=true`
- **THEN** the system SHALL proceed with the broadcast, overwriting existing files in target tenants

### Requirement: Source file pre-validation
The system SHALL validate that all requested source files exist before starting the broadcast.

#### Scenario: Source file does not exist
- **WHEN** a broadcast request includes `file_names=["AGENTS.md"]` but `AGENTS.md` does not exist in the source workspace
- **THEN** the system SHALL reject the request with HTTP 400 and a message indicating the file was not found

#### Scenario: All source files exist
- **WHEN** all files in `file_names` exist in the source workspace
- **THEN** the system SHALL proceed with the broadcast

### Requirement: Broadcast tenant list endpoint
The system SHALL provide a `GET /workspace/broadcast/tenants` endpoint that returns tenant IDs available for file broadcast.

#### Scenario: Successful tenant list retrieval
- **WHEN** an authenticated request is made to `GET /workspace/broadcast/tenants`
- **THEN** the system SHALL return `{"tenant_ids": [...]}` with tenant IDs filtered by the current `source_id`

### Requirement: Broadcast files endpoint
The system SHALL provide a `POST /workspace/broadcast/files` endpoint that accepts `file_names`, `target_tenant_ids`, and `overwrite` in the request body.

#### Scenario: Successful broadcast
- **WHEN** a valid request is made with `file_names`, `target_tenant_ids`, and `overwrite=true`
- **THEN** the system SHALL return a `BroadcastFilesResponse` with per-tenant results

#### Scenario: Missing required fields
- **WHEN** a request is missing `target_tenant_ids` or `file_names`
- **THEN** the system SHALL return HTTP 400 with an appropriate error message

### Requirement: Tenant ID validation
The system SHALL validate that each `target_tenant_id` is non-empty, does not exceed 256 characters, and does not contain path traversal characters (`..`, `/`, `\`).

#### Scenario: Tenant ID with path traversal
- **WHEN** a broadcast request includes `target_tenant_ids=["../etc"]`
- **THEN** the system SHALL reject the tenant ID with a validation error

#### Scenario: Valid tenant ID
- **WHEN** a broadcast request includes `target_tenant_ids=["alice"]`
- **THEN** the system SHALL accept the tenant ID and proceed

### Requirement: Frontend file selection on page cards
The frontend SHALL display a "选择/已选择" toggle button on each broadcastable file's card in the workspace file list.

#### Scenario: Broadcastable file shows select button
- **WHEN** a file card belongs to `BROADCASTABLE_FILES` (e.g., AGENTS.md)
- **THEN** the card SHALL display a "选择" button

#### Scenario: Non-broadcastable file hides select button
- **WHEN** a file card does not belong to `BROADCASTABLE_FILES` (e.g., a daily memory file)
- **THEN** the card SHALL NOT display a select button

#### Scenario: Selecting a file
- **WHEN** user clicks the "选择" button on a file card
- **THEN** the button text SHALL change to "已选择", the card SHALL display a blue border, and the file name SHALL be added to the selection

#### Scenario: Deselecting a file
- **WHEN** user clicks the "已选择" button on a previously selected file card
- **THEN** the button text SHALL change back to "选择", the blue border SHALL be removed, and the file name SHALL be removed from the selection

### Requirement: Frontend broadcast button in page header
The frontend SHALL display a "分发" button with `SendOutlined` icon in the PageHeader action area.

#### Scenario: No files selected
- **WHEN** no files are selected for broadcast
- **THEN** the "分发" button SHALL be disabled

#### Scenario: Files selected
- **WHEN** one or more files are selected for broadcast
- **THEN** the "分发" button SHALL be enabled and a selection count badge SHALL appear next to it

### Requirement: Frontend broadcast modal
The frontend SHALL display an inline Modal when the "分发" button is clicked.

#### Scenario: Opening broadcast modal
- **WHEN** user clicks the "分发" button
- **THEN** a Modal SHALL open with: hint text, current source file count, an orange warning about overwrite behavior, and a `TenantTargetPicker` component

#### Scenario: Tenant list loading
- **WHEN** the broadcast modal opens
- **THEN** the system SHALL asynchronously load the tenant list from `GET /workspace/broadcast/tenants`, filter out the current tenant, and display a loading state until complete

#### Scenario: Current tenant excluded
- **WHEN** the tenant list is loaded
- **THEN** the current tenant ID SHALL be excluded from the available targets

#### Scenario: No tenant selected
- **WHEN** no target tenants are selected in the picker
- **THEN** the OK button SHALL be disabled

### Requirement: Frontend broadcast execution
The frontend SHALL call `POST /workspace/broadcast/files` when the user confirms the broadcast.

#### Scenario: Successful broadcast with results
- **WHEN** the broadcast API returns successful results
- **THEN** the frontend SHALL display a success message and a `Modal.confirm` dialog listing succeeded tenants, marking bootstrapped tenants with a suffix

#### Scenario: Partial failure
- **WHEN** some tenants succeed and some fail
- **THEN** the frontend SHALL display a success dialog for succeeded tenants and a separate error dialog for failed tenants with error details

#### Scenario: All failures
- **WHEN** all tenants fail
- **THEN** the frontend SHALL display an error message and a `Modal.confirm` dialog with failure details

### Requirement: Frontend i18n support
The frontend SHALL provide i18n keys for all broadcast-related text in Chinese, English, Russian, and Japanese.

#### Scenario: Chinese locale
- **WHEN** the locale is set to "zh"
- **THEN** all broadcast UI text SHALL display in Chinese

#### Scenario: English locale
- **WHEN** the locale is set to "en"
- **THEN** all broadcast UI text SHALL display in English
