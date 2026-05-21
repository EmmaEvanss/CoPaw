# -*- coding: utf-8 -*-
import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock


def _make_service(tmp_path, mock_db=None):
    from market.marketplace.service import MarketplaceService

    if mock_db is None:
        mock_db = AsyncMock()
        mock_db.is_connected = True
        mock_db.fetch_one = AsyncMock(return_value=None)
        mock_db.fetch_all = AsyncMock(return_value=[])
    return MarketplaceService(
        db=mock_db,
        marketplace_root=tmp_path / "market",
        swe_root=tmp_path / "swe",
    )


@pytest.mark.asyncio
async def test_publish_skill_creates_index_entry(tmp_path):
    from market.marketplace.schemas import PublishSkillRequest

    svc = _make_service(tmp_path)
    req = PublishSkillRequest(
        name="skill_a",
        description="desc",
        creator_id="user1",
        creator_name="User One",
        skill_json={"name": "skill_a"},
        skill_md="# Skill A",
    )
    item = await svc.publish_skill("src_a", req)
    assert item.name == "skill_a"
    assert item.version == "1.0.0"
    assert item.status == "active"
    # index.json should exist
    index_path = tmp_path / "market" / "src_a" / "index.json"
    assert index_path.exists()
    data = json.loads(index_path.read_text())
    assert len(data["items"]) == 1


@pytest.mark.asyncio
async def test_publish_skill_increments_version_on_republish(tmp_path):
    from market.marketplace.schemas import PublishSkillRequest

    svc = _make_service(tmp_path)
    req = PublishSkillRequest(
        name="skill_a",
        description="",
        creator_id="u1",
        creator_name="",
        skill_json={},
        skill_md="",
    )
    await svc.publish_skill("src_a", req)
    item2 = await svc.publish_skill("src_a", req)
    assert item2.version == "1.0.1"


@pytest.mark.asyncio
async def test_unpublish_skill_sets_inactive(tmp_path):
    from market.marketplace.schemas import PublishSkillRequest

    svc = _make_service(tmp_path)
    req = PublishSkillRequest(
        name="skill_b",
        description="",
        creator_id="u1",
        creator_name="",
        skill_json={},
        skill_md="",
    )
    item = await svc.publish_skill("src_a", req)
    await svc.unpublish_skill("src_a", item.item_id, "u1", "User One")
    items = await svc.list_skills("src_a", user_bbk_id="100")
    assert all(
        i.status == "inactive" for i in items if i.item_id == item.item_id
    )


@pytest.mark.asyncio
async def test_list_skills_filters_by_bbk_id(tmp_path):
    from market.marketplace.schemas import PublishSkillRequest

    svc = _make_service(tmp_path)
    # skill visible to all (bbk_ids=[])
    req_all = PublishSkillRequest(
        name="skill_all",
        description="",
        creator_id="u1",
        creator_name="",
        skill_json={},
        skill_md="",
        bbk_ids=[],
    )
    # skill visible only to bbk_id=200
    req_200 = PublishSkillRequest(
        name="skill_200",
        description="",
        creator_id="u1",
        creator_name="",
        skill_json={},
        skill_md="",
        bbk_ids=["200"],
    )
    await svc.publish_skill("src_a", req_all)
    await svc.publish_skill("src_a", req_200)
    # bbk_id=100 (总行) sees all
    items_100 = await svc.list_skills("src_a", user_bbk_id="100")
    assert len(items_100) == 2
    # bbk_id=300 sees only skill_all (bbk_ids=[])
    items_300 = await svc.list_skills("src_a", user_bbk_id="300")
    assert len(items_300) == 1
    assert items_300[0].name == "skill_all"


@pytest.mark.asyncio
async def test_get_skill_detail_returns_item(tmp_path):
    from market.marketplace.schemas import PublishSkillRequest

    svc = _make_service(tmp_path)
    req = PublishSkillRequest(
        name="skill_c",
        description="",
        creator_id="u1",
        creator_name="",
        skill_json={},
        skill_md="",
    )
    item = await svc.publish_skill("src_a", req)
    detail = await svc.get_skill_detail(
        "src_a",
        item.item_id,
        user_bbk_id="100",
    )
    assert detail is not None
    assert detail.item_id == item.item_id


@pytest.mark.asyncio
async def test_get_skill_detail_returns_none_for_unknown(tmp_path):
    svc = _make_service(tmp_path)
    detail = await svc.get_skill_detail(
        "src_a",
        "nonexistent-id",
        user_bbk_id="100",
    )
    assert detail is None


@pytest.mark.asyncio
async def test_get_my_skills_returns_time_fields(tmp_path):
    """get_my_skills 应返回 created_at 和 updated_at 字段."""
    from market.marketplace.service import get_user_skills_dir

    svc = _make_service(tmp_path)
    user_id = "test_user"
    source_id = "test_source"
    agent_id = "default"

    # 创建用户技能目录
    skills_dir = get_user_skills_dir(
        tmp_path / "swe",
        user_id,
        agent_id,
        source_id,
    )
    skill_dir = skills_dir / "test_skill"
    skill_dir.mkdir(parents=True)

    # 写入 skill.json 含时间字段
    skill_data = {
        "name": "Test Skill",
        "source": "customized",
        "description": "A test skill",
        "created_at": "2025-05-14T10:00:00+00:00",
        "updated_at": "2025-05-14T12:00:00+00:00",
    }
    (skill_dir / "skill.json").write_text(
        json.dumps(skill_data, ensure_ascii=False),
        encoding="utf-8",
    )
    (skill_dir / "SKILL.md").write_text("# Test Skill", encoding="utf-8")

    # 调用服务
    result = await svc.get_my_skills(source_id, user_id, agent_id)

    assert len(result) == 1
    assert result[0].skill_name == "test_skill"
    assert result[0].created_at == "2025-05-14T10:00:00+00:00"
    assert result[0].updated_at == "2025-05-14T12:00:00+00:00"


@pytest.mark.asyncio
async def test_get_my_skills_handles_missing_time_fields(tmp_path):
    """get_my_skills 应处理缺失的时间字段."""
    from market.marketplace.service import get_user_skills_dir

    svc = _make_service(tmp_path)
    user_id = "test_user"
    source_id = "test_source"
    agent_id = "default"

    # 创建用户技能目录
    skills_dir = get_user_skills_dir(
        tmp_path / "swe",
        user_id,
        agent_id,
        source_id,
    )
    skill_dir = skills_dir / "old_skill"
    skill_dir.mkdir(parents=True)

    # 写入 skill.json 不含时间字段（模拟旧技能）
    skill_data = {
        "name": "Old Skill",
        "source": "customized",
        "description": "An old skill without time fields",
    }
    (skill_dir / "skill.json").write_text(
        json.dumps(skill_data, ensure_ascii=False),
        encoding="utf-8",
    )
    (skill_dir / "SKILL.md").write_text("# Old Skill", encoding="utf-8")

    # 调用服务
    result = await svc.get_my_skills(source_id, user_id, agent_id)

    assert len(result) == 1
    assert result[0].skill_name == "old_skill"
    assert result[0].created_at is None
    assert result[0].updated_at is None
