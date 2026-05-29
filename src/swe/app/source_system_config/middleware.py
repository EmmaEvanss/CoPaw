# -*- coding: utf-8 -*-
"""Source 系统配置 HTTP 请求绑定中间件。"""

import logging
from typing import Awaitable, Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from .runtime import (
    reset_current_source_system_config,
    set_current_source_system_config,
)
from .service import (
    SourceSystemConfigDataInvalid,
    SourceSystemConfigService,
    SourceSystemConfigUnavailable,
)

logger = logging.getLogger(__name__)


class SourceSystemConfigMiddleware(BaseHTTPMiddleware):
    """按请求 source_id 加载并绑定 effective source 系统配置。"""

    def __init__(
        self,
        app: ASGIApp,
        service: SourceSystemConfigService | None = None,
    ):
        """初始化中间件。"""
        super().__init__(app)
        self.service = service

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """在 request.state 和 ContextVar 中绑定 source 系统配置。"""
        source_id = getattr(request.state, "source_id", None)
        service = self.service or getattr(
            request.app.state,
            "source_system_config_service",
            None,
        )
        if source_id is None or service is None:
            return await call_next(request)

        token = None
        try:
            config = await service.resolve_config(source_id)
            request.state.source_system_config = config
            token = set_current_source_system_config(config)
            return await call_next(request)
        except SourceSystemConfigUnavailable as exc:
            logger.error("Source 系统配置不可用: %s", exc)
            return JSONResponse(
                status_code=503,
                content={"detail": "Source system config unavailable"},
            )
        except SourceSystemConfigDataInvalid as exc:
            logger.error("Source 系统配置数据损坏: %s", exc)
            return JSONResponse(
                status_code=500,
                content={"detail": "Source system config data is invalid"},
            )
        finally:
            if token is not None:
                reset_current_source_system_config(token)
