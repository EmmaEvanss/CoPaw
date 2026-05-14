# -*- coding: utf-8 -*-
"""Skills browse router tests."""

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from market.app.routers.skills_browse import _update_skill_json


def test_update_skill_json_writes_created_at():
    """上传技能时应写入 created_at 时间字段."""
    with tempfile.TemporaryDirectory() as tmpdir:
        skill_dir = Path(tmpdir) / "test_skill"
        skill_dir.mkdir()
        skill_json_path = skill_dir / "skill.json"

        result = _update_skill_json(
            skill_json_path=skill_json_path,
            skill_name="test_skill",
            original_name="Test Skill",
            user_id="user1",
            user_name="Test User",
            bbk_id="100",
            category_id=None,
        )

        # 验证返回结果包含 created_at
        assert "created_at" in result
        # 验证时间格式为 ISO 8601
        parsed_time = datetime.fromisoformat(
            result["created_at"].replace("Z", "+00:00"),
        )
        assert parsed_time.year == datetime.now(timezone.utc).year

        # 验证文件已写入
        saved_data = json.loads(skill_json_path.read_text(encoding="utf-8"))
        assert "created_at" in saved_data
        # 验证时间与返回值一致
        assert saved_data["created_at"] == result["created_at"]


def test_update_skill_json_preserves_existing_created_at():
    """更新现有技能时应保留已有的 created_at 时间."""
    with tempfile.TemporaryDirectory() as tmpdir:
        skill_dir = Path(tmpdir) / "existing_skill"
        skill_dir.mkdir()
        skill_json_path = skill_dir / "skill.json"

        # 先写入已有的 skill.json，包含 created_at
        existing_time = "2024-01-15T10:30:00Z"
        existing_data = {
            "name": "Existing Skill",
            "description": "An existing skill",
            "created_at": existing_time,
        }
        skill_json_path.write_text(
            json.dumps(existing_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        result = _update_skill_json(
            skill_json_path=skill_json_path,
            skill_name="existing_skill",
            original_name="Updated Skill Name",
            user_id="user2",
            user_name="Another User",
            bbk_id="200",
            category_id=5,
        )

        # 验证 created_at 未被覆盖
        assert result["created_at"] == existing_time
        saved_data = json.loads(skill_json_path.read_text(encoding="utf-8"))
        assert saved_data["created_at"] == existing_time


def test_update_skill_json_updates_updated_at():
    """更新技能时应写入 updated_at 时间字段."""
    with tempfile.TemporaryDirectory() as tmpdir:
        skill_dir = Path(tmpdir) / "skill_to_update"
        skill_dir.mkdir()
        skill_json_path = skill_dir / "skill.json"

        # 先创建一个已有的 skill.json
        existing_data = {
            "name": "Original Skill",
            "created_at": "2024-01-15T10:30:00Z",
        }
        skill_json_path.write_text(
            json.dumps(existing_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        result = _update_skill_json(
            skill_json_path=skill_json_path,
            skill_name="skill_to_update",
            original_name="Updated Skill",
            user_id="user3",
            user_name="Updater",
            bbk_id="300",
            category_id=None,
        )

        # 验证 updated_at 被写入
        assert "updated_at" in result
        parsed_time = datetime.fromisoformat(
            result["updated_at"].replace("Z", "+00:00"),
        )
        assert parsed_time.year == datetime.now(timezone.utc).year

        # 验证 created_at 未被覆盖
        assert result["created_at"] == "2024-01-15T10:30:00Z"
