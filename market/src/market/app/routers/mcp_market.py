# -*- coding: utf-8 -*-
"""市场 MCP 管理路由（管理员）。"""

import json
import re
from typing import Optional

from fastapi import APIRouter, File, Form, Header, HTTPException, Request, UploadFile, status

from ...marketplace.schemas import (
    DistributeRequest,
    DistributeResponse,
    MarketMCPItem,
    PublishMCPRequest,
    UploadMCPResponse,
)
from ...marketplace.fs import load_mcp_config, load_index
from ..deps import require_source_id

router = APIRouter()


def _require_manager(x_manager: Optional[str]) -> None:
    """校验管理员权限。"""
    if x_manager != "true":
        raise HTTPException(status_code=403, detail="Manager access required")


@router.post(
    "/market/mcp",
    response_model=MarketMCPItem,
    status_code=status.HTTP_201_CREATED,
)
async def publish_mcp(
    req: PublishMCPRequest,
    request: Request,
    x_source_id: Optional[str] = Header(default=None, alias="X-Source-Id"),
    x_manager: Optional[str] = Header(default=None, alias="X-Manager"),
):
    """发布 MCP 到市场（管理员）。"""
    source_id = require_source_id(x_source_id)
    _require_manager(x_manager)
    svc = request.app.state.marketplace
    item = await svc.publish_mcp(source_id, req)
    return MarketMCPItem(
        item_id=item.item_id,
        client_key=item.client_key,
        name=item.name,
        description=item.description,
        creator_id=item.creator_id,
        creator_name=item.creator_name,
        category_id=item.category_id,
        bbk_ids=item.bbk_ids,
        created_at=item.created_at,
        updated_at=item.updated_at,
        call_count=0,
        user_count=0,
    )


@router.post(
    "/market/mcp/upload",
    response_model=UploadMCPResponse,
)
async def upload_mcp(
    request: Request,
    file: UploadFile = File(...),
    name: Optional[str] = Form(default=None),
    description: Optional[str] = Form(default=""),
    category_id: Optional[int] = Form(default=None),
    bbk_ids: Optional[str] = Form(default=None),
    x_source_id: Optional[str] = Header(default=None, alias="X-Source-Id"),
    x_manager: Optional[str] = Header(default=None, alias="X-Manager"),
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    x_user_name: Optional[str] = Header(default=None, alias="X-User-Name"),
):
    """上传 MCP 连接器文件到市场（管理员）。"""
    source_id = require_source_id(x_source_id)
    _require_manager(x_manager)

    # 校验文件格式
    if not file.filename or not file.filename.endswith(".json"):
        return UploadMCPResponse(success=False, error="Only .json files are accepted")

    try:
        content = await file.read()
        file_data = json.loads(content.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        return UploadMCPResponse(success=False, error=f"Invalid JSON: {e}")

    # 提取 client_key 和 config
    client_key = file_data.get("client_key", "")
    config = file_data.get("config", file_data)

    # 若未提供 client_key，从文件名生成
    if not client_key:
        client_key = re.sub(r"[^a-zA-Z0-9_-]", "-", file.filename[:-5])

    final_name = name or config.get("name", client_key)

    # 构建发布请求
    req = PublishMCPRequest(
        client_key=client_key,
        name=final_name,
        description=description or config.get("description", ""),
        creator_id=x_user_id or "unknown",
        creator_name=x_user_name or "",
        category_id=category_id,
        bbk_ids=json.loads(bbk_ids) if bbk_ids else [],
        config=config,
    )

    svc = request.app.state.marketplace
    try:
        await svc.publish_mcp(source_id, req)
        return UploadMCPResponse(success=True)
    except Exception as e:
        return UploadMCPResponse(success=False, error=str(e))


@router.post(
    "/market/mcp/{item_id}/distribute",
    response_model=DistributeResponse,
)
async def distribute_mcp(
    item_id: str,
    req: DistributeRequest,
    request: Request,
    x_source_id: Optional[str] = Header(default=None, alias="X-Source-Id"),
    x_manager: Optional[str] = Header(default=None, alias="X-Manager"),
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    x_user_name: Optional[str] = Header(default=None, alias="X-User-Name"),
):
    """分发 MCP（管理员）。"""
    source_id = require_source_id(x_source_id)
    _require_manager(x_manager)
    svc = request.app.state.marketplace

    # 检查条目是否存在
    items = load_index(svc.marketplace_root, source_id)
    item = next(
        (i for i in items if i.item_id == item_id and i.item_type == "mcp"),
        None,
    )
    if item is None:
        raise HTTPException(status_code=404, detail="MCP not found or already deleted")

    try:
        result = await svc.distribute_mcp(
            source_id,
            item_id,
            operator_id=x_user_id or "",
            operator_name=x_user_name or "",
            req=req,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return result


@router.delete(
    "/market/mcp/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_mcp(
    item_id: str,
    request: Request,
    x_source_id: Optional[str] = Header(default=None, alias="X-Source-Id"),
    x_manager: Optional[str] = Header(default=None, alias="X-Manager"),
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    x_user_name: Optional[str] = Header(default=None, alias="X-User-Name"),
):
    """删除市场 MCP（管理员）。"""
    source_id = require_source_id(x_source_id)
    _require_manager(x_manager)
    svc = request.app.state.marketplace

    # 检查条目是否存在
    items = load_index(svc.marketplace_root, source_id)
    item = next(
        (i for i in items if i.item_id == item_id and i.item_type == "mcp"),
        None,
    )
    if item is None:
        raise HTTPException(status_code=404, detail="MCP not found or already deleted")

    ok = await svc.delete_mcp(
        source_id,
        item_id,
        operator_id=x_user_id or "",
        operator_name=x_user_name or "",
    )
    if not ok:
        raise HTTPException(status_code=404, detail="MCP not found")


@router.post("/market/mcp/{item_id}/test")
async def test_market_mcp(
    item_id: str,
    request: Request,
    x_source_id: Optional[str] = Header(default=None, alias="X-Source-Id"),
):
    """测试市场 MCP 连接。"""
    source_id = require_source_id(x_source_id)
    svc = request.app.state.marketplace

    # 获取 MCP 配置
    items = load_index(svc.marketplace_root, source_id)
    item = next(
        (i for i in items if i.item_id == item_id and i.item_type == "mcp"),
        None,
    )
    if item is None:
        raise HTTPException(status_code=404, detail="MCP not found or already deleted")

    mcp_config = load_mcp_config(svc.marketplace_root, source_id, item_id)
    if mcp_config is None:
        raise HTTPException(status_code=404, detail="MCP config not found")

    # 测试连接（使用原始值）
    import asyncio

    try:
        # 导入 MCP 客户端类（这些在 swe 模块，不是 market）
        from swe.config.config import MCPClientConfig
        from swe.app.mcp.stateful_client import StatefulStdioClient, HttpStatefulClient

        config_data = mcp_config.get("config", {})
        client_config = MCPClientConfig(**config_data)

        if client_config.transport == "stdio":
            mcp_client = StatefulStdioClient(
                name="test",
                command=client_config.command,
                args=client_config.args,
                env=client_config.env,
                cwd=client_config.cwd or None,
            )
        else:
            mcp_client = HttpStatefulClient(
                name="test",
                transport=client_config.transport,
                url=client_config.url,
                headers=client_config.headers,
            )

        await mcp_client.connect()
        tools = await mcp_client.list_tools(timeout=30.0)
        await mcp_client.close()

        return {
            "success": True,
            "tools": [{"name": t.name, "description": t.description or ""} for t in tools],
        }
    except asyncio.TimeoutError:
        return {"success": False, "error": "连接超时"}
    except Exception as e:
        return {"success": False, "error": str(e)}
