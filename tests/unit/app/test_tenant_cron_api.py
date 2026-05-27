# -*- coding: utf-8 -*-
"""Tenant injection regression tests for cron APIs."""

import importlib.util
import sys
import types
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from swe.config.context import encode_scope_id

SRC_ROOT = Path(__file__).parent.parent.parent.parent / "src"
sys.path.insert(0, str(SRC_ROOT))

_ORIGINAL_MODULES = {
    name: sys.modules.get(name)
    for name in [
        "swe.app.crons",
        "swe.app.channels.schema",
        "swe.app.crons.models",
        "swe.app.crons.manager",
        "swe.app.crons.api",
    ]
}

if "swe.app.crons" not in sys.modules:
    pkg = types.ModuleType("swe.app.crons")
    pkg.__path__ = [str(SRC_ROOT / "swe" / "app" / "crons")]
    sys.modules["swe.app.crons"] = pkg

channels_schema_module = types.ModuleType("swe.app.channels.schema")
channels_schema_module.ChannelType = str
channels_schema_module.DEFAULT_CHANNEL = "console"
sys.modules["swe.app.channels.schema"] = channels_schema_module

models_spec = importlib.util.spec_from_file_location(
    "swe.app.crons.models",
    SRC_ROOT / "swe" / "app" / "crons" / "models.py",
)
assert models_spec is not None and models_spec.loader is not None
models_module = importlib.util.module_from_spec(models_spec)
sys.modules["swe.app.crons.models"] = models_module
models_spec.loader.exec_module(models_module)

manager_module = types.ModuleType("swe.app.crons.manager")
manager_module.CronManager = object
sys.modules["swe.app.crons.manager"] = manager_module

api_spec = importlib.util.spec_from_file_location(
    "swe.app.crons.api",
    SRC_ROOT / "swe" / "app" / "crons" / "api.py",
)
assert api_spec is not None and api_spec.loader is not None
api_module = importlib.util.module_from_spec(api_spec)
sys.modules["swe.app.crons.api"] = api_module
api_spec.loader.exec_module(api_module)

for _name, _module in _ORIGINAL_MODULES.items():
    if _module is None:
        sys.modules.pop(_name, None)
    else:
        sys.modules[_name] = _module


class _TenantStateMiddleware:
    def __init__(
        self,
        app,
        tenant_id: str,
        source_id: str,
        user_name: str,
        bbk_id: str,
    ):
        self.app = app
        self.tenant_id = tenant_id
        self.source_id = source_id
        self.user_name = user_name
        self.bbk_id = bbk_id

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            scope.setdefault("state", {})
            scope["state"]["tenant_id"] = self.tenant_id
            scope["state"]["source_id"] = self.source_id
            scope["state"]["scope_id"] = encode_scope_id(
                self.tenant_id,
                self.source_id,
            )
            scope["state"]["user_name"] = self.user_name
            scope["state"]["bbk_id"] = self.bbk_id
        await self.app(scope, receive, send)


class _Manager:
    def __init__(self):
        self.created = []

    async def create_or_replace_job(self, spec):
        self.created.append(spec)

    async def list_jobs(self):
        return []

    async def get_job(self, job_id):
        return None

    def get_state(self, job_id):
        return types.SimpleNamespace(model_dump=lambda mode=None: {})


class _Provider:
    def __init__(self, models: list[str]):
        self._models = set(models)

    def has_model(self, model_id: str) -> bool:
        return model_id in self._models


class _ProviderManager:
    def __init__(self, providers: dict[str, _Provider]):
        self._providers = providers

    def get_provider(self, provider_id: str):
        return self._providers.get(provider_id)


CronJobSpec = models_module.CronJobSpec
ScheduleSpec = models_module.ScheduleSpec
DispatchSpec = models_module.DispatchSpec
DispatchTarget = models_module.DispatchTarget
JobRuntimeSpec = models_module.JobRuntimeSpec
CronJobRequest = models_module.CronJobRequest


def _job_spec(
    job_id: str = "",
    *,
    task_type: str = "agent",
    model_slot: dict | None = None,
):
    payload = {
        "id": job_id,
        "name": "tenant cron",
        "enabled": True,
        "tenant_id": None,
        "schedule": ScheduleSpec(cron="* * * * *").model_dump(mode="json"),
        "dispatch": DispatchSpec(
            channel="console",
            target=DispatchTarget(user_id="user-a", session_id="session-a"),
            meta={},
        ).model_dump(mode="json"),
        "runtime": JobRuntimeSpec().model_dump(mode="json"),
        "meta": {},
    }
    if task_type == "agent":
        payload.update(
            {
                "task_type": "agent",
                "request": CronJobRequest(
                    input=[{"content": [{"type": "text", "text": "ping"}]}],
                ).model_dump(mode="json"),
            },
        )
    else:
        payload.update(
            {
                "task_type": "text",
                "text": "hello cron",
            },
        )
    if model_slot is not None:
        payload["model_slot"] = model_slot
    return payload


def _install_provider_manager(
    providers: dict[str, _Provider],
):
    api_module.ProviderManager = types.SimpleNamespace(  # type: ignore[attr-defined]
        ensure_tenant_provider_storage=lambda _tenant_id: None,
        get_instance=lambda _tenant_id: _ProviderManager(providers),
    )


def _model_slot(
    provider_id: str = "openai",
    model: str = "gpt-5.4",
) -> dict[str, str]:
    return {
        "provider_id": provider_id,
        "model": model,
    }


def _build_client(manager: _Manager) -> TestClient:
    app = FastAPI()
    app.add_middleware(
        _TenantStateMiddleware,
        tenant_id="tenant-a",
        source_id="source-a",
        user_name="Alice",
        bbk_id="1001",
    )
    app.include_router(api_module.router)

    async def _get_mgr():
        return manager

    app.dependency_overrides[api_module.get_cron_manager] = _get_mgr
    return TestClient(app)


def test_create_job_injects_request_tenant_id():
    manager = _Manager()
    client = _build_client(manager)

    response = client.post("/cron/jobs", json=_job_spec())

    assert response.status_code == 200
    assert manager.created[0].tenant_id == "tenant-a"
    assert manager.created[0].source_id == "source-a"
    assert manager.created[0].scope_id == encode_scope_id(
        "tenant-a",
        "source-a",
    )
    assert manager.created[0].tenant_name == "Alice"
    assert manager.created[0].bbk_id == "1001"


def test_replace_job_overrides_payload_tenant_with_request_tenant():
    manager = _Manager()
    client = _build_client(manager)

    response = client.put(
        "/cron/jobs/job-1",
        json={**_job_spec("job-1"), "tenant_id": "other-tenant"},
    )

    assert response.status_code == 200
    assert manager.created[0].tenant_id == "tenant-a"
    assert manager.created[0].source_id == "source-a"
    assert manager.created[0].scope_id == encode_scope_id(
        "tenant-a",
        "source-a",
    )


def test_create_job_persists_model_slot():
    manager = _Manager()
    client = _build_client(manager)
    _install_provider_manager(
        {
            "openai": _Provider(["gpt-5.4"]),
        },
    )

    response = client.post(
        "/cron/jobs",
        json=_job_spec(model_slot=_model_slot()),
    )

    assert response.status_code == 200
    assert manager.created[0].model_slot is not None
    assert manager.created[0].model_slot.provider_id == "openai"
    assert manager.created[0].model_slot.model == "gpt-5.4"
    assert response.json()["model_slot"] == _model_slot()


def test_create_job_rejects_unknown_model_slot_provider():
    manager = _Manager()
    client = _build_client(manager)
    _install_provider_manager(
        {
            "openai": _Provider(["gpt-5.4"]),
        },
    )

    response = client.post(
        "/cron/jobs",
        json=_job_spec(
            model_slot=_model_slot(provider_id="missing-provider"),
        ),
    )

    assert response.status_code == 404
    assert (
        response.json()["detail"] == "Provider 'missing-provider' not found."
    )
    assert manager.created == []


def test_replace_job_rejects_unknown_model_slot_model():
    manager = _Manager()
    client = _build_client(manager)
    _install_provider_manager(
        {
            "openai": _Provider(["gpt-5.4"]),
        },
    )

    response = client.put(
        "/cron/jobs/job-1",
        json=_job_spec(
            "job-1",
            model_slot=_model_slot(model="gpt-4.1"),
        ),
    )

    assert response.status_code == 400
    assert (
        response.json()["detail"]
        == "Model 'gpt-4.1' not found in provider 'openai'."
    )
    assert manager.created == []


def test_create_text_job_clears_model_slot():
    manager = _Manager()
    client = _build_client(manager)
    _install_provider_manager(
        {
            "openai": _Provider(["gpt-5.4"]),
        },
    )

    response = client.post(
        "/cron/jobs",
        json=_job_spec(
            task_type="text",
            model_slot=_model_slot(),
        ),
    )

    assert response.status_code == 200
    assert manager.created[0].task_type == "text"
    assert manager.created[0].model_slot is None
    assert response.json().get("model_slot") is None
