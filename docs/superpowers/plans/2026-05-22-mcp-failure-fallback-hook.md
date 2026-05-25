# MCP Failure Fallback Hook Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a skill-owned `PostToolUseFailure` hook demo that injects a unified fallback prompt into `additionalContext` whenever a tool call fails.

**Architecture:** The implementation stays entirely at the skill layer under `docs/hook/` and does not modify the shared hook runtime. A small command hook script reads the failure `HookContext` JSON from stdin, emits `hookSpecificOutput.additionalContext` when `error` is present, and is exercised by a dedicated unit test file that also verifies the skill hook loader can load the demo config from disk.

**Tech Stack:** Python, pytest, skill-level hook runtime config (`hooks/hooks.json`), `subprocess`, `pathlib`, `json`

---

## File Map

- Create: `docs/hook/mcp-failure-fallback-demo/SKILL.md`
  Explains that this is a minimal skill-owned failure fallback demo and that it injects fallback guidance through `additionalContext`.
- Create: `docs/hook/mcp-failure-fallback-demo/hooks/hooks.json`
  Registers a `PostToolUseFailure` command hook that runs the local script with `failPolicy: "allow"`.
- Create: `docs/hook/mcp-failure-fallback-demo/scripts/mcp_failure_fallback.py`
  Reads hook payload JSON from stdin and returns either `{}` or a `hookSpecificOutput.additionalContext` payload.
- Create: `tests/unit/agents/hook_runtime/test_mcp_failure_fallback_demo.py`
  Verifies script behavior and confirms the skill hook loader accepts the demo layout.

## Implementation Assumptions

- Because no concrete MCP tool name was provided, the demo hook will intentionally match all `PostToolUseFailure` events instead of pinning `matcher.tools` to one tool name.
- The fallback guidance string is unified and fixed to the text already approved in the design: `MCP 工具调用失败。请不要继续依赖本次工具结果，改为向用户说明当前调用暂时失败，并使用统一兜底话术回复。`
- Invalid JSON input from stdin is treated as a script error: exit code `1`, no stdout payload, and an explanatory stderr message.

### Task 1: Add Script Tests And Minimal Failure Handler

**Files:**
- Create: `tests/unit/agents/hook_runtime/test_mcp_failure_fallback_demo.py`
- Create: `docs/hook/mcp-failure-fallback-demo/scripts/mcp_failure_fallback.py`
- Test: `tests/unit/agents/hook_runtime/test_mcp_failure_fallback_demo.py`

- [ ] **Step 1: Write the failing tests**

```python
# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[4]
    / "docs"
    / "hook"
    / "mcp-failure-fallback-demo"
    / "scripts"
    / "mcp_failure_fallback.py"
)
FALLBACK_TEXT = (
    "MCP 工具调用失败。请不要继续依赖本次工具结果，改为向用户说明"
    "当前调用暂时失败，并使用统一兜底话术回复。"
)


def _run_script(payload: dict[str, object] | str) -> subprocess.CompletedProcess[str]:
    raw_input = (
        payload
        if isinstance(payload, str)
        else json.dumps(payload, ensure_ascii=False)
    )
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH)],
        input=raw_input,
        text=True,
        capture_output=True,
        check=False,
    )


def test_failure_event_with_error_returns_additional_context() -> None:
    result = _run_script(
        {
            "hook_event_name": "PostToolUseFailure",
            "tool_name": "demo_tool",
            "tool_input": {"query": "hello"},
            "tool_use_id": "tool-1",
            "error": "HTTP 401 unauthorized",
        },
    )

    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data == {
        "hookSpecificOutput": {
            "additionalContext": [FALLBACK_TEXT],
        },
    }


def test_failure_event_without_error_returns_empty_object() -> None:
    result = _run_script(
        {
            "hook_event_name": "PostToolUseFailure",
            "tool_name": "demo_tool",
            "tool_input": {"query": "hello"},
            "tool_use_id": "tool-1",
            "error": "",
        },
    )

    assert result.returncode == 0
    assert json.loads(result.stdout) == {}


def test_non_failure_event_returns_empty_object() -> None:
    result = _run_script(
        {
            "hook_event_name": "PostToolUse",
            "tool_name": "demo_tool",
            "tool_input": {"query": "hello"},
            "tool_use_id": "tool-1",
            "error": "HTTP 500",
        },
    )

    assert result.returncode == 0
    assert json.loads(result.stdout) == {}


def test_invalid_json_returns_exit_code_one() -> None:
    result = _run_script("{")

    assert result.returncode == 1
    assert result.stdout == ""
    assert "invalid hook payload" in result.stderr
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/bin/python -m pytest tests/unit/agents/hook_runtime/test_mcp_failure_fallback_demo.py -v`

Expected: FAIL because `docs/hook/mcp-failure-fallback-demo/scripts/mcp_failure_fallback.py` does not exist yet.

- [ ] **Step 3: Write minimal implementation**

```python
# -*- coding: utf-8 -*-
"""MCP 工具失败时注入统一兜底上下文的 skill hook 样例。"""

from __future__ import annotations

import json
import sys
from typing import Any

FALLBACK_TEXT = (
    "MCP 工具调用失败。请不要继续依赖本次工具结果，改为向用户说明"
    "当前调用暂时失败，并使用统一兜底话术回复。"
)
FAILURE_EVENT = "PostToolUseFailure"


def _load_payload() -> dict[str, Any]:
    """读取并校验 hook runtime 传入的 JSON 负载。"""
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        print("invalid hook payload", file=sys.stderr)
        raise SystemExit(1)
    if not isinstance(payload, dict):
        print("invalid hook payload", file=sys.stderr)
        raise SystemExit(1)
    return payload


def _build_output(payload: dict[str, Any]) -> dict[str, Any]:
    """仅在失败事件且存在 error 文本时返回 additionalContext。"""
    event_name = str(payload.get("hook_event_name") or "")
    error = str(payload.get("error") or "").strip()
    if event_name != FAILURE_EVENT or not error:
        return {}
    return {
        "hookSpecificOutput": {
            "additionalContext": [FALLBACK_TEXT],
        },
    }


def main() -> int:
    """执行脚本入口。"""
    payload = _load_payload()
    json.dump(_build_output(payload), sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv/bin/python -m pytest tests/unit/agents/hook_runtime/test_mcp_failure_fallback_demo.py -v`

Expected: PASS for the four script behavior tests.

- [ ] **Step 5: Commit**

```bash
git add tests/unit/agents/hook_runtime/test_mcp_failure_fallback_demo.py docs/hook/mcp-failure-fallback-demo/scripts/mcp_failure_fallback.py
git commit -m "feat(hooks): add mcp failure fallback script demo"
```

### Task 2: Add Skill Metadata, Hook Config, And Loader Coverage

**Files:**
- Modify: `tests/unit/agents/hook_runtime/test_mcp_failure_fallback_demo.py`
- Create: `docs/hook/mcp-failure-fallback-demo/SKILL.md`
- Create: `docs/hook/mcp-failure-fallback-demo/hooks/hooks.json`
- Test: `tests/unit/agents/hook_runtime/test_mcp_failure_fallback_demo.py`

- [ ] **Step 1: Write the failing loader test**

Append this test to `tests/unit/agents/hook_runtime/test_mcp_failure_fallback_demo.py`:

```python
from swe.agents.hook_runtime.models import HookEventName, HookSessionState
from swe.agents.hook_runtime.skill_loader import load_skill_hooks_for_session


def test_demo_skill_hook_config_loads_from_repo_files() -> None:
    repo_root = Path(__file__).resolve().parents[4]
    skill_root = (
        repo_root / "docs" / "hook" / "mcp-failure-fallback-demo"
    )

    result = load_skill_hooks_for_session(
        skill_name="mcp-failure-fallback-demo",
        skill_root=skill_root,
        workspace_dir=repo_root,
        session_state=HookSessionState(),
    )

    source = result.loaded_skill_sources[0]
    group = source.hook_config.events[HookEventName.POST_TOOL_USE_FAILURE][0]
    handler = group.hooks[0]

    assert source.source_id == "skill:mcp-failure-fallback-demo"
    assert group.id == "skill:mcp-failure-fallback-demo:mcp-failure-fallback"
    assert handler.id == "skill:mcp-failure-fallback-demo:mcp-failure-context"
    assert handler.cwd == str(skill_root.resolve())
    assert handler.argv == [
        "python",
        str(
            (
                skill_root
                / "scripts"
                / "mcp_failure_fallback.py"
            ).resolve()
        ),
    ]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/bin/python -m pytest tests/unit/agents/hook_runtime/test_mcp_failure_fallback_demo.py::test_demo_skill_hook_config_loads_from_repo_files -v`

Expected: FAIL because `SKILL.md` and `hooks/hooks.json` do not exist yet.

- [ ] **Step 3: Write minimal implementation**

Create `docs/hook/mcp-failure-fallback-demo/SKILL.md`:

```markdown
---
name: mcp-failure-fallback-demo
description: "Use this skill when the user wants a minimal skill-owned PostToolUseFailure hook that injects a unified fallback prompt through additionalContext after a tool call fails."
license: Proprietary. LICENSE.txt has complete terms
metadata:
  builtin_skill_version: "1.0"
---

> **重要：** 这个 skill 是一个最小样例，重点演示 `PostToolUseFailure`、`error` 和 `additionalContext` 的组合方式。

# MCP Failure Fallback Demo

这个样例 skill 在工具调用失败时返回统一兜底提示，供后续对话使用。

## 样例结构

1. `hooks/hooks.json`
2. `scripts/mcp_failure_fallback.py`
3. 当前 `SKILL.md`

## 行为说明

- 只依赖 hook 上下文中的 `hook_event_name` 和 `error`
- 当事件为 `PostToolUseFailure` 且 `error` 非空时，返回统一 `additionalContext`
- 不直接生成最终用户回复
```

Create `docs/hook/mcp-failure-fallback-demo/hooks/hooks.json`:

```json
{
  "enabled": true,
  "events": {
    "PostToolUseFailure": [
      {
        "id": "mcp-failure-fallback",
        "hooks": [
          {
            "id": "mcp-failure-context",
            "type": "command",
            "argv": ["python", "scripts/mcp_failure_fallback.py"],
            "timeout": 5,
            "failPolicy": "allow"
          }
        ]
      }
    ]
  }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv/bin/python -m pytest tests/unit/agents/hook_runtime/test_mcp_failure_fallback_demo.py -v`

Expected: PASS for both the script tests and the loader coverage test.

- [ ] **Step 5: Commit**

```bash
git add tests/unit/agents/hook_runtime/test_mcp_failure_fallback_demo.py docs/hook/mcp-failure-fallback-demo/SKILL.md docs/hook/mcp-failure-fallback-demo/hooks/hooks.json
git commit -m "feat(hooks): add mcp failure fallback skill demo"
```

### Task 3: Run Regression Verification For Hook Runtime Paths

**Files:**
- Test: `tests/unit/agents/hook_runtime/test_mcp_failure_fallback_demo.py`
- Test: `tests/unit/agents/hook_runtime/test_skill_hook_loader.py`

- [ ] **Step 1: Run the focused regression suite**

Run:

```bash
venv/bin/python -m pytest \
  tests/unit/agents/hook_runtime/test_mcp_failure_fallback_demo.py \
  tests/unit/agents/hook_runtime/test_skill_hook_loader.py -v
```

Expected: PASS. The new demo stays green and existing skill hook loader coverage remains green.

- [ ] **Step 2: Review the created skill files for accidental drift**

Check:

```bash
sed -n '1,220p' docs/hook/mcp-failure-fallback-demo/SKILL.md
sed -n '1,220p' docs/hook/mcp-failure-fallback-demo/hooks/hooks.json
sed -n '1,220p' docs/hook/mcp-failure-fallback-demo/scripts/mcp_failure_fallback.py
```

Expected:

- The fallback string matches the approved design exactly.
- `hooks/hooks.json` only registers `PostToolUseFailure`.
- The script exits with code `1` for invalid JSON and returns `{}` for non-failure cases.

- [ ] **Step 3: Commit verification-safe final state**

```bash
git add docs/hook/mcp-failure-fallback-demo tests/unit/agents/hook_runtime/test_mcp_failure_fallback_demo.py
git commit -m "test(hooks): verify mcp failure fallback demo"
```

## Self-Review

- Spec coverage:
  The plan covers the skill-owned demo layout, `PostToolUseFailure` handling, unified fallback context injection, `failPolicy: "allow"`, and targeted pytest verification. The only intentional refinement is that the demo matches all `PostToolUseFailure` events because the user did not provide a concrete MCP tool name.
- Placeholder scan:
  No `TODO`, `TBD`, or deferred implementation notes remain.
- Type consistency:
  `mcp_failure_fallback.py`, `mcp-failure-fallback-demo`, `mcp-failure-context`, `PostToolUseFailure`, and the fallback string are consistent across all tasks.
