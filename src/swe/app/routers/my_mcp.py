# -*- coding: utf-8 -*-
"""我的 MCP 管理路由."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Dict, Optional, Literal

from fastapi import APIRouter, Body, HTTPException, Path as FastAPIPath, Request
from pydantic import BaseModel, Field

from ..agent_context import get_agent_and_config_for_request
from ..utils import schedule_agent_reload
from ...config.config import (
    MCPClientConfig,
    MCPConfig,
    save_agent_config,
)
from .mcp import _mask_env_value, _restore_original_values

router = APIRouter(prefix="/my-mcp", tags=["my-mcp"])

# 市场分发的 MCP 不允许修改的敏感字段
SENSITIVE_FIELDS = ["transport", "url", "headers", "command", "args", "env", "cwd"]


def _is_distributed_from_market(client: MCPClientConfig) -> bool:
    """判断 MCP 是否来自市场分发."""
    return client.source.startswith("marketplace:")


def _get_tenant_id(request: Request) -> str | None:
    """获取请求中的租户 ID."""
    return getattr(request.state, "tenant_id", None)


def _get_source_id(request: Request) -> str | None:
    """获取请求中的来源 ID."""
    return getattr(request.state, "source_id", None)


class MyMCPListItem(BaseModel):
    """我的 MCP 列表项."""

    client_key: str = Field(..., description="唯一标识 key")
    name: str = Field(..., description="显示名称")
    description: str = Field(default="", description="描述")
    transport: Literal["stdio", "streamable_http", "sse"] = Field(
        default="stdio",
        description="MCP 传输类型",
    )
    enabled: bool = Field(default=True, description="是否启用")
    source: str = Field(default="", description="来源（本地/市场）")
    market_client_key: str = Field(default="", description="市场原始 client_key")
    created_at: str = Field(default="", description="创建时间")
    updated_at: str = Field(default="", description="更新时间")


class MyMCPDetail(MyMCPListItem):
    """我的 MCP 详情."""

    url: str = Field(default="", description="HTTP/SSE URL")
    headers: Dict[str, str] = Field(default_factory=dict, description="HTTP headers")
    command: str = Field(default="", description="stdio 命令")
    args: List[str] = Field(default_factory=list, description="命令行参数")
    env: Dict[str, str] = Field(default_factory=dict, description="环境变量")
    cwd: str = Field(default="", description="工作目录")
    lazy_load: bool = Field(default=False, description="是否懒加载")
    distributed_by: str = Field(default="", description="分发来源")


class MyMCPCreateRequest(BaseModel):
    """创建 MCP 请求."""

    client_key: str = Field(..., description="唯一标识 key")
    name: str = Field(..., description="显示名称")
    description: str = Field(default="", description="描述")
    transport: Literal["stdio", "streamable_http", "sse"] = Field(
        default="stdio",
        description="MCP 传输类型",
    )
    url: str = Field(default="", description="HTTP/SSE URL")
    headers: Dict[str, str] = Field(default_factory=dict, description="HTTP headers")
    command: str = Field(default="", description="stdio 命令")
    args: List[str] = Field(default_factory=list, description="命令行参数")
    env: Dict[str, str] = Field(default_factory=dict, description="环境变量")
    cwd: str = Field(default="", description="工作目录")


class MyMCPUpdateRequest(BaseModel):
    """更新 MCP 请求（所有字段可选）."""

    name: Optional[str] = Field(None, description="显示名称")
    description: Optional[str] = Field(None, description="描述")
    transport: Optional[Literal["stdio", "streamable_http", "sse"]] = Field(
        None,
        description="MCP 传输类型",
    )
    url: Optional[str] = Field(None, description="HTTP/SSE URL")
    headers: Optional[Dict[str, str]] = Field(None, description="HTTP headers")
    command: Optional[str] = Field(None, description="stdio 命令")
    args: Optional[List[str]] = Field(None, description="命令行参数")
    env: Optional[Dict[str, str]] = Field(None, description="环境变量")
    cwd: Optional[str] = Field(None, description="工作目录")


class PublishMCPRequest(BaseModel):
    """发布到市场请求."""

    client_keys: List[str] = Field(..., description="要发布的 client_key 列表")
    category_id: Optional[int] = Field(None, description="分类 ID")
    bbk_ids: List[str] = Field(default_factory=list, description="关联 BBK ID 列表")


class PublishMCPResult(BaseModel):
    """单个发布结果."""

    client_key: str = Field(..., description="MCP client key")
    item_id: Optional[str] = Field(None, description="市场 item ID")
    success: bool = Field(..., description="是否成功")
    error: Optional[str] = Field(None, description="错误信息")


class PublishMCPResponse(BaseModel):
    """发布响应."""

    results: List[PublishMCPResult] = Field(
        default_factory=list,
        description="发布结果列表",
    )


@router.get("", response_model=List[MyMCPListItem])
async def list_my_mcp(request: Request) -> List[MyMCPListItem]:
    """获取我的 MCP 列表."""
    _, agent_config = await get_agent_and_config_for_request(request)

    if agent_config.mcp is None or not agent_config.mcp.clients:
        return []

    result = []
    for client_key, client in agent_config.mcp.clients.items():
        result.append(
            MyMCPListItem(
                client_key=client_key,
                name=client.name,
                description=client.description,
                transport=client.transport,
                enabled=client.enabled,
                source=client.source,
                market_client_key=client.market_client_key,
                created_at=client.created_at,
                updated_at=client.updated_at,
            ),
        )

    # 按更新时间降序排序（最新的在前）
    result.sort(key=lambda x: x.updated_at or "", reverse=True)
    return result


def _mask_sensitive_values(client) -> MyMCPDetail:
    """构建详情响应，脱敏 env 和 headers.

    client_key 字段由路由层填充，不在 helper 中设置。
    """
    from ...config.config import MCPClientConfig

    masked_env = (
        {k: _mask_env_value(v) for k, v in client.env.items()}
        if client.env
        else {}
    )
    masked_headers = (
        {k: _mask_env_value(v) for k, v in client.headers.items()}
        if client.headers
        else {}
    )

    return MyMCPDetail(
        client_key="",  # 由路由层填充
        name=client.name,
        description=client.description,
        transport=client.transport,
        enabled=client.enabled,
        source=client.source,
        market_client_key=client.market_client_key,
        created_at=client.created_at,
        updated_at=client.updated_at,
        url=client.url,
        headers=masked_headers,
        command=client.command,
        args=client.args,
        env=masked_env,
        cwd=client.cwd,
        lazy_load=client.lazy_load,
        distributed_by=client.distributed_by,
    )


@router.get("/{client_key}", response_model=MyMCPDetail)
async def get_my_mcp_detail(
    request: Request,
    client_key: str = FastAPIPath(..., description="MCP client key"),
) -> MyMCPDetail:
    """获取单个 MCP 详情."""
    _, agent_config = await get_agent_and_config_for_request(request)

    if agent_config.mcp is None:
        raise HTTPException(404, detail=f"MCP client '{client_key}' not found")

    client = agent_config.mcp.clients.get(client_key)
    if client is None:
        raise HTTPException(404, detail=f"MCP client '{client_key}' not found")

    detail = _mask_sensitive_values(client)
    detail.client_key = client_key
    return detail


@router.post("", response_model=MyMCPDetail, status_code=201)
async def create_my_mcp(
    request: Request,
    body: MyMCPCreateRequest = Body(...),
) -> MyMCPDetail:
    """创建新的 MCP."""
    workspace, agent_config = await get_agent_and_config_for_request(request)

    # 初始化 MCP 配置（如果不存在）
    if agent_config.mcp is None:
        agent_config.mcp = MCPConfig(clients={})

    # 检查 client_key 是否已存在
    if body.client_key in agent_config.mcp.clients:
        raise HTTPException(
            400,
            detail=f"MCP client '{body.client_key}' already exists",
        )

    # 创建新的客户端配置
    now = datetime.now(timezone.utc).isoformat()
    new_client = MCPClientConfig(
        name=body.name,
        description=body.description,
        enabled=True,
        transport=body.transport,
        url=body.url,
        headers=body.headers,
        command=body.command,
        args=body.args,
        env=body.env,
        cwd=body.cwd,
        source="",  # 我创建的
        created_at=now,
        updated_at=now,
    )

    # 添加到配置并保存
    agent_config.mcp.clients[body.client_key] = new_client
    save_agent_config(
        workspace.agent_id,
        agent_config,
        tenant_id=workspace.tenant_id,
    )

    # 热重载配置（异步，非阻塞）
    schedule_agent_reload(
        request,
        workspace.agent_id,
        tenant_id=workspace.tenant_id,
    )

    # 返回详情（脱敏敏感值）
    detail = _mask_sensitive_values(new_client)
    detail.client_key = body.client_key
    return detail


@router.put("/{client_key}", response_model=MyMCPDetail)
async def update_my_mcp(
    request: Request,
    client_key: str = FastAPIPath(...),
    body: MyMCPUpdateRequest = Body(...),
) -> MyMCPDetail:
    """更新 MCP 配置.

    注意：市场分发的 MCP（source 以 "marketplace:" 开头）不允许修改敏感字段
    （transport, url, headers, command, args, env, cwd）。
    """
    workspace, agent_config = await get_agent_and_config_for_request(request)

    if agent_config.mcp is None or client_key not in agent_config.mcp.clients:
        raise HTTPException(404, detail=f"MCP client '{client_key}' not found")

    existing = agent_config.mcp.clients[client_key]

    # 获取更新的数据（只包含实际设置的字段）
    update_data = body.model_dump(exclude_unset=True)

    # 市场分发的 MCP 不允许修改连接配置敏感字段
    if _is_distributed_from_market(existing):
        for field in SENSITIVE_FIELDS:
            if field in update_data:
                raise HTTPException(
                    403,
                    detail=f"Cannot modify '{field}' for distributed MCP",
                )

    # 合并更新数据
    merged_data = existing.model_dump(mode="json")

    # 处理 env/headers 脱敏值恢复（复用 mcp.py 逻辑）
    if "env" in update_data and update_data["env"] is not None:
        update_data["env"] = _restore_original_values(
            update_data["env"],
            existing.env or {},
        )
    if "headers" in update_data and update_data["headers"] is not None:
        update_data["headers"] = _restore_original_values(
            update_data["headers"],
            existing.headers or {},
        )

    merged_data.update(update_data)
    merged_data["updated_at"] = datetime.now(timezone.utc).isoformat()

    updated_client = MCPClientConfig.model_validate(merged_data)
    agent_config.mcp.clients[client_key] = updated_client

    save_agent_config(
        workspace.agent_id,
        agent_config,
        tenant_id=workspace.tenant_id,
    )
    schedule_agent_reload(
        request,
        workspace.agent_id,
        tenant_id=workspace.tenant_id,
    )

    detail = _mask_sensitive_values(updated_client)
    detail.client_key = client_key
    return detail
