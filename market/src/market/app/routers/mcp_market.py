# -*- coding: utf-8 -*-
"""市场 MCP 管理路由（管理员）。"""

import json
import re
from typing import Optional
from urllib.parse import unquote

from fastapi import (
    APIRouter,
    File,
    Form,
    Header,
    HTTPException,
    Request,
    UploadFile,
    status,
)

from ...marketplace.schemas import (
    MCPDistributionRequest,
    MCPDistributionResponse,
    MarketMCPDetail,
    MarketMCPItem,
    PublishMCPRequest,
    UpdateMarketMCPMetadataRequest,
    UploadMCPResponse,
)
from ...marketplace.fs import load_mcp_config, load_index
from ...marketplace.service import _normalize_market_mcp_config_data
from swe.config.config import MCPClientConfig
from swe.config.context import tenant_context
from ..deps import require_source_id
from .my_mcp import _test_mcp_connection

router = APIRouter()


def _require_manager(x_manager: Optional[str]) -> None:
    """校验管理员权限。"""
    if x_manager != "true":
        raise HTTPException(status_code=403, detail="Manager access required")


def _normalize_client_key(value: str) -> str:
    """规范化 client_key，保持与前端自动生成逻辑一致。"""
    normalized = re.sub(r"[^a-z0-9_-]+", "-", value.strip().lower())
    normalized = re.sub(r"-+", "-", normalized).strip("-_")
    return normalized or "mcp"


def _infer_transport(config: dict) -> Optional[str]:
    """从兼容格式中推断 transport。"""
    raw_transport = (
        config.get("transport")
        or config.get("type")
        or (config.get("advanced") or {}).get("transport")
    )
    if isinstance(raw_transport, str):
        normalized = raw_transport.lower()
        if normalized == "stdio":
            return "stdio"
        if normalized == "sse":
            return "sse"
        if normalized in {"streamable_http", "streamable-http"}:
            return "streamable_http"
    if (
        isinstance(config.get("command"), str)
        and config.get("command", "").strip()
    ):
        return "stdio"
    if isinstance(config.get("url"), str) and config.get("url", "").strip():
        return "streamable_http"
    return None


def _extract_upload_payload(
    filename: str,
    file_data: dict,
) -> tuple[str, str, dict]:
    """从上传文件中提取 client_key、name 和规范化后的 config。"""
    fallback_name = re.sub(
        r"\.(json|mcp\.json)$",
        "",
        filename,
        flags=re.IGNORECASE,
    )
    config = {}
    client_key = ""
    name = ""

    mcp_servers = file_data.get("mcpServers")
    if isinstance(mcp_servers, dict) and mcp_servers:
        first_key, first_value = next(iter(mcp_servers.items()))
        if isinstance(first_value, dict):
            client_key = str(first_key)
            config = dict(first_value)
            name = str(config.get("name") or "")

    if not config:
        raw_config = file_data.get("config", file_data)
        if isinstance(raw_config, dict):
            config = dict(raw_config)
        client_key = str(file_data.get("client_key") or client_key or "")
        name = str(config.get("name") or file_data.get("name") or name or "")

    if not config:
        raise ValueError("文件格式不正确")

    transport = _infer_transport(config)
    if not transport:
        raise ValueError("文件格式不正确：无法识别连接方式")

    config["transport"] = transport
    final_name = name.strip() or fallback_name
    final_client_key = _normalize_client_key(
        client_key or final_name or fallback_name,
    )
    return final_client_key, final_name, config


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
        chinese_name=item.chinese_name,
        description=item.description,
        guidance=item.guidance,
        version=item.version,
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
    chinese_name: Optional[str] = Form(default=""),
    description: Optional[str] = Form(default=""),
    guidance: Optional[str] = Form(default=""),
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
        return UploadMCPResponse(
            success=False,
            error="Only .json files are accepted",
        )

    try:
        content = await file.read()
        file_data = json.loads(content.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        return UploadMCPResponse(success=False, error=f"Invalid JSON: {e}")

    try:
        client_key, inferred_name, config = _extract_upload_payload(
            file.filename,
            file_data,
        )
    except ValueError as e:
        return UploadMCPResponse(success=False, error=str(e))

    final_name = name or inferred_name

    # 构建发布请求
    req = PublishMCPRequest(
        client_key=client_key,
        name=final_name,
        chinese_name=chinese_name or "",
        description=description or config.get("description", ""),
        guidance=guidance or "",
        creator_id=x_user_id or "unknown",
        creator_name=unquote(x_user_name or ""),
        category_id=None,
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
    response_model=MCPDistributionResponse,
)
async def distribute_mcp(
    item_id: str,
    req: MCPDistributionRequest,
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
        raise HTTPException(
            status_code=404,
            detail="MCP not found or already deleted",
        )

    try:
        result = await svc.distribute_mcp(
            source_id,
            item_id,
            operator_id=x_user_id or "",
            operator_name=unquote(x_user_name or ""),
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
        raise HTTPException(
            status_code=404,
            detail="MCP not found or already deleted",
        )

    ok = await svc.delete_mcp(
        source_id,
        item_id,
        operator_id=x_user_id or "",
        operator_name=unquote(x_user_name or ""),
    )
    if not ok:
        raise HTTPException(status_code=404, detail="MCP not found")


@router.put("/market/mcp/{item_id}/metadata", response_model=MarketMCPDetail)
async def update_market_mcp_metadata(
    item_id: str,
    payload: UpdateMarketMCPMetadataRequest,
    request: Request,
    x_source_id: Optional[str] = Header(default=None, alias="X-Source-Id"),
    x_bbk_id: Optional[str] = Header(default=None, alias="X-Bbk-Id"),
    x_manager: Optional[str] = Header(default=None, alias="X-Manager"),
):
    """更新 MCP 市场条目的展示元数据。"""
    source_id = require_source_id(x_source_id)
    _require_manager(x_manager)
    user_bbk_id = x_bbk_id or "100"
    svc = request.app.state.marketplace
    try:
        svc.update_mcp_metadata(
            source_id=source_id,
            item_id=item_id,
            chinese_name=payload.chinese_name,
            description=payload.description,
            guidance=payload.guidance,
            bbk_ids=payload.bbk_ids,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    detail = await svc.get_mcp_detail(source_id, item_id, user_bbk_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="MCP not found")
    return detail


@router.post("/market/mcp/{item_id}/test")
async def test_market_mcp(
    item_id: str,
    request: Request,
    x_source_id: Optional[str] = Header(default=None, alias="X-Source-Id"),
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
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
        raise HTTPException(
            status_code=404,
            detail="MCP not found or already deleted",
        )

    mcp_config = load_mcp_config(svc.marketplace_root, source_id, item_id)
    if mcp_config is None:
        raise HTTPException(status_code=404, detail="MCP config not found")

    config_data = _normalize_market_mcp_config_data(
        mcp_config.get("config", {}),
    )
    if not config_data.get("name"):
        config_data["name"] = item.name or item.client_key or "market-mcp"
    config_data.setdefault("description", item.description or "")
    config_data.setdefault("enabled", True)
    client_config = MCPClientConfig(**config_data)

    # 与 MyMCP 测试连接保持同一实现，避免两处逻辑继续漂移。
    tenant_id = x_user_id or "default"
    with tenant_context(
        tenant_id=tenant_id,
        user_id=tenant_id,
        source_id=source_id,
    ):
        return await _test_mcp_connection(client_config)
