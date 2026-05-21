# -*- coding: utf-8 -*-
"""MySkillItem schema tests."""

import pytest
from market.marketplace.schemas import MySkillItem


def test_my_skill_item_has_time_fields():
    """MySkillItem should include created_at and updated_at fields."""
    item = MySkillItem(
        skill_name="test_skill",
        display_name="Test Skill",
        source="customized",
        description="A test skill",
        version="1.0.0",
        enabled=True,
        created_at="2025-05-14T10:00:00Z",
        updated_at="2025-05-14T12:00:00Z",
    )
    assert item.created_at == "2025-05-14T10:00:00Z"
    assert item.updated_at == "2025-05-14T12:00:00Z"


def test_my_skill_item_time_fields_optional():
    """Time fields should be optional for backward compatibility."""
    item = MySkillItem(
        skill_name="test_skill",
        display_name="Test Skill",
        source="customized",
    )
    assert item.created_at is None
    assert item.updated_at is None
