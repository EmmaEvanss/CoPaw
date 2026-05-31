# -*- coding: utf-8 -*-
"""HTML 预览点击统计数据库存储。"""

from datetime import datetime
from typing import Any, Optional

from .models import (
    HtmlPreviewClickEventCreate,
    HtmlPreviewClickSummaryItem,
)


class HtmlPreviewClickStore:
    """负责 HTML 预览点击事件的落库与聚合查询。"""

    def __init__(self, db: Optional[Any] = None):
        """初始化点击统计存储。

        Args:
            db: 已连接的数据库对象
        """
        self.db = db
        self._use_db = db is not None and db.is_connected

    @staticmethod
    def _clean_text(value: Optional[str]) -> Optional[str]:
        """清理空字符串，避免聚合字段里混入无意义值。"""
        if not isinstance(value, str):
            return None
        stripped = value.strip()
        return stripped or None

    @staticmethod
    def _to_summary_item(row: dict[str, Any]) -> HtmlPreviewClickSummaryItem:
        """把数据库行转换为点击聚合模型。"""
        return HtmlPreviewClickSummaryItem(
            button_label=row.get("button_label") or "未知按钮",
            button_id=row.get("button_id"),
            button_name=row.get("button_name"),
            button_text=row.get("button_text"),
            bbk_id=row.get("bbk_id"),
            cron_task_id=row.get("cron_task_id"),
            cron_task_name=row.get("cron_task_name"),
            file_url=row.get("file_url"),
            file_name=row.get("file_name"),
            click_count=int(row.get("click_count") or 0),
            last_clicked_at=row.get("last_clicked_at"),
        )

    async def create_event(
        self,
        event: HtmlPreviewClickEventCreate,
    ) -> None:
        """保存一条 HTML 预览按钮点击明细。"""
        if not self._use_db:
            return

        query = """
            INSERT INTO swe_html_preview_click_events (
                source_id,
                user_id,
                bbk_id,
                cron_task_id,
                cron_task_name,
                file_url,
                file_name,
                button_id,
                button_name,
                button_text,
                clicked_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        await self.db.execute(
            query,
            (
                self._clean_text(event.source_id),
                self._clean_text(event.user_id),
                self._clean_text(event.bbk_id),
                self._clean_text(event.cron_task_id),
                self._clean_text(event.cron_task_name),
                event.file_url,
                self._clean_text(event.file_name),
                self._clean_text(event.button_id),
                self._clean_text(event.button_name),
                self._clean_text(event.button_text),
                event.clicked_at or datetime.now(),
            ),
        )

    async def list_summary(
        self,
        *,
        source_id: Optional[str],
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        bbk_ids: Optional[list[str]] = None,
        cron_task_id: Optional[str] = None,
        file_url: Optional[str] = None,
        limit: int = 100,
    ) -> list[HtmlPreviewClickSummaryItem]:
        """按按钮、任务和 HTML 文件聚合点击次数。"""
        if not self._use_db:
            return []

        where_clauses: list[str] = []
        params: list[Any] = []
        if source_id:
            where_clauses.append("source_id <=> %s")
            params.append(source_id)
        if start_time:
            where_clauses.append("clicked_at >= %s")
            params.append(start_time)
        if end_time:
            where_clauses.append("clicked_at <= %s")
            params.append(end_time)
        if bbk_ids:
            placeholders = ", ".join(["%s"] * len(bbk_ids))
            where_clauses.append(f"bbk_id IN ({placeholders})")
            params.extend(bbk_ids)
        if cron_task_id:
            where_clauses.append("cron_task_id = %s")
            params.append(cron_task_id)
        if file_url:
            where_clauses.append("file_url = %s")
            params.append(file_url)

        where_sql = (
            f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        )
        safe_limit = max(1, min(limit, 200))

        query = f"""
            SELECT
                COALESCE(
                    NULLIF(button_name, ''),
                    NULLIF(button_text, ''),
                    NULLIF(button_id, ''),
                    '未知按钮'
                ) AS button_label,
                button_id,
                button_name,
                button_text,
                cron_task_id,
                cron_task_name,
                file_url,
                file_name,
                COUNT(*) AS click_count,
                MAX(clicked_at) AS last_clicked_at
            FROM swe_html_preview_click_events
            {where_sql}
            GROUP BY
                button_id,
                button_name,
                button_text,
                cron_task_id,
                cron_task_name,
                file_url,
                file_name
            ORDER BY click_count DESC, last_clicked_at DESC
            LIMIT {safe_limit}
        """
        rows = await self.db.fetch_all(query, tuple(params))
        return [self._to_summary_item(row) for row in rows]
