## 1. Pre-change Analysis

- [x] 1.1 Run GitNexus impact analysis for hook session state models, hook resolver, skill invocation activation, and runner session persistence symbols before editing.
- [x] 1.2 Review current hook runtime tests and skill invocation tests to identify the smallest regression coverage additions.

## 2. Session Hook Source Model

- [x] 2.1 Extend hook runtime models with a session-scoped loaded skill hook source structure that stores skill name, skill root, namespaced hook config, loaded timestamp, and source metadata.
- [x] 2.2 Add a backward-compatible session hook state model that separates loaded skill hook definitions, overlay entries, and `once` tracking.
- [x] 2.3 Extend legacy `hook_overlay` loading so existing session state deserializes with empty loaded skill hook sources.
- [x] 2.4 Add model validation for loaded skill hook source ids, duplicate skill entries, namespaced handler ids, and overlay references to namespaced skill hook ids.
- [x] 2.5 Add unit tests for empty legacy overlay state, loaded source serialization, duplicate detection, and overlay references to namespaced skill hook ids.

## 3. Skill Hook Loading

- [x] 3.1 Add a skill hook loader that discovers only `<skill>/hooks/hooks.json` and ignores other files under `hooks/`.
- [x] 3.2 Parse `hooks/hooks.json` using the existing `HookConfig` schema and skip loading when the file is missing or disabled.
- [x] 3.3 Namespace matcher group ids and handler ids with `skill:<skill_name>:` during load.
- [x] 3.4 Normalize accepted skill command handler script paths to resolved absolute paths and normalize cwd to the skill root unless an explicit safe cwd is provided.
- [x] 3.5 Make repeated loads of the same skill idempotent within the current session hook state.
- [x] 3.6 Add unit tests for missing file behavior, invalid JSON/schema rejection, disabled config, namespacing, path normalization, and repeated activation idempotency.

## 4. Command Script Boundary

- [x] 4.1 Require skill-owned command handlers to use `argv` and reject shell-string `command` handlers during skill hook loading.
- [x] 4.2 Implement validation for skill-owned command handlers so exactly one script argument resolves under the same skill's `scripts/` directory.
- [x] 4.3 Reject missing script arguments, ambiguous multiple script arguments, traversal, absolute path escape, symlink escape, missing files, directory script paths, and literal `env` values before handlers are added to session state.
- [x] 4.4 Preserve existing tenant workspace path checks during actual command hook execution.
- [x] 4.5 Add unit tests for valid `argv` with `scripts/check.py`, shell command rejection, missing script argument rejection, ambiguous script rejection, invalid sibling skill paths, traversal escape, absolute escape, symlink escape, missing file rejection, and directory path rejection.

## 5. Hook Resolution Integration

- [x] 5.1 Extend hook resolver input so event plans merge tenant hooks, agent hooks, loaded skill hook sources, and overlay overrides in deterministic order.
- [x] 5.2 Ensure available handler id validation includes namespaced loaded skill hook ids before applying overlay disables or overrides.
- [x] 5.3 Update runner and tool hook enabled gates so non-empty loaded skill hook sources trigger hook emission even when tenant and agent hooks are disabled.
- [x] 5.4 Preserve current empty-config and no-loaded-skill behavior.
- [x] 5.5 Add resolver and emission gate tests for tenant/agent/skill merge order, deduplication, overlay disable of a skill hook, skill-only hook execution, and no-config regression behavior.

## 6. Skill Activation Integration

- [x] 6.1 Pass workspace directory and current session hook state into the skill activation path through runner/agent session context, not only through tracing context.
- [x] 6.2 Load a skill's hook config from `SkillInvocationDetector.start_skill()` or an equivalent activation collaborator after the skill is activated for the current session.
- [x] 6.3 Ensure skill hook loading runs when tracing is enabled and when tracing is disabled.
- [x] 6.4 Persist mutated session hook state so later runner and tool hook events observe loaded skill hooks at event boundaries.
- [x] 6.5 Ensure hooks loaded after a skill activation do not affect an in-flight hook event plan.
- [x] 6.6 Add integration tests proving a skill activation loads hooks that affect a later `PreToolUse` or `Stop` event with tracing enabled and disabled.

## 7. Security and Tenant Isolation

- [x] 7.1 Ensure skill hook loading uses the current effective tenant workspace and cannot read another tenant's skill directory.
- [x] 7.2 Add tenant-governed approval for skill-owned HTTP hook endpoint URLs and reject skill HTTP handlers that do not match the current tenant policy.
- [x] 7.3 Reject skill-owned HTTP handlers with literal `headers` or `allowedEnvVars`; allow tenant-scoped `headerSecretRefs` only.
- [x] 7.4 Ensure HTTP hook header secret refs from skill configs still resolve only through current tenant secret scope and are not stored resolved in session state.
- [x] 7.5 Verify existing skill scanner import, save, and enable flows scan `hooks/hooks.json` and `scripts/` files before a skill can run hook code.
- [x] 7.6 Add regression tests for cross-tenant skill hook loading attempts, tenant-scoped HTTP secret resolution, unapproved HTTP endpoint rejection, literal header/env-var rejection, and scanner rejection of unsafe hook files or scripts.

## 8. Documentation and Verification

- [x] 8.1 Update hook or skill developer documentation with the `hooks/hooks.json` and `scripts/` directory convention.
- [x] 8.2 Add a minimal example skill hook config showing a command handler that invokes a script under `scripts/`.
- [x] 8.3 Run focused pytest suites for hook runtime models/resolver, skill invocation detector, runner hook runtime, and tenant path boundary tests.
- [x] 8.4 Run `openspec status --change skill-session-hook-loading` and ensure the change is apply-ready.
- [x] 8.5 Run `gitnexus_detect_changes()` before any implementation commit to confirm affected flows match the expected hook and skill-loading scope.
