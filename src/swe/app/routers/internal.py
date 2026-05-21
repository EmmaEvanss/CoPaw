# -*- coding: utf-8 -*-
"""Internal API for service-to-service communication."""

import base64
import json
from datetime import datetime, timezone
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Header, HTTPException, Request
from pydantic import BaseModel, Field

from ...config.context import is_valid_identity_value, resolve_scope_id
from ...config.utils import list_all_tenant_ids
from ...constant import WORKING_DIR

router = APIRouter(prefix="/internal", tags=["internal"])
public_router = APIRouter(prefix="/assets/text", tags=["assets"])
logger = logging.getLogger(__name__)

# 内部服务认证 Token（可选）
_INTERNAL_TOKEN = os.environ.get("SWE_INTERNAL_TOKEN", "")
_ASSET_ROOT_DIRNAME = "asset"
_DEFAULT_FILE_URL_BASE = "http://localhost:8088"
_STATIC_AGENT_ID = "default"
_INVALID_FILE_NAME_DETAIL = "Invalid file_name"
_ASSET_NOT_FOUND_DETAIL = "Asset file not found"
_ASSET_INVALID_UTF8_DETAIL = "Asset file is not valid UTF-8"
_CONTENT_INVALID_UTF8_DETAIL = "Content is not valid UTF-8"


class InternalErrorResponse(BaseModel):
    detail: str = Field(..., description="Error detail message.")


class InternalTextAssetReadResponse(BaseModel):
    success: bool = Field(default=True)
    file_name: str
    content: str


class InternalTextAssetWriteRequest(BaseModel):
    user_id: str
    source_id: str
    content: str


class InternalTextAssetWriteResponse(BaseModel):
    success: bool = Field(default=True)
    file_name: str
    scope_id: str
    public_url: str


def _verify_internal_token(token: Optional[str]) -> None:
    """验证内部服务 Token（如果配置了的话）."""
    if _INTERNAL_TOKEN:
        if not token or token != f"Bearer {_INTERNAL_TOKEN}":
            raise HTTPException(status_code=401, detail="Unauthorized")


def _validate_asset_file_name(file_name: str) -> str:
    path = Path(file_name)
    has_reserved_name = not file_name or file_name in {".", ".."}
    has_path_component = path.name != file_name or path.is_absolute()
    has_forbidden_character = any(
        char in file_name for char in ("/", "\\", "\x00")
    )
    if has_reserved_name or has_path_component or has_forbidden_character:
        raise HTTPException(
            status_code=400,
            detail=_INVALID_FILE_NAME_DETAIL,
        )
    return file_name


def _decode_utf8_content(raw_content: bytes) -> str:
    try:
        return raw_content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(
            status_code=400,
            detail=_ASSET_INVALID_UTF8_DETAIL,
        ) from exc


def _validate_utf8_text(content: str) -> str:
    try:
        content.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise HTTPException(
            status_code=400,
            detail=_CONTENT_INVALID_UTF8_DETAIL,
        ) from exc
    return content


def _generate_text_asset_file_name(user_id: str) -> str:
    timestamp = datetime.now(tz=timezone.utc).strftime(
        "%Y%m%d%H%M%S%f",
    )[:-3]
    return f"{user_id}-{timestamp}.html"


def _build_public_url(scope_id: str, file_name: str) -> str:
    base_url = os.getenv("FILE_URL", _DEFAULT_FILE_URL_BASE).rstrip("/")
    return f"{base_url}/static/{scope_id}/{_STATIC_AGENT_ID}/{file_name}"


def _get_asset_file_path(file_name: str) -> Path:
    return WORKING_DIR / _ASSET_ROOT_DIRNAME / file_name


def _get_scope_static_dir(scope_id: str) -> Path:
    return WORKING_DIR / scope_id / "workspaces" / _STATIC_AGENT_ID / "static"


def _read_text_asset(file_name: str) -> InternalTextAssetReadResponse:
    safe_file_name = _validate_asset_file_name(file_name)
    asset_file = _get_asset_file_path(safe_file_name)
    if not asset_file.exists() or not asset_file.is_file():
        raise HTTPException(status_code=404, detail=_ASSET_NOT_FOUND_DETAIL)
    content = _decode_utf8_content(asset_file.read_bytes())
    return InternalTextAssetReadResponse(
        file_name=safe_file_name,
        content=content,
    )


def _write_text_asset(
    payload: InternalTextAssetWriteRequest,
) -> InternalTextAssetWriteResponse:
    if not is_valid_identity_value(payload.user_id):
        raise HTTPException(status_code=400, detail="Invalid user_id")
    if not is_valid_identity_value(payload.source_id):
        raise HTTPException(status_code=400, detail="Invalid source_id")

    scope_id = resolve_scope_id(payload.user_id, payload.source_id)
    if scope_id is None:
        raise HTTPException(status_code=400, detail="Failed to resolve scope")

    file_name = _generate_text_asset_file_name(payload.user_id)
    content = _validate_utf8_text(payload.content)
    static_dir = _get_scope_static_dir(scope_id)
    static_dir.mkdir(parents=True, exist_ok=True)
    (static_dir / file_name).write_text(content, encoding="utf-8")

    return InternalTextAssetWriteResponse(
        file_name=file_name,
        scope_id=scope_id,
        public_url=_build_public_url(scope_id, file_name),
    )


@router.get(
    "/assets/text/read",
    response_model=InternalTextAssetReadResponse,
    responses={
        400: {"model": InternalErrorResponse},
        401: {"model": InternalErrorResponse},
        404: {"model": InternalErrorResponse},
    },
)
async def internal_read_text_asset(
    file_name: str,
    x_internal_token: Optional[str] = Header(
        default=None,
        alias="X-Internal-Token",
    ),
) -> InternalTextAssetReadResponse:
    _verify_internal_token(x_internal_token)
    return _read_text_asset(file_name)


@router.post(
    "/assets/text/write",
    response_model=InternalTextAssetWriteResponse,
    responses={
        400: {"model": InternalErrorResponse},
        401: {"model": InternalErrorResponse},
    },
)
async def internal_write_text_asset(
    payload: InternalTextAssetWriteRequest,
    x_internal_token: Optional[str] = Header(
        default=None,
        alias="X-Internal-Token",
    ),
) -> InternalTextAssetWriteResponse:
    _verify_internal_token(x_internal_token)
    return _write_text_asset(payload)


@public_router.get(
    "/read",
    response_model=InternalTextAssetReadResponse,
    responses={
        400: {"model": InternalErrorResponse},
        404: {"model": InternalErrorResponse},
    },
)
async def read_text_asset(
    file_name: str,
) -> InternalTextAssetReadResponse:
    return _read_text_asset(file_name)


@public_router.post(
    "/write",
    response_model=InternalTextAssetWriteResponse,
    responses={
        400: {"model": InternalErrorResponse},
    },
)
async def write_text_asset(
    payload: InternalTextAssetWriteRequest,
) -> InternalTextAssetWriteResponse:
    return _write_text_asset(payload)


@router.post("/agents/{agent_id}/reload")
async def internal_reload_agent(
    agent_id: str,
    request: Request,
    tenant_id: str = "default",
    source_id: Optional[str] = None,
    x_internal_token: Optional[str] = Header(
        default=None,
        alias="X-Internal-Token",
    ),
):
    """内部服务调用：重载指定 Agent.

    用于 market 服务修改技能配置后通知主服务重载 Agent。
    """
    _verify_internal_token(x_internal_token)

    manager = getattr(request.app.state, "multi_agent_manager", None)
    if manager is None:
        logger.warning("MultiAgentManager not initialized")
        raise HTTPException(status_code=503, detail="Manager not available")

    if not source_id:
        raise HTTPException(status_code=400, detail="source_id is required")
    if not is_valid_identity_value(tenant_id):
        raise HTTPException(status_code=400, detail="Invalid tenant_id")
    if not is_valid_identity_value(source_id):
        raise HTTPException(status_code=400, detail="Invalid source_id")

    scope_id = resolve_scope_id(tenant_id, source_id)
    if scope_id is None:
        raise HTTPException(status_code=400, detail="Failed to resolve scope")

    try:
        await manager.reload_agent(agent_id, tenant_id=scope_id)
        logger.info(
            f"Agent '{agent_id}' (scope={scope_id}) reloaded via internal API",
        )
        return {
            "success": True,
            "agent_id": agent_id,
            "tenant_id": tenant_id,
            "source_id": source_id,
            "scope_id": scope_id,
        }
    except Exception as e:
        logger.error(f"Failed to reload agent '{agent_id}': {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def _get_cron_manager(manager, tenant_id: str, agent_id: str):
    """获取指定 tenant/agent 的 CronManager 实例。"""
    try:
        ws = await manager.get_agent(agent_id, tenant_id=tenant_id)
    except ValueError:
        return None
    return ws.cron_manager


def _get_configured_agent_ids(tenant_id: str) -> list[str]:
    """读取指定租户配置中的所有 Agent ID。"""
    from ...config.utils import get_tenant_config_path, load_config

    config = load_config(get_tenant_config_path(tenant_id))
    return sorted(config.agents.profiles.keys())


@router.post("/cron/register-missing-jobs")
async def register_missing_cron_jobs(request: Request):
    """手动补注册所有租户、所有 Agent 中未注册到外部平台的定时任务。"""
    manager = getattr(request.app.state, "multi_agent_manager", None)
    if manager is None:
        logger.warning("MultiAgentManager not initialized")
        raise HTTPException(status_code=503, detail="Manager not available")

    tenant_ids = list_all_tenant_ids()
    summary: dict[str, Any] = {
        "tenant_count": len(tenant_ids),
        "agent_count": 0,
        "total": 0,
        "registered": 0,
        "updated": 0,
        "skipped": 0,
        "failed": 0,
        "results": [],
        "errors": [],
    }

    for tenant_id in tenant_ids:
        try:
            agent_ids = _get_configured_agent_ids(tenant_id)
        except Exception as exc:  # pylint: disable=broad-except
            summary["failed"] += 1
            summary["errors"].append(
                {
                    "tenant_id": tenant_id,
                    "agent_id": "",
                    "error": str(exc),
                },
            )
            continue

        for agent_id in agent_ids:
            summary["agent_count"] += 1
            mgr = await _get_cron_manager(manager, tenant_id, agent_id)
            if mgr is None:
                summary["failed"] += 1
                summary["errors"].append(
                    {
                        "tenant_id": tenant_id,
                        "agent_id": agent_id,
                        "error": "CronManager not found",
                    },
                )
                continue

            try:
                result = await mgr.register_missing_external_jobs()
            except Exception as exc:  # pylint: disable=broad-except
                summary["failed"] += 1
                summary["errors"].append(
                    {
                        "tenant_id": tenant_id,
                        "agent_id": agent_id,
                        "error": str(exc),
                    },
                )
                continue

            summary["total"] += int(result.get("total", 0))
            summary["registered"] += int(result.get("registered", 0))
            summary["updated"] += int(result.get("updated", 0))
            summary["skipped"] += int(result.get("skipped", 0))
            summary["failed"] += int(result.get("failed", 0))
            summary["errors"].extend(result.get("errors", []))
            summary["results"].append(result)

    return summary


# ── Unified callback endpoint (jobParam-based) ──


@router.post("/cron/callback")
async def internal_cron_callback(
    request: Request,
    x_internal_token: Optional[str] = Header(
        default=None,
        alias="X-Internal-Token",
    ),
    body: Dict[str, Any] = Body(...),
):
    """外部调度平台统一回调端点。

    支持两种参数传入方式：
    1. jobParam（base64 JSON 包裹）→ 解码后提取参数
    2. body 顶层直接携带 tenant_id / agent_id / task_type / job_id

    根据 task_type 分发到对应的 CronManager 方法。
    """
    _verify_internal_token(x_internal_token)

    job_param = body.get("jobParam") or body.get("job_param") or ""
    if job_param:
        # base64 JSON 包裹格式：jobParam 编码后下发，回调时原样传回
        try:
            params = json.loads(base64.urlsafe_b64decode(job_param))
        except Exception as e:
            logger.warning("Failed to decode jobParam: %s", e)
            raise HTTPException(
                status_code=400,
                detail=f"Invalid jobParam: {e}",
            )
    else:
        # 直接参数格式：外部平台直接将参数字段展开在 body 中
        params = body

    try:
        tenant_id = params["tenant_id"]
        agent_id = params["agent_id"]
        task_type = params["task_type"]
        job_id = params.get("job_id", "")
    except KeyError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Missing required param in callback body: {e}",
        )

    manager = getattr(request.app.state, "multi_agent_manager", None)
    if manager is None:
        logger.warning("MultiAgentManager not initialized")
        raise HTTPException(status_code=503, detail="Manager not available")

    mgr = await _get_cron_manager(manager, tenant_id, agent_id)
    if mgr is None:
        raise HTTPException(status_code=404, detail="CronManager not found")

    try:
        if task_type == "heartbeat":
            await mgr.run_heartbeat()
        elif task_type == "dream":
            await mgr.run_dream()
        else:
            if not job_id:
                raise HTTPException(
                    status_code=400,
                    detail="job_id required for task_type=job",
                )
            # 调度回调触发的执行是自动执行，不是手动执行
            await mgr.run_job(job_id, is_manual=False)

        logger.info(
            "Callback dispatched: type=%s tenant=%s agent=%s job=%s",
            task_type,
            tenant_id,
            agent_id,
            job_id,
        )
        return {"status": "ok", "task_type": task_type}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to run callback (type=%s, tenant=%s, agent=%s, job=%s): %s",
            task_type,
            tenant_id,
            agent_id,
            job_id,
            e,
        )
        raise HTTPException(status_code=500, detail=str(e))
