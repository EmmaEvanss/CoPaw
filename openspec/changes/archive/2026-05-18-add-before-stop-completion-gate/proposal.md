## Why

Agents can currently stop after producing a final-looking answer even when
required completion checks have not run or the task is only partially done.
The existing `Stop` hook runs after the answer is finalized, so it can audit or
block the end of the turn but cannot act as a completion gate that drives the
agent to continue.

## What Changes

- Add a `BeforeStop` hook event that runs after a candidate assistant response
  is produced and before `Stop` or normal turn completion.
- Treat `BeforeStop` as a completion gate with two supported outcomes:
  `allow` and `block(reason)`.
- When `BeforeStop` blocks, convert the block reason into an internal follow-up
  instruction and continue the agent within the same request while automatic
  continuation budget remains.
- Keep first-version streaming behavior unchanged: the candidate assistant
  response is already visible to the user before `BeforeStop` runs.
- Add runner-level `stop_hook_active` re-entry protection so completion-gate
  continuations cannot recursively trigger the same stop hook path.
- Add bounded automatic continuation handling so repeatedly blocking gates
  surface the latest reason and mark the task incomplete instead of looping
  indefinitely.
- Keep existing `Stop` semantics for final audit, additional context, and
  final block behavior.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `unified-agent-hook-protocol`: Add the `BeforeStop` lifecycle event and its
  completion-gate semantics.
- `prompt-hook-handler`: Allow prompt handlers on `BeforeStop` and constrain
  prompt judgment output to the same allow/block completion-gate contract.

## Impact

- Affected backend code:
  - `src/swe/agents/hook_runtime/models.py`
  - `src/swe/agents/hook_runtime/output.py`
  - `src/swe/agents/hook_runtime/merge.py`
  - `src/swe/app/runner/runner.py`
  - hook runtime and runner tests under `tests/unit/agents/` and
    `tests/unit/app/`
- Documentation impact:
  - `docs/hook-runtime.md` should describe `BeforeStop`, its two-state output,
    and how it differs from `Stop`.
- No breaking change is intended for existing hook configurations.
- No frontend or API contract changes are required for the first version.
