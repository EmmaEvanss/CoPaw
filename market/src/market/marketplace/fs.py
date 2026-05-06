# -*- coding: utf-8 -*-
"""市场文件系统工具.

市场目录结构：
  <marketplace_root>/<source_id>/index.json
  <marketplace_root>/<source_id>/skills/<item_id>/skill.json
  <marketplace_root>/<source_id>/skills/<item_id>/SKILL.md

用户技能目录：
  <swe_root>/<user_id>/workspaces/<agent_id>/skills/<skill_name>/
"""
from __future__ import annotations

import json
import logging
import os
import re
import tempfile
from pathlib import Path
from typing import Optional

from .models import MarketItem

logger = logging.getLogger(__name__)

DEFAULT_AGENT_ID = "default"

# Allows alphanumerics, underscores, hyphens, and dots (for version strings like "1.0.0")
_SAFE_SEGMENT_RE = re.compile(r"^[a-zA-Z0-9_\-\.]+$")


def _validate_path_segment(value: str, name: str = "segment") -> None:
    """Raise ValueError if value contains path traversal or unsafe characters."""
    if not _SAFE_SEGMENT_RE.match(value):
        raise ValueError(
            f"Invalid {name} {value!r}: only alphanumerics, underscores, hyphens, and dots are allowed",
        )


def get_marketplace_dir(marketplace_root: Path, source_id: str) -> Path:
    _validate_path_segment(source_id, "source_id")
    return marketplace_root / source_id


def get_index_path(marketplace_root: Path, source_id: str) -> Path:
    _validate_path_segment(source_id, "source_id")
    return get_marketplace_dir(marketplace_root, source_id) / "index.json"


def get_skill_dir(
    marketplace_root: Path,
    source_id: str,
    item_id: str,
) -> Path:
    _validate_path_segment(source_id, "source_id")
    _validate_path_segment(item_id, "item_id")
    return (
        get_marketplace_dir(marketplace_root, source_id) / "skills" / item_id
    )


def get_user_skills_dir(
    swe_root: Path,
    user_id: str,
    agent_id: str = DEFAULT_AGENT_ID,
) -> Path:
    _validate_path_segment(user_id, "user_id")
    _validate_path_segment(agent_id, "agent_id")
    return swe_root / user_id / "workspaces" / agent_id / "skills"


def load_index(marketplace_root: Path, source_id: str) -> list[MarketItem]:
    """读取市场索引，不存在时返回空列表."""
    path = get_index_path(marketplace_root, source_id)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return [MarketItem(**item) for item in data.get("items", [])]
    except (json.JSONDecodeError, KeyError, TypeError, AttributeError) as e:
        logger.error("Failed to load index %s: %s", path, e)
        return []


def save_index(
    marketplace_root: Path,
    source_id: str,
    items: list[MarketItem],
) -> None:
    """原子写入市场索引."""
    path = get_index_path(marketplace_root, source_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {"items": [item.model_dump() for item in items]}
    _atomic_write_json(path, data)


def _atomic_write_json(path: Path, data: dict) -> None:
    """原子写入 JSON 文件，防止并发损坏."""
    dir_ = path.parent
    dir_.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=dir_, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def copy_skill_to_user(
    marketplace_root: Path,
    source_id: str,
    item_id: str,
    swe_root: Path,
    user_id: str,
    skill_name: str,
    distributed_by: str,
    version: str,
    agent_id: str = DEFAULT_AGENT_ID,
) -> None:
    """将市场技能复制到用户工作目录，并写入分发元数据."""
    _validate_path_segment(skill_name, "skill_name")
    src_dir = get_skill_dir(marketplace_root, source_id, item_id)
    dst_dir = get_user_skills_dir(swe_root, user_id, agent_id) / skill_name
    dst_dir.mkdir(parents=True, exist_ok=True)

    src_skill_md = src_dir / "SKILL.md"
    if src_skill_md.exists():
        (dst_dir / "SKILL.md").write_bytes(src_skill_md.read_bytes())

    src_skill_json = src_dir / "skill.json"
    skill_data: dict = {}
    if src_skill_json.exists():
        try:
            skill_data = json.loads(src_skill_json.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(
                "Failed to read source skill.json %s: %s",
                src_skill_json,
                e,
            )

    skill_data["source"] = f"marketplace:{item_id}"
    skill_data["distributed_by"] = distributed_by
    skill_data["received_version"] = version

    _atomic_write_json(dst_dir / "skill.json", skill_data)


def get_user_skill_manifest_path(
    swe_root: Path,
    user_id: str,
    agent_id: str = DEFAULT_AGENT_ID,
) -> Path:
    """获取用户工作空间的 skill.json 路径."""
    workspace_dir = swe_root / user_id / "workspaces" / agent_id
    return workspace_dir / "skill.json"


def read_user_skill_manifest(
    swe_root: Path,
    user_id: str,
    agent_id: str = DEFAULT_AGENT_ID,
) -> dict:
    """读取用户技能 manifest，不存在时返回默认结构."""
    manifest_path = get_user_skill_manifest_path(swe_root, user_id, agent_id)
    if not manifest_path.exists():
        return {
            "schema_version": "workspace-skill-manifest.v1",
            "version": 0,
            "skills": {},
        }
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Failed to read manifest %s: %s", manifest_path, e)
        return {
            "schema_version": "workspace-skill-manifest.v1",
            "version": 0,
            "skills": {},
        }


def mutate_user_skill_manifest(
    swe_root: Path,
    user_id: str,
    agent_id: str,
    mutation_fn,
) -> bool:
    """原子修改用户技能 manifest.

    Args:
        mutation_fn: 接受 dict 参数，返回 bool 表示是否修改成功
    """
    manifest_path = get_user_skill_manifest_path(swe_root, user_id, agent_id)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    current = read_user_skill_manifest(swe_root, user_id, agent_id)
    if not mutation_fn(current):
        return False

    _atomic_write_json(manifest_path, current)
    return True
