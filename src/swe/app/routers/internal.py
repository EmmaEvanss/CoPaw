# -*- coding: utf-8 -*-
"""Internal API for service-to-service communication."""

import logging
import os
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Request

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
