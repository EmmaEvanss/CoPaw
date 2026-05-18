## Why

The current tenant-isolation model mixes logical tenant identity with runtime
storage identity. `source_id` is only applied in limited `default`-tenant
paths, which allows different source systems to share local state, runtime
caches, and temporary stores unexpectedly.

This change is needed now because the service must support multiple external
systems on top of the existing tenant boundary and treat `source_id +
tenant_id` as the authoritative runtime scope for all local state access.

## What Changes

- Introduce a formal runtime `scope_id` derived from `X-Source-Id` and
  `X-Tenant-Id`.
- Define `scope_id` as a centrally encoded, reversible, collision-safe runtime
  identifier rather than an ad-hoc string concatenation.
- Require every non-exempt request path and non-HTTP runtime entry point to
  provide `source_id`; requests without `source_id` become invalid.
- Require explicit `source_id` even on callback-style ingress that remains
  auth-exempt; authentication exemption does not imply runtime-scope exemption.
- Upgrade tenant-scoped runtime identities so workspace loading, runner
  execution, provider access, cron execution, and helper-based path resolution
  all use `scope_id` instead of logical `tenant_id`.
- Preserve logical `tenant_id` and raw `source_id` alongside `scope_id` in
  runtime bindings so background flows, tracing, callbacks, and source-aware
  lookups can recover the original scope components.
- **BREAKING** Remove the current `default`-tenant-only source scoping rule and
  replace it with uniform source scoping for every tenant.
- **BREAKING** Remove implicit fallback behavior that treats missing
  `source_id` as `"default"` in isolated runtime flows.
- Convert temporary in-memory stores and request-side control paths to isolate
  by `scope_id`, including session/chat keyed stores that currently depend on
  logical tenant identity or default fallback keys.
- Re-key or namespace process-wide singletons and caches that currently key by
  logical tenant/session only, including approval state, MCP progress tokens,
  runtime registries, and any scope-sensitive in-memory stores.
- Update CLI and internal/callback entry protocols so source identity is
  explicitly supplied whenever tenant-scoped state is touched.
- Treat rollout as a hard namespace cutover for long-lived process caches:
  mixed old/new runtime keys are not supported during one process lifetime.

## Capabilities

### New Capabilities

- `source-scoped-runtime-isolation`: Define `source_id + tenant_id` as the
  single runtime scope for ingress validation, runtime propagation, local path
  resolution, and temporary state isolation.

### Modified Capabilities

None.

## Impact

- Affected backend modules:
  - `src/swe/config/context.py`
  - `src/swe/config/utils.py`
  - `src/swe/app/middleware/tenant_identity.py`
  - `src/swe/app/tenant_context.py`
  - `src/swe/app/multi_agent_manager.py`
  - `src/swe/app/workspace/*`
  - `src/swe/app/runner/runner.py`
  - `src/swe/providers/provider_manager.py`
  - tenant-scoped routers such as `envs`, `settings`, `providers`,
    `agents`, `console`, `skills`, and `workspace`
  - cron, channel callback, internal API, and CLI entry points
- Affected temporary stores:
  - `console_push_store`
  - `post_turn_continuation_store`
  - `suggestions/store`
  - `approvals/service`
  - MCP progress-token / request-side transient state
- API impact:
  - Non-exempt requests become invalid when `X-Source-Id` is missing.
  - CLI and internal service callers must provide explicit source identity.
  - Callback-style HTTP entry points that still bypass auth must provide an
    explicit source transport contract before entering runtime-scoped code.
- Deployment impact:
  - Runtime cache namespaces change; rollout requires process restart or an
    equivalent cache-flush boundary so old tenant-only keys cannot be reused.
- Out of scope:
  - No in-app data migration flow
  - No compatibility fallback to legacy tenant-only runtime behavior
  - No database backfill or historical row migration in this change
