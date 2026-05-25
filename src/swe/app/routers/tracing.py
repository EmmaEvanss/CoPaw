# -*- coding: utf-8 -*-
"""运营看板在 SWE 侧使用的 tracing 辅助接口。"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query, Request

from ...config.context import resolve_scope_preferred_tenant_id
from ...config.utils import get_tenant_config_path, load_config
from ..runner.models import ChatSpec

logger = logging.getLogger(__name__)

router = APIRouter(tags=["monitor-tracing"])


def _request_source_id(request: Request) -> str | None:
    """读取当前请求的数据来源，用于定位目标用户的运行时工作区。"""
    source_id = getattr(request.state, "source_id", None)
    if isinstance(source_id, str) and source_id:
        return source_id
    header_source_id = request.headers.get("X-Source-Id")
    return header_source_id or None


def _request_agent_id(request: Request, tenant_id: str | None) -> str:
    """解析目标用户下用于读取聊天映射的 agent。"""
    agent_id = request.headers.get("X-Agent-Id")
    if agent_id:
        return agent_id

    config = (
        load_config(get_tenant_config_path(tenant_id))
        if tenant_id
        else load_config()
    )
    return config.agents.active_agent or "default"


async def _get_target_workspace(
    request: Request,
    target_user_id: str,
):
    """按目标用户获取 SWE 工作区，避免通过 Monitor 二次转发。"""
    source_id = _request_source_id(request)
    target_tenant_id = resolve_scope_preferred_tenant_id(
        target_user_id,
        source_id,
    )

    pool = getattr(request.app.state, "tenant_workspace_pool", None)
    if pool is not None:
        await pool.ensure_bootstrap(
            target_user_id,
            source_id=source_id,
            tenant_name=None,
            bbk_id=request.headers.get("X-Bbk-Id"),
        )

    manager = getattr(request.app.state, "multi_agent_manager", None)
    if manager is None:
        raise HTTPException(
            status_code=500,
            detail="MultiAgentManager not initialized",
        )

    agent_id = _request_agent_id(request, target_tenant_id)
    try:
        return await manager.get_agent(agent_id, tenant_id=target_tenant_id)
    except ValueError as exc:
        logger.warning(
            "Failed to resolve target chat workspace: user_id=%s agent_id=%s",
            target_user_id,
            agent_id,
        )
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/tracing/chats", response_model=list[ChatSpec])
async def get_user_chats(
    request: Request,
    user_id: str = Query(..., description="目标用户 ID"),
    channel: str | None = Query(None, description="按渠道筛选"),
) -> list[ChatSpec]:
    """获取目标用户聊天映射列表。

    该接口专供运营看板用户详情弹窗使用，直接从 SWE 目标用户工作区读取
    ChatSpec 映射，不改变现有 `/chats` 的当前用户语义。
    """
    workspace = await _get_target_workspace(request, user_id)
    return await workspace.chat_manager.list_chats(
        user_id=user_id,
        channel=channel,
    )
