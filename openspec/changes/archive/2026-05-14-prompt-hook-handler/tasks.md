## 1. Config Models and Validation

- [x] 1.1 Add `PromptHookHandlerConfig` with `type="prompt"` and non-empty business-rules validation.
- [x] 1.2 Extend `HookHandlerConfig` discriminated union to include prompt handlers.
- [x] 1.3 Add blockable-event validation so prompt handlers are accepted only under `SessionStart`, `UserPromptSubmit`, `PreToolUse`, and `Stop`.
- [x] 1.4 Reject handler-level model/provider routing fields and unknown prompt handler fields instead of silently ignoring them.
- [x] 1.5 Make prompt handlers default to `failPolicy="block"` while preserving existing command/http defaults.
- [x] 1.6 Override prompt handler target identity so resolver dedupe includes a stable digest of the business-rules prompt.
- [x] 1.7 Add config model tests for tenant and agent prompt handler acceptance, invalid event rejection, rejected override fields, default fail policy, and prompt dedupe identity.

## 2. Prompt Execution

- [x] 2.1 Add prompt-handler execution branch in `execute_handler`.
- [x] 2.2 Build the final model input from platform scaffold, handler business rules, redacted serialized HookContext JSON, and structured output constraints.
- [x] 2.3 Bind tenant/user/source/workspace context from `HookContext` before model creation and invocation.
- [x] 2.4 Call the current effective tenant active model through existing model factory/provider context, preserving `context.agent_id` for runtime configs.
- [x] 2.5 Apply hook payload redaction before serializing HookContext into the model input.
- [x] 2.6 Include the finalized assistant response in `Stop` prompt hook context before executing Stop prompt handlers.
- [x] 2.7 Enforce prompt handler timeout across model creation, request dispatch, response extraction, and streaming cleanup.
- [x] 2.8 Extract model response text from normal and streaming model responses, including tests for delta-style and cumulative streaming chunks.
- [x] 2.9 Map model creation/call failures and extraction failures through existing fail-policy behavior.

## 3. Judgment Output Parsing

- [x] 3.1 Implement strict prompt judgment parser for JSON object output with exactly `decision` and non-empty string `reason`.
- [x] 3.2 Map `allow`, `deny`, and `block` to `HookDecision.ALLOW`, `HookDecision.DENY`, and `HookDecision.BLOCK`.
- [x] 3.3 Reject unsupported full HookOutput fields such as `hookSpecificOutput`, `updatedInput`, `additionalContext`, `sessionTitle`, `systemMessage`, and `continue`.
- [x] 3.4 Reject any extra fields, empty reasons, and oversized reasons.
- [x] 3.5 Add tests for valid decisions, malformed JSON, missing fields, unsupported decisions, non-string reasons, empty reasons, extra fields, unsupported fields, and oversized reasons.

## 4. Skill Hook Loading

- [x] 4.1 Update skill hook loader normalization to allow prompt handlers from `hooks/hooks.json`.
- [x] 4.2 Preserve existing skill id namespacing and session-scoped loading behavior for prompt handlers.
- [x] 4.3 Ensure skill prompt handlers inherit the same prompt-specific validation as tenant and agent prompt handlers.
- [x] 4.4 Add skill loader tests for accepted skill prompt hooks, invalid prompt hook event placement, rejected override fields, and namespaced prompt dedupe identity.

## 5. Runtime Integration and Merge Behavior

- [x] 5.1 Verify prompt handlers run in the existing concurrent event plan with command and HTTP handlers.
- [x] 5.2 Verify prompt handler decisions participate in existing deterministic merge priority.
- [x] 5.3 Verify `once`, `if`, `timeout`, `statusMessage`, and `failPolicy` behavior works for prompt handlers.
- [x] 5.4 Verify prompt handler `allow` does not bypass existing tool guard checks outside the hook runtime merge.
- [x] 5.5 Add regression tests showing existing command and HTTP handler behavior remains unchanged.

## 6. Documentation and Verification

- [x] 6.1 Update `docs/hook-runtime.md` with prompt handler configuration, event limits, model selection rules, prompt assembly order, output contract, fail-closed default, and skill-owned prompt governance.
- [x] 6.2 Run focused unit tests for hook runtime, config models, and skill hook loader.
- [x] 6.3 Run OpenSpec validation/status checks for `prompt-hook-handler`.
