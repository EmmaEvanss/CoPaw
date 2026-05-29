# -*- coding: utf-8 -*-
"""Internal reload API source-scope regression tests."""

import base64
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from swe.app.routers.internal import router
from swe.config.context import encode_scope_id


def _build_client(manager) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.state.multi_agent_manager = manager
    return TestClient(app)


def test_internal_reload_requires_source_id() -> None:
    manager = SimpleNamespace(reload_agent=AsyncMock(return_value=True))
    client = _build_client(manager)

    response = client.post(
        "/internal/agents/default/reload?tenant_id=tenant-a",
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "source_id is required"
    manager.reload_agent.assert_not_called()


def test_internal_reload_resolves_scope_id() -> None:
    manager = SimpleNamespace(reload_agent=AsyncMock(return_value=True))
    client = _build_client(manager)

    response = client.post(
        "/internal/agents/default/reload"
        "?tenant_id=tenant-a&source_id=source-a",
    )

    assert response.status_code == 200
    assert response.json()["tenant_id"] == "tenant-a"
    assert response.json()["scope_id"] == encode_scope_id(
        "tenant-a",
        "source-a",
    )
    manager.reload_agent.assert_awaited_once_with(
        "default",
        tenant_id=encode_scope_id("tenant-a", "source-a"),
    )


def test_internal_reload_rejects_invalid_source_id() -> None:
    manager = SimpleNamespace(reload_agent=AsyncMock(return_value=True))
    client = _build_client(manager)

    response = client.post(
        "/internal/agents/default/reload"
        "?tenant_id=tenant-a&source_id=../bad",
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid source_id"
    manager.reload_agent.assert_not_called()


def test_internal_cron_callback_dispatches_job_param_tenant() -> None:
    cron_manager = SimpleNamespace(run_job=AsyncMock())
    manager = SimpleNamespace(
        get_agent=AsyncMock(
            return_value=SimpleNamespace(cron_manager=cron_manager),
        ),
    )
    client = _build_client(manager)
    payload = {
        "tenant_id": "runtime-scope",
        "agent_id": "default",
        "task_type": "job",
        "job_id": "job-1",
    }
    job_param = base64.urlsafe_b64encode(
        json.dumps(payload).encode(),
    ).decode()

    response = client.post(
        "/internal/cron/callback",
        json={"jobParam": job_param},
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "task_type": "job"}
    manager.get_agent.assert_awaited_once_with(
        "default",
        tenant_id="runtime-scope",
    )
    cron_manager.run_job.assert_awaited_once_with(
        "job-1",
        is_manual=False,
    )
