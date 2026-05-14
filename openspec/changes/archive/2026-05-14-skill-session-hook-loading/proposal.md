## Why

Swe can already resolve tenant, agent, and session hook configuration at hook
event boundaries, but skill-specific runtime policies still have to be wired
through tenant or agent config manually. Skills need a portable way to bring
their own session hooks when the agent starts using that skill.

This change extends the unified hook protocol so an active skill can
contribute hook handlers from its own directory, while keeping command
execution inside the skill and tenant workspace boundaries.

## What Changes

- Add support for a single skill hook configuration file at
  `<workspace>/skills/<skill_name>/hooks/hooks.json`.
- Allow skill hook configuration to define `command` and `http` handlers using
  the existing unified hook protocol shape, with additional skill-owned
  validation for script paths, environment values, and HTTP destinations.
- Require tenant governance for skill-owned HTTP hooks so arbitrary skills
  cannot exfiltrate hook context to unapproved remote endpoints.
- Load skill hooks when a skill is activated during an agent session, using
  the skill invocation flow as the session-scoped loading boundary.
- Require `command` hook scripts declared by a skill hook config to resolve
  under that same skill's `scripts/` directory and pass normal file checks.
- Namespace skill hook group ids and handler ids so they cannot collide with
  tenant, agent, or other skill hook ids.
- Keep loaded skill hooks session-scoped and idempotent across repeated
  activations of the same skill.
- Preserve tenant-scoped handling for HTTP hook secrets and headers.

## Capabilities

### New Capabilities

- `skill-session-hook-loading`: Defines how active skills contribute session
  hook handlers from `hooks/hooks.json`, how command scripts are constrained
  to `scripts/`, and when those hooks become effective.

### Modified Capabilities

None.

## Impact

- Affected backend code:
  - `src/swe/agents/skill_invocation_detector.py`
  - `src/swe/agents/skill_context_manager.py`
  - `src/swe/agents/skills_manager.py`
  - `src/swe/agents/hook_runtime/*`
  - `src/swe/app/runner/runner.py`
  - `src/swe/agents/tool_guard_mixin.py`
- Affected security boundaries:
  - skill hook configs must not load hooks from another skill or tenant.
  - command hook paths must remain under the active skill's `scripts/`
    directory.
  - skill command hooks must not persist literal environment variables in
    handler config.
  - skill HTTP hooks must not use literal sensitive headers or process
    environment variable headers.
  - skill hook configs and scripts must be covered by existing skill scanning
    before the skill can be enabled or imported.
  - HTTP hook secrets remain tenant-scoped and are not copied into skill files
    or session state.
- Affected tests:
  - unit tests for skill hook config parsing, command path validation,
    namespacing, idempotent session loading, and tenant isolation.
  - integration tests proving skill-loaded hooks affect later hook event
    boundaries without changing no-skill/no-config behavior.
