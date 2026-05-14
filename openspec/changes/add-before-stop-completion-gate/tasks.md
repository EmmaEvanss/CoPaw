## 1. Contract And Validation Tests

- [x] 1.1 Add hook model tests proving `BeforeStop` is accepted as a `HookEventName` and appears in prompt-handler blockable events.
- [x] 1.2 Add config resolver tests proving tenant, agent, and skill prompt handlers can be configured under `BeforeStop`.
- [x] 1.3 Add output normalization tests proving `BeforeStop` accepts `allow` and `block(reason)` and rejects unsupported first-version outputs such as `deny`, `ask`, `continue=false`, `permissionDecision`, `updatedInput`, `sessionTitle`, and `additionalContext`.
- [x] 1.4 Add regression tests proving event-aware `BeforeStop` validation does not change existing `Stop`, `PreToolUse`, `UserPromptSubmit`, or non-`BeforeStop` prompt handler semantics.

## 2. Hook Runtime Contract

- [x] 2.1 Add `BeforeStop` to the hook event enum and supported event parsing.
- [x] 2.2 Update prompt handler validation so `BeforeStop` is a valid blockable prompt event.
- [x] 2.3 Add event-aware normalization or validation so `BeforeStop` uses the completion-gate decision contract without changing existing event semantics.
- [x] 2.4 Ensure `BeforeStop` HookContext carries the original prompt and candidate `assistant_response`.
- [x] 2.5 Ensure unsupported `BeforeStop` output follows the individual handler's configured `failPolicy`.

## 3. Runner Completion Gate

- [x] 3.1 Add runner state for `stop_hook_active`, `before_stop_follow_up_turns`, and a bounded `max_before_stop_turns` default.
- [x] 3.2 Refactor runner completion handling into a lifecycle loop that can re-enter agent streaming after `BeforeStop block`.
- [x] 3.3 Emit `BeforeStop` after post-turn validation settles and before the existing `Stop` hook path in each lifecycle loop.
- [x] 3.4 On `BeforeStop allow`, continue through the existing `Stop` hook and normal completion flow.
- [x] 3.5 On `BeforeStop block(reason)`, skip `Stop` for that candidate response and convert the reason into an internal follow-up message for the next lifecycle loop.
- [x] 3.6 Enforce the `BeforeStop` continuation limit by surfacing the latest reason and marking the task incomplete when the budget is exhausted.
- [x] 3.7 Add an aggregate automatic continuation cap that counts both post-turn-validation follow-ups and `BeforeStop` follow-ups for the current request.
- [x] 3.8 Prevent recursive gate execution when `stop_hook_active` is already set, and clear the guard before starting a legitimate gate-driven follow-up turn.
- [x] 3.9 Defer pending validation storage, suggestions, final model-output indexing, trace completion, and QA extraction until the `BeforeStop` gate allows completion or the task is explicitly marked incomplete.

## 4. Runner Tests

- [x] 4.1 Add a query runner test where `BeforeStop allow` emits `Stop` and completes normally.
- [x] 4.2 Add a query runner test where `BeforeStop block` triggers an internal continuation and does not emit `Stop` for the blocked candidate response.
- [x] 4.3 Add a query runner test where repeated `BeforeStop block` results stop at the configured continuation limit and return the latest reason.
- [x] 4.4 Add a query runner test proving `stop_hook_active` prevents recursive `BeforeStop` emission.
- [x] 4.5 Add a query runner test proving existing `Stop` block behavior remains unchanged.
- [x] 4.6 Add a query runner test proving a gate-driven follow-up can legitimately emit `BeforeStop` after the re-entry guard is cleared.
- [x] 4.7 Add a query runner test proving aggregate continuation budget prevents post-turn validation and `BeforeStop` follow-ups from compounding beyond the request cap.
- [x] 4.8 Add a query runner test proving completion side effects do not run for a blocked candidate before `BeforeStop` settles.
- [x] 4.9 Add a query runner test proving budget exhaustion emits an explicit incomplete message after the already streamed candidate response.

## 5. Documentation

- [x] 5.1 Update `docs/hook-runtime.md` with the `BeforeStop` event, timing, supported outputs, and differences from `Stop`.
- [x] 5.2 Document first-version streaming behavior: candidate responses are visible before the completion gate can block stopping.
- [x] 5.3 Add examples for task enforcement and automated test/build/lint completion checks.

## 6. Verification

- [x] 6.1 Run targeted hook runtime model/resolver tests.
- [x] 6.2 Run targeted runner hook runtime and post-turn validation tests.
- [x] 6.3 Run `venv/bin/python -m pytest tests/unit/agents/hook_runtime tests/unit/app/test_runner_hook_runtime.py tests/unit/app/test_runner_post_turn_validation.py`.
- [x] 6.4 Run `openspec validate add-before-stop-completion-gate --strict`.
- [x] 6.5 Run `gitnexus_detect_changes()` before any commit to verify affected execution flows match the expected hook runtime and runner scope.
