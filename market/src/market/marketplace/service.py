# -*- coding: utf-8 -*-
"""应用市场业务服务."""

from __future__ import annotations

import json
import logging
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from urllib.parse import unquote

import httpx

from ..config.constant import SWE_INTERNAL_URL, SWE_INTERNAL_TOKEN
from ..database.connection import DatabaseConnection
from ..security import SkillScanError, scan_skill_directory
from .fs import (
    _mask_env_value,
    copy_mcp_to_user,
    copy_skill_to_user,
    get_mcp_dir,
    get_skill_dir,
    get_user_skills_dir,
    load_index,
    mutate_user_skill_manifest,
    read_user_skill_manifest,
    load_mcp_config,
    save_index,
    save_mcp_config,
)
from .models import MarketItem
from .schemas import (
    DistributeRequest,
    DistributeResponse,
    MCPDistributionRequest,
    MCPDistributionResponse,
    MCPDistributionTenantResult,
    MarketMCPDetail,
    MarketMCPItem,
    MarketSkillDetail,
    MarketSkillResponse,
    MCPConfigDetail,
    MCPUserStat,
    MySkillItem,
    PublishMCPRequest,
    PublishSkillRequest,
    SkillUserStat,
)

logger = logging.getLogger(__name__)

_TRACING_STATS_SQL = """
    SELECT
        COUNT(*) AS call_count,
        COUNT(DISTINCT user_id) AS user_count
    FROM swe_tracing_spans
    WHERE event_type = 'skill_invocation'
      AND skill_name = %s
      AND source_id = %s
"""

_TRACING_USER_STATS_SQL = """
    SELECT
        user_id,
        MAX(COALESCE(metadata->>'$.user_name', '')) AS user_name,
        COUNT(*) AS call_count
    FROM swe_tracing_spans
    WHERE event_type = 'skill_invocation'
      AND skill_name = %s
      AND source_id = %s
    GROUP BY user_id
    ORDER BY call_count DESC
    LIMIT 100
"""

# MCP 专用统计 SQL - 使用 mcp_server 字段匹配 client_key
_TRACING_STATS_MCP_SQL = """
    SELECT
        COUNT(*) AS call_count,
        COUNT(DISTINCT user_id) AS user_count
    FROM swe_tracing_spans
    WHERE mcp_server = %s
      AND source_id = %s
"""

_TRACING_USER_STATS_MCP_SQL = """
    SELECT
        user_id,
        MAX(COALESCE(metadata->>'$.user_name', '')) AS user_name,
        COUNT(*) AS call_count
    FROM swe_tracing_spans
    WHERE mcp_server = %s
      AND source_id = %s
    GROUP BY user_id
    ORDER BY call_count DESC
    LIMIT 100
"""

_LOG_MARKET_OP_SQL = """
    INSERT INTO swe_marketplace_operation_logs
        (source_id, operator_id, operator_name, operation,
         item_type, item_id, item_name,
         target_user_id, target_user_name, target_bbk_id)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
"""

_QUERY_USERS_BY_SOURCE_SQL = """
    SELECT tenant_id, tenant_name, bbk_id
    FROM swe_tenant_init_source
    WHERE source_id = %s
"""

_QUERY_USERS_BY_BBK_SQL = """
    SELECT tenant_id, tenant_name, bbk_id
    FROM swe_tenant_init_source
    WHERE source_id = %s AND bbk_id IN ({placeholders})
"""


def _sort_items_by_updated_at_desc(
    items: list[MarketItem],
) -> list[MarketItem]:
    """按更新时间倒序排列，缺失时回退到创建时间。"""

    def sort_key(item: MarketItem) -> tuple[int, str]:
        timestamp = item.updated_at or item.created_at or ""
        return (1 if timestamp else 0, timestamp)

    return sorted(items, key=sort_key, reverse=True)


def _normalize_market_mcp_config_data(config_data: dict) -> dict:
    """兼容旧市场条目中的原始 MCP 上传结构。

    历史上部分市场条目直接把上传 JSON 原样保存到了 config 中，
    例如 {"mcpServers": {...}}。详情展示和测试连接都需要先把这类
    旧结构归一化成 MCPClientConfig 可识别的扁平字段。
    """
    if not isinstance(config_data, dict):
        return {}

    normalized = dict(config_data)

    mcp_servers = normalized.get("mcpServers")
    if isinstance(mcp_servers, dict) and mcp_servers:
        _, first_value = next(iter(mcp_servers.items()))
        if isinstance(first_value, dict):
            normalized = dict(first_value)

    advanced = normalized.get("advanced")
    if isinstance(advanced, dict):
        if "headers" not in normalized and isinstance(
            advanced.get("headers"),
            dict,
        ):
            normalized["headers"] = advanced.get("headers", {})
        if "transport" not in normalized and isinstance(
            advanced.get("transport"),
            str,
        ):
            raw_transport = advanced["transport"].strip().lower()
            if raw_transport == "streamable-http":
                normalized["transport"] = "streamable_http"
            elif raw_transport in {"stdio", "sse", "streamable_http"}:
                normalized["transport"] = raw_transport

    raw_transport = normalized.get("transport") or normalized.get("type")
    if isinstance(raw_transport, str):
        lowered = raw_transport.strip().lower()
        if lowered == "streamable-http":
            normalized["transport"] = "streamable_http"
        elif lowered in {"stdio", "sse", "streamable_http"}:
            normalized["transport"] = lowered

    if "transport" not in normalized:
        if (
            isinstance(normalized.get("command"), str)
            and normalized.get("command", "").strip()
        ):
            normalized["transport"] = "stdio"
        elif (
            isinstance(normalized.get("url"), str)
            and normalized.get("url", "").strip()
        ):
            normalized["transport"] = "streamable_http"

    return normalized


def _bump_patch(version: str) -> str:
    """Increment patch version: '1.0.0' -> '1.0.1'."""
    parts = version.split(".")
    if len(parts) == 3:
        try:
            parts[2] = str(int(parts[2]) + 1)
            return ".".join(parts)
        except ValueError:
            pass
    return version + ".1"


def _decode_creator_name(value: str) -> str:
    """解码通过请求头传入的创建人名称，并兼容历史已编码数据。"""
    if not value:
        return value
    try:
        return unquote(value)
    except Exception:  # pylint: disable=broad-except
        return value


def _item_visible(item: MarketItem, user_bbk_id: str) -> bool:
    """Return True if item is visible to user with given bbk_id."""
    if item.status != "active":
        return False
    if user_bbk_id == "100":
        return True
    if not item.bbk_ids:
        return True
    return "100" in item.bbk_ids or user_bbk_id in item.bbk_ids


class MarketplaceService:
    def __init__(
        self,
        db: DatabaseConnection,
        marketplace_root: Path,
        swe_root: Path,
    ) -> None:
        self.db = db
        self.marketplace_root = marketplace_root
        self.swe_root = swe_root

    async def _trigger_agent_reload(
        self,
        user_id: str,
        agent_id: str = "default",
    ) -> None:
        """通过 HTTP 回调触发 src/swe 的 Agent 重载."""
        url = f"{SWE_INTERNAL_URL}/api/internal/agents/{agent_id}/reload"
        headers = {}
        if SWE_INTERNAL_TOKEN:
            headers["X-Internal-Token"] = f"Bearer {SWE_INTERNAL_TOKEN}"

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    url,
                    params={"tenant_id": user_id},
                    headers=headers,
                )
                if response.status_code == 200:
                    logger.info(
                        f"Agent reload triggered for '{agent_id}' (tenant={user_id})",
                    )
                else:
                    logger.warning(
                        f"Agent reload failed: {response.status_code} - {response.text}",
                    )
        except Exception as e:
            logger.warning(f"Failed to trigger agent reload: {e}")

    def _scan_skill_or_raise(
        self,
        user_id: str,
        skill_name: str,
        agent_id: str = "default",
    ) -> None:
        """扫描技能目录，发现安全问题抛出异常."""
        skills_dir = get_user_skills_dir(self.swe_root, user_id, agent_id)
        skill_dir = skills_dir / skill_name
        if skill_dir.exists():
            scan_skill_directory(skill_dir, skill_name=skill_name)

    async def enable_skill(
        self,
        user_id: str,
        skill_name: str,
        agent_id: str = "default",
    ) -> dict[str, Any]:
        """启用技能（含安全扫描 + 回调重载）."""
        skills_dir = get_user_skills_dir(self.swe_root, user_id, agent_id)
        skill_dir = skills_dir / skill_name
        if not skill_dir.exists():
            return {"success": False, "reason": "not_found"}

        # 安全扫描
        try:
            self._scan_skill_or_raise(user_id, skill_name, agent_id)
        except SkillScanError as e:
            return {
                "success": False,
                "reason": "security_scan_failed",
                "detail": str(e),
            }

        # 更新 manifest
        def _update(payload: dict) -> bool:
            entry = payload.setdefault("skills", {}).setdefault(skill_name, {})
            entry["enabled"] = True
            entry["updated_at"] = datetime.now(timezone.utc).isoformat()
            return True

        updated = mutate_user_skill_manifest(
            self.swe_root,
            user_id,
            agent_id,
            _update,
        )

        if updated:
            await self._trigger_agent_reload(user_id, agent_id)

        return {"success": updated}

    async def disable_skill(
        self,
        user_id: str,
        skill_name: str,
        agent_id: str = "default",
    ) -> dict[str, Any]:
        """禁用技能（含回调重载）."""

        def _update(payload: dict) -> bool:
            entry = payload.get("skills", {}).get(skill_name)
            if entry is None:
                return False
            entry["enabled"] = False
            entry["updated_at"] = datetime.now(timezone.utc).isoformat()
            return True

        updated = mutate_user_skill_manifest(
            self.swe_root,
            user_id,
            agent_id,
            _update,
        )

        if updated:
            await self._trigger_agent_reload(user_id, agent_id)

        return {"success": updated}

    async def batch_delete_skills(
        self,
        user_id: str,
        skill_names: list[str],
        agent_id: str = "default",
    ) -> dict[str, Any]:
        """批量删除技能."""
        import shutil

        skills_dir = get_user_skills_dir(self.swe_root, user_id, agent_id)
        results: dict[str, Any] = {}

        for skill_name in skill_names:
            skill_dir = skills_dir / skill_name
            if not skill_dir.exists():
                results[skill_name] = {"success": False, "reason": "not_found"}
                continue

            # 先禁用
            await self.disable_skill(user_id, skill_name, agent_id)

            # 删除目录
            try:
                shutil.rmtree(skill_dir)
                results[skill_name] = {"success": True}
            except Exception as e:
                results[skill_name] = {"success": False, "reason": str(e)}
                continue

            # 从 manifest 移除
            name_to_remove = skill_name

            def _remove(payload: dict, _name: str = name_to_remove) -> bool:
                payload.get("skills", {}).pop(_name, None)
                return True

            mutate_user_skill_manifest(
                self.swe_root,
                user_id,
                agent_id,
                _remove,
            )

        return results

    async def batch_enable_skills(
        self,
        user_id: str,
        skill_names: list[str],
        agent_id: str = "default",
    ) -> dict[str, Any]:
        """批量启用技能."""
        results: dict[str, Any] = {}
        for skill_name in skill_names:
            results[skill_name] = await self.enable_skill(
                user_id,
                skill_name,
                agent_id,
            )
        return results

    async def batch_disable_skills(
        self,
        user_id: str,
        skill_names: list[str],
        agent_id: str = "default",
    ) -> dict[str, Any]:
        """批量禁用技能."""
        results: dict[str, Any] = {}
        for skill_name in skill_names:
            results[skill_name] = await self.disable_skill(
                user_id,
                skill_name,
                agent_id,
            )
        return results

    async def publish_skill(
        self,
        source_id: str,
        req: PublishSkillRequest,
    ) -> MarketItem:
        """上架技能。同名技能已存在时递增 patch 版本号。"""
        items = load_index(self.marketplace_root, source_id)
        existing = next((i for i in items if i.name == req.name), None)

        now = datetime.now(timezone.utc).isoformat()
        if existing is not None:
            version = _bump_patch(existing.version)
            existing.version = version
            existing.description = req.description
            existing.creator_id = req.creator_id
            existing.creator_name = req.creator_name
            existing.category_id = req.category_id
            existing.bbk_ids = req.bbk_ids
            existing.status = "active"
            existing.updated_at = now
            item = existing
        else:
            item = MarketItem(
                item_id=str(uuid.uuid4()),
                item_type="skill",
                name=req.name,
                description=req.description,
                version="1.0.0",
                creator_id=req.creator_id,
                creator_name=req.creator_name,
                category_id=req.category_id,
                bbk_ids=req.bbk_ids,
                status="active",
                created_at=now,
                updated_at=now,
            )
            items.append(item)

        skill_dir = get_skill_dir(
            self.marketplace_root,
            source_id,
            item.item_id,
        )
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "skill.json").write_text(
            json.dumps(req.skill_json, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        if req.skill_md:
            (skill_dir / "SKILL.md").write_text(req.skill_md, encoding="utf-8")

        save_index(self.marketplace_root, source_id, items)

        if self.db.is_connected:
            try:
                await self.db.execute(
                    _LOG_MARKET_OP_SQL,
                    (
                        source_id,
                        req.creator_id,
                        req.creator_name,
                        "publish",
                        "skill",
                        item.item_id,
                        item.name,
                        None,
                        None,
                        None,
                    ),
                )
            except Exception as e:
                logger.warning("Failed to log publish operation: %s", e)

        return item

    async def unpublish_skill(
        self,
        source_id: str,
        item_id: str,
        operator_id: str,
        operator_name: str,
    ) -> bool:
        """下架技能（设为 inactive）。返回 True 表示成功。"""
        items = load_index(self.marketplace_root, source_id)
        item = next(
            (
                i
                for i in items
                if i.item_id == item_id and i.item_type == "skill"
            ),
            None,
        )
        if item is None:
            return False
        item.status = "inactive"
        item.updated_at = datetime.now(timezone.utc).isoformat()
        save_index(self.marketplace_root, source_id, items)

        if self.db.is_connected:
            try:
                await self.db.execute(
                    _LOG_MARKET_OP_SQL,
                    (
                        source_id,
                        operator_id,
                        operator_name,
                        "unpublish",
                        "skill",
                        item_id,
                        item.name,
                        None,
                        None,
                        None,
                    ),
                )
            except Exception as e:
                logger.warning("Failed to log unpublish operation: %s", e)

        return True

    async def list_skills(
        self,
        source_id: str,
        user_bbk_id: str,
        category_id: Optional[int] = None,
    ) -> list[MarketSkillResponse]:
        """列出市场技能，按 bbk_id 过滤，可选按分类过滤。"""
        items = load_index(self.marketplace_root, source_id)
        visible = [
            i
            for i in items
            if i.item_type == "skill" and _item_visible(i, user_bbk_id)
        ]
        if category_id is not None:
            visible = [i for i in visible if i.category_id == category_id]

        result = []
        for item in visible:
            call_count, user_count = await self._get_stats(
                item.name,
                source_id,
            )
            result.append(
                MarketSkillResponse(
                    item_id=item.item_id,
                    name=item.name,
                    description=item.description,
                    version=item.version,
                    creator_id=item.creator_id,
                    creator_name=item.creator_name,
                    category_id=item.category_id,
                    bbk_ids=item.bbk_ids,
                    status=item.status,
                    created_at=item.created_at,
                    updated_at=item.updated_at,
                    call_count=call_count,
                    user_count=user_count,
                ),
            )
        return result

    async def get_skill_detail(
        self,
        source_id: str,
        item_id: str,
        user_bbk_id: str,
    ) -> Optional[MarketSkillDetail]:
        """获取技能详情（含调用客户明细）。"""
        items = load_index(self.marketplace_root, source_id)
        item = next(
            (
                i
                for i in items
                if i.item_id == item_id and i.item_type == "skill"
            ),
            None,
        )
        if item is None or not _item_visible(item, user_bbk_id):
            return None

        call_count, user_count = await self._get_stats(item.name, source_id)
        user_stats = await self._get_user_stats(item.name, source_id)

        return MarketSkillDetail(
            item_id=item.item_id,
            name=item.name,
            description=item.description,
            version=item.version,
            creator_id=item.creator_id,
            creator_name=item.creator_name,
            category_id=item.category_id,
            bbk_ids=item.bbk_ids,
            status=item.status,
            created_at=item.created_at,
            updated_at=item.updated_at,
            call_count=call_count,
            user_count=user_count,
            user_stats=user_stats,
        )

    async def distribute_skill(
        self,
        source_id: str,
        item_id: str,
        operator_id: str,
        operator_name: str,
        req: DistributeRequest,
    ) -> DistributeResponse:
        """分发技能到目标用户工作目录，并写操作日志。"""
        items = load_index(self.marketplace_root, source_id)
        item = next(
            (
                i
                for i in items
                if i.item_id == item_id and i.item_type == "skill"
            ),
            None,
        )
        if item is None:
            raise ValueError(f"Item {item_id} not found in source {source_id}")

        target_users = await self._resolve_target_users(source_id, req)
        count = 0
        for user in target_users:
            try:
                copy_skill_to_user(
                    marketplace_root=self.marketplace_root,
                    source_id=source_id,
                    item_id=item_id,
                    swe_root=self.swe_root,
                    user_id=user["tenant_id"],
                    skill_name=item.name,
                    distributed_by=operator_id,
                    version=item.version,
                )
                count += 1
            except Exception as e:
                logger.warning(
                    "Failed to copy skill to user %s: %s",
                    user["tenant_id"],
                    e,
                )
                continue

            if self.db.is_connected:
                try:
                    await self.db.execute(
                        _LOG_MARKET_OP_SQL,
                        (
                            source_id,
                            operator_id,
                            operator_name,
                            "distribute",
                            "skill",
                            item_id,
                            item.name,
                            user["tenant_id"],
                            user.get("tenant_name", ""),
                            user.get("bbk_id", ""),
                        ),
                    )
                except Exception as e:
                    logger.warning("Failed to log distribute operation: %s", e)

        return DistributeResponse(distributed_count=count, item_id=item_id)

    async def get_my_skills(
        self,
        source_id: str,
        user_id: str,
        agent_id: str = "default",
    ) -> list[MySkillItem]:
        """获取用户技能列表（我创建的 + 我接收的）。"""
        skills_dir = get_user_skills_dir(self.swe_root, user_id, agent_id)
        if not skills_dir.exists():
            return []

        # 读取 manifest 获取启用状态
        manifest = read_user_skill_manifest(self.swe_root, user_id, agent_id)
        manifest_skills = manifest.get("skills", {})

        market_index = load_index(self.marketplace_root, source_id)
        market_versions: dict[str, str] = {
            i.name: i.version for i in market_index if i.status == "active"
        }

        result = []
        for skill_dir in sorted(skills_dir.iterdir()):
            if not skill_dir.is_dir():
                continue
            skill_json_path = skill_dir / "skill.json"
            if not skill_json_path.exists():
                continue
            try:
                data = json.loads(skill_json_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue

            skill_name = skill_dir.name
            source = data.get("source", "customized")
            is_received = source.startswith("marketplace:")
            received_version = data.get("received_version")
            market_version = market_versions.get(skill_name)
            has_update = (
                is_received
                and received_version is not None
                and market_version is not None
                and received_version != market_version
            )

            # 从 manifest 获取启用状态
            manifest_entry = manifest_skills.get(skill_name, {})
            enabled = manifest_entry.get("enabled", True)

            result.append(
                MySkillItem(
                    skill_name=skill_name,
                    source=source,
                    description=data.get("description", ""),
                    version=data.get("version"),
                    received_version=received_version,
                    distributed_by=data.get("distributed_by"),
                    is_received=is_received,
                    has_update=has_update,
                    enabled=enabled,
                ),
            )
        return result

    async def _get_stats(
        self,
        skill_name: str,
        source_id: str,
    ) -> tuple[int, int]:
        if not self.db.is_connected:
            return 0, 0
        try:
            row = await self.db.fetch_one(
                _TRACING_STATS_SQL,
                (skill_name, source_id),
            )
            if row:
                return int(row.get("call_count", 0)), int(
                    row.get("user_count", 0),
                )
        except Exception as e:
            logger.warning("Failed to fetch stats for %s: %s", skill_name, e)
        return 0, 0

    async def _get_user_stats(
        self,
        skill_name: str,
        source_id: str,
    ) -> list[SkillUserStat]:
        if not self.db.is_connected:
            return []
        try:
            rows = await self.db.fetch_all(
                _TRACING_USER_STATS_SQL,
                (skill_name, source_id),
            )
            return [
                SkillUserStat(
                    user_id=r["user_id"],
                    user_name=r.get("user_name", ""),
                    call_count=int(r["call_count"]),
                )
                for r in rows
            ]
        except Exception as e:
            logger.warning(
                "Failed to fetch user stats for %s: %s",
                skill_name,
                e,
            )
        return []

    async def _resolve_target_users(
        self,
        source_id: str,
        req: DistributeRequest,
    ) -> list[dict]:
        if not self.db.is_connected:
            return []
        try:
            if req.target_type == "all":
                return await self.db.fetch_all(
                    _QUERY_USERS_BY_SOURCE_SQL,
                    (source_id,),
                )
            if req.target_type == "bbk_id" and req.target_values:
                placeholders = ",".join(["%s"] * len(req.target_values))
                sql = _QUERY_USERS_BY_BBK_SQL.format(placeholders=placeholders)
                return await self.db.fetch_all(
                    sql,
                    (source_id, *req.target_values),
                )
            if req.target_type == "user_id" and req.target_values:
                return [
                    {"tenant_id": uid, "tenant_name": "", "bbk_id": ""}
                    for uid in req.target_values
                ]
        except Exception as e:
            logger.warning("Failed to resolve target users: %s", e)
        return []

    def list_skill_files(
        self,
        user_id: str,
        skill_name: str,
        agent_id: str = "default",
    ) -> list[dict]:
        """列出技能文件树（不包含 skill.json）."""
        skills_dir = get_user_skills_dir(self.swe_root, user_id, agent_id)
        skill_dir = skills_dir / skill_name
        if not skill_dir.exists():
            return []

        # 需要隐藏的文件名
        HIDDEN_FILES = {"skill.json"}

        def build_tree(path: Path, base: Path) -> dict:
            relative = path.relative_to(base)
            if path.is_file():
                return {
                    "name": path.name,
                    "type": "file",
                    "path": str(relative),
                }
            children = []
            for child in sorted(path.iterdir()):
                if child.name.startswith(".") or child.name in HIDDEN_FILES:
                    continue
                children.append(build_tree(child, base))
            return {
                "name": path.name,
                "type": "directory",
                "path": str(relative),
                "children": children,
            }

        items = list(skill_dir.iterdir())
        items.sort(
            key=lambda p: (
                0 if p.name == "SKILL.md" else 2 if p.is_dir() else 3,
                p.name.lower(),
            ),
        )

        return [
            build_tree(item, skill_dir)
            for item in items
            if not item.name.startswith(".") and item.name not in HIDDEN_FILES
        ]

    def read_skill_file(
        self,
        user_id: str,
        skill_name: str,
        file_path: str,
        agent_id: str = "default",
    ) -> tuple[str | None, str]:
        """读取技能文件内容，返回 (content, file_type)."""
        skills_dir = get_user_skills_dir(self.swe_root, user_id, agent_id)
        skill_dir = skills_dir / skill_name
        target = skill_dir / file_path

        try:
            target.resolve().relative_to(skill_dir.resolve())
        except ValueError:
            return None, "error"

        if not target.exists() or not target.is_file():
            return None, "error"

        ext = target.suffix.lower()
        if ext == ".md":
            file_type = "markdown"
        elif ext == ".json":
            file_type = "json"
        elif ext in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".pdf"):
            return None, "binary"
        else:
            file_type = "text"

        try:
            content = target.read_text(encoding="utf-8")
            return content, file_type
        except Exception:
            return None, "error"

    def save_skill_file(
        self,
        user_id: str,
        skill_name: str,
        file_path: str,
        content: str,
        agent_id: str = "default",
    ) -> bool:
        """保存技能文件内容."""
        skills_dir = get_user_skills_dir(self.swe_root, user_id, agent_id)
        skill_dir = skills_dir / skill_name
        target = skill_dir / file_path

        try:
            target.resolve().relative_to(skill_dir.resolve())
        except ValueError:
            return False

        if not target.exists() or not target.is_file():
            return False

        try:
            target.write_text(content, encoding="utf-8")
            return True
        except Exception:
            return False

    def delete_skill(
        self,
        user_id: str,
        skill_name: str,
        agent_id: str = "default",
    ) -> bool:
        """删除用户技能."""
        import shutil

        skills_dir = get_user_skills_dir(self.swe_root, user_id, agent_id)
        skill_dir = skills_dir / skill_name

        if not skill_dir.exists():
            return False

        try:
            shutil.rmtree(skill_dir)
            return True
        except Exception:
            return False

    # ============ MCP 服务方法 ============

    async def publish_mcp(
        self,
        source_id: str,
        req: PublishMCPRequest,
    ) -> MarketItem:
        """发布 MCP 到市场。覆盖已存在条目。

        Args:
            source_id: 来源 ID。
            req: 发布请求体。

        Returns:
            创建或更新的 MarketItem。
        """
        items = load_index(self.marketplace_root, source_id)

        # 按 client_key 查找已存在的 MCP 条目
        existing = next(
            (
                i
                for i in items
                if i.item_type == "mcp" and i.client_key == req.client_key
            ),
            None,
        )

        now = datetime.now(timezone.utc).isoformat()
        if existing is not None:
            # 覆盖：复用 item_id
            existing.version = _bump_patch(existing.version)
            existing.name = req.name
            existing.chinese_name = req.chinese_name
            existing.description = req.description
            existing.guidance = req.guidance
            existing.creator_id = req.creator_id
            existing.creator_name = req.creator_name
            existing.category_id = req.category_id
            existing.bbk_ids = req.bbk_ids
            existing.status = "active"
            existing.updated_at = now
            item = existing
        else:
            # 创建新条目
            item = MarketItem(
                item_id=str(uuid.uuid4()),
                item_type="mcp",
                client_key=req.client_key,
                name=req.name,
                chinese_name=req.chinese_name,
                description=req.description,
                guidance=req.guidance,
                creator_id=req.creator_id,
                creator_name=req.creator_name,
                category_id=req.category_id,
                bbk_ids=req.bbk_ids,
                status="active",
                created_at=now,
                updated_at=now,
            )
            items.append(item)

        # 保存 MCP 配置文件
        mcp_config = {
            "client_key": req.client_key,
            "config": req.config,
        }
        save_mcp_config(
            self.marketplace_root,
            source_id,
            item.item_id,
            mcp_config,
        )

        # 更新索引
        save_index(self.marketplace_root, source_id, items)

        # 记录操作日志
        if self.db.is_connected:
            try:
                await self.db.execute(
                    _LOG_MARKET_OP_SQL,
                    (
                        source_id,
                        req.creator_id,
                        req.creator_name,
                        "publish",
                        "mcp",
                        item.item_id,
                        item.name,
                        None,
                        None,
                        None,
                    ),
                )
            except Exception as e:
                logger.warning("Failed to log MCP publish operation: %s", e)

        return item

    async def list_mcp_items(
        self,
        source_id: str,
        user_bbk_id: str,
        category_id: Optional[int] = None,
    ) -> list[MarketMCPItem]:
        """列出市场 MCP 条目。

        Args:
            source_id: 来源 ID。
            user_bbk_id: 用户 bbk_id，用于权限过滤。
            category_id: 可选的分类 ID 过滤。

        Returns:
            MCP 条目列表（含调用统计）。
        """
        items = load_index(self.marketplace_root, source_id)
        mcp_items = [
            i
            for i in items
            if i.item_type == "mcp" and _item_visible(i, user_bbk_id)
        ]
        mcp_items = _sort_items_by_updated_at_desc(mcp_items)

        if category_id is not None:
            mcp_items = [i for i in mcp_items if i.category_id == category_id]

        result = []
        for item in mcp_items:
            call_count, user_count = await self._get_mcp_stats(
                item.client_key,
                source_id,
            )
            result.append(
                MarketMCPItem(
                    item_id=item.item_id,
                    client_key=item.client_key,
                    name=item.name,
                    chinese_name=item.chinese_name,
                    description=item.description,
                    guidance=item.guidance,
                    version=item.version,
                    creator_id=item.creator_id,
                    creator_name=_decode_creator_name(item.creator_name),
                    category_id=item.category_id,
                    bbk_ids=item.bbk_ids,
                    created_at=item.created_at,
                    updated_at=item.updated_at,
                    call_count=call_count,
                    user_count=user_count,
                ),
            )
        return result

    async def get_mcp_detail(
        self,
        source_id: str,
        item_id: str,
        user_bbk_id: str,
    ) -> Optional[MarketMCPDetail]:
        """获取 MCP 详情（含配置和用户统计）。

        Args:
            source_id: 来源 ID。
            item_id: 条目 ID。
            user_bbk_id: 用户 bbk_id，用于权限过滤。

        Returns:
            MCP 详情，不存在或无权限返回 None。
        """
        items = load_index(self.marketplace_root, source_id)
        item = next(
            (
                i
                for i in items
                if i.item_id == item_id and i.item_type == "mcp"
            ),
            None,
        )
        if item is None or not _item_visible(item, user_bbk_id):
            return None

        # 加载 MCP 配置
        mcp_config = load_mcp_config(self.marketplace_root, source_id, item_id)
        if mcp_config is None:
            return None

        call_count, user_count = await self._get_mcp_stats(
            item.client_key,
            source_id,
        )
        user_stats = await self._get_mcp_user_stats(item.client_key, source_id)

        # 获取并脱敏敏感字段
        config_data = _normalize_market_mcp_config_data(
            mcp_config.get("config", {}),
        )
        masked_env = {
            k: _mask_env_value(v)
            for k, v in config_data.get("env", {}).items()
        }
        masked_headers = {
            k: _mask_env_value(v)
            for k, v in config_data.get("headers", {}).items()
        }

        return MarketMCPDetail(
            item_id=item.item_id,
            client_key=item.client_key,
            name=item.name,
            chinese_name=item.chinese_name,
            description=item.description,
            guidance=item.guidance,
            version=item.version,
            creator_id=item.creator_id,
            creator_name=_decode_creator_name(item.creator_name),
            category_id=item.category_id,
            bbk_ids=item.bbk_ids,
            created_at=item.created_at,
            updated_at=item.updated_at,
            call_count=call_count,
            user_count=user_count,
            config=MCPConfigDetail(
                transport=config_data.get("transport", "stdio"),
                url=config_data.get("url", ""),
                headers=masked_headers,
                command=config_data.get("command", ""),
                args=config_data.get("args", []),
                env=masked_env,
                cwd=config_data.get("cwd", ""),
                lazy_load=config_data.get("lazy_load", False),
            ),
            user_stats=user_stats,
        )

    async def distribute_mcp(
        self,
        source_id: str,
        item_id: str,
        operator_id: str,
        operator_name: str,
        req: MCPDistributionRequest,
    ) -> MCPDistributionResponse:
        """分发 MCP 到目标租户。

        Args:
            source_id: 来源 ID。
            item_id: 条目 ID。
            operator_id: 操作者 ID。
            operator_name: 操作者名称。
            req: 分发请求体。

        Returns:
            分发结果（逐租户返回）。

        Raises:
            ValueError: 条目不存在。
        """
        items = load_index(self.marketplace_root, source_id)
        item = next(
            (
                i
                for i in items
                if i.item_id == item_id and i.item_type == "mcp"
            ),
            None,
        )
        if item is None:
            raise ValueError(
                f"MCP item {item_id} not found in source {source_id}",
            )

        results: list[MCPDistributionTenantResult] = []

        for tenant_id in req.target_tenant_ids:
            try:
                user_config_path = (
                    self.swe_root
                    / tenant_id
                    / "workspaces"
                    / "default"
                    / "agent.json"
                )
                bootstrapped = not user_config_path.exists()
                copy_mcp_to_user(
                    marketplace_root=self.marketplace_root,
                    source_id=source_id,
                    item_id=item_id,
                    swe_root=self.swe_root,
                    user_id=tenant_id,
                    client_key=item.client_key,
                    distributed_by=operator_id,
                )

                # 记录分发日志
                if self.db.is_connected:
                    try:
                        await self.db.execute(
                            _LOG_MARKET_OP_SQL,
                            (
                                source_id,
                                operator_id,
                                operator_name,
                                "distribute",
                                "mcp",
                                item_id,
                                item.name,
                                tenant_id,
                                "",
                                "",
                            ),
                        )
                    except Exception as e:
                        logger.warning(
                            "Failed to log MCP distribute operation: %s",
                            e,
                        )
                results.append(
                    MCPDistributionTenantResult(
                        tenant_id=tenant_id,
                        success=True,
                        bootstrapped=bootstrapped,
                        default_agent_updated=[item.client_key],
                    ),
                )
            except Exception as e:
                logger.warning(
                    "Failed to copy MCP to user %s: %s",
                    tenant_id,
                    e,
                )
                results.append(
                    MCPDistributionTenantResult(
                        tenant_id=tenant_id,
                        success=False,
                        error=str(e),
                    ),
                )

        return MCPDistributionResponse(
            source_agent_id=item_id,
            results=results,
        )

    async def delete_mcp(
        self,
        source_id: str,
        item_id: str,
        operator_id: str = "",
        operator_name: str = "",
    ) -> bool:
        """删除市场 MCP 条目。

        Args:
            source_id: 来源 ID。
            item_id: 条目 ID。
            operator_id: 操作者 ID（可选）。
            operator_name: 操作者名称（可选）。

        Returns:
            True 表示删除成功，False 表示条目不存在。
        """
        items = load_index(self.marketplace_root, source_id)
        item = next(
            (
                i
                for i in items
                if i.item_id == item_id and i.item_type == "mcp"
            ),
            None,
        )
        if item is None:
            return False

        # 从索引中移除
        items.remove(item)
        save_index(self.marketplace_root, source_id, items)

        # 删除配置目录
        mcp_dir = get_mcp_dir(self.marketplace_root, source_id, item_id)
        if mcp_dir.exists():
            shutil.rmtree(mcp_dir)

        # 记录删除日志
        if self.db.is_connected:
            try:
                await self.db.execute(
                    _LOG_MARKET_OP_SQL,
                    (
                        source_id,
                        operator_id,
                        operator_name,
                        "delete",
                        "mcp",
                        item_id,
                        item.name,
                        None,
                        None,
                        None,
                    ),
                )
            except Exception as e:
                logger.warning("Failed to log MCP delete operation: %s", e)

        return True

    def update_mcp_metadata(
        self,
        *,
        source_id: str,
        item_id: str,
        chinese_name: str | None,
        description: str | None,
        guidance: str | None,
        bbk_ids: list[str],
    ) -> MarketItem:
        """仅更新 MCP 市场条目的展示元数据。"""
        items = load_index(self.marketplace_root, source_id)
        item = next(
            (
                i
                for i in items
                if i.item_id == item_id and i.item_type == "mcp"
            ),
            None,
        )
        if item is None:
            raise FileNotFoundError(f"MCP item '{item_id}' not found")

        item.chinese_name = chinese_name or ""
        item.description = description or ""
        item.guidance = guidance or ""
        item.bbk_ids = bbk_ids
        item.updated_at = datetime.now(timezone.utc).isoformat()
        save_index(self.marketplace_root, source_id, items)
        return item

    async def _get_mcp_stats(
        self,
        client_key: str,
        source_id: str,
    ) -> tuple[int, int]:
        """获取 MCP 调用统计。

        Args:
            client_key: MCP 客户端标识。
            source_id: 来源 ID。

        Returns:
            (调用次数, 用户数)。
        """
        if not self.db.is_connected:
            return 0, 0
        try:
            row = await self.db.fetch_one(
                _TRACING_STATS_MCP_SQL,
                (client_key, source_id),
            )
            if row:
                return int(row.get("call_count", 0)), int(
                    row.get("user_count", 0),
                )
        except Exception as e:
            logger.warning("Failed to get MCP stats for %s: %s", client_key, e)
        return 0, 0

    async def _get_mcp_user_stats(
        self,
        client_key: str,
        source_id: str,
    ) -> list[MCPUserStat]:
        """获取 MCP 用户统计明细。

        Args:
            client_key: MCP 客户端标识。
            source_id: 来源 ID。

        Returns:
            用户统计列表（最多 100 条）。
        """
        if not self.db.is_connected:
            return []
        try:
            rows = await self.db.fetch_all(
                _TRACING_USER_STATS_MCP_SQL,
                (client_key, source_id),
            )
            return [
                MCPUserStat(
                    user_id=r["user_id"],
                    user_name=r.get("user_name", ""),
                    call_count=int(r["call_count"]),
                )
                for r in rows
            ]
        except Exception as e:
            logger.warning(
                "Failed to get MCP user stats for %s: %s",
                client_key,
                e,
            )
        return []
