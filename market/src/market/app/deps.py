# -*- coding: utf-8 -*-
"""FastAPI 依赖注入."""

from typing import Annotated, Optional
from urllib.parse import unquote
from fastapi import Depends, HTTPException, Request
from ..database.connection import DatabaseConnection


def get_db(request: Request) -> DatabaseConnection:
    """从 app.state 获取数据库连接."""
    return request.app.state.db


def require_source_id(x_source_id: Optional[str]) -> str:
    """Validate X-Source-Id header; raise 400 if missing."""
    if not x_source_id:
        raise HTTPException(
            status_code=400,
            detail="X-Source-Id header is required",
        )
    return x_source_id


def decode_user_name(user_name: str | None) -> str | None:
    """解码 URL 编码的用户名。

    前端 authHeaders.ts 对 X-User-Name 进行 encodeURIComponent 编码，
    market 服务没有 TenantIdentityMiddleware 解码，需要手动解码。
    """
    if not user_name:
        return user_name
    try:
        decoded = unquote(user_name)
        return decoded if decoded != user_name else user_name
    except Exception:
        return user_name


DbDep = Annotated[DatabaseConnection, Depends(get_db)]
