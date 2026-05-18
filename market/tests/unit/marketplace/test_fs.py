# -*- coding: utf-8 -*-
import json
import pytest
from pathlib import Path


def test_get_marketplace_dir(tmp_path):
    from market.marketplace.fs import get_marketplace_dir

    result = get_marketplace_dir(tmp_path, "source_a")
    assert result == tmp_path / "source_a"


def test_get_index_path(tmp_path):
    from market.marketplace.fs import get_index_path

    result = get_index_path(tmp_path, "source_a")
    assert result == tmp_path / "source_a" / "index.json"


def test_load_index_returns_empty_when_not_exists(tmp_path):
    from market.marketplace.fs import load_index

    result = load_index(tmp_path, "source_a")
    assert result == []


def test_save_and_load_index(tmp_path):
    from market.marketplace.fs import load_index, save_index
    from market.marketplace.models import MarketItem

    item = MarketItem(
        item_id="uuid-1",
        item_type="skill",
        name="test_skill",
        description="desc",
        version="1.0.0",
        creator_id="user1",
        creator_name="User One",
        category_id=None,
        bbk_ids=[],
        status="active",
    )
    save_index(tmp_path, "source_a", [item])
    loaded = load_index(tmp_path, "source_a")
    assert len(loaded) == 1
    assert loaded[0].name == "test_skill"


def test_get_skill_dir_in_marketplace(tmp_path):
    from market.marketplace.fs import get_skill_dir

    result = get_skill_dir(tmp_path, "source_a", "item-123")
    assert result == tmp_path / "source_a" / "skills" / "item-123"


def test_get_user_skills_dir(tmp_path):
    from market.marketplace.fs import get_user_skills_dir
    from market.runtime.context import encode_scope_id

    result = get_user_skills_dir(tmp_path, "user1", "agent1", "source_a")
    assert result == (
        tmp_path
        / encode_scope_id("user1", "source_a")
        / "workspaces"
        / "agent1"
        / "skills"
    )


def test_get_user_skills_dir_allows_main_service_identity_values(tmp_path):
    from market.marketplace.fs import get_user_skills_dir
    from market.runtime.context import encode_scope_id

    result = get_user_skills_dir(
        tmp_path,
        "alice@example.com",
        "agent1",
        "skill:xlsx",
    )

    assert result == (
        tmp_path
        / encode_scope_id("alice@example.com", "skill:xlsx")
        / "workspaces"
        / "agent1"
        / "skills"
    )


def test_copy_skill_to_user_happy_path(tmp_path):
    from market.marketplace.fs import (
        copy_skill_to_user,
        get_skill_dir,
        get_user_skills_dir,
    )
    import json

    # Setup source skill
    src_dir = get_skill_dir(tmp_path / "market", "src_a", "item-1")
    src_dir.mkdir(parents=True)
    (src_dir / "SKILL.md").write_text("# Skill", encoding="utf-8")
    (src_dir / "skill.json").write_text(
        json.dumps({"name": "test"}),
        encoding="utf-8",
    )
    # Copy
    copy_skill_to_user(
        tmp_path / "market",
        "src_a",
        "item-1",
        tmp_path / "swe",
        "user1",
        "my_skill",
        "my_skill",
        "desc",
        "admin1",
        "1.0.0",
    )
    dst_dir = (
        get_user_skills_dir(tmp_path / "swe", "user1", source_id="src_a")
        / "my_skill"
    )
    assert (dst_dir / "SKILL.md").read_text() == "# Skill"
    data = json.loads((dst_dir / "skill.json").read_text())
    assert data["source"] == "marketplace:item-1"
    assert data["distributed_by"] == "admin1"
    assert data["received_version"] == "1.0.0"


def test_copy_skill_to_user_missing_skill_md(tmp_path):
    from market.marketplace.fs import (
        copy_skill_to_user,
        get_skill_dir,
        get_user_skills_dir,
    )
    import json

    src_dir = get_skill_dir(tmp_path / "market", "src_a", "item-2")
    src_dir.mkdir(parents=True)
    # No SKILL.md, only skill.json
    (src_dir / "skill.json").write_text(
        json.dumps({"name": "test"}),
        encoding="utf-8",
    )
    copy_skill_to_user(
        tmp_path / "market",
        "src_a",
        "item-2",
        tmp_path / "swe",
        "user1",
        "my_skill2",
        "my_skill2",
        "desc",
        "admin1",
        "1.0.0",
    )
    dst_dir = (
        get_user_skills_dir(tmp_path / "swe", "user1", source_id="src_a")
        / "my_skill2"
    )
    assert not (dst_dir / "SKILL.md").exists()
    data = json.loads((dst_dir / "skill.json").read_text())
    assert data["source"] == "marketplace:item-2"


def test_copy_skill_to_user_missing_skill_json(tmp_path):
    from market.marketplace.fs import (
        copy_skill_to_user,
        get_skill_dir,
        get_user_skills_dir,
    )
    import json

    src_dir = get_skill_dir(tmp_path / "market", "src_a", "item-3")
    src_dir.mkdir(parents=True)
    (src_dir / "SKILL.md").write_text("# Skill", encoding="utf-8")
    # No skill.json
    copy_skill_to_user(
        tmp_path / "market",
        "src_a",
        "item-3",
        tmp_path / "swe",
        "user1",
        "my_skill3",
        "my_skill3",
        "desc",
        "admin1",
        "2.0.0",
    )
    dst_dir = (
        get_user_skills_dir(tmp_path / "swe", "user1", source_id="src_a")
        / "my_skill3"
    )
    data = json.loads((dst_dir / "skill.json").read_text())
    assert data["source"] == "marketplace:item-3"
    assert data["received_version"] == "2.0.0"


def test_validate_path_segment_rejects_traversal(tmp_path):
    from market.marketplace.fs import get_marketplace_dir
    import pytest

    with pytest.raises(ValueError):
        get_marketplace_dir(tmp_path, "../../etc")
