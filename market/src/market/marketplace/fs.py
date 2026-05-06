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
from datetime import datetime, timezone
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


def _mask_env_value(value: Optional[str]) -> Optional[str]:
    """脱敏环境变量值。

    Args:
        value: 原始值。

    Returns:
        脱敏后的值，短值全部遮盖，长值显示前2-3字符和后4字符。
    """
    if value is None or value == "":
        return value
    length = len(value)
    if length <= 8:
        return "*" * length
    # 如果第3位是 "-"，前缀取3字符（如 "sk-"），否则取2字符
    prefix_len = 3 if length > 2 and value[2] == "-" else 2
    prefix = value[:prefix_len]
    suffix = value[-4:]
    masked_len = max(length - prefix_len - 4, 4)
    return f"{prefix}{'*' * masked_len}{suffix}"


def get_mcp_dir(
    marketplace_root: Path,
    source_id: str,
    item_id: str,
) -> Path:
    """获取 MCP 条目目录路径。

    Args:
        marketplace_root: 市场根目录。
        source_id: 来源 ID。
        item_id: 条目 ID。

    Returns:
        MCP 条目目录路径。
    """
    _validate_path_segment(source_id, "source_id")
    _validate_path_segment(item_id, "item_id")
    return marketplace_root / source_id / "mcp" / item_id


def get_mcp_config_path(
    marketplace_root: Path,
    source_id: str,
    item_id: str,
) -> Path:
    """获取 MCP 配置文件路径。

    Args:
        marketplace_root: 市场根目录。
        source_id: 来源 ID。
        item_id: 条目 ID。

    Returns:
        MCP 配置文件路径 (mcp.json)。
    """
    return get_mcp_dir(marketplace_root, source_id, item_id) / "mcp.json"


def load_mcp_config(
    marketplace_root: Path,
    source_id: str,
    item_id: str,
) -> Optional[dict]:
    """读取 MCP 配置文件。

    Args:
        marketplace_root: 市场根目录。
        source_id: 来源 ID。
        item_id: 条目 ID。

    Returns:
        MCP 配置字典，不存在或解析失败返回 None。
    """
    path = get_mcp_config_path(marketplace_root, source_id, item_id)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.error("Failed to load MCP config %s: %s", path, e)
        return None


def save_mcp_config(
    marketplace_root: Path,
    source_id: str,
    item_id: str,
    config: dict,
) -> None:
    """保存 MCP 配置文件。

    Args:
        marketplace_root: 市场根目录。
        source_id: 来源 ID。
        item_id: 条目 ID。
        config: MCP 配置字典。
    """
    mcp_dir = get_mcp_dir(marketplace_root, source_id, item_id)
    mcp_dir.mkdir(parents=True, exist_ok=True)
    path = mcp_dir / "mcp.json"
    _atomic_write_json(path, config)


def copy_mcp_to_user(
    marketplace_root: Path,
    source_id: str,
    item_id: str,
    swe_root: Path,
    user_id: str,
    client_key: str,
    distributed_by: str,
    agent_id: str = DEFAULT_AGENT_ID,
) -> None:
    """将市场 MCP 复制到用户本地配置。

    Args:
        marketplace_root: 市场根目录。
        source_id: 来源 ID。
        item_id: 条目 ID。
        swe_root: SWE 用户根目录。
        user_id: 用户 ID。
        client_key: MCP 客户端标识。
        distributed_by: 分发者标识。
        agent_id: Agent ID，默认为 "default"。
    """
    _validate_path_segment(client_key, "client_key")

    mcp_config = load_mcp_config(marketplace_root, source_id, item_id)
    if mcp_config is None:
        raise ValueError(f"MCP config not found for item {item_id}")

    # 加载用户 agent.json
    user_config_path = swe_root / user_id / "workspaces" / agent_id / "agent.json"
    user_config_path.parent.mkdir(parents=True, exist_ok=True)

    user_config: dict = {}
    if user_config_path.exists():
        try:
            user_config = json.loads(user_config_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass

    # 确保结构存在
    if "mcp" not in user_config:
        user_config["mcp"] = {"clients": {}}
    if "clients" not in user_config["mcp"]:
        user_config["mcp"]["clients"] = {}

    # 合并 MCP 配置
    config_data = mcp_config.get("config", {})
    config_data["source"] = f"marketplace:{item_id}"
    config_data["market_client_key"] = client_key
    config_data["distributed_by"] = distributed_by
    config_data["updated_at"] = datetime.now(timezone.utc).isoformat()

    user_config["mcp"]["clients"][client_key] = config_data

    _atomic_write_json(user_config_path, user_config)
