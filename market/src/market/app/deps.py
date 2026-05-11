# -*- coding: utf-8 -*-
"""FastAPI 依赖注入."""

from typing import Annotated, Optional
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


DbDep = Annotated[DatabaseConnection, Depends(get_db)]
