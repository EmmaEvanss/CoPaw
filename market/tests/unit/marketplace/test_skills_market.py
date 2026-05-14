# -*- coding: utf-8 -*-
import asyncio
import json
import pytest
from unittest.mock import AsyncMock
from fastapi.testclient import TestClient


def _make_app(tmp_path):
    from fastapi import FastAPI
    from market.app.routers.skills_market import router
    from market.marketplace.service import MarketplaceService
    from market.database.connection import DatabaseConnection

    mock_db = AsyncMock(spec=DatabaseConnection)
    mock_db.is_connected = True
    mock_db.execute = AsyncMock(return_value=1)
    mock_db.fetch_one = AsyncMock(return_value=None)
    mock_db.fetch_all = AsyncMock(return_value=[])

    svc = MarketplaceService(
        db=mock_db,
        marketplace_root=tmp_path / "market",
        swe_root=tmp_path / "swe",
    )
    app = FastAPI()
    app.state.marketplace = svc
    app.include_router(router, prefix="/api")
    return app


def test_publish_skill_returns_201(tmp_path):
    app = _make_app(tmp_path)
    client = TestClient(app)
    payload = {
        "name": "skill_x",
        "description": "test",
        "creator_id": "u1",
        "creator_name": "User",
        "skill_json": {"name": "skill_x"},
        "skill_md": "# Skill X",
    }
    resp = client.post(
        "/api/market/skills",
        json=payload,
        headers={"X-Source-Id": "src_a", "X-Manager": "true"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "skill_x"
    assert data["version"] == "1.0.0"


def test_publish_skill_non_manager_returns_403(tmp_path):
    app = _make_app(tmp_path)
    client = TestClient(app)
    payload = {
        "name": "skill_x",
        "description": "",
        "creator_id": "u1",
        "creator_name": "",
        "skill_json": {},
        "skill_md": "",
    }
    resp = client.post(
        "/api/market/skills",
        json=payload,
        headers={"X-Source-Id": "src_a"},
    )
    assert resp.status_code == 403


def test_unpublish_skill_returns_204(tmp_path):
    from market.marketplace.schemas import PublishSkillRequest

    app = _make_app(tmp_path)
    svc = app.state.marketplace
    req = PublishSkillRequest(
        name="skill_y",
        description="",
        creator_id="u1",
        creator_name="",
        skill_json={},
        skill_md="",
    )
    item = asyncio.run(svc.publish_skill("src_a", req))
    client = TestClient(app)
    resp = client.delete(
        f"/api/market/skills/{item.item_id}",
        headers={
            "X-Source-Id": "src_a",
            "X-Manager": "true",
            "X-User-Id": "u1",
            "X-User-Name": "User",
        },
    )
    assert resp.status_code == 204


def test_unpublish_skill_not_found_returns_404(tmp_path):
    app = _make_app(tmp_path)
    client = TestClient(app)
    resp = client.delete(
        "/api/market/skills/nonexistent-id",
        headers={
            "X-Source-Id": "src_a",
            "X-Manager": "true",
            "X-User-Id": "u1",
            "X-User-Name": "User",
        },
    )
    assert resp.status_code == 404


def test_distribute_skill_returns_200(tmp_path):
    from market.marketplace.schemas import PublishSkillRequest

    app = _make_app(tmp_path)
    svc = app.state.marketplace
    req = PublishSkillRequest(
        name="skill_z",
        description="",
        creator_id="u1",
        creator_name="",
        skill_json={},
        skill_md="",
    )
    item = asyncio.run(svc.publish_skill("src_a", req))
    svc.db.fetch_all = AsyncMock(
        return_value=[
            {"tenant_id": "user1", "tenant_name": "User One", "bbk_id": "200"},
        ],
    )
    client = TestClient(app)
    resp = client.post(
        f"/api/market/skills/{item.item_id}/distribute",
        json={"target_type": "all", "target_values": []},
        headers={
            "X-Source-Id": "src_a",
            "X-Manager": "true",
            "X-User-Id": "u1",
            "X-User-Name": "User",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["distributed_count"] == 1


def test_publish_skill_missing_source_id_returns_400(tmp_path):
    app = _make_app(tmp_path)
    client = TestClient(app)
    payload = {
        "name": "skill_x",
        "description": "",
        "creator_id": "u1",
        "creator_name": "",
        "skill_json": {},
        "skill_md": "",
    }
    resp = client.post(
        "/api/market/skills",
        json=payload,
        headers={"X-Manager": "true"},
    )
    assert resp.status_code == 400


def test_publish_skill_upload_reactivates_inactive_skill(tmp_path):
    """验证下架后重新上传同名技能可以成功上架（复用条目，版本号递增）."""
    import io
    import zipfile
    from market.marketplace.fs import load_index

    app = _make_app(tmp_path)
    svc = app.state.marketplace
    client = TestClient(app)

    # 第一步：通过 JSON API 创建技能
    payload = {
        "name": "test_skill",
        "description": "initial",
        "creator_id": "u1",
        "creator_name": "User",
        "skill_json": {"name": "test_skill"},
        "skill_md": "# Test Skill",
    }
    resp = client.post(
        "/api/market/skills",
        json=payload,
        headers={"X-Source-Id": "src_a", "X-Manager": "true"},
    )
    assert resp.status_code == 201
    item_id = resp.json()["item_id"]
    assert resp.json()["version"] == "1.0.0"

    # 第二步：下架技能
    resp = client.delete(
        f"/api/market/skills/{item_id}",
        headers={
            "X-Source-Id": "src_a",
            "X-Manager": "true",
            "X-User-Id": "u1",
            "X-User-Name": "User",
        },
    )
    assert resp.status_code == 204

    # 验证状态已变为 inactive
    items = load_index(svc.marketplace_root, "src_a")
    inactive_item = next(i for i in items if i.item_id == item_id)
    assert inactive_item.status == "inactive"

    # 第三步：创建同名技能的 zip 文件并上传
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as zf:
        zf.writestr(
            "test_skill/skill.json",
            json.dumps({"name": "test_skill", "description": "updated"}),
        )
        zf.writestr("test_skill/SKILL.md", "# Updated Skill")

    zip_buffer.seek(0)
    resp = client.post(
        "/api/market/skills/publish-upload",
        files={"file": ("skill.zip", zip_buffer, "application/zip")},
        headers={
            "X-Source-Id": "src_a",
            "X-Manager": "true",
            "X-User-Id": "u1",
            "X-User-Name": "User",
        },
    )
    assert resp.status_code == 201
    data = resp.json()

    # 验证：成功上传，没有冲突，版本号递增
    assert "test_skill" in data["imported"]
    assert data["count"] == 1
    assert data.get("conflicts") is None or len(data.get("conflicts", [])) == 0

    # 验证条目被复用，状态重新激活，版本号递增
    items = load_index(svc.marketplace_root, "src_a")
    reactivated_item = next(i for i in items if i.item_id == item_id)
    assert reactivated_item.status == "active"
    assert reactivated_item.version == "1.0.1"  # patch 版本递增
