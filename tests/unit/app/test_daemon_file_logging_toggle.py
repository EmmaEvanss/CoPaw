# -*- coding: utf-8 -*-
"""Regression tests for daemon behavior when file logging is disabled."""

from __future__ import annotations

from pathlib import Path

from swe.app.runner import daemon_commands


def test_run_daemon_logs_reports_disabled_fallback(
    monkeypatch,
    tmp_path,
) -> None:
    """文件日志关闭时应返回明确的兜底提示。"""
    monkeypatch.setattr(
        daemon_commands,
        "FILE_LOG_ENABLED",
        False,
        raising=False,
    )

    message = daemon_commands.run_daemon_logs(
        lines=25,
        context=daemon_commands.DaemonContext(working_dir=tmp_path),
    )

    assert "File log unavailable" in message
    assert "SWE_FILE_LOG_ENABLED=false" in message
    assert "This command reads the file-backed swe.log only." in message
    assert "Check the app process stdout/stderr output instead." in message


def test_run_daemon_version_reports_disabled_log_file(
    monkeypatch,
) -> None:
    """版本信息应展示文件日志被关闭。"""
    monkeypatch.setattr(
        daemon_commands,
        "FILE_LOG_ENABLED",
        False,
        raising=False,
    )

    message = daemon_commands.run_daemon_version(
        daemon_commands.DaemonContext(
            working_dir=Path("/tmp/daemon-disabled"),
        ),
    )

    assert "- Log file: disabled (SWE_FILE_LOG_ENABLED=false)" in message


def test_run_daemon_logs_reads_existing_file_even_if_cli_env_disables_it(
    monkeypatch,
    tmp_path,
) -> None:
    """存在 swe.log 时应按实际文件状态返回日志内容。"""
    monkeypatch.setattr(
        daemon_commands,
        "FILE_LOG_ENABLED",
        False,
        raising=False,
    )
    log_path = tmp_path / "swe.log"
    log_path.write_text("line-1\nline-2\nline-3\n", encoding="utf-8")

    message = daemon_commands.run_daemon_logs(
        lines=2,
        context=daemon_commands.DaemonContext(working_dir=tmp_path),
    )

    assert "File log (last 2 lines)" in message
    assert "line-2\nline-3" in message
    assert "File log unavailable" not in message


def test_run_daemon_version_prefers_existing_log_file_over_cli_env(
    monkeypatch,
    tmp_path,
) -> None:
    """版本信息应展示 daemon 实际写入的日志文件路径。"""
    monkeypatch.setattr(
        daemon_commands,
        "FILE_LOG_ENABLED",
        False,
        raising=False,
    )
    log_path = tmp_path / "swe.log"
    log_path.write_text("daemon log\n", encoding="utf-8")

    message = daemon_commands.run_daemon_version(
        daemon_commands.DaemonContext(working_dir=tmp_path),
    )

    assert f"- Log file: {log_path}" in message
    assert "disabled (SWE_FILE_LOG_ENABLED=false)" not in message
