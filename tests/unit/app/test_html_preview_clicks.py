# -*- coding: utf-8 -*-
"""HTML 预览点击统计模块测试。"""

import importlib
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from swe.app.html_preview_clicks.models import (
    HtmlPreviewClickEventCreate,
    HtmlPreviewClickSummaryItem,
)
from swe.app.html_preview_clicks.router import (
    router as html_preview_click_router,
)
from swe.app.html_preview_clicks.store import HtmlPreviewClickStore

html_preview_router_module = importlib.import_module(
    "swe.app.html_preview_clicks.router",
)


@pytest.fixture
def mock_db():
    """构造一个可编排返回值的数据库桩。"""
    db = MagicMock()
    db.is_connected = True
    db.execute = AsyncMock(return_value=1)
    db.fetch_all = AsyncMock()
    return db


@pytest.mark.asyncio
async def test_create_event_writes_click_detail(mock_db):
    """点击明细应按一期字段写入数据库。"""
    store = HtmlPreviewClickStore(mock_db)
    clicked_at = datetime(2026, 5, 30, 10, 0, 0)

    await store.create_event(
        HtmlPreviewClickEventCreate(
            source_id="copaw",
            user_id="u-1",
            bbk_id="branch-1",
            cron_task_id="task-1",
            cron_task_name="存款到期提醒",
            file_url="https://example.com/a.html",
            file_name="存款到期完整客户名单.html",
            button_id="follow",
            button_name="立即跟进",
            button_text="立即跟进",
            clicked_at=clicked_at,
        ),
    )

    query, params = mock_db.execute.call_args[0]
    assert "INSERT INTO swe_html_preview_click_events" in query
    assert "bbk_id" in query
    assert params == (
        "copaw",
        "u-1",
        "branch-1",
        "task-1",
        "存款到期提醒",
        "https://example.com/a.html",
        "存款到期完整客户名单.html",
        "follow",
        "立即跟进",
        "立即跟进",
        clicked_at,
    )


@pytest.mark.asyncio
async def test_list_summary_filters_by_source_and_time(mock_db):
    """聚合查询应带上来源、时间范围并按点击次数排序。"""
    clicked_at = datetime(2026, 5, 30, 11, 0, 0)
    mock_db.fetch_all.return_value = [
        {
            "button_label": "立即跟进",
            "button_id": "follow",
            "button_name": "立即跟进",
            "button_text": "立即跟进",
            "bbk_id": "branch-1",
            "cron_task_id": "task-1",
            "cron_task_name": "存款到期提醒",
            "file_url": "https://example.com/a.html",
            "file_name": "a.html",
            "click_count": 3,
            "last_clicked_at": clicked_at,
        },
    ]
    store = HtmlPreviewClickStore(mock_db)

    items = await store.list_summary(
        source_id="copaw",
        start_time=datetime(2026, 5, 30, 0, 0, 0),
        end_time=datetime(2026, 5, 30, 23, 59, 59),
        bbk_ids=["branch-1", "branch-2"],
        limit=50,
    )

    query, params = mock_db.fetch_all.call_args[0]
    assert "source_id <=> %s" in query
    assert "clicked_at >= %s" in query
    assert "clicked_at <= %s" in query
    assert "bbk_id IN (%s, %s)" in query
    assert "ORDER BY click_count DESC, last_clicked_at DESC" in query
    assert params[0] == "copaw"
    assert "branch-1" in params
    assert "branch-2" in params
    assert len(items) == 1
    assert items[0].click_count == 3
    assert items[0].last_clicked_at == clicked_at


def test_create_route_enriches_source_and_user(monkeypatch):
    """路由应从请求上下文补齐来源和用户标识。"""

    class _FakeService:
        async def create_event(self, event):
            assert event.source_id == "copaw"
            assert event.user_id == "user-9"
            assert event.bbk_id == "branch-1"
            assert event.file_url == "https://example.com/a.html"

    app = FastAPI()

    @app.middleware("http")
    async def _inject_state(request: Request, call_next):
        request.state.source_id = "copaw"
        request.state.user_id = "user-9"
        request.state.bbk = "branch-1"
        return await call_next(request)

    app.include_router(html_preview_click_router)
    monkeypatch.setattr(html_preview_router_module, "_service", _FakeService())

    client = TestClient(app)
    response = client.post(
        "/html-preview/events",
        json={
            "file_url": "https://example.com/a.html",
            "button_id": "follow",
        },
    )

    assert response.status_code == 200
    assert response.json()["success"] is True


def test_summary_route_returns_items(monkeypatch):
    """聚合路由应返回服务层查询结果。"""

    class _FakeService:
        async def list_summary(self, **kwargs):
            assert kwargs["source_id"] == "copaw"
            assert kwargs["bbk_ids"] == ["branch-1", "branch-2"]
            assert kwargs["limit"] == 20
            return [
                HtmlPreviewClickSummaryItem(
                    button_label="立即跟进",
                    button_id="follow",
                    click_count=2,
                ),
            ]

    app = FastAPI()

    @app.middleware("http")
    async def _inject_state(request: Request, call_next):
        request.state.source_id = "copaw"
        return await call_next(request)

    app.include_router(html_preview_click_router)
    monkeypatch.setattr(html_preview_router_module, "_service", _FakeService())

    client = TestClient(app)
    response = client.get(
        "/html-preview/events/summary",
        params={"limit": 20, "bbk_ids": "branch-1, branch-2"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["items"][0]["button_id"] == "follow"
