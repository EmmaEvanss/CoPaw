# -*- coding: utf-8 -*-
"""build_env_context 运行时元信息回归测试。"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

from swe.app.runner import utils as runner_utils


class _FixedDatetime:
    """固定时间桩，保证断言稳定。"""

    @classmethod
    def now(cls, tz=None):
        return datetime(2026, 5, 21, 12, 34, 56, tzinfo=tz)


def test_build_env_context_includes_explicit_source_id(monkeypatch):
    """提供 source_id 时，应原样写入运行时上下文。"""
    monkeypatch.setattr(
        runner_utils,
        "load_config",
        lambda: SimpleNamespace(user_timezone="Asia/Shanghai"),
    )
    monkeypatch.setattr(runner_utils, "datetime", _FixedDatetime)

    context = runner_utils.build_env_context(
        session_id="session-1",
        user_id="user-1",
        channel="console",
        source_id="portal",
        working_dir="/workspace",
        add_hint=False,
    )

    assert "- Source ID: portal" in context
    assert (
        "- Current time: 2026-05-21 12:34:56 Asia/Shanghai (Thursday)"
        in context
    )


def test_build_env_context_marks_missing_source_id_explicitly(monkeypatch):
    """未提供 source_id 时，应展示明确占位符而非默认值。"""
    monkeypatch.setattr(
        runner_utils,
        "load_config",
        lambda: SimpleNamespace(user_timezone="Asia/Shanghai"),
    )
    monkeypatch.setattr(runner_utils, "datetime", _FixedDatetime)

    context = runner_utils.build_env_context(
        session_id="session-1",
        user_id="user-1",
        channel="console",
        source_id=None,
        working_dir="/workspace",
        add_hint=False,
    )

    assert "- Source ID: (not provided)" in context
    assert "- Source ID: default" not in context


def test_build_env_context_falls_back_to_utc_for_invalid_timezone(
    monkeypatch,
):
    """非法时区配置时，运行时上下文应回退到 UTC。"""
    monkeypatch.setattr(
        runner_utils,
        "load_config",
        lambda: SimpleNamespace(user_timezone="Invalid/Timezone"),
    )
    monkeypatch.setattr(runner_utils, "datetime", _FixedDatetime)

    context = runner_utils.build_env_context(
        source_id="portal",
        add_hint=False,
    )

    assert "- Current time: 2026-05-21 12:34:56 UTC (Thursday)" in context
