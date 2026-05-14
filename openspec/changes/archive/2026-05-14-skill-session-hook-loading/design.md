## Context

The unified agent hook runtime already supports tenant-scoped hooks,
agent-scoped hooks, and session overlays. Hook plans are resolved at every
event boundary, which is the right execution model for dynamic session
behavior.

Skills currently load into the agent toolkit from the workspace skills
directory, and the skill invocation detector tracks which skill is active
during a trace when tracing is enabled. Skill hook loading must not depend
solely on tracing being enabled, because hook policy should work for any
agent session. The skill activation path is still the right semantic boundary,
but the loading collaborator must be available from session/runtime context,
not only from tracing context.

The new convention is:

```text
<workspace>/skills/<skill_name>/
├── SKILL.md
├── hooks/
│   └── hooks.json
└── scripts/
    └── <hook scripts>
```

`hooks/hooks.json` uses the existing `HookConfig` shape. Skill-owned command
handlers may reference scripts, but those script paths must resolve under the
same skill's `scripts/` directory.

## Goals / Non-Goals

**Goals:**

- Load a skill's `hooks/hooks.json` when that skill becomes active in an
  agent session, whether tracing is enabled or disabled.
- Allow the file to define MVP hook handlers using the existing `command` and
  `http` handler types, with additional validation for skill-owned handlers.
- Keep skill-loaded hooks session scoped, idempotent, persisted in session
  state, and effective only at later hook event boundaries.
- Namespace skill hook ids to avoid collisions across tenant, agent, and
  other skill hook sources.
- Enforce that skill command hooks execute scripts from the same skill's
  `scripts/` directory.
- Preserve tenant isolation and tenant-scoped HTTP secret handling.

**Non-Goals:**

- Add new hook event types.
- Add new handler types beyond the unified hook runtime MVP.
- Add a frontend UI for editing skill hook files.
- Support multiple hook config files per skill.
- Automatically unload hooks when the detector ends a skill invocation.
- Allowing skill hook command scripts outside the skill's own `scripts/`
  directory.
- Supporting shell-string `command` handlers in skill hook configs.
  Skill-owned command hooks must use `argv` so script paths can be validated
  and normalized without shell parsing ambiguity.

## Decisions

### Decision 1: Use `hooks/hooks.json` as the single skill hook config file

Each skill may provide exactly one hook config file at
`<skill>/hooks/hooks.json`. The file uses the existing `HookConfig` schema:
`enabled` plus `events -> matcher groups -> hooks`.

This keeps skill hook authoring aligned with tenant and agent hook
configuration and avoids introducing another config shape.

Alternative considered: allow multiple files under `hooks/`. That is more
flexible but creates ordering, deduplication, and error reporting questions
that are not needed for the first implementation.

### Decision 2: Load hooks at skill activation time through session runtime state

The runtime loads a skill hook config from the skill activation flow, when
the session starts using a skill. `SkillInvocationDetector.start_skill()` can
remain the call site, but it must receive a session-scoped hook loader or
state accessor from the agent/runner runtime. Loading must not be skipped just
because tracing is disabled.

This matches the user's intent that hooks load during the agent session when
the skill is used. It also preserves the hook runtime's existing rule that
in-flight hook events keep their original immutable plan.

Alternative considered: load all enabled skill hooks when `SWEAgent` registers
skills. That is simpler but expands hook behavior to skills that are enabled
but never used.

### Decision 3: Treat skill hooks as session hook sources, not tenant config

Skill hook configs should not be copied into tenant or agent configuration.
They should be stored in session-scoped hook state as loaded skill hook
sources. The implementation should introduce a `HookSessionState`-style model
or an equivalent backward-compatible extension that separates:

- loaded hook definitions from skills.
- overlay entries that enable, disable, or override existing handlers.
- `once` execution tracking.

The hook resolver should merge sources in deterministic order:

```text
tenant hooks -> agent hooks -> loaded skill hook sources -> overlay overrides
```

Overlay entries can still disable or override handlers after namespacing.
Runner and tool hook emission must treat a non-empty loaded skill hook source
as hook-enabled even when tenant and agent hook configs are both disabled.

Alternative considered: rewrite skill hooks into overlay entries only. The
current overlay model primarily references already-available handler ids, so
using it as the only storage would blur the difference between handler
definitions and handler overrides.

### Decision 4: Namespace every loaded skill hook id

Loaded skill group ids and handler ids are rewritten with a stable namespace:

```text
skill:<skill_name>:<original_id>
```

For anonymous matcher groups, the generated group id should also include the
skill namespace and group index. Namespacing prevents collisions with tenant,
agent, and other skill handlers and makes session state readable.

Alternative considered: reject collisions without rewriting ids. That would
make skill packages less portable because authors would need to coordinate ids
with each tenant and agent profile.

### Decision 5: Skill command handlers must use `argv` and scripts under `scripts/`

For skill-owned `command` handlers, `argv` is required and shell-string
`command` is rejected during skill hook loading. This still permits
argv-based command handlers using the existing command handler type, but
avoids unsafe shell parsing when proving the target script is skill-owned.

The loader must identify the script argument in `argv`, resolve it relative
to the skill root, require the resolved path to be under the same skill's
`scripts/` directory, and rewrite the script argument to a normalized absolute
path before storing the loaded handler. The resolved script must exist and be
a regular file at load time. The handler `cwd` should be normalized to the
skill root unless an explicit cwd is provided; explicit cwd must still resolve
under the same skill directory and the tenant workspace boundary.

The implementation should reject path traversal, symlink escapes, missing
script arguments, ambiguous multiple script arguments, missing files,
directories, and definitions that cannot be validated safely. Non-script
executable names such as `python` may appear as interpreters, but the script
argument must still be identified and validated.

Alternative considered: keep the current workspace-level command boundary
only. That is too broad for portable skill hooks because one skill could
execute another skill's script.

Alternative considered: allow shell-string `command` for skill hooks. That
keeps parity with tenant hooks but cannot be made robust without implementing
a shell parser for every supported shell and rejecting many real-world shell
constructs. Requiring `argv` is a narrower, testable contract.

### Decision 6: Keep loaded skill hooks until session end or explicit disable

Once a skill's hooks are loaded, they remain available for the current session.
Repeated activations of the same skill are idempotent and must not duplicate
handlers. Later overlay entries may disable namespaced handlers.

This avoids confusing behavior caused by idle-threshold based skill end
detection and makes hook behavior stable after a skill has contributed policy
to a session.

Alternative considered: unload hooks in `_end_skill()`. That gives stricter
active-skill scoping but couples hook availability to heuristic skill
attribution and nested skill boundaries.

### Decision 7: Reuse skill scanning for hook configs and scripts

Skill hook config files and hook scripts live inside the skill directory and
must be covered by the existing skill scanner during skill import, save, and
enable flows. A skill with hook files that fail scanning should not become
enabled for runtime loading.

This avoids creating a new executable surface that bypasses the current skill
governance path.

Alternative considered: scan only at hook load time. That catches runtime
edits, but it is too late for user-facing enable/import workflows and should
be a defense-in-depth check rather than the primary gate.

### Decision 8: Restrict skill-owned HTTP hooks to tenant-approved endpoints

Skill-owned HTTP handlers can use the existing HTTP handler shape, but they
must not be able to leak data to arbitrary remote destinations. The loader
should reject skill HTTP hooks unless their URL matches a tenant-approved
endpoint allowlist, and it should reject literal headers and `allowedEnvVars`
on skill-owned HTTP handlers. Skill HTTP hooks may still use
`headerSecretRefs` so tenant-scoped secrets are injected at execution time.

This preserves compatibility with the existing handler model while keeping
tenant governance over where hook context can go.

Alternative considered: allow any skill HTTP URL. That would be portable, but
it would make skill packages an exfiltration surface without additional tenant
approval.

## Risks / Trade-offs

- Skill command hooks can become a policy bypass -> Validate command script
  paths against the same skill's `scripts/` directory and keep tenant
  workspace boundary checks.
- Skill hook configs can make session behavior hard to explain -> Namespace
  ids and persist loaded source metadata in session state for observability.
- Loading hooks on skill activation means the first event that caused the
  activation is not affected by those hooks -> Document that skill hooks apply
  to later hook event boundaries.
- HTTP hooks in skill configs may leak context -> Keep tenant-scoped secret
  resolution and require normal hook failure policies and redaction.
- Existing overlay validation only knows tenant/agent ids -> Extend validation
  to include loaded session hook source ids before applying overrides.
- Tracing-disabled sessions could miss skill hook loading -> Wire loading
  through runner/agent session context and keep tracing as an observer, not
  the owner of hook loading.
- Skill-only hook sessions could skip hook emission because current gates only
  check tenant/agent configs -> Update runner and tool hook gates to also
  enable emission when session hook state has loaded skill sources.
- Shell-string command configs are hard to validate safely -> Reject
  skill-owned shell `command` handlers and require `argv` with a single
  validated script argument.
- Hook scripts could bypass skill scanner if the scanner only reads
  `SKILL.md` -> Verify scanner coverage for `hooks/` and `scripts/`, and add
  regression tests around import/save/enable flows.
- Skill HTTP hooks could exfiltrate hook context to arbitrary URLs -> Require
  tenant-approved endpoint matching and reject literal headers plus
  `allowedEnvVars` on skill-owned HTTP handlers.

## Migration Plan

1. Add the session hook state data model behind empty defaults so existing
   sessions deserialize unchanged.
2. Implement skill hook config discovery, parsing, namespacing, and command
   path validation.
3. Wire skill hook loading into skill activation through runner/agent session
   context and persist the updated session hook state.
4. Extend hook resolution to include loaded skill hook sources.
5. Add tests for no-file/no-config behavior to prove existing sessions and
   skills are unchanged.
6. Roll back by ignoring `hooks/hooks.json` loading; tenant and agent hook
   configuration remains unaffected.

## Open Questions

None.
