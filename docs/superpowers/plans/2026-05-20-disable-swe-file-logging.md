# Disable swe.log File Logging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop multi-instance app processes from writing `WORKING_DIR/swe.log` by default while keeping console logging available and making daemon log commands fail gracefully.

**Architecture:** Add a single env-backed switch, `SWE_FILE_LOG_ENABLED`, in `src/swe/constant.py` and default it to `false` in both `dev.json` and `prd.json`. Gate file-handler registration in `src/swe/app/_app.py`, update daemon log/version messaging to reflect the disabled state, and cover the behavior with config bootstrap tests, daemon unit tests, and an app-startup integration test. No changes to stdout/stderr logging, tracing, or query error dumps.

**Tech Stack:** Python 3.12, FastAPI, Click, pytest, environment JSON defaults

---

## File Structure

- Modify: `src/swe/constant.py`
  - Expose the new env-backed `FILE_LOG_ENABLED` constant
- Modify: `src/swe/config/envs/dev.json`
  - Default `SWE_FILE_LOG_ENABLED` to `false` for dev bootstraps
- Modify: `src/swe/config/envs/prd.json`
  - Default `SWE_FILE_LOG_ENABLED` to `false` for prd bootstraps
- Modify: `src/swe/app/_app.py`
  - Skip `add_swe_file_handler()` when file logging is disabled
- Modify: `src/swe/app/runner/daemon_commands.py`
  - Make `/daemon version` and `/daemon logs` report the disabled state instead of pretending `swe.log` always exists
- Modify: `src/swe/cli/daemon_cmd.py`
  - Update the `logs` command help text so CLI wording matches the optional file-log behavior
- Modify: `tests/unit/config/test_env_defaults.py`
  - Assert the new env default is loaded
- Modify: `tests/unit/config/test_bootstrap_env_order.py`
  - Assert package bootstrap resolves `FILE_LOG_ENABLED` correctly before constants are imported
- Create: `tests/unit/app/test_daemon_file_logging_toggle.py`
  - Add regression tests for daemon output when file logging is off
- Modify: `tests/integrated/test_app_startup.py`
  - Start the app with `SWE_FILE_LOG_ENABLED=false` and assert no `swe.log` file is created
- Modify: `analysis/playbook/log-entrypoints.md`
  - Document stdout/stderr as the primary runtime log source when file logging is disabled

### Task 1: Add the Config Toggle and Bootstrap Coverage

**Files:**
- Modify: `src/swe/constant.py`
- Modify: `src/swe/config/envs/dev.json`
- Modify: `src/swe/config/envs/prd.json`
- Modify: `tests/unit/config/test_env_defaults.py`
- Modify: `tests/unit/config/test_bootstrap_env_order.py`
- Test: `tests/unit/config/test_env_defaults.py`
- Test: `tests/unit/config/test_bootstrap_env_order.py`

- [ ] **Step 1: Write the failing config/bootstrap tests**

```python
# tests/unit/config/test_env_defaults.py
@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    """Remove test-related env vars before each test."""
    test_vars = [
        "SWE_ENV",
        "SWE_LOG_LEVEL",
        "SWE_FILE_LOG_ENABLED",
        "SWE_OPENAPI_DOCS",
        "SWE_CORS_ORIGINS",
        "SWE_LLM_MAX_CONCURRENT",
        "SWE_LLM_MAX_QPM",
        "SWE_AUTH_ENABLED",
        "SWE_ENABLED_CHANNELS",
        "SWE_DISABLED_CHANNELS",
    ]
    for var in test_vars:
        monkeypatch.delenv(var, raising=False)


def test_load_dev_defaults(self, monkeypatch):
    """load_env_defaults should load dev.json values."""
    result = load_env_defaults("dev")

    assert "SWE_LOG_LEVEL" in result
    assert "SWE_FILE_LOG_ENABLED" in result
    assert os.environ.get("SWE_LOG_LEVEL") == "debug"
    assert os.environ.get("SWE_FILE_LOG_ENABLED") == "false"
    assert os.environ.get("SWE_OPENAPI_DOCS") == "true"


def test_load_prd_defaults(self, monkeypatch):
    """load_env_defaults should load prd.json values."""
    result = load_env_defaults("prd")

    assert "SWE_LOG_LEVEL" in result
    assert "SWE_FILE_LOG_ENABLED" in result
    assert os.environ.get("SWE_LOG_LEVEL") == "info"
    assert os.environ.get("SWE_FILE_LOG_ENABLED") == "false"
    assert os.environ.get("SWE_OPENAPI_DOCS") == "false"


def test_returns_empty_dict_when_all_vars_exist(self, monkeypatch):
    """load_env_defaults should return empty dict when all vars exist."""
    monkeypatch.setenv("SWE_LOG_LEVEL", "test")
    monkeypatch.setenv("SWE_FILE_LOG_ENABLED", "test")
    monkeypatch.setenv("SWE_OPENAPI_DOCS", "test")
    monkeypatch.setenv("SWE_CORS_ORIGINS", "test")
    monkeypatch.setenv("SWE_LLM_MAX_CONCURRENT", "test")
    monkeypatch.setenv("SWE_LLM_MAX_QPM", "test")
    monkeypatch.setenv("SWE_AUTH_ENABLED", "test")
    monkeypatch.setenv("SWE_ENABLED_CHANNELS", "test")
    monkeypatch.setenv("SWE_DISABLED_CHANNELS", "test")

    result = load_env_defaults("dev")

    assert result == {}


# tests/unit/config/test_bootstrap_env_order.py
env.pop("SWE_FILE_LOG_ENABLED", None)

script = """
import json
import os
import swe
import swe.constant as constant

print(json.dumps({
    "env_docs": os.environ.get("SWE_OPENAPI_DOCS"),
    "env_log_level": os.environ.get("SWE_LOG_LEVEL"),
    "env_file_log": os.environ.get("SWE_FILE_LOG_ENABLED"),
    "docs_enabled": constant.DOCS_ENABLED,
    "file_log_enabled": constant.FILE_LOG_ENABLED,
}))
"""

assert payload == {
    "env_docs": "true",
    "env_log_level": "debug",
    "env_file_log": "false",
    "docs_enabled": True,
    "file_log_enabled": False,
}
```

- [ ] **Step 2: Run the config/bootstrap tests to verify they fail**

Run: `venv/bin/python -m pytest tests/unit/config/test_env_defaults.py tests/unit/config/test_bootstrap_env_order.py -q`

Expected: `FAIL` because `SWE_FILE_LOG_ENABLED` is not yet present in `dev.json` / `prd.json`, and `constant.FILE_LOG_ENABLED` does not exist.

- [ ] **Step 3: Implement the env toggle and defaults**

```python
# src/swe/constant.py
# Env key for app log level (used by CLI and app load for reload child).
LOG_LEVEL_ENV = "SWE_LOG_LEVEL"

# 是否启用 swe.log 文件日志；关闭时仅保留 stdout/stderr 日志。
FILE_LOG_ENABLED = EnvVarLoader.get_bool(
    "SWE_FILE_LOG_ENABLED",
    False,
)
```

```jsonc
// src/swe/config/envs/dev.json
{
  "SWE_LOG_LEVEL": "debug",
  "SWE_FILE_LOG_ENABLED": "false",
  "SWE_OPENAPI_DOCS": "true"
}
```

```jsonc
// src/swe/config/envs/prd.json
{
  "SWE_LOG_LEVEL": "info",
  "SWE_FILE_LOG_ENABLED": "false",
  "SWE_OPENAPI_DOCS": "false"
}
```

- [ ] **Step 4: Run the config/bootstrap tests to verify they pass**

Run: `venv/bin/python -m pytest tests/unit/config/test_env_defaults.py tests/unit/config/test_bootstrap_env_order.py -q`

Expected: `PASS`, including the new assertions for `SWE_FILE_LOG_ENABLED` and `constant.FILE_LOG_ENABLED`.

- [ ] **Step 5: Commit the config toggle**

```bash
git add src/swe/constant.py src/swe/config/envs/dev.json src/swe/config/envs/prd.json tests/unit/config/test_env_defaults.py tests/unit/config/test_bootstrap_env_order.py
git commit -m "feat(logging): add swe file log toggle"
```

### Task 2: Gate Runtime File Logging and Add Regression Coverage

**Files:**
- Modify: `src/swe/app/_app.py`
- Modify: `src/swe/app/runner/daemon_commands.py`
- Modify: `src/swe/cli/daemon_cmd.py`
- Create: `tests/unit/app/test_daemon_file_logging_toggle.py`
- Modify: `tests/integrated/test_app_startup.py`
- Test: `tests/unit/app/test_daemon_file_logging_toggle.py`
- Test: `tests/integrated/test_app_startup.py`

- [ ] **Step 1: Write the failing daemon and startup tests**

```python
# tests/unit/app/test_daemon_file_logging_toggle.py
# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from swe.app.runner import daemon_commands


def test_run_daemon_logs_reports_disabled_when_file_logging_is_off(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(daemon_commands, "FILE_LOG_ENABLED", False)
    monkeypatch.setattr(daemon_commands, "WORKING_DIR", tmp_path)

    text = daemon_commands.run_daemon_logs(lines=20)

    assert "File logging is disabled" in text
    assert "stdout/stderr" in text


def test_run_daemon_version_reports_disabled_log_file(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(daemon_commands, "FILE_LOG_ENABLED", False)

    text = daemon_commands.run_daemon_version(
        daemon_commands.DaemonContext(working_dir=tmp_path),
    )

    assert "- Log file: disabled (SWE_FILE_LOG_ENABLED=false)" in text
```

```python
# tests/integrated/test_app_startup.py
def _subprocess_env(
    extra: dict[str, str] | None = None,
) -> dict[str, str]:
    """Force subprocesses to import the current worktree sources."""
    root = Path(__file__).resolve().parents[2]
    env = os.environ.copy()
    pythonpath_parts = [str(root / "src")]
    existing_pythonpath = env.get("PYTHONPATH")
    if existing_pythonpath:
        pythonpath_parts.append(existing_pythonpath)
    env["PYTHONPATH"] = os.pathsep.join(pythonpath_parts)
    if extra:
        env.update(extra)
    return env


def test_app_startup_without_swe_log_file(tmp_path: Path) -> None:
    """关闭文件日志后，应用启动不应生成 swe.log。"""
    host = "127.0.0.1"
    port = _find_free_port(host)
    log_lines: list[str] = []
    working_dir = tmp_path / ".swe"
    secret_dir = tmp_path / ".swe.secret"

    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "swe",
            "app",
            "--host",
            host,
            "--port",
            str(port),
            "--log-level",
            "info",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        cwd=str(Path(__file__).resolve().parents[2]),
        env=_subprocess_env(
            {
                "SWE_WORKING_DIR": str(working_dir),
                "SWE_SECRET_DIR": str(secret_dir),
                "SWE_FILE_LOG_ENABLED": "false",
            },
        ),
    )

    assert process.stdout is not None

    log_thread = threading.Thread(
        target=_tee_stream,
        args=(process.stdout, log_lines),
        daemon=True,
    )
    log_thread.start()

    try:
        max_wait = 60
        start_time = time.time()

        with httpx.Client(timeout=5.0, trust_env=False) as client:
            while time.time() - start_time < max_wait:
                if process.poll() is not None:
                    logs = "".join(log_lines)[-4000:]
                    raise AssertionError(
                        f"Process exited early with code {process.returncode}.\nLogs:\n{logs}",
                    )

                try:
                    response = client.get(f"http://{host}:{port}/api/version")
                    if response.status_code == 200:
                        break
                except (httpx.ConnectError, httpx.TimeoutException):
                    time.sleep(1.0)
            else:
                logs = "".join(log_lines)[-4000:]
                raise AssertionError(
                    "Backend did not start within timeout period.\n"
                    f"Logs:\n{logs}",
                )

            assert not (working_dir / "swe.log").exists()
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)

        log_thread.join(timeout=2)
```

- [ ] **Step 2: Run the new regression tests to verify they fail on current code**

Run: `venv/bin/python -m pytest tests/unit/app/test_daemon_file_logging_toggle.py tests/integrated/test_app_startup.py::test_app_startup_without_swe_log_file -q`

Expected: `FAIL` because `/daemon logs` currently falls back to `(Log file not found: ...)`, `/daemon version` still prints a concrete `swe.log` path, and app startup still creates `WORKING_DIR/swe.log`.

- [ ] **Step 3: Implement the runtime gate and daemon fallback**

```python
# src/swe/app/_app.py
from ..constant import (
    DOCS_ENABLED,
    FILE_LOG_ENABLED,
    LOG_LEVEL_ENV,
    CORS_ORIGINS,
    WORKING_DIR,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    startup_start_time = time.time()
    if FILE_LOG_ENABLED:
        add_swe_file_handler(WORKING_DIR / "swe.log")
    else:
        logger.info(
            "SWE file logging disabled via SWE_FILE_LOG_ENABLED=false",
        )
```

```python
# src/swe/app/runner/daemon_commands.py
from ...constant import FILE_LOG_ENABLED, WORKING_DIR


def _get_log_file_path(working_dir: Path) -> Path:
    """返回 daemon 文件日志路径。"""
    return working_dir / "swe.log"


def run_daemon_version(context: DaemonContext) -> str:
    """Return version and paths."""
    try:
        from ...__version__ import __version__ as ver
    except ImportError:
        ver = "unknown"

    log_file_line = (
        f"- Log file: {_get_log_file_path(context.working_dir)}"
        if FILE_LOG_ENABLED
        else "- Log file: disabled (SWE_FILE_LOG_ENABLED=false)"
    )

    return (
        f"**Daemon version**\n\n"
        f"- Version: {ver}\n"
        f"- Working dir: {context.working_dir}\n"
        f"{log_file_line}"
    )


def run_daemon_logs(lines: int = 100) -> str:
    """Tail last N lines from swe.log when file logging is enabled."""
    if not FILE_LOG_ENABLED:
        return (
            f"**Console log (last {lines} lines)**\n\n"
            "- File logging is disabled (`SWE_FILE_LOG_ENABLED=false`).\n"
            "- Inspect process stdout/stderr or container logs instead."
        )

    log_path = _get_log_file_path(WORKING_DIR)
    content = _get_last_lines(log_path, lines=lines)
    return f"**Console log (last {lines} lines)**\n\n```\n{content}\n```"
```

```python
# src/swe/cli/daemon_cmd.py
@daemon_group.command("logs")
@click.option(
    "-n",
    "--lines",
    default=100,
    type=int,
    help="Number of last file-log lines to show when swe.log logging is enabled.",
)
def logs_cmd(lines: int) -> None:
    """Show last N file-log lines when swe.log logging is enabled."""
    lines = min(max(1, lines), 2000)
    click.echo(run_daemon_logs(lines=lines))
```

- [ ] **Step 4: Run the daemon and startup regressions to verify they pass**

Run: `venv/bin/python -m pytest tests/unit/app/test_daemon_file_logging_toggle.py tests/integrated/test_app_startup.py::test_app_startup_without_swe_log_file -q`

Expected: `PASS`, with the unit tests reporting the disabled fallback text and the integration test confirming that no `swe.log` file is created when `SWE_FILE_LOG_ENABLED=false`.

- [ ] **Step 5: Commit the runtime behavior change**

```bash
git add src/swe/app/_app.py src/swe/app/runner/daemon_commands.py src/swe/cli/daemon_cmd.py tests/unit/app/test_daemon_file_logging_toggle.py tests/integrated/test_app_startup.py
git commit -m "fix(logging): disable swe file logs by config"
```

### Task 3: Document the New Logging Entry Points

**Files:**
- Modify: `analysis/playbook/log-entrypoints.md`
- Test: `analysis/playbook/log-entrypoints.md`

- [ ] **Step 1: Expand the playbook entry for optional file logging**

```markdown
# 日志入口

本文档记录运行时问题最常用的日志与快照入口。

## 应用运行日志

- 进程标准输出 / 标准错误：默认入口。`swe app` 启动后，控制台日志始终会输出到当前进程的 stdout/stderr。
- `WORKING_DIR/swe.log`：仅当 `SWE_FILE_LOG_ENABLED=true` 时才会创建并写入。
- `/daemon logs` 或 `swe daemon logs`：只在文件日志开启时读取 `WORKING_DIR/swe.log`；如果文件日志关闭，应改查容器日志、Supervisor 日志或 systemd journal。

## 其他运行时快照

- query error dump：入口在 `src/swe/app/runner/query_error_dump.py`
- tracing：入口在 `src/swe/tracing/`
```

- [ ] **Step 2: Verify the playbook mentions the new operational path**

Run: `rg -n "SWE_FILE_LOG_ENABLED|stdout/stderr|daemon logs|query error dump" analysis/playbook/log-entrypoints.md`

Expected: `rg` prints the new log-entry bullets so operators can see the non-file fallback immediately.

- [ ] **Step 3: Commit the playbook update**

```bash
git add analysis/playbook/log-entrypoints.md
git commit -m "docs(playbook): document optional swe file logging"
```
