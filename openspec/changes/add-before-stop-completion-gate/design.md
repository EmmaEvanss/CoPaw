## Context

The hook runtime currently emits `Stop` after the agent has produced the final
assistant response for a turn. `Stop` is useful for final audit, logging, and
blocking downstream completion work, but it runs too late to enforce task
completion by driving the agent to continue.

Swe already has a post-turn validation loop that can ask the agent to continue
when a model-based completion check marks the task incomplete. The requested
`BeforeStop` event should sit in the same runner area, but it must remain a
hook-runtime capability so tenants, agents, and skills can define policy-driven
completion gates such as test, build, lint, or custom readiness checks.

The first version keeps the existing streaming behavior: the candidate
assistant response is already visible before `BeforeStop` runs. If the gate
blocks, the runner appends an internal follow-up and the agent continues.

Current runner control flow matters for this change: agent streaming and
post-turn validation run inside `_stream_agent_turns`, while `Stop` is emitted
after that loop. `BeforeStop block` therefore cannot be implemented as a small
addition inside the existing stop hook helper. It must participate in a wider
completion lifecycle loop that can re-enter agent streaming before any
post-completion side effects run.

## Goals / Non-Goals

**Goals:**

- Add `BeforeStop` as a lifecycle event before `Stop`.
- Support a completion-gate outcome contract of `allow` or `block(reason)`.
- Convert `block(reason)` into an internal follow-up instruction that continues
  the agent while budget remains.
- Run `BeforeStop` inside a full completion lifecycle loop so a block can
  safely re-enter agent streaming in the same request.
- Enforce the `BeforeStop` output contract with event-aware normalization or
  validation without weakening existing `Stop` or prompt-handler semantics.
- Prevent recursive stop-hook execution with a runner-level
  `stop_hook_active` guard.
- Bound automatic continuation so repeatedly blocking gates cannot loop
  forever.
- Surface an explicit incomplete message when the `BeforeStop` budget is
  exhausted.
- Keep existing `Stop` behavior unchanged.

**Non-Goals:**

- Do not buffer or hide candidate assistant responses in the first version.
- Do not add `ask`, `deny`, `updatedInput`, `sessionTitle`, or
  `additionalContext` semantics for `BeforeStop`.
- Do not replace the existing post-turn validation feature.
- Do not add frontend UI or API changes for this first implementation.

## Decisions

### Decision: Model BeforeStop as a new hook event

Add `HookEventName.BEFORE_STOP = "BeforeStop"` instead of overloading `Stop`.
The two events have different meanings:

- `BeforeStop` asks whether the agent may stop.
- `Stop` runs after stopping is allowed and handles final audit or cleanup.

Alternative considered: extend `Stop` so `block` means continue. This was
rejected because existing `Stop` already treats blocking as a final blocked
completion and changing that would be surprising for current hook users.

### Decision: Use a two-state completion-gate contract

For `BeforeStop`, the runtime should only honor:

- `decision="allow"` with a non-empty reason
- `decision="block"` with a non-empty reason

`block` means "do not stop yet" for this event. It does not mean "deny the
user request" or "end with an error". The runner turns the reason into an
internal follow-up instruction, such as:

```text
BeforeStop completion gate blocked stopping: <reason>
Continue working until the gate can allow completion.
```

Alternative considered: support `deny` and `ask`. This was rejected for the
first version because approval and final denial are not needed for task
enforcement and would blur the gate semantics.

### Decision: Run BeforeStop after post-turn validation

The runner should wrap the existing agent streaming and post-turn validation
work in a completion lifecycle loop. The loop for each candidate response is:

```text
agent candidate response
  -> post-turn validation auto-continuation, if enabled
  -> BeforeStop completion gate
     -> allow: Stop -> normal completion
     -> block with budget: hidden internal follow-up -> next lifecycle loop
     -> block without budget: visible incomplete message -> incomplete
```

This prevents expensive checks such as tests or builds from running before the
existing semantic validation decides whether the answer is obviously
incomplete.

This also preserves completion side-effect ordering. The runner must not store
pending validation continuations, generate suggestions, index final model
output, or mark the trace completed until the `BeforeStop` gate has settled
with `allow` or the continuation budget has been exhausted.

Alternative considered: run `BeforeStop` before post-turn validation. This was
rejected because tenant or skill checks may be costly and should happen after
the built-in completion loop has had a chance to finish the task.

Alternative considered: emit `BeforeStop` only inside the existing Stop helper.
This was rejected because the current Stop helper runs after the agent streaming
loop has already ended, so a block result would not have a clean path to
continue the same request.

### Decision: Keep BeforeStop output validation event-aware

Existing prompt handlers on other events can return `deny`, and existing hook
runtime output normalization preserves several event-specific fields. The
`BeforeStop` contract is narrower. The implementation should either pass the
event into output normalization or apply a `BeforeStop`-specific validation step
after normal handler execution.

For `BeforeStop`, unsupported output such as `deny`, `ask`,
`permissionDecision`, `continue=false`, `updatedInput`, `sessionTitle`, or
`additionalContext` must be treated as invalid for this event and then follow
the handler's configured failure policy. This must not change the accepted
outputs for `Stop`, `PreToolUse`, `UserPromptSubmit`, or prompt handlers on
other events.

### Decision: Keep candidate responses streaming in version one

Do not buffer the final assistant response before `BeforeStop`. The first
version matches current runner behavior and the existing post-turn validation
model: users may see a candidate answer, then see continuation output if the
gate blocks stopping.

Alternative considered: buffer the final assistant message until the gate
allows completion. This was rejected for the first version because it would
require stream-boundary changes and broader SSE/console testing.

### Decision: Add re-entry and budget protection

Add a runner/session-level `stop_hook_active` flag. If the stop hook path is
already active, the runner must not recursively trigger `BeforeStop` again.
This prevents nested hook execution when a gate-driven continuation itself
reaches a stop boundary.

The guard is scoped only to the currently executing stop/gate path. It must be
cleared before a gate-driven follow-up starts its next agent turn. Otherwise a
legitimate later stop boundary would incorrectly skip `BeforeStop`.

Also add an automatic continuation counter for `BeforeStop` so repeated
`block` results stop after a configured limit. When the limit is reached, the
runner should surface the latest reason in a final assistant message and mark
the task incomplete.

Use a hook-runtime-specific `max_before_stop_turns` value with conservative
fallback `2`. In addition, protect the request with an aggregate automatic
continuation cap that counts both post-turn-validation follow-ups and
`BeforeStop` follow-ups, so two independent continuation systems cannot combine
into an unexpectedly long request.

Alternative considered: rely only on `once=true` hook configuration. This was
rejected because completion gates should be safe by default even when
configuration is incomplete or multiple handlers participate.

## Risks / Trade-offs

- Candidate responses remain visible before the gate finishes -> document this
  clearly and keep buffering out of scope for the first version.
- A poorly written gate may keep blocking -> enforce automatic continuation
  limits, an aggregate continuation cap, and surface the latest reason.
- Running tests/builds inside hooks can be slow -> honor existing handler
  timeouts and fail policies; recommend scoped checks in documentation.
- `block` has different runtime meaning on `BeforeStop` than on final `Stop`
  -> keep this event-specific behavior explicit in docs and tests.
- Event-aware output validation adds a new branch in hook runtime behavior ->
  cover it with tests proving existing `Stop`, `PreToolUse`, and prompt-handler
  `deny` semantics remain unchanged.

## Migration Plan

1. Add the new event enum and accept `BeforeStop` in hook configuration.
2. Add event-aware output validation for the `BeforeStop` completion-gate
   contract.
3. Refactor runner completion handling into a lifecycle loop that can continue
   after `BeforeStop block`.
4. Add continuation handling for `block(reason)` with re-entry, per-gate
   budget, aggregate budget, and explicit incomplete output.
5. Update prompt handler validation to allow `BeforeStop`.
6. Add focused unit tests for allow, block continuation, max continuation,
   aggregate budget, re-entry behavior, and unchanged `Stop` semantics.
7. Update hook runtime documentation.

Rollback is straightforward: remove `BeforeStop` configuration or disable the
new event path. Existing `Stop` and tool hook behavior remains compatible.
