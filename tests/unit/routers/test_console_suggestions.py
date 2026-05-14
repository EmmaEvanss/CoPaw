# -*- coding: utf-8 -*-
"""Console 猜你想问接口的回归测试。"""

from __future__ import annotations

import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.swe.app.routers import console as console_router
from src.swe.app.suggestions import store_qa_content


@pytest.mark.asyncio
async def test_qa_content_endpoint_queries_by_user_message() -> None:
    chat_id = f"chat-{uuid.uuid4()}"
    await store_qa_content(
        chat_id=chat_id,
        user_message="帮我总结",
        assistant_response="总结完成",
        tenant_id=None,
    )

    app = FastAPI()
    app.include_router(console_router.router)
    client = TestClient(app)

    response = client.post(
        "/console/suggestions/qa-content",
        json={
            "chat_id": chat_id,
            "user_message": "帮我总结",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "qa_content": {
            "user_message": "帮我总结",
            "assistant_response": "总结完成",
        },
    }


def test_qa_content_endpoint_returns_empty_for_unknown_message() -> None:
    app = FastAPI()
    app.include_router(console_router.router)
    client = TestClient(app)

    response = client.post(
        "/console/suggestions/qa-content",
        json={
            "chat_id": f"chat-{uuid.uuid4()}",
            "user_message": "不存在的问题",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "success": False,
        "qa_content": None,
    }
