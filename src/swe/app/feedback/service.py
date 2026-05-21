# -*- coding: utf-8 -*-
"""回答反馈业务服务。"""

from typing import Optional

from .models import FeedbackCreate, FeedbackRecord
from .store import FeedbackStore


class FeedbackService:
    """封装回答反馈保存逻辑。"""

    def __init__(self, store: FeedbackStore):
        """初始化反馈服务。

        Args:
            store: 反馈存储实例
        """
        self.store = store

    async def get_feedback(
        self,
        *,
        source_id: Optional[str],
        feedback_id: Optional[int] = None,
        response_id: Optional[str] = None,
        trace_id: Optional[str] = None,
    ) -> FeedbackRecord | None:
        """按反馈标识查询已存在的回答反馈。"""
        return await self.store.get_feedback(
            source_id=source_id,
            feedback_id=feedback_id,
            response_id=response_id,
            trace_id=trace_id,
        )

    async def list_feedbacks_by_session(
        self,
        *,
        source_id: Optional[str],
        session_id: Optional[str],
        chat_id: Optional[str] = None,
    ) -> list[FeedbackRecord]:
        """按聊天 ID 或运行时会话 ID 查询反馈列表。"""
        return await self.store.list_feedbacks_by_session(
            source_id=source_id,
            session_id=session_id,
            chat_id=chat_id,
        )

    async def create_feedback(
        self,
        feedback: FeedbackCreate,
        *,
        source_id: Optional[str],
    ) -> tuple[int | None, bool, Optional[str]]:
        """保存或更新用户对某次回答或任务结果的反馈。"""
        return await self.store.upsert_feedback(
            feedback,
            source_id=source_id,
        )
