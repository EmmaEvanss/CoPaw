# -*- coding: utf-8 -*-
"""Cron executor tenant context regression tests."""

# pylint: disable=protected-access
import asyncio
import importlib
import importlib.util
import sys
import types
from pathlib import Path

import pytest

from swe.config.config import Config
from swe.config.utils import save_config

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

SRC_ROOT = Path(__file__).parent.parent.parent.parent / "src"
_MODELS_FILE = SRC_ROOT / "swe" / "app" / "crons" / "models.py"
_EXECUTOR_FILE = SRC_ROOT / "swe" / "app" / "crons" / "executor.py"

_ORIGINAL_MODULES = {
    name: sys.modules.get(name)
    for name in [
        "swe.app",
        "swe.app.crons",
        "swe.app.channels.schema",
        "swe.app.crons.models",
        "swe.app.crons.executor",
    ]
}

if "swe.app" not in sys.modules:
    app_pkg = types.ModuleType("swe.app")
    app_pkg.__path__ = [str(SRC_ROOT / "swe" / "app")]
    sys.modules["swe.app"] = app_pkg

if "swe.app.crons" not in sys.modules:
    crons_pkg = types.ModuleType("swe.app.crons")
    crons_pkg.__path__ = [str(SRC_ROOT / "swe" / "app" / "crons")]
    sys.modules["swe.app.crons"] = crons_pkg

channels_schema = types.ModuleType("swe.app.channels.schema")
channels_schema.ChannelType = str
channels_schema.DEFAULT_CHANNEL = "console"
sys.modules["swe.app.channels.schema"] = channels_schema

context_module = importlib.import_module("swe.config.context")
llm_workload_module = importlib.import_module("swe.config.llm_workload")
importlib.import_module("swe.app.tenant_context")

models_spec = importlib.util.spec_from_file_location(
    "swe.app.crons.models",
    _MODELS_FILE,
)
assert models_spec is not None and models_spec.loader is not None
models_module = importlib.util.module_from_spec(models_spec)
sys.modules["swe.app.crons.models"] = models_module
models_spec.loader.exec_module(models_module)


executor_spec = importlib.util.spec_from_file_location(
    "swe.app.crons.executor",
    _EXECUTOR_FILE,
)
assert executor_spec is not None and executor_spec.loader is not None
executor_module = importlib.util.module_from_spec(executor_spec)
sys.modules["swe.app.crons.executor"] = executor_module
executor_spec.loader.exec_module(executor_module)

for _name, _module in _ORIGINAL_MODULES.items():
    if _module is None:
        sys.modules.pop(_name, None)
    else:
        sys.modules[_name] = _module


auth_state_module = importlib.import_module("swe.app.crons.auth_state")


CronExecutor = executor_module.CronExecutor
CronJobRequest = models_module.CronJobRequest
CronJobSpec = models_module.CronJobSpec
DispatchSpec = models_module.DispatchSpec
DispatchTarget = models_module.DispatchTarget
JobRuntimeSpec = models_module.JobRuntimeSpec
ScheduleSpec = models_module.ScheduleSpec


def _get_current_workspace_dir():
    return context_module.get_current_workspace_dir()


def _get_current_source_id():
    return context_module.get_current_source_id()


def _get_current_effective_tenant_id():
    return context_module.get_current_effective_tenant_id()


def _get_current_llm_workload():
    return llm_workload_module.get_current_llm_workload()


class _Runner:
    async def stream_query(self, _req):
        for _item in ():
            yield _item


class _ChannelManager:
    async def send_text(self, **_kwargs):
        return None

    async def send_event(self, **_kwargs):
        return None


def _build_text_job(workspace_dir: str) -> object:
    return CronJobSpec(
        id="job-text",
        name="text job",
        tenant_id="tenant-a",
        source_id="source-a",
        schedule=ScheduleSpec(cron="* * * * *"),
        task_type="text",
        text="hello",
        dispatch=DispatchSpec(
            channel="console",
            target=DispatchTarget(user_id="user-a", session_id="session-a"),
            meta={"workspace_dir": workspace_dir},
        ),
        runtime=JobRuntimeSpec(timeout_seconds=1),
    )


def _build_agent_job(workspace_dir: str, timeout_seconds: int = 1) -> object:
    return CronJobSpec(
        id="job-agent",
        name="agent job",
        tenant_id="tenant-a",
        source_id="source-a",
        schedule=ScheduleSpec(cron="* * * * *"),
        task_type="agent",
        request=CronJobRequest(input=[{"content": [{"text": "ping"}]}]),
        dispatch=DispatchSpec(
            channel="console",
            target=DispatchTarget(user_id="user-a", session_id="session-a"),
            meta={"workspace_dir": workspace_dir},
        ),
        runtime=JobRuntimeSpec(timeout_seconds=timeout_seconds),
    )


def test_job_runtime_defaults_allow_longer_cron_runs() -> None:
    runtime = JobRuntimeSpec()

    assert runtime.timeout_seconds == 7200
    assert runtime.misfire_grace_seconds == 300


def test_execute_binds_workspace_dir_during_job_and_resets_afterward(
    monkeypatch,
):
    observed = {}
    executor = CronExecutor(
        runner=_Runner(),
        channel_manager=_ChannelManager(),
    )
    job = _build_text_job("/tmp/tenant-a/workspaces/alpha")

    async def fake_execute_job(
        _self,
        _job,
        _target_user_id,
        _target_session_id,
        dispatch_meta,
    ):
        observed["workspace_in_job"] = _get_current_workspace_dir()
        observed["meta_workspace"] = dispatch_meta.get("workspace_dir")

    monkeypatch.setattr(CronExecutor, "_execute_job", fake_execute_job)

    asyncio.run(executor.execute(job))

    assert observed["workspace_in_job"] == Path(
        "/tmp/tenant-a/workspaces/alpha",
    )
    assert _get_current_workspace_dir() is None


def test_execute_binds_source_scope_during_job_and_resets_afterward(
    monkeypatch,
):
    observed = {}
    executor = CronExecutor(
        runner=_Runner(),
        channel_manager=_ChannelManager(),
    )
    job = _build_text_job("/tmp/tenant-a/workspaces/alpha")

    async def fake_execute_job(
        _self,
        _job,
        _target_user_id,
        _target_session_id,
        dispatch_meta,
    ):
        observed["source_id"] = _get_current_source_id()
        observed["effective_tenant_id"] = _get_current_effective_tenant_id()
        observed["meta_source"] = dispatch_meta.get("source_id")
        observed["meta_scope"] = dispatch_meta.get("scope_id")

    monkeypatch.setattr(CronExecutor, "_execute_job", fake_execute_job)

    asyncio.run(executor.execute(job))

    assert observed["source_id"] == "source-a"
    assert observed["effective_tenant_id"] is not None
    assert observed["meta_source"] == "source-a"
    assert observed["meta_scope"] == observed["effective_tenant_id"]
    assert _get_current_source_id() is None


def test_build_agent_request_includes_runtime_scope():
    executor = CronExecutor(
        runner=_Runner(),
        channel_manager=_ChannelManager(),
    )
    job = _build_agent_job("/tmp/tenant-a/workspaces/beta")
    job = job.model_copy(
        update={
            "scope_id": context_module.encode_scope_id("tenant-a", "source-a"),
        },
    )

    req = executor._build_agent_request(job, "user-a", "session-a")

    assert req["source_id"] == "source-a"
    assert req["scope_id"] == context_module.encode_scope_id(
        "tenant-a",
        "source-a",
    )


def test_apply_auth_token_uses_runtime_scope(monkeypatch):
    """Cron auth 读取必须使用 scope_id，不能回退到逻辑 tenant。"""
    observed = {}
    executor = CronExecutor(
        runner=_Runner(),
        channel_manager=_ChannelManager(),
    )
    job = _build_agent_job("/tmp/tenant-a/workspaces/beta").model_copy(
        update={
            "scope_id": context_module.encode_scope_id(
                "tenant-a",
                "source-a",
            ),
        },
    )

    def fake_resolve_auth_token_for_execution(*, tenant_id, workspace_dir):
        observed["tenant_id"] = tenant_id
        observed["workspace_dir"] = workspace_dir
        return types.SimpleNamespace(token=None, cookie_header=None)

    monkeypatch.setattr(
        executor_module,
        "resolve_auth_token_for_execution",
        fake_resolve_auth_token_for_execution,
    )

    executor._apply_auth_token(
        job,
        {"workspace_dir": "/tmp/tenant-a/workspaces/beta"},
        {},
    )

    assert observed == {
        "tenant_id": context_module.encode_scope_id("tenant-a", "source-a"),
        "workspace_dir": "/tmp/tenant-a/workspaces/beta",
    }


def test_execute_binds_cron_workload_during_job_and_resets_afterward(
    monkeypatch,
):
    observed = {}
    executor = CronExecutor(
        runner=_Runner(),
        channel_manager=_ChannelManager(),
    )
    job = _build_text_job("/tmp/tenant-a/workspaces/alpha")

    async def fake_execute_job(
        _self,
        _job,
        _target_user_id,
        _target_session_id,
        _dispatch_meta,
    ):
        observed["workload"] = _get_current_llm_workload()

    monkeypatch.setattr(CronExecutor, "_execute_job", fake_execute_job)

    with llm_workload_module.bind_llm_workload(
        llm_workload_module.LLM_WORKLOAD_CHAT,
    ):
        asyncio.run(executor.execute(job))
        assert (
            _get_current_llm_workload()
            == llm_workload_module.LLM_WORKLOAD_CHAT
        )

    assert observed["workload"] == llm_workload_module.LLM_WORKLOAD_CRON
    assert _get_current_llm_workload() == llm_workload_module.LLM_WORKLOAD_CHAT


def test_execute_resets_workspace_dir_after_timeout(monkeypatch):
    observed = {}

    executor = CronExecutor(
        runner=_Runner(),
        channel_manager=_ChannelManager(),
    )
    job = _build_agent_job("/tmp/tenant-a/workspaces/beta")

    async def fake_execute_job(
        _self,
        _job,
        _target_user_id,
        _target_session_id,
        _dispatch_meta,
    ):
        observed["workspace_in_job"] = _get_current_workspace_dir()
        raise asyncio.TimeoutError

    monkeypatch.setattr(CronExecutor, "_execute_job", fake_execute_job)

    with pytest.raises(asyncio.TimeoutError):
        asyncio.run(executor.execute(job))

    assert observed["workspace_in_job"] == Path(
        "/tmp/tenant-a/workspaces/beta",
    )
    assert _get_current_workspace_dir() is None


def test_execute_aborts_agent_job_when_user_info_expired(monkeypatch):
    executor = CronExecutor(
        runner=_Runner(),
        channel_manager=_ChannelManager(),
    )
    job = _build_agent_job("/tmp/tenant-a/workspaces/beta")

    def fake_resolve_auth_token_for_execution(
        *,
        tenant_id=None,
        workspace_dir=None,
    ):
        del tenant_id, workspace_dir
        raise ValueError("cron auth user_info is expired")

    monkeypatch.setattr(
        executor_module,
        "resolve_auth_token_for_execution",
        fake_resolve_auth_token_for_execution,
    )

    with pytest.raises(
        RuntimeError,
        match="please refresh cron auth configuration",
    ):
        asyncio.run(
            executor._execute_job(
                job,
                "user-a",
                "session-a",
                {"workspace_dir": "/tmp/tenant-a/workspaces/beta"},
            ),
        )


def test_execute_allows_agent_job_when_user_info_missing(monkeypatch):
    observed = {}
    executor = CronExecutor(
        runner=_Runner(),
        channel_manager=_ChannelManager(),
    )
    job = _build_agent_job("/tmp/tenant-a/workspaces/beta")

    def fake_resolve_auth_token_for_execution(
        *,
        tenant_id=None,
        workspace_dir=None,
    ):
        del tenant_id, workspace_dir
        return auth_state_module.ResolvedAuthToken(
            token=None,
            expires_at=None,
            reused=False,
            cookie_header=None,
        )

    async def fake_stream_query(req):
        observed["req"] = req
        for _item in ():
            yield _item

    monkeypatch.setattr(
        executor_module,
        "resolve_auth_token_for_execution",
        fake_resolve_auth_token_for_execution,
    )
    monkeypatch.setattr(executor._runner, "stream_query", fake_stream_query)

    asyncio.run(
        executor._execute_job(
            job,
            "user-a",
            "session-a",
            {"workspace_dir": "/tmp/tenant-a/workspaces/beta"},
        ),
    )

    assert observed["req"]["user_id"] == "user-a"
    assert observed["req"]["session_id"] == "session-a"
    assert "auth_token" not in observed["req"]
    assert "cookie" not in observed["req"]


def test_execute_injects_auth_token_and_cookie_into_agent_request(monkeypatch):
    observed = {}
    executor = CronExecutor(
        runner=_Runner(),
        channel_manager=_ChannelManager(),
    )
    job = _build_agent_job("/tmp/tenant-a/workspaces/beta")

    def fake_resolve_auth_token_for_execution(
        *,
        tenant_id=None,
        workspace_dir=None,
    ):
        del tenant_id, workspace_dir
        return auth_state_module.ResolvedAuthToken(
            token="auth-123",
            expires_at=None,
            reused=True,
            cookie_header="foo=bar; com.cmb.dw.rtl.sso.token=auth-123",
        )

    async def fake_stream_query(req):
        observed["req"] = req
        for _item in ():
            yield _item

    monkeypatch.setattr(
        executor_module,
        "resolve_auth_token_for_execution",
        fake_resolve_auth_token_for_execution,
    )
    monkeypatch.setattr(executor._runner, "stream_query", fake_stream_query)

    asyncio.run(
        executor._execute_job(
            job,
            "user-a",
            "session-a",
            {"workspace_dir": "/tmp/tenant-a/workspaces/beta"},
        ),
    )

    assert observed["req"]["auth_token"] == "auth-123"
    assert observed["req"]["cookie"] == (
        "foo=bar; com.cmb.dw.rtl.sso.token=auth-123"
    )


def test_execute_exposes_tenant_process_limit_policy_inside_cron_context(
    monkeypatch,
    tmp_path: Path,
):
    from swe.config.context import encode_scope_id
    from swe.security.process_limits import (
        resolve_current_process_limit_policy,
    )

    observed = {}
    executor = CronExecutor(
        runner=_Runner(),
        channel_manager=_ChannelManager(),
    )
    job = _build_text_job("/tmp/tenant-a/workspaces/alpha")

    scope_id = encode_scope_id("tenant-a", "source-a")
    tenant_dir = tmp_path / scope_id
    tenant_dir.mkdir(parents=True, exist_ok=True)
    save_config(
        Config.model_validate(
            {
                "security": {
                    "process_limits": {
                        "enabled": True,
                        "shell": True,
                        "mcp_stdio": True,
                        "cpu_time_limit_seconds": 3,
                    },
                },
            },
        ),
        tenant_dir / "config.json",
    )

    async def fake_execute_job(
        _self,
        _job,
        _target_user_id,
        _target_session_id,
        _dispatch_meta,
    ):
        policy = resolve_current_process_limit_policy("shell")
        observed["tenant_id"] = policy.tenant_id
        observed["enabled"] = policy.enabled
        observed["cpu"] = policy.cpu_time_limit_seconds

    monkeypatch.setattr(CronExecutor, "_execute_job", fake_execute_job)
    monkeypatch.setattr("swe.constant.WORKING_DIR", tmp_path)
    monkeypatch.setattr("swe.config.utils.WORKING_DIR", tmp_path)

    asyncio.run(executor.execute(job))

    assert observed == {
        "tenant_id": scope_id,
        "enabled": True,
        "cpu": 3,
    }
