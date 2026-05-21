# -*- coding: utf-8 -*-
"""市场文件系统工具.

市场目录结构：
  <marketplace_root>/<source_id>/index.json
  <marketplace_root>/<source_id>/skills/<item_id>/skill.json
  <marketplace_root>/<source_id>/skills/<item_id>/SKILL.md

用户技能目录：
  <swe_root>/<scope_id>/workspaces/<agent_id>/skills/<skill_name>/
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
from ..runtime.context import (
    encode_scope_id,
    migrate_legacy_scope_dir_if_needed,
)

logger = logging.getLogger(__name__)

DEFAULT_AGENT_ID = "default"

# 系统标识符 (source_id, item_id, user_id, agent_id)：仅允许 ASCII 安全字符
_SAFE_SYSTEM_SEGMENT_RE = re.compile(r"^[a-zA-Z0-9_\-\.]+$")

# 技能目录名危险字符：控制字符、空格、Windows 保留字符、路径分隔符
# 空格也替换为下划线，避免脚本/工具兼容问题
_UNSAFE_SKILL_NAME_CHARS_RE = re.compile(r'[\x00-\x1f <>:"|?*\\/]')


def normalize_skill_name(name: str) -> str:
    """将技能名称规范化为安全的目录名，保留中文等 Unicode 字符.

    与 SWE 服务的 _normalize_skill_dir_name() 行为对齐，仅过滤真正危险的
    文件系统字符，保留中文、日文、韩文等 Unicode 字符。

    处理流程：
    1. 去除前后空格
    2. 检查空值、NUL 字节、路径遍历
    3. 替换危险字符（控制字符、空格、Windows 保留字符、路径分隔符）为下划线
    4. 合并连续下划线
    5. 去除首尾下划线
    6. 截断到 64 个字符

    Args:
        name: 原始技能名称，如 "数据分析" 或 "Word / DOCX"

    Returns:
        规范的目录名，如 "数据分析" 或 "Word_DOCX"

    Raises:
        ValueError: 名称为空或仅包含非法字符
    """
    normalized = str(name or "").strip()
    if not normalized:
        raise ValueError("Skill name cannot be empty")
    if "\x00" in normalized:
        raise ValueError("Skill name cannot contain NUL bytes")
    if normalized in {".", ".."}:
        raise ValueError(f"Invalid skill name: {normalized!r}")
    # 替换危险字符为下划线（保留对含 / 的 frontmatter 名称的兼容）
    normalized = _UNSAFE_SKILL_NAME_CHARS_RE.sub("_", normalized)
    # 合并连续下划线
    normalized = re.sub(r"_+", "_", normalized)
    # 去除首尾下划线
    normalized = normalized.strip("_")
    # 截断到 64 个字符
    if len(normalized) > 64:
        normalized = normalized[:64].strip("_")
    if not normalized:
        raise ValueError("Skill name contains only invalid characters")
    return normalized


def _validate_path_segment(value: str, name: str = "segment") -> None:
    """校验系统标识符（source_id, item_id, user_id, agent_id）仅包含 ASCII 安全字符."""
    if not _SAFE_SYSTEM_SEGMENT_RE.match(value):
        raise ValueError(
            f"Invalid {name} {value!r}: only alphanumerics, underscores, hyphens, and dots are allowed",
        )


def _validate_skill_name_segment(value: str) -> None:
    """校验技能目录名，允许 Unicode 字符但拦截危险文件系统字符."""
    if not value:
        raise ValueError("Skill name cannot be empty")
    if "\x00" in value:
        raise ValueError("Skill name cannot contain NUL bytes")
    if value in {".", ".."}:
        raise ValueError(f"Invalid skill name: {value!r}")
    if _UNSAFE_SKILL_NAME_CHARS_RE.search(value):
        raise ValueError(
            f"Invalid skill name {value!r}: contains unsafe filesystem characters",
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


def resolve_effective_user_id(
    user_id: str,
    source_id: str | None = None,
) -> str:
    """解析用户本地状态使用的运行时 scope 标识。"""
    if not source_id:
        return user_id
    return encode_scope_id(user_id, source_id)


def get_user_skills_dir(
    swe_root: Path,
    user_id: str,
    agent_id: str = DEFAULT_AGENT_ID,
    source_id: str | None = None,
) -> Path:
    effective_user_id = resolve_effective_user_id(user_id, source_id)
    _validate_path_segment(effective_user_id, "user_id")
    _validate_path_segment(agent_id, "agent_id")
    user_root = migrate_legacy_scope_dir_if_needed(swe_root, effective_user_id)
    return user_root / "workspaces" / agent_id / "skills"


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
    original_name: str,
    description: str,
    distributed_by: str,
    version: str,
    agent_id: str = DEFAULT_AGENT_ID,
) -> None:
    """将市场技能复制到用户工作目录，并写入分发元数据.

    Args:
        skill_name: 规范的目录名（normalize 后，保留中文等 Unicode 字符）
        original_name: 原始技能名称（用于前端展示）
        description: 技能描述（用于前端展示）
    """
    _validate_skill_name_segment(skill_name)
    src_dir = get_skill_dir(marketplace_root, source_id, item_id)
    dst_dir = (
        get_user_skills_dir(swe_root, user_id, agent_id, source_id)
        / skill_name
    )
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

    # 重复分发时保留目标目录已有的 created_at
    dst_skill_json = dst_dir / "skill.json"
    if dst_skill_json.exists():
        try:
            existing_data = json.loads(
                dst_skill_json.read_text(encoding="utf-8"),
            )
            if "created_at" in existing_data:
                skill_data["created_at"] = existing_data["created_at"]
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(
                "Failed to read existing skill.json %s: %s",
                dst_skill_json,
                e,
            )

    # 确保 name 字段存在（用于前端展示）
    if "name" not in skill_data:
        skill_data["name"] = original_name

    # 确保 description 字段存在（用于前端展示）
    if not skill_data.get("description"):
        skill_data["description"] = description

    skill_data["source"] = f"marketplace:{item_id}"
    skill_data["distributed_by"] = distributed_by
    skill_data["received_version"] = version
    # 保留原有 created_at（重复分发时不覆盖首次创建时间）
    skill_data.setdefault("created_at", datetime.now(timezone.utc).isoformat())

    _atomic_write_json(dst_dir / "skill.json", skill_data)


def get_user_skill_manifest_path(
    swe_root: Path,
    user_id: str,
    agent_id: str = DEFAULT_AGENT_ID,
    source_id: str | None = None,
) -> Path:
    """获取用户工作空间的 skill.json 路径."""
    return (
        get_user_skills_dir(swe_root, user_id, agent_id, source_id)
        / "skill.json"
    )


def read_user_skill_manifest(
    swe_root: Path,
    user_id: str,
    agent_id: str = DEFAULT_AGENT_ID,
    source_id: str | None = None,
) -> dict:
    """读取用户技能 manifest，不存在时返回默认结构."""
    manifest_path = get_user_skill_manifest_path(
        swe_root,
        user_id,
        agent_id,
        source_id,
    )
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
    source_id: str | None = None,
) -> bool:
    """原子修改用户技能 manifest.

    Args:
        mutation_fn: 接受 dict 参数，返回 bool 表示是否修改成功
    """
    manifest_path = get_user_skill_manifest_path(
        swe_root,
        user_id,
        agent_id,
        source_id,
    )
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    current = read_user_skill_manifest(swe_root, user_id, agent_id, source_id)
    if not mutation_fn(current):
        return False

    _atomic_write_json(manifest_path, current)
    return True


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
    mcp_config = load_mcp_config(marketplace_root, source_id, item_id)
    if mcp_config is None:
        raise ValueError(f"MCP config not found for item {item_id}")

    # 加载用户 agent.json
    user_config_path = (
        swe_root / user_id / "workspaces" / agent_id / "agent.json"
    )
    user_config_path.parent.mkdir(parents=True, exist_ok=True)

    user_config: dict = {}
    if user_config_path.exists():
        try:
            user_config = json.loads(
                user_config_path.read_text(encoding="utf-8"),
            )
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
