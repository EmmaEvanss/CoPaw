## Context

The unified hook runtime already resolves tenant, agent, and session-loaded skill hook sources at event boundaries, then executes matched handlers concurrently and merges their results deterministically. The current handler union supports `command` and `http`; both externalize policy logic outside the main runtime.

The new `prompt` handler should let hook authors express policy rules in hook configuration and let the current tenant's configured model judge the event. This must preserve tenant provider isolation, avoid creating a second model selection surface, and avoid letting prompt hooks mutate event context in the MVP.

## Goals / Non-Goals

**Goals:**

- Add a `prompt` handler type to the existing hook handler union.
- Execute prompt handlers through the current effective tenant's active model.
- Treat the configured `prompt` field as business rules, not as the final model prompt.
- Build the final model input in a fixed order: platform policy scaffold, business rules, redacted runtime HookContext JSON, structured output constraints.
- Accept only judgment-style output: `allow`, `deny`, or `block` with a non-empty string reason and no extra fields.
- Allow prompt handlers from tenant, agent, and skill hook sources.
- Restrict prompt handlers to events where a blocking decision can still be applied.
- Reuse existing concurrent execution, timeout, once, if-condition, fail policy, and merge behavior.

**Non-Goals:**

- Allow handler-level provider or model selection.
- Support `ask`, `defer`, `updatedInput`, `additionalContext`, `sessionTitle`, `systemMessage`, or `continue=false` from prompt handler output in the MVP.
- Add prompt file references or template expression support.
- Add a frontend UI for authoring or approving prompt hook rules.
- Support prompt handlers on post-tool events that cannot roll back completed side effects.

## Decisions

### Decision 1: Add `PromptHookHandlerConfig` as a first-class handler type

Extend the existing discriminated union with `type: "prompt"` and a required non-empty `prompt` field. The class should inherit shared handler fields from `BaseHookHandlerConfig` so prompt handlers participate in existing resolver, overlay, once, fail-policy, and deduplication behavior.

Prompt handlers need prompt-specific hardening on top of the shared base fields:

- Reject unknown handler fields rather than silently ignoring them.
- Reject handler-level `model`, `provider`, provider id, base URL, prompt-file, template, or similar routing/template override fields.
- Enforce a bounded business-rules length so a hook config cannot create unbounded model input.
- Override `target_identity()` to include a stable digest of the `prompt` text; otherwise two prompt handlers with the same id, event, group, and type would collapse under the existing dedupe key even when their rules differ.
- Use `failPolicy: "block"` as the prompt-handler default. Prompt hooks are policy gates, not passive audit sinks, and model/runtime failures should fail closed unless the hook author explicitly opts into `failPolicy: "allow"`.

Alternative considered: model prompt hooks as a special HTTP-like adapter. That would hide the type-specific validation and make skill-owned prompt governance harder to explain.

### Decision 2: Fixed tenant active model, no handler-level model field

Prompt handlers must use `create_model_and_formatter(agent_id=context.agent_id or None)` under a tenant context explicitly bound from the `HookContext` being executed. The executor should not rely on whatever ambient context happens to be active when the handler branch runs; it must bind `tenant_id`, `user_id`, `source_id`, and `workspace_dir` from the hook context before model creation and model invocation.

This still resolves provider storage and active model through tenant-aware provider management, while preserving agent-scoped retry/rate-limit configuration. The handler config must not include a model or provider override.

Alternative considered: allow `model` in handler config, matching the broader Claude-style shape in `hool_design.txt`. That creates a second model routing policy and makes skill-owned hooks able to influence tenant spend and provider selection without explicit tenant configuration.

### Decision 3: Treat `prompt` as business rules inside a platform scaffold

The final model input is assembled by the runtime in this order:

```text
platform fixed scaffold
hook business rules from handler.prompt
runtime HookContext JSON
structured output constraints
```

The platform scaffold must state that HookContext values are data, not instructions, and that the model must not execute tools, request more information, or output prose outside the required JSON object. The runtime context should be serialized with stable JSON formatting from a prompt-safe copy of `HookContext.to_handler_payload()`. That copy should apply the existing hook payload redaction before serialization so obvious secret-bearing fields are not sent to the tenant model by default.

For `Stop`, the prompt-safe context must include the assistant response being finalized. Without that field, a prompt handler on `Stop` can only judge the original user prompt and metadata, which makes final-answer policy checks blind. If the runtime cannot provide the assistant response for `Stop`, prompt handlers should not be accepted on `Stop` for that execution path.

Alternative considered: pass `handler.prompt` directly to the model after replacing a `{{context_json}}` placeholder. That is more flexible but puts policy authors in charge of instruction ordering and makes prompt injection defenses inconsistent across handlers.

### Decision 4: Judgment-only output contract

Prompt handler model output is valid only when it parses as a JSON object with:

```json
{"decision": "allow|deny|block", "reason": "..."}
```

The executor maps `allow` to `HookDecision.ALLOW`, `deny` to `HookDecision.DENY`, and `block` to `HookDecision.BLOCK`. Parsing must use a prompt-specific schema rather than the existing permissive `HookOutput` parser. The object must contain exactly the `decision` and `reason` keys, the decision must be lower-case exactly, and the reason must be a non-empty string within a bounded length. Unknown keys and full-hook fields such as `hookSpecificOutput`, `continue`, `updatedInput`, `additionalContext`, `sessionTitle`, and `systemMessage` are invalid.

Invalid JSON, missing fields, unsupported decisions, non-string or empty reasons, oversized reasons, extra fields, streaming extraction failures, and empty output are handler failures.

Alternative considered: reuse full `HookOutput` parsing. That would expose `updatedInput`, `additionalContext`, `sessionTitle`, and `continue=false`, which is too broad for an MVP whose purpose is policy judgment.

### Decision 5: Restrict prompt handlers to blockable events

Prompt handlers are valid only on `SessionStart`, `UserPromptSubmit`, `PreToolUse`, and `Stop`. Configuration containing a prompt handler under `PostToolUse` or `PostToolUseFailure` should fail validation rather than silently produce confusing behavior.

Alternative considered: execute prompt handlers on all events and ignore blocking decisions for non-blockable events. That would make configuration look successful while hiding the most important outcome.

### Decision 6: Allow skill-owned prompt handlers

Skill `hooks/hooks.json` may declare prompt handlers. They are namespaced and session-scoped like other skill hooks, but still execute through the current effective tenant active model. Skill prompt handlers do not need HTTP endpoint approval or command path normalization because they do not call external URLs or local scripts.

Alternative considered: limit prompt handlers to tenant and agent config. That is safer for spending control, but it prevents skills from packaging lightweight policy rules. The model isolation rule keeps the first version within the tenant's existing provider boundary.

### Decision 7: Keep existing concurrent execution and deterministic merge

Prompt handlers should run alongside command and HTTP handlers in the existing event plan concurrency model. The executor still applies per-handler timeout and returns normalized `HookHandlerResult` objects; merge order remains based on configured handler order, not completion order.

Alternative considered: serialize prompt handlers to reduce concurrent LLM calls. That would be simpler for capacity control but would create a handler-type-specific execution model and increase event latency. Existing model rate limiting should remain the primary concurrency control.

### Decision 8: Bound the whole model call, including streaming cleanup

The prompt handler timeout must cover model creation, request dispatch, non-streaming response extraction, streaming response consumption, and stream close/cancellation cleanup. A timeout around only `model(messages)` is insufficient because a streaming model may return an async iterator quickly and then stall while emitting text.

The response extractor should handle both normal responses and streaming responses, ignore tool-call blocks, extract only text content, and close an async stream when cancellation or timeout interrupts consumption.

## Risks / Trade-offs

- Prompt injection through HookContext text -> The platform scaffold must explicitly classify all HookContext values as data, keep output constraints outside business rules, and serialize context as redacted JSON data.
- Unexpected model output shape -> Strict prompt-specific JSON parsing and judgment-only validation turn malformed output into handler failure governed by `failPolicy`.
- Prompt hook latency increases event latency -> Per-handler `timeout` and existing model rate limiting bound the effect.
- Skill-owned prompt hooks can consume tenant model quota and influence blocking decisions -> They still use the tenant active model and remain visible as loaded skill hook sources; tenants can disable skills or hook handlers through existing governance paths. Documentation and tests must make this governance boundary explicit, and prompt handlers should default to fail-closed behavior.
- Active model missing or misconfigured -> Treat as handler failure and apply `failPolicy`.
- Blocking prompt hooks on `Stop` cannot produce an alternate agent answer by themselves -> Existing Stop blocking behavior returns the blocking reason and prevents normal turn completion.
- Stop prompt checks are blind without assistant output -> Include the assistant response in Stop hook context before allowing prompt handlers to run on Stop.

## Migration Plan

- Additive configuration change only; existing `command` and `http` hook configs continue to parse and execute unchanged.
- Existing hook runtime behavior remains unchanged when no `prompt` handlers are configured.
- Rollback is removing `prompt` handler configs and reverting the additive handler implementation.

## Open Questions

None for the MVP.
