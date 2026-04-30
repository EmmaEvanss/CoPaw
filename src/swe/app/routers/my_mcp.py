# -*- coding: utf-8 -*-
"""我的 MCP 管理路由."""

from __future__ import annotations

from typing import List, Dict, Optional, Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

router = APIRouter(prefix="/my-mcp", tags=["my-mcp"])


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
