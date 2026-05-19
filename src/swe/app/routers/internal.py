# -*- coding: utf-8 -*-
"""Internal API for service-to-service communication."""

import base64
import json
import logging
import os
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Header, HTTPException, Request

from ...config.utils import list_all_tenant_ids

router = APIRouter(prefix="/internal", tags=["internal"])
logger = logging.getLogger(__name__)

# 内部服务认证 Token（可选）
_INTERNAL_TOKEN = os.environ.get("SWE_INTERNAL_TOKEN", "")


def _verify_internal_token(token: Optional[str]) -> None:
    """验证内部服务 Token（如果配置了的话）."""
    if _INTERNAL_TOKEN:
        if not token or token != f"Bearer {_INTERNAL_TOKEN}":
            raise HTTPException(status_code=401, detail="Unauthorized")


@router.post("/agents/{agent_id}/reload")
async def internal_reload_agent(
    agent_id: str,
    request: Request,
    tenant_id: str = "default",
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

    try:
        await manager.reload_agent(agent_id, tenant_id=tenant_id)
        logger.info(
            f"Agent '{agent_id}' (tenant={tenant_id}) reloaded via internal API",
        )
        return {"success": True, "agent_id": agent_id, "tenant_id": tenant_id}
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
            raise HTTPException(status_code=400, detail=f"Invalid jobParam: {e}")
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
            await mgr.run_job(job_id)

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
