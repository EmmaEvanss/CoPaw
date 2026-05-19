## 1. Scope Model And Ingress Contract

- [x] 1.1 Define a versioned, reversible, collision-safe `scope_id` format and central encode/decode helpers in the tenant/source context layer.
- [x] 1.2 Add central validation/normalization rules for raw `tenant_id` and `source_id`, and reject malformed source values before scope resolution.
- [x] 1.3 Update tenant identity middleware to require `X-Source-Id` on all non-exempt tenant-scoped HTTP routes.
- [x] 1.4 Add request-state fields and context binding for logical `tenant_id`, `source_id`, and resolved `scope_id`.
- [x] 1.5 Split auth/workspace exemption handling from source-scope exemption handling so callback-style routes can stay auth-exempt without becoming source-optional.
- [x] 1.6 Remove implicit `"default"` source fallback from scoped ingress validation paths.

## 2. Runtime Scope Propagation

- [x] 2.1 Upgrade `MultiAgentManager`, `Workspace`, and `AgentRunner` runtime tenant semantics so their internal tenant-scoped identity is `scope_id`.
- [x] 2.2 Refactor tenant-scoped config and path helpers to resolve local state strictly by `scope_id`.
- [x] 2.3 Update provider storage and provider-manager runtime caching to isolate by `scope_id` for every tenant.
- [x] 2.4 Update tenant workspace/bootstrap utilities to treat source scoping as uniform runtime behavior rather than a `default`-tenant special case.
- [x] 2.5 Upgrade tenant/source binding helpers used by channels, cron, callbacks, and background tasks to carry logical `tenant_id`, raw `source_id`, and resolved `scope_id` together instead of only a runtime tenant string.
- [x] 2.6 Audit all `get_current_effective_tenant_id`, `resolve_effective_tenant_id`, and `tenant_id or "default"` call sites, replacing legacy semantics rather than layering new helpers on top.

## 3. Router And Control-Plane Hardening

- [x] 3.1 Update tenant-scoped routers such as `settings`, `envs`, `providers`, `agents`, `skills`, `workspace`, and `console` to use request `scope_id` for all local-state access.
- [x] 3.2 Update reload and control helpers so background reloads and daemon control target runtimes by `scope_id`.
- [x] 3.3 Remove helper call sites that explicitly pass logical `tenant_id` into scoped path/config resolution.
- [x] 3.4 Expand the router audit to other local-state or control-plane endpoints that still use logical tenant fallbacks, including `mcp`, `messages`, `dream_logs`, cron auth/config, and any callback ingress that constructs runtime requests.
- [x] 3.5 Re-key process-wide approval/control state such as `ApprovalService` lookups and MCP progress-token namespaces so same-session requests from different scopes cannot collide.

## 4. Temporary Stores And Background Flows

- [x] 4.1 Re-key console push, post-turn continuation, and other tenant-scoped temporary stores by `scope_id`.
- [x] 4.2 Redesign suggestions and QA-content stores to use scope-aware composite keys instead of bare `session_id` or `chat_id`.
- [x] 4.3 Ensure runner background tasks pass runtime `scope_id` when storing suggestions, validation state, and other asynchronous artifacts.
- [x] 4.4 Update cron execution and other background write paths to preserve originating `scope_id`.
- [x] 4.5 Re-key or namespace all process-wide singleton caches that survive across requests, including `MultiAgentManager`, `ProviderManager`, and other scope-sensitive registries.
- [x] 4.6 Define rollout behavior for long-lived caches: fresh-process requirement or explicit cache flush before serving scope-aware traffic.

## 5. Non-HTTP Entry Protocols

- [x] 5.1 Extend CLI request headers to send `X-Source-Id` alongside `X-Tenant-Id` for tenant-scoped operations.
- [x] 5.2 Update internal APIs that target tenant-scoped runtimes to require and propagate `source_id`.
- [x] 5.3 Update channel callback flows, including Zhaohu, to attach explicit `source_id` before entering runtime-scoped execution.
- [x] 5.4 Audit cron/job payload construction so source identity is always persisted and restored for scoped execution.
- [x] 5.5 Require callback/background protocols that are auth-exempt at ingress to carry explicit source identity before any scoped workspace/provider/runtime access.

## 6. Verification

- [x] 6.1 Add unit tests for scope resolution, missing-source rejection, and scope-aware helper behavior.
- [x] 6.2 Add regression tests for router flows that previously used logical `tenant_id` directly, including `settings`, `envs`, `providers`, and `console`.
- [x] 6.3 Add tests proving temporary stores remain isolated when two scopes share the same `session_id` or `chat_id`.
- [x] 6.4 Add tests for CLI/internal/callback/cron source propagation and invalid-source rejection.
- [x] 6.5 Add tests for auth-exempt callback ingress, approval flows, and MCP progress reporting when two scopes share the same session/chat identifiers.
- [x] 6.6 Add deployment-safety coverage proving old tenant-only caches are not reused after the scope cutover.
- [x] 6.7 Run targeted pytest coverage for tenant/source isolation paths and run `openspec validate source-scoped-tenant-isolation --strict`.
