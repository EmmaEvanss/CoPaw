# -*- coding: utf-8 -*-
"""技能版本管理 API 路由."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Request, status

from ..deps import require_source_id
from ...marketplace.version_models import (
    VersionCompareRequest,
    VersionCompareResult,
    VersionDeleteResult,
    VersionSwitchResult,
    VersionsManifest,
)
from ...marketplace.version_service import SkillVersionService
from ...marketplace.fs import get_skill_dir
from ...marketplace.service import load_index, save_index

router = APIRouter()
logger = logging.getLogger(__name__)


def _require_manager(x_manager: Optional[str]) -> None:
    """验证管理员权限."""
    if x_manager != "true":
        raise HTTPException(status_code=403, detail="Manager access required")


def _get_version_service(request: Request) -> SkillVersionService:
    """从 app.state 获取版本服务."""
    marketplace = request.app.state.marketplace
    return SkillVersionService(marketplace.marketplace_root)


def _validate_item_exists(
    svc: SkillVersionService,
    source_id: str,
    item_id: str,
) -> None:
    """验证技能条目存在."""
    items = load_index(svc.marketplace_root, source_id)
    item = next((i for i in items if i.item_id == item_id), None)
    if not item:
        raise HTTPException(
            status_code=404,
            detail=f"Skill item {item_id} not found",
        )


@router.get(
    "/market/skills/{item_id}/versions",
    response_model=VersionsManifest,
    status_code=status.HTTP_200_OK,
)
async def list_versions(
    request: Request,
    item_id: str,
    x_source_id: Optional[str] = Header(default=None, alias="X-Source-Id"),
):
    """获取技能版本历史列表."""
    source_id = require_source_id(x_source_id)
    svc = _get_version_service(request)

    _validate_item_exists(svc, source_id, item_id)

    versions = svc.list_versions(source_id, item_id)
    return VersionsManifest(
        skill_name=versions.get("skill_name", ""),
        versions=versions.get("versions", []),
    )


@router.get(
    "/market/skills/{item_id}/versions/{version_id}",
    response_model=dict,
    status_code=status.HTTP_200_OK,
)
async def get_version_detail(
    request: Request,
    item_id: str,
    version_id: str,
    x_source_id: Optional[str] = Header(default=None, alias="X-Source-Id"),
):
    """获取单个版本详情（含文件树）."""
    source_id = require_source_id(x_source_id)
    svc = _get_version_service(request)

    _validate_item_exists(svc, source_id, item_id)

    detail = svc.get_version_detail(source_id, item_id, version_id)
    if not detail:
        raise HTTPException(
            status_code=404,
            detail=f"Version {version_id} not found",
        )
    return detail


@router.post(
    "/market/skills/{item_id}/versions/{version_id}/switch",
    response_model=VersionSwitchResult,
    status_code=status.HTTP_200_OK,
)
async def switch_version(
    request: Request,
    item_id: str,
    version_id: str,
    x_source_id: Optional[str] = Header(default=None, alias="X-Source-Id"),
    x_manager: Optional[str] = Header(default=None, alias="X-Manager"),
):
    """切换到指定版本（管理员）."""
    source_id = require_source_id(x_source_id)
    _require_manager(x_manager)

    svc = _get_version_service(request)
    marketplace = request.app.state.marketplace

    _validate_item_exists(svc, source_id, item_id)

    skill_dir = get_skill_dir(
        marketplace.marketplace_root,
        source_id,
        item_id,
    )

    result = svc.switch_version(source_id, item_id, version_id, skill_dir)

    if not result.success:
        raise HTTPException(
            status_code=400,
            detail=result.message or "Version switch failed",
        )

    # 更新市场索引中的技能信息
    items = load_index(marketplace.marketplace_root, source_id)
    item = next((i for i in items if i.item_id == item_id), None)
    if item:
        # 从切换后的 SKILL.md 提取完整信息并更新索引
        skill_md_path = skill_dir / "SKILL.md"
        if skill_md_path.exists():
            skill_md_content = skill_md_path.read_text(encoding="utf-8")
            # 解析 frontmatter 提取 name 和 description
            new_name = item.name
            new_desc = item.description
            if skill_md_content.startswith("---"):
                try:
                    end_idx = skill_md_content.index("---", 3)
                    fm_text = skill_md_content[3:end_idx].strip()
                    for line in fm_text.split("\n"):
                        if ":" in line:
                            key, val = line.split(":", 1)
                            key = key.strip().lower()
                            val = val.strip()
                            if key == "name" and val:
                                new_name = val
                            elif key == "description" and val:
                                new_desc = val
                except ValueError:
                    pass
            # 更新名称和描述
            item.name = new_name
            item.description = new_desc
            # 更新版本号为目标版本号
            item.version = version_id
            # 使用切换时间作为更新时间
            item.updated_at = datetime.now(timezone.utc).isoformat()
            save_index(marketplace.marketplace_root, source_id, items)

    return result


@router.post(
    "/market/skills/{item_id}/versions/compare",
    response_model=VersionCompareResult,
    status_code=status.HTTP_200_OK,
)
async def compare_versions(
    request: Request,
    item_id: str,
    compare_request: VersionCompareRequest,
    x_source_id: Optional[str] = Header(default=None, alias="X-Source-Id"),
):
    """比对两个版本."""
    source_id = require_source_id(x_source_id)
    svc = _get_version_service(request)

    _validate_item_exists(svc, source_id, item_id)

    result = svc.compare_versions(
        source_id,
        item_id,
        compare_request.base_version_id,
        compare_request.target_version_id,
    )

    if not result:
        raise HTTPException(
            status_code=400,
            detail="Version comparison failed",
        )

    return result


@router.delete(
    "/market/skills/{item_id}/versions/{version_id}",
    response_model=VersionDeleteResult,
    status_code=status.HTTP_200_OK,
)
async def delete_version(
    request: Request,
    item_id: str,
    version_id: str,
    x_source_id: Optional[str] = Header(default=None, alias="X-Source-Id"),
    x_manager: Optional[str] = Header(default=None, alias="X-Manager"),
):
    """删除指定版本（管理员）."""
    source_id = require_source_id(x_source_id)
    _require_manager(x_manager)

    svc = _get_version_service(request)

    _validate_item_exists(svc, source_id, item_id)

    success = svc.delete_version(source_id, item_id, version_id)

    if not success:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete current version or initial version",
        )

    return VersionDeleteResult(
        success=True,
        deleted_version=version_id,
        message="Version deleted successfully",
    )
