# -*- coding: utf-8 -*-
"""HTML 预览点击统计数据模型。"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class HtmlPreviewClickEventCreate(BaseModel):
    """提交 HTML 预览按钮点击事件的请求体。"""

    source_id: Optional[str] = Field(default=None, max_length=64)
    user_id: Optional[str] = Field(default=None, max_length=128)
    bbk_id: Optional[str] = Field(default=None, max_length=128)
    cron_task_id: Optional[str] = Field(default=None, max_length=128)
    cron_task_name: Optional[str] = Field(default=None, max_length=255)
    file_url: str = Field(..., min_length=1, max_length=4096)
    file_name: Optional[str] = Field(default=None, max_length=512)
    button_id: Optional[str] = Field(default=None, max_length=255)
    button_name: Optional[str] = Field(default=None, max_length=255)
    button_text: Optional[str] = Field(default=None, max_length=512)
    customer_info: Optional[dict[str, str]] = None
    clicked_at: Optional[datetime] = None


class HtmlPreviewClickCreateResponse(BaseModel):
    """保存 HTML 预览点击事件后的响应。"""

    success: bool = True


class HtmlPreviewClickSummaryItem(BaseModel):
    """HTML 预览点击聚合结果。"""

    button_label: str
    button_id: Optional[str] = None
    button_name: Optional[str] = None
    button_text: Optional[str] = None
    bbk_id: Optional[str] = None
    cron_task_id: Optional[str] = None
    cron_task_name: Optional[str] = None
    file_url: Optional[str] = None
    file_name: Optional[str] = None
    click_count: int = 0
    last_clicked_at: Optional[datetime] = None


class HtmlPreviewClickSummaryResponse(BaseModel):
    """HTML 预览点击聚合查询响应。"""

    success: bool = True
    items: list[HtmlPreviewClickSummaryItem] = Field(default_factory=list)


class HtmlPreviewClickEventItem(BaseModel):
    """HTML 预览点击明细。"""

    id: int
    source_id: Optional[str] = None
    user_id: Optional[str] = None
    bbk_id: Optional[str] = None
    cron_task_id: Optional[str] = None
    cron_task_name: Optional[str] = None
    file_url: str
    file_name: Optional[str] = None
    button_id: Optional[str] = None
    button_name: Optional[str] = None
    button_text: Optional[str] = None
    customer_info: Optional[dict[str, str]] = None
    clicked_at: Optional[datetime] = None


class HtmlPreviewClickEventListResponse(BaseModel):
    """HTML 预览点击明细查询响应。"""

    success: bool = True
    items: list[HtmlPreviewClickEventItem] = Field(default_factory=list)
