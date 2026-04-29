# -*- coding: utf-8 -*-
def test_publish_request_defaults():
    from market.marketplace.schemas import PublishSkillRequest

    req = PublishSkillRequest(
        name="my_skill",
        description="desc",
        creator_id="user1",
        creator_name="User One",
        skill_json={"name": "my_skill"},
        skill_md="# My Skill",
    )
    assert req.category_id is None
    assert req.bbk_ids == []


def test_distribute_request_all():
    from market.marketplace.schemas import DistributeRequest

    req = DistributeRequest(target_type="all", target_values=[])
    assert req.target_type == "all"


def test_distribute_request_rejects_invalid_type():
    from market.marketplace.schemas import DistributeRequest
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        DistributeRequest(target_type="invalid", target_values=[])


def test_market_skill_response_fields():
    from market.marketplace.schemas import MarketSkillResponse

    r = MarketSkillResponse(
        item_id="id1",
        name="skill",
        description="",
        version="1.0.0",
        creator_id="u1",
        creator_name="U",
        category_id=None,
        bbk_ids=[],
        status="active",
        created_at=None,
        updated_at=None,
        call_count=0,
        user_count=0,
    )
    assert r.item_id == "id1"
