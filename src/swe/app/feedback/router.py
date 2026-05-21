# -*- coding: utf-8 -*-
"""回答反馈接口路由。"""

import logging
from typing import Optional
from urllib.parse import unquote

from fastapi import APIRouter, HTTPException, Request

from .models import (
    FeedbackCreate,
    FeedbackCreateResponse,
    FeedbackLookupResponse,
    FeedbackSessionLookupResponse,
)
from .service import FeedbackService
from .store import FeedbackStore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/feedback", tags=["feedback"])

_store: Optional[FeedbackStore] = None
_service: Optional[FeedbackService] = None


def init_feedback_module(db=None) -> None:
    """初始化回答反馈模块。

    Args:
        db: 已连接的数据库对象

    Raises:
        RuntimeError: 数据库不可用时抛出异常
    """
    global _store, _service

    if db is None or not getattr(db, "is_connected", False):
        raise RuntimeError("Feedback module requires a connected database.")

    _store = FeedbackStore(db)
    _service = FeedbackService(_store)
    logger.info("Feedback module initialized")


def get_service() -> FeedbackService:
    """获取回答反馈服务实例。"""
    if _service is None:
        raise RuntimeError("Feedback module not initialized")
    return _service


def _first_text(*values: Optional[str]) -> Optional[str]:
    """返回第一个非空字符串。"""
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _decode_header(value: Optional[str]) -> Optional[str]:
    """解码前端为避免 header 编码问题而转义的文本。"""
    if not value:
        return None
    return unquote(value)


def _get_request_user_sap(request: Request) -> Optional[str]:
    """从请求上下文解析当前用户 SAP。"""
    return _first_text(
        getattr(request.state, "user_id", None),
        request.headers.get("X-User-Id"),
    )


def _get_request_source_id(request: Request) -> Optional[str]:
    """从请求上下文解析当前来源标识。"""
    return getattr(request.state, "source_id", None) or request.headers.get(
        "X-Source-Id",
    )


@router.get("/current", response_model=FeedbackLookupResponse)
async def get_feedback(
    request: Request,
    response_id: Optional[str] = None,
    trace_id: Optional[str] = None,
) -> FeedbackLookupResponse:
    """查询当前回答是否已存在反馈记录。"""
    try:
        service = get_service()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    record = await service.get_feedback(
        source_id=_get_request_source_id(request),
        response_id=_first_text(response_id),
        trace_id=_first_text(trace_id),
    )
    return FeedbackLookupResponse(feedback=record)


@router.get("/session", response_model=FeedbackSessionLookupResponse)
async def get_session_feedbacks(
    request: Request,
    session_id: Optional[str] = None,
    chat_id: Optional[str] = None,
) -> FeedbackSessionLookupResponse:
    """按聊天 ID 和运行时会话 ID 查询反馈列表。"""
    try:
        service = get_service()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    items = await service.list_feedbacks_by_session(
        source_id=_get_request_source_id(request),
        chat_id=_first_text(chat_id),
        session_id=_first_text(
            session_id,
            getattr(request.state, "session_id", None),
        ),
    )
    return FeedbackSessionLookupResponse(items=items)


@router.post("", response_model=FeedbackCreateResponse)
async def create_feedback(
    request: Request,
    feedback: FeedbackCreate,
) -> FeedbackCreateResponse:
    """提交一次回答或任务结果反馈。"""
    try:
        service = get_service()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    enriched = feedback.model_copy(
        update={
            "feedback_user_name": _first_text(
                feedback.feedback_user_name,
                getattr(request.state, "user_name", None),
                _decode_header(request.headers.get("X-User-Name")),
            ),
            "feedback_user_sap": _first_text(
                feedback.feedback_user_sap,
                _get_request_user_sap(request),
            ),
            "feedback_branch": _first_text(
                feedback.feedback_branch,
                getattr(request.state, "bbk_id", None),
                request.headers.get("X-Bbk-Id"),
            ),
            "feedback_sub_branch": _first_text(
                feedback.feedback_sub_branch,
                request.headers.get("X-Org-Code"),
            ),
            "feedback_position": _first_text(
                feedback.feedback_position,
                request.headers.get("X-Position-Id"),
            ),
        },
    )

    try:
        feedback_id, updated, trace_id = await service.create_feedback(
            enriched,
            source_id=_get_request_source_id(request),
        )
    except Exception as exc:
        logger.exception("提交回答反馈失败: %s", exc)
        raise HTTPException(
            status_code=500,
            detail="保存反馈失败，请检查反馈表结构与后端日志。",
        ) from exc

    return FeedbackCreateResponse(
        feedback_id=feedback_id,
        updated=updated,
        trace_id=trace_id,
    )
