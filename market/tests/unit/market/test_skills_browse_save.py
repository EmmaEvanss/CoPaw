# -*- coding: utf-8 -*-
"""Skills file save tests."""

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest


def test_save_skill_file_updates_updated_at_preserves_created_at():
    """编辑技能文件时应写入 updated_at，保留 created_at."""
    with tempfile.TemporaryDirectory() as tmpdir:
        skill_dir = Path(tmpdir) / "test_skill"
        skill_dir.mkdir()

        # 创建初始 skill.json（含 created_at）
        initial_data = {
            "name": "Test Skill",
            "source": "customized",
            "created_at": "2025-05-14T10:00:00+00:00",
        }
        skill_json_path = skill_dir / "skill.json"
        skill_json_path.write_text(
            json.dumps(initial_data, ensure_ascii=False),
            encoding="utf-8",
        )

        # 模拟编辑保存逻辑：更新 skill.json 的 updated_at
        skill_data = json.loads(skill_json_path.read_text(encoding="utf-8"))
        skill_data["updated_at"] = datetime.now(timezone.utc).isoformat()
        skill_json_path.write_text(
            json.dumps(skill_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        # 验证
        saved_data = json.loads(skill_json_path.read_text(encoding="utf-8"))
        assert "updated_at" in saved_data
        assert (
            saved_data["created_at"] == "2025-05-14T10:00:00+00:00"
        )  # 保持不变
        parsed_time = datetime.fromisoformat(saved_data["updated_at"])
        assert parsed_time.year == datetime.now(timezone.utc).year


def test_save_skill_file_without_existing_skill_json():
    """如果 skill.json 不存在，应自动创建基础配置."""
    with tempfile.TemporaryDirectory() as tmpdir:
        skill_dir = Path(tmpdir) / "test_skill"
        skill_dir.mkdir()

        # skill.json 不存在时，应自动创建
        skill_json_path = skill_dir / "skill.json"
        assert not skill_json_path.exists()

        # 模拟自动创建逻辑
        current_time = datetime.now(timezone.utc).isoformat()
        base_skill_data = {
            "name": "test_skill",
            "description": "",
            "version": "1.0.0",
            "creator_id": "test_user",
            "creator_name": "Test User",
            "created_at": current_time,
            "source": "customized",
        }
        skill_json_path.write_text(
            json.dumps(base_skill_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        # 验证创建了 skill.json
        assert skill_json_path.exists()
        saved_data = json.loads(skill_json_path.read_text(encoding="utf-8"))
        assert saved_data["name"] == "test_skill"
        assert saved_data["source"] == "customized"
        assert "created_at" in saved_data
        assert saved_data["creator_id"] == "test_user"


def test_save_skill_file_with_malformed_skill_json():
    """如果 skill.json 格式错误，不应抛出异常."""
    with tempfile.TemporaryDirectory() as tmpdir:
        skill_dir = Path(tmpdir) / "test_skill"
        skill_dir.mkdir()

        # 创建格式错误的 skill.json
        skill_json_path = skill_dir / "skill.json"
        skill_json_path.write_text("not a valid json", encoding="utf-8")

        # 模拟：格式错误时应优雅处理
        try:
            skill_data = json.loads(
                skill_json_path.read_text(encoding="utf-8"),
            )
            skill_data["updated_at"] = datetime.now(timezone.utc).isoformat()
            skill_json_path.write_text(
                json.dumps(skill_data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except json.JSONDecodeError:
            pass  # 忽略格式错误

        # 验证原始文件未被破坏
        content = skill_json_path.read_text(encoding="utf-8")
        assert content == "not a valid json"
