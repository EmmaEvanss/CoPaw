# -*- coding: utf-8 -*-
"""Tests for Monitor tracing chat mapping API."""

from fastapi import FastAPI
from fastapi import Request
from fastapi.testclient import TestClient

from monitor.app.routers import tracing as tracing_router


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(tracing_router.router)
    return TestClient(app)


def test_get_user_chats_requires_user_id() -> None:
    client = _client()

    response = client.get("/monitor/tracing/chats")

    assert response.status_code == 422


def test_get_user_chats_returns_target_user_chats(monkeypatch) -> None:
    captured: dict[str, object] = {}

    async def fake_fetch(request, target_user_id: str, channel: str | None):
        captured["target_user_id"] = target_user_id
        captured["channel"] = channel
        return [
            {
                "id": "chat-1",
                "session_id": "cron-task:job-1",
                "user_id": "target-user",
                "channel": "console",
                "name": "任务会话",
            },
        ]

    monkeypatch.setattr(tracing_router, "_fetch_swe_chats", fake_fetch)
    client = _client()

    response = client.get(
        "/monitor/tracing/chats",
        params={"user_id": "target-user", "channel": "console"},
    )

    assert response.status_code == 200
    assert response.json()[0]["id"] == "chat-1"
    assert captured == {
        "target_user_id": "target-user",
        "channel": "console",
    }


def test_forward_swe_headers_overrides_identity_to_target_user() -> None:
    client = _client()

    @client.app.get("/capture-headers")
    async def capture_headers(request: Request):
        return tracing_router._forward_swe_headers(request, "target-user")

    response = client.get(
        "/capture-headers",
        headers={
            "Authorization": "Bearer token",
            "X-Agent-Id": "agent-a",
            "X-User-Id": "viewer-user",
            "X-Tenant-Id": "viewer-user",
            "X-Source-Id": "CMSJY",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "Authorization": "Bearer token",
        "X-Agent-Id": "agent-a",
        "X-Source-Id": "CMSJY",
        "X-User-Id": "target-user",
        "X-Tenant-Id": "target-user",
    }
