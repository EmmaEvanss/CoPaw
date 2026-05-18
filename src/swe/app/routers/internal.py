# -*- coding: utf-8 -*-
"""Internal API for service-to-service communication."""

import logging
import os
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Request

from ...config.context import is_valid_identity_value, resolve_scope_id

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
