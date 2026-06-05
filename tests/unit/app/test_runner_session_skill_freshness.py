# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from agentscope.message import Msg

from swe.agents.hook_runtime.models import (
    HookConfig,
    HookSessionOverlay,
    LoadedSkillHookSource,
)
from swe.app.runner.runner import AgentRunner
from swe.app.runner.session import SafeJSONSession
from swe.config.config import SuggestionMode


def _agent_config():
    return SimpleNamespace(
        id="test-agent",
        hooks=SimpleNamespace(enabled=False, events={}),
        mcp=None,
        running=SimpleNamespace(
            suggestions=SimpleNamespace(
                enabled=False,
                mode=SuggestionMode.DISABLED,
            ),
        ),
    )


class _FakeMemory:
    def __init__(self) -> None:
        self.content = []

    async def add(self, msg, marks=None):
        if marks is None:
            marks = []
        elif not isinstance(marks, list):
            marks = [marks]
        self.content.append((msg, marks))


class _FakeAgent:
    effective_skills: list[str] = []
    last_instance: "_FakeAgent | None" = None

    def __init__(self, **kwargs):
        self.memory = _FakeMemory()
        self._request_context = kwargs.get("request_context", {})
        self.rebuild_sys_prompt_calls = 0
        self.turn_msgs = []
        _FakeAgent.last_instance = self

    async def register_mcp_clients(self):
        return

    def set_console_output_enabled(self, enabled=False):
        del enabled

    def get_effective_skills(self) -> list[str]:
        return list(type(self).effective_skills)

    def rebuild_sys_prompt(self):
        self.rebuild_sys_prompt_calls += 1

    async def setup_skill_detector(self, trace_id: str) -> None:
        del trace_id

    async def __call__(self, turn_msgs):
        self.turn_msgs = list(turn_msgs)
        for msg in turn_msgs:
            self.memory.content.append((msg, []))
        reply = Msg(name="Friday", role="assistant", content="agent reply")
        self.memory.content.append((reply, []))
        return [reply]

    def state_dict(self):
        return {
            "memory": {
                "content": [
                    [msg.to_dict(), marks]
                    for msg, marks in self.memory.content
                ],
            },
        }

    def load_state_dict(self, state):
        memory_state = (
            state.get("memory", {}) if isinstance(state, dict) else {}
        )
        restored = []
        for raw_msg, marks in memory_state.get("content", []) or []:
            restored.append((Msg.from_dict(raw_msg), marks))
        self.memory.content = restored


async def _fake_stream_printing_messages(*, agents, coroutine_task):
    del agents
    turn_msgs = await coroutine_task
    for msg in turn_msgs:
        yield msg, True


def _patch_runner(monkeypatch, tmp_path: Path) -> AgentRunner:
    runner = AgentRunner(agent_id="test-agent", workspace_dir=tmp_path)
    runner.session = SafeJSONSession(save_dir=str(tmp_path / "sessions"))
    setattr(runner, "_chat_manager", None)
    monkeypatch.setattr(
        "swe.app.runner.runner._build_and_connect_mcp_clients",
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr("swe.app.runner.runner.SWEAgent", _FakeAgent)
    monkeypatch.setattr(
        "swe.app.runner.runner.stream_printing_messages",
        _fake_stream_printing_messages,
    )
    monkeypatch.setattr(
        "swe.app.runner.runner._cleanup_mcp_clients",
        AsyncMock(),
    )
    monkeypatch.setattr(
        "swe.app.runner.runner.build_env_context",
        lambda **kwargs: "base context",
    )
    monkeypatch.setattr(
        "swe.app.runner.runner.load_agent_config",
        lambda *args, **kwargs: _agent_config(),
    )
    monkeypatch.setattr(
        "swe.app.runner.runner._load_tenant_hook_config",
        lambda *args, **kwargs: SimpleNamespace(enabled=False, events={}),
    )
    return runner


def _write_skill_manifest(
    workspace_dir: Path,
    *,
    skills: list[str],
) -> None:
    payload = {
        "skills": {
            skill_name: {
                "enabled": True,
                "channels": ["all"],
                "metadata": {"description": f"{skill_name} skill"},
            }
            for skill_name in skills
        },
    }
    (workspace_dir / "skill.json").write_text(
        json.dumps(payload),
        encoding="utf-8",
    )


def _write_skill_dir(workspace_dir: Path, skill_name: str) -> Path:
    skill_dir = workspace_dir / "skills" / skill_name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {skill_name}\ndescription: {skill_name}\n---\n",
        encoding="utf-8",
    )
    return skill_dir


def _request() -> SimpleNamespace:
    return SimpleNamespace(
        session_id="session-1",
        user_id="user-1",
        channel="console",
        channel_meta={},
    )


@pytest.mark.asyncio
async def test_safe_json_session_persists_skill_snapshot_at_top_level(
    tmp_path: Path,
) -> None:
    session = SafeJSONSession(save_dir=str(tmp_path))

    await session.save_session_skill_snapshot(
        session_id="session-1",
        user_id="user-1",
        snapshot={
            "xlsx": {
                "skill_name": "xlsx",
                "resolved_skill_dir": "/tmp/xlsx",
                "freshness_token": 123.0,
            },
        },
    )

    state = await session.get_session_state_dict("session-1", user_id="user-1")

    assert state["session_skill_snapshot"]["xlsx"]["skill_name"] == "xlsx"
    assert "session_skill_snapshot" not in state.get("agent", {})


@pytest.mark.asyncio
async def test_declared_skill_start_persists_snapshot_in_same_turn(
    monkeypatch,
    tmp_path: Path,
) -> None:
    runner = _patch_runner(monkeypatch, tmp_path)
    _FakeAgent.effective_skills = ["xlsx"]
    _write_skill_manifest(tmp_path, skills=["xlsx"])
    skill_dir = _write_skill_dir(tmp_path, "xlsx")
    monkeypatch.setattr(
        "swe.app.runner.runner.get_skill_freshness_token",
        lambda path: 55.0 if Path(path) == skill_dir else 0.0,
    )

    msgs = [Msg(name="user", role="user", content="use xlsx")]
    await anext(runner.query_handler(msgs, request=_request()))

    state = await runner.session.get_session_state_dict(
        "session-1",
        user_id="user-1",
    )
    assert state["session_skill_snapshot"]["xlsx"] == {
        "skill_name": "xlsx",
        "resolved_skill_dir": str(skill_dir),
        "freshness_token": 55.0,
    }


@pytest.mark.asyncio
async def test_turn_start_aggregates_token_change_and_withdrawal_notice(
    monkeypatch,
    tmp_path: Path,
) -> None:
    runner = _patch_runner(monkeypatch, tmp_path)
    _FakeAgent.effective_skills = ["xlsx"]
    _write_skill_manifest(tmp_path, skills=["xlsx", "pdf"])
    xlsx_dir = _write_skill_dir(tmp_path, "xlsx")
    pdf_dir = _write_skill_dir(tmp_path, "pdf")
    await runner.session.save_session_skill_snapshot(
        session_id="session-1",
        user_id="user-1",
        snapshot={
            "xlsx": {
                "skill_name": "xlsx",
                "resolved_skill_dir": str(xlsx_dir),
                "freshness_token": 10.0,
            },
            "pdf": {
                "skill_name": "pdf",
                "resolved_skill_dir": str(pdf_dir),
                "freshness_token": 20.0,
            },
        },
    )
    monkeypatch.setattr(
        "swe.app.runner.runner.get_skill_freshness_token",
        lambda path: 11.0 if Path(path) == xlsx_dir else 20.0,
    )

    outputs = [
        item
        async for item in runner.query_handler(
            [Msg(name="user", role="user", content="continue")],
            request=_request(),
        )
    ]

    assert outputs[-1][0].get_text_content() == "agent reply"
    assert _FakeAgent.last_instance is not None
    notice = _FakeAgent.last_instance.turn_msgs[0]
    assert notice.role == "system"
    assert "xlsx" in notice.get_text_content()
    assert "detected skill-directory change" in notice.get_text_content()
    assert "pdf" in notice.get_text_content()
    assert "no longer effective" in notice.get_text_content()
    assert (
        len(
            [
                msg
                for msg in _FakeAgent.last_instance.turn_msgs
                if msg.role == "system"
            ],
        )
        == 1
    )
    state = await runner.session.get_session_state_dict(
        "session-1",
        user_id="user-1",
    )
    assert state["session_skill_snapshot"] == {
        "xlsx": {
            "skill_name": "xlsx",
            "resolved_skill_dir": str(xlsx_dir),
            "freshness_token": 11.0,
        },
    }


@pytest.mark.asyncio
async def test_turn_start_notice_reports_directory_switch_paths(
    monkeypatch,
    tmp_path: Path,
) -> None:
    runner = _patch_runner(monkeypatch, tmp_path)
    _FakeAgent.effective_skills = ["xlsx"]
    _write_skill_manifest(tmp_path, skills=["xlsx"])
    new_dir = _write_skill_dir(tmp_path, "xlsx")
    old_dir = tmp_path / "legacy-skills" / "xlsx"
    old_dir.mkdir(parents=True)
    await runner.session.save_session_skill_snapshot(
        session_id="session-1",
        user_id="user-1",
        snapshot={
            "xlsx": {
                "skill_name": "xlsx",
                "resolved_skill_dir": str(old_dir),
                "freshness_token": 10.0,
            },
        },
    )
    monkeypatch.setattr(
        "swe.app.runner.runner.get_skill_freshness_token",
        lambda _path: 44.0,
    )

    outputs = [
        item
        async for item in runner.query_handler(
            [Msg(name="user", role="user", content="continue")],
            request=_request(),
        )
    ]

    assert outputs[-1][0].get_text_content() == "agent reply"
    assert _FakeAgent.last_instance is not None
    notice_text = _FakeAgent.last_instance.turn_msgs[0].get_text_content()
    assert f"{old_dir} -> {new_dir}" in notice_text


@pytest.mark.asyncio
async def test_missing_skill_snapshot_entry_is_removed_without_notice(
    monkeypatch,
    tmp_path: Path,
) -> None:
    runner = _patch_runner(monkeypatch, tmp_path)
    _FakeAgent.effective_skills = []
    _write_skill_manifest(tmp_path, skills=[])
    missing_dir = tmp_path / "skills" / "missing"
    await runner.session.save_session_skill_snapshot(
        session_id="session-1",
        user_id="user-1",
        snapshot={
            "missing": {
                "skill_name": "missing",
                "resolved_skill_dir": str(missing_dir),
                "freshness_token": 10.0,
            },
        },
    )
    monkeypatch.setattr(
        "swe.app.runner.runner.get_skill_freshness_token",
        lambda _path: 0.0,
    )

    outputs = [
        item
        async for item in runner.query_handler(
            [Msg(name="user", role="user", content="continue")],
            request=_request(),
        )
    ]

    assert outputs[-1][0].get_text_content() == "agent reply"
    assert _FakeAgent.last_instance is not None
    assert [
        msg
        for msg in _FakeAgent.last_instance.turn_msgs
        if msg.role == "system"
    ] == []
    state = await runner.session.get_session_state_dict(
        "session-1",
        user_id="user-1",
    )
    assert state["session_skill_snapshot"] == {}


@pytest.mark.asyncio
async def test_missing_stored_skill_dir_still_reports_directory_switch(
    monkeypatch,
    tmp_path: Path,
) -> None:
    runner = _patch_runner(monkeypatch, tmp_path)
    _FakeAgent.effective_skills = ["xlsx"]
    _write_skill_manifest(tmp_path, skills=["xlsx"])
    new_dir = _write_skill_dir(tmp_path, "xlsx")
    old_dir = tmp_path / "legacy-skills" / "xlsx"
    await runner.session.save_session_skill_snapshot(
        session_id="session-1",
        user_id="user-1",
        snapshot={
            "xlsx": {
                "skill_name": "xlsx",
                "resolved_skill_dir": str(old_dir),
                "freshness_token": 10.0,
            },
        },
    )
    monkeypatch.setattr(
        "swe.app.runner.runner.get_skill_freshness_token",
        lambda _path: 44.0,
    )

    outputs = [
        item
        async for item in runner.query_handler(
            [Msg(name="user", role="user", content="continue")],
            request=_request(),
        )
    ]

    assert outputs[-1][0].get_text_content() == "agent reply"
    assert _FakeAgent.last_instance is not None
    notice_text = _FakeAgent.last_instance.turn_msgs[0].get_text_content()
    assert f"{old_dir} -> {new_dir}" in notice_text
    state = await runner.session.get_session_state_dict(
        "session-1",
        user_id="user-1",
    )
    assert state["session_skill_snapshot"] == {
        "xlsx": {
            "skill_name": "xlsx",
            "resolved_skill_dir": str(new_dir),
            "freshness_token": 44.0,
        },
    }


@pytest.mark.asyncio
async def test_unchanged_snapshot_emits_no_notice(
    monkeypatch,
    tmp_path: Path,
) -> None:
    runner = _patch_runner(monkeypatch, tmp_path)
    _FakeAgent.effective_skills = ["xlsx"]
    _write_skill_manifest(tmp_path, skills=["xlsx"])
    skill_dir = _write_skill_dir(tmp_path, "xlsx")
    await runner.session.save_session_skill_snapshot(
        session_id="session-1",
        user_id="user-1",
        snapshot={
            "xlsx": {
                "skill_name": "xlsx",
                "resolved_skill_dir": str(skill_dir),
                "freshness_token": 42.0,
            },
        },
    )
    monkeypatch.setattr(
        "swe.app.runner.runner.get_skill_freshness_token",
        lambda _path: 42.0,
    )

    outputs = [
        item
        async for item in runner.query_handler(
            [Msg(name="user", role="user", content="continue")],
            request=_request(),
        )
    ]

    assert outputs[-1][0].get_text_content() == "agent reply"
    assert _FakeAgent.last_instance is not None
    assert [
        msg
        for msg in _FakeAgent.last_instance.turn_msgs
        if msg.role == "system"
    ] == []


@pytest.mark.asyncio
async def test_regular_session_save_clears_stale_hook_overlay(
    monkeypatch,
    tmp_path: Path,
) -> None:
    runner = _patch_runner(monkeypatch, tmp_path)
    _write_skill_manifest(tmp_path, skills=["xlsx"])
    persisted_overlay = HookSessionOverlay(
        loaded_skill_sources=[
            LoadedSkillHookSource(
                source_id="skill:xlsx",
                skill_name="xlsx",
                skill_root=str(tmp_path / "skills" / "xlsx"),
                source_path=str(
                    tmp_path / "skills" / "xlsx" / "hooks" / "hooks.json",
                ),
                hook_config=HookConfig(enabled=True),
            ),
        ],
        once_executed={"skill:xlsx:once": True},
    )
    await runner.session.save_merged_state(
        session_id="session-1",
        user_id="user-1",
        state={
            "agent": {"memory": {"content": []}},
            "hook_overlay": persisted_overlay.model_dump(
                mode="json",
                by_alias=True,
            ),
            "session_skill_snapshot": {
                "xlsx": {
                    "skill_name": "xlsx",
                    "resolved_skill_dir": str(
                        tmp_path / "skills" / "xlsx",
                    ),
                    "freshness_token": 11.0,
                },
            },
        },
    )

    agent = _FakeAgent()
    await runner._save_regular_session_state(
        agent,
        session_id="session-1",
        user_id="user-1",
        hook_overlay=None,
    )

    state = await runner.session.get_session_state_dict(
        "session-1",
        user_id="user-1",
    )
    assert "hook_overlay" not in state
    assert state["session_skill_snapshot"] == {
        "xlsx": {
            "skill_name": "xlsx",
            "resolved_skill_dir": str(tmp_path / "skills" / "xlsx"),
            "freshness_token": 11.0,
        },
    }


@pytest.mark.asyncio
async def test_regular_session_save_preserves_task_session_metadata(
    monkeypatch,
    tmp_path: Path,
) -> None:
    runner = _patch_runner(monkeypatch, tmp_path)
    await runner.session.save_merged_state(
        session_id="session-1",
        user_id="user-1",
        state={
            "agent": {"memory": {"content": []}},
            "task_runs": [
                {
                    "run_id": "run-1",
                    "memory_start": 0,
                    "memory_end": 2,
                },
            ],
            "task_messages": [
                {
                    "id": "msg-1",
                    "role": "assistant",
                    "content": "persisted task update",
                },
            ],
            "custom_top_level_state": {"keep": True},
        },
    )

    agent = _FakeAgent()
    await runner._save_regular_session_state(
        agent,
        session_id="session-1",
        user_id="user-1",
        hook_overlay=None,
    )

    state = await runner.session.get_session_state_dict(
        "session-1",
        user_id="user-1",
    )
    assert state["task_runs"] == [
        {
            "run_id": "run-1",
            "memory_start": 0,
            "memory_end": 2,
        },
    ]
    assert state["task_messages"] == [
        {
            "id": "msg-1",
            "role": "assistant",
            "content": "persisted task update",
        },
    ]
    assert state["custom_top_level_state"] == {"keep": True}


@pytest.mark.asyncio
async def test_applied_snapshot_prevents_repeat_notice_on_later_turn(
    monkeypatch,
    tmp_path: Path,
) -> None:
    runner = _patch_runner(monkeypatch, tmp_path)
    _FakeAgent.effective_skills = ["xlsx"]
    _write_skill_manifest(tmp_path, skills=["xlsx"])
    skill_dir = _write_skill_dir(tmp_path, "xlsx")
    await runner.session.save_session_skill_snapshot(
        session_id="session-1",
        user_id="user-1",
        snapshot={
            "xlsx": {
                "skill_name": "xlsx",
                "resolved_skill_dir": str(skill_dir),
                "freshness_token": 10.0,
            },
        },
    )
    monkeypatch.setattr(
        "swe.app.runner.runner.get_skill_freshness_token",
        lambda _path: 11.0,
    )

    first_outputs = [
        item
        async for item in runner.query_handler(
            [Msg(name="user", role="user", content="continue")],
            request=_request(),
        )
    ]

    assert first_outputs[-1][0].get_text_content() == "agent reply"
    assert _FakeAgent.last_instance is not None
    assert _FakeAgent.last_instance.turn_msgs[0].role == "system"

    second_outputs = [
        item
        async for item in runner.query_handler(
            [Msg(name="user", role="user", content="continue again")],
            request=_request(),
        )
    ]

    assert second_outputs[-1][0].get_text_content() == "agent reply"
    assert _FakeAgent.last_instance is not None
    assert [
        msg
        for msg in _FakeAgent.last_instance.turn_msgs
        if msg.role == "system"
    ] == []


@pytest.mark.asyncio
async def test_freshness_notice_is_not_persisted_in_session_memory(
    monkeypatch,
    tmp_path: Path,
) -> None:
    runner = _patch_runner(monkeypatch, tmp_path)
    _FakeAgent.effective_skills = ["xlsx"]
    _write_skill_manifest(tmp_path, skills=["xlsx"])
    skill_dir = _write_skill_dir(tmp_path, "xlsx")
    await runner.session.save_session_skill_snapshot(
        session_id="session-1",
        user_id="user-1",
        snapshot={
            "xlsx": {
                "skill_name": "xlsx",
                "resolved_skill_dir": str(skill_dir),
                "freshness_token": 10.0,
            },
        },
    )
    monkeypatch.setattr(
        "swe.app.runner.runner.get_skill_freshness_token",
        lambda _path: 11.0,
    )

    outputs = [
        item
        async for item in runner.query_handler(
            [Msg(name="user", role="user", content="continue")],
            request=_request(),
        )
    ]

    assert outputs[-1][0].get_text_content() == "agent reply"
    assert _FakeAgent.last_instance is not None
    assert _FakeAgent.last_instance.turn_msgs[0].role == "system"

    state = await runner.session.get_session_state_dict(
        "session-1",
        user_id="user-1",
    )
    persisted_texts = [
        entry[0]["content"]
        for entry in state["agent"]["memory"]["content"]
        if isinstance(entry, list)
        and entry
        and isinstance(entry[0], dict)
        and isinstance(entry[0].get("content"), str)
    ]
    assert not any(
        text.startswith("[Skill freshness notice]") for text in persisted_texts
    )
