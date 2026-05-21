# -*- coding: utf-8 -*-
"""回答反馈数据模型。"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class FeedbackCreate(BaseModel):
    """提交回答反馈的请求体。"""

    id: Optional[int] = Field(default=None, ge=1)
    feedback_content: str = Field(..., min_length=1, max_length=2000)
    feedback_options: list[str] = Field(default_factory=list, max_length=10)
    response_id: Optional[str] = Field(default=None, max_length=128)
    trace_id: Optional[str] = Field(default=None, max_length=36)
    chat_id: Optional[str] = Field(default=None, max_length=128)
    session_id: Optional[str] = Field(default=None, max_length=256)
    cron_task_name: Optional[str] = Field(default=None, max_length=255)
    cron_task_id: Optional[str] = Field(default=None, max_length=128)
    feedback_user_name: Optional[str] = Field(default=None, max_length=128)
    feedback_user_sap: Optional[str] = Field(default=None, max_length=64)
    feedback_branch: Optional[str] = Field(default=None, max_length=128)
    feedback_sub_branch: Optional[str] = Field(default=None, max_length=128)
    feedback_position: Optional[str] = Field(default=None, max_length=128)


class FeedbackRecord(FeedbackCreate):
    """已保存的回答反馈记录。"""

    id: int
    source_id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class FeedbackLookupResponse(BaseModel):
    """查询单条回答反馈的响应。"""

    success: bool = True
    feedback: Optional[FeedbackRecord] = None


class FeedbackSessionLookupResponse(BaseModel):
    """按会话查询反馈列表的响应。"""

    success: bool = True
    items: list[FeedbackRecord] = Field(default_factory=list)


class FeedbackCreateResponse(BaseModel):
    """提交回答反馈后的响应。"""

    success: bool = True
    feedback_id: Optional[int] = None
    updated: bool = False
    trace_id: Optional[str] = None
