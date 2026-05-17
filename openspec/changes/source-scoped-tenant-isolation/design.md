## Context

The current system already tracks both logical tenant identity and source
identity, but they are not treated as a single first-class runtime scope.
Today:

- HTTP middleware records `tenant_id` and `source_id`
- some runtime helpers resolve an "effective tenant" only for the `default`
  tenant
- many routers and temporary stores still use logical `tenant_id` directly
- several non-HTTP entry points never provide source identity at all

This creates a split-brain model where some local state is source-scoped while
other state is only tenant-scoped or falls back to `"default"`.

The requested rollout is a hard cutover:

- existing data is assumed to have been migrated outside the application
- missing `source_id` is invalid rather than tolerated
- database history and backfill are out of scope

## Goals / Non-Goals

**Goals:**

- Define one authoritative runtime `scope_id = encode(source_id, tenant_id)`.
- Validate and normalize `source_id` before scope resolution so runtime scope
  keys are safe for headers, logs, directory names, and cache keys.
- Make every local-state read/write path depend on `scope_id`.
- Keep logical `tenant_id` available for business-facing identity while
  upgrading runtime-scoped `tenant_id` parameters to mean `scope_id`.
- Enforce `X-Source-Id` on all non-exempt tenant-scoped requests.
- Ensure non-HTTP entry points propagate source identity before they touch
  scoped runtime state.
- Remove implicit `"default"` source fallback from isolated runtime paths.
- Re-key temporary stores so source-separated sessions/chats cannot collide.
- Ensure process-wide singletons, registries, and transient control stores use
  scope-aware namespaces and cannot reuse tenant-only cache entries.

**Non-Goals:**

- No compatibility mode that preserves the old `default_{source}` special case.
- No application-managed migration or legacy directory probing.
- No database schema migration or historical row rewrite.
- No redesign of user-facing logical tenant semantics.

## Decisions

### Decision: Separate logical tenant identity from runtime scope identity

The system will explicitly distinguish:

- `tenant_id`: logical tenant from `X-Tenant-Id`
- `source_id`: external source from `X-Source-Id`
- `scope_id`: encoded runtime identity used for local state

Request state will carry all three values. Routers may still read logical
tenant for business behavior, but any filesystem, provider, workspace, or
temporary-store isolation must use `scope_id`.

Alternative considered: continue reusing `effective_tenant_id` with expanded
logic. This was rejected because the current name carries `default`-tenant
legacy semantics and invites continued mixing of logical tenant and runtime
scope concepts.

### Decision: Make `scope_id` versioned, opaque, and centrally validated

The system will define one central encoder/decoder for `scope_id`. The encoded
format must be:

- reversible back to `(source_id, tenant_id)`
- safe for directory names and cache keys
- collision-resistant against existing tenant names and old
  `default_{source}`-style paths
- versioned so future format changes can be introduced without silent overlap

The same module will validate raw `tenant_id` and `source_id` before scope
resolution. Missing or malformed `source_id` is invalid for scoped entry
points; unvalidated source strings must never reach filesystem or cache keys.

Alternative considered: concatenate `tenant_id` and `source_id` directly using
separators such as `:` or `_`. This was rejected because it risks collisions
with existing tenant names, ambiguous decoding, and unsafe path/key material.

### Decision: Upgrade runtime-internal tenant parameters to scope semantics

Existing runtime objects already pass `tenant_id` through a central chain:

`MultiAgentManager -> Workspace -> AgentRunner -> provider/config/runtime helpers`

Instead of introducing parallel `scope_id` parameters everywhere, this change
will upgrade runtime-internal `tenant_id` parameters to mean `scope_id` where
the code path only needs the runtime isolation key. However, runtime context
binding helpers and persisted background payloads must carry the full trio:
logical `tenant_id`, raw `source_id`, and resolved `scope_id`.

This prevents a false simplification where runtime code only receives the
opaque scope string and then loses the source information needed by tracing,
callback protocols, source-aware DB lookups, or downstream header transport.
Logical tenant identity remains separate at ingress and business-facing router
layers.

Alternative considered: add new `scope_id` parameters everywhere and preserve
runtime `tenant_id` as logical tenant. This was rejected because it would keep
two competing internal identities alive for too long and make call-site review
error-prone.

### Decision: Require explicit source identity on all non-exempt scoped entry points

Non-exempt HTTP routes must reject requests without `X-Source-Id`. The same
requirement applies to non-HTTP scoped entry points:

- CLI HTTP callers
- cron job creation/execution
- internal reload and control APIs
- channel callbacks and background continuations

Routes that remain auth-exempt, such as channel callbacks, still need a source
contract before they touch scoped runtime state. Source enforcement therefore
cannot rely only on the current tenant-auth exemption list.

Alternative considered: allow source omission and derive `"default"`. This was
rejected because it recreates the same ambiguity that caused the current split
scope behavior.

### Decision: Re-key stores by scope-aware composite keys

Stores keyed only by `session_id` or `chat_id` are not safe in a
source-scoped model, even if each entry carries a tenant field. Temporary
stores must be keyed by `(scope_id, session_id)` or `(scope_id, chat_id)`, or
an equivalent composite scope-aware key.

Alternative considered: keep existing top-level keys and validate scope only on
read. This was rejected because it allows accidental overwrite or eviction
across scopes that share the same session/chat identifier.

### Decision: Expand transient-state hardening to all process-wide control stores

Scope hardening will cover not only the three user-facing temporary stores but
also any process-wide singleton or transient control structure whose lookup key
can collide across scopes. This includes approval state keyed by `session_id`,
MCP progress-token namespaces, and any runtime registry or queue keyed only by
logical tenant, chat, or session identifiers.

Alternative considered: only re-key the currently known user-facing stores and
leave other singletons unchanged. This was rejected because it preserves
cross-scope overwrite and lookup ambiguity in less-visible control paths.

### Decision: Treat rollout as a namespace cutover for long-lived caches

`scope_id` changes not only filesystem paths but also runtime cache keys.
Long-lived process caches such as `MultiAgentManager`, `ProviderManager`, and
other scope-sensitive registries must not serve mixed tenant-only and
scope-aware entries in one process lifetime. Rollout must therefore either:

- start from a fresh process boundary, or
- clear all scope-sensitive singletons before serving scoped traffic

Alternative considered: allow mixed old/new cache entries until they naturally
expire. This was rejected because it can silently reuse tenant-only instances
for requests that now require source separation.

### Decision: Keep database mappings out of this change

Filesystem/runtime hardening is the only goal here. Database views that store
logical tenant/source associations may continue to use logical identifiers until
a later change addresses them explicitly.

Alternative considered: expand the proposal to include DB backfill and schema
changes. This was rejected to keep the rollout bounded and aligned with the
assumption that migrated local state already exists.

## Risks / Trade-offs

- Missing source propagation in background or callback flows could silently
  route work into the wrong scope if not fully covered by tests
  -> Add ingress-specific tests for HTTP, CLI, cron, internal API, and channel
     callbacks before enabling the hard cutover.
- Auth-exempt callback routes may bypass the generic source-required gate even
  though they enter scoped runtime code
  -> Split auth exemption from scope exemption and add callback-specific source
     validation tests.
- Upgrading runtime `tenant_id` semantics may confuse existing code readers
  -> Add explicit naming/documentation around logical `tenant_id` vs runtime
     `scope_id`, and update high-touch helpers first.
- Runtime binders that only carry `tenant_id`/workspace today can lose the raw
  `source_id` required by tracing, callback protocols, and source-aware stores
  -> Upgrade binders and background payloads to transport full runtime scope
     context, not only the encoded scope key.
- Stores with implicit `"default"` fallback may continue leaking across scopes
  if not fully re-keyed
  -> Audit every tenant-scoped temporary store and remove fallback semantics
     during the same change.
- Process-wide singletons may retain stale tenant-only cache entries across
  deployment
  -> Namespace runtime caches by the new `scope_id` format and require restart
     or explicit cache flush at rollout.
- Some routers currently pass logical `tenant_id` into helper APIs that infer
  scope only when no explicit argument is present
  -> Update call sites, not just helpers, and add regression tests for
     settings/envs/providers/console flows.

## Migration Plan

1. Land the runtime scope model and helper changes behind the hard-cutover
   assumption that migrated local data already exists.
2. Update HTTP ingress validation to require `X-Source-Id` on all non-exempt
   tenant-scoped routes, and add explicit source enforcement for callback-style
   routes that remain auth-exempt.
3. Update runtime propagation and helper call sites so workspace/provider/config
   resolution always uses `scope_id` while preserving logical tenant and raw
   source in runtime bindings.
4. Update temporary stores, control-plane singletons, and background flows to
   use scope-aware keys or versioned namespaces.
5. Update CLI, internal APIs, cron, and callback paths to pass explicit source
   identity.
6. Restart or flush scope-sensitive runtime caches at rollout, then run
   targeted regression tests covering cross-source isolation and missing source
   rejection.

Rollback strategy:

- Revert the runtime scope refactor before rollout if validation fails.
- No partial compatibility mode is planned for this change.

## Open Questions

- What encoded format should `scope_id` use so it is reversible and safe for
  directory names without colliding with existing tenant naming rules?
- Which exempt routes, if any, should remain source-optional beyond health,
  docs, and authentication/bootstrap endpoints?
- Should router helper APIs be renamed from `get_tenant_*` to `get_scope_*`
  immediately, or should semantic upgrades happen first with naming cleanup in
  a follow-up?
