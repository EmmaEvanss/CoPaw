# -*- coding: utf-8 -*-
"""HTML 预览点击统计数据库存储。"""

import json
from datetime import datetime
from typing import Any, Optional

from .models import (
    HtmlPreviewClickEventCreate,
    HtmlPreviewClickEventItem,
    HtmlPreviewClickSummaryItem,
    HtmlPreviewCustomerClickSummaryItem,
)

CUSTOMER_ID_SQL = (
    "NULLIF(JSON_UNQUOTE(JSON_EXTRACT(customer_info, '$.customer_id')), '')"
)
CUSTOMER_NAME_SQL = """
    COALESCE(
        NULLIF(JSON_UNQUOTE(JSON_EXTRACT(customer_info, '$.name')), ''),
        NULLIF(JSON_UNQUOTE(JSON_EXTRACT(customer_info, '$.customer_name')), ''),
        NULLIF(JSON_UNQUOTE(JSON_EXTRACT(customer_info, '$."客户姓名"')), ''),
        NULLIF(JSON_UNQUOTE(JSON_EXTRACT(customer_info, '$."客户名称"')), ''),
        NULLIF(JSON_UNQUOTE(JSON_EXTRACT(customer_info, '$."姓名"')), '')
    )
"""
INSIGHT_BUTTON_SQL = """
    (
        LOWER(COALESCE(button_id, '')) LIKE '%insight%'
        OR COALESCE(button_name, '') LIKE '%洞察%'
        OR COALESCE(button_text, '') LIKE '%洞察%'
    )
"""
PHONE_BUTTON_SQL = """
    (
        LOWER(COALESCE(button_id, '')) LIKE '%phone%'
        OR COALESCE(button_name, '') LIKE '%电访%'
        OR COALESCE(button_name, '') LIKE '%电话访问%'
        OR COALESCE(button_text, '') LIKE '%电访%'
        OR COALESCE(button_text, '') LIKE '%电话访问%'
    )
"""


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
    def _encode_customer_info(
        value: Optional[dict[str, str]],
    ) -> Optional[str]:
        """把客户信息序列化为 JSON，避免数据库驱动差异影响写入。"""
        if not value:
            return None
        cleaned = {
            str(key).strip(): str(item).strip()
            for key, item in value.items()
            if str(key).strip() and str(item).strip()
        }
        return json.dumps(cleaned, ensure_ascii=False) if cleaned else None

    @staticmethod
    def _decode_customer_info(value: Any) -> Optional[dict[str, str]]:
        """解析数据库中的客户信息 JSON。"""
        if not value:
            return None
        if isinstance(value, dict):
            return {str(key): str(item) for key, item in value.items()}
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError):
            return None
        if not isinstance(parsed, dict):
            return None
        return {str(key): str(item) for key, item in parsed.items()}

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

    @staticmethod
    def _to_customer_summary_item(
        row: dict[str, Any],
    ) -> HtmlPreviewCustomerClickSummaryItem:
        """把数据库行转换为客户维度点击聚合模型。"""
        return HtmlPreviewCustomerClickSummaryItem(
            customer_id=row.get("customer_id"),
            customer_name=row.get("customer_name") or "未知客户",
            insight_count=int(row.get("insight_count") or 0),
            phone_count=int(row.get("phone_count") or 0),
            last_clicked_at=row.get("last_clicked_at"),
        )

    @classmethod
    def _to_event_item(cls, row: dict[str, Any]) -> HtmlPreviewClickEventItem:
        """把数据库行转换为点击明细模型。"""
        return HtmlPreviewClickEventItem(
            id=int(row.get("id") or 0),
            source_id=row.get("source_id"),
            user_id=row.get("user_id"),
            bbk_id=row.get("bbk_id"),
            cron_task_id=row.get("cron_task_id"),
            cron_task_name=row.get("cron_task_name"),
            file_url=row.get("file_url") or "",
            file_name=row.get("file_name"),
            button_id=row.get("button_id"),
            button_name=row.get("button_name"),
            button_text=row.get("button_text"),
            customer_info=cls._decode_customer_info(row.get("customer_info")),
            clicked_at=row.get("clicked_at"),
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
                customer_info,
                clicked_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                self._encode_customer_info(event.customer_info),
                event.clicked_at or datetime.now(),
            ),
        )

    async def list_events(
        self,
        *,
        source_id: Optional[str],
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        bbk_ids: Optional[list[str]] = None,
        cron_task_id: Optional[str] = None,
        file_url: Optional[str] = None,
        limit: int = 100,
    ) -> list[HtmlPreviewClickEventItem]:
        """查询 HTML 预览按钮点击明细。"""
        if not self._use_db:
            return []

        where_sql, params = self._build_where_clause(
            source_id=source_id,
            start_time=start_time,
            end_time=end_time,
            bbk_ids=bbk_ids,
            cron_task_id=cron_task_id,
            file_url=file_url,
        )
        safe_limit = max(1, min(limit, 200))
        query = f"""
            SELECT
                id,
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
                customer_info,
                clicked_at
            FROM swe_html_preview_click_events
            {where_sql}
            ORDER BY clicked_at DESC, id DESC
            LIMIT {safe_limit}
        """
        rows = await self.db.fetch_all(query, tuple(params))
        return [self._to_event_item(row) for row in rows]

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

        where_sql, params = self._build_where_clause(
            source_id=source_id,
            start_time=start_time,
            end_time=end_time,
            bbk_ids=bbk_ids,
            cron_task_id=cron_task_id,
            file_url=file_url,
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

    async def list_customer_summary(
        self,
        *,
        source_id: Optional[str],
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        bbk_ids: Optional[list[str]] = None,
        cron_task_id: Optional[str] = None,
        file_url: Optional[str] = None,
        limit: int = 100,
    ) -> list[HtmlPreviewCustomerClickSummaryItem]:
        """按客户聚合洞察和电访按钮点击次数。"""
        if not self._use_db:
            return []

        where_sql, params = self._build_where_clause(
            source_id=source_id,
            start_time=start_time,
            end_time=end_time,
            bbk_ids=bbk_ids,
            cron_task_id=cron_task_id,
            file_url=file_url,
        )
        safe_limit = max(1, min(limit, 200))

        query = f"""
            SELECT
                customer_id,
                COALESCE(customer_name, '未知客户') AS customer_name,
                SUM(CASE WHEN is_insight THEN 1 ELSE 0 END) AS insight_count,
                SUM(CASE WHEN is_phone THEN 1 ELSE 0 END) AS phone_count,
                MAX(clicked_at) AS last_clicked_at
            FROM (
                SELECT
                    {CUSTOMER_ID_SQL} AS customer_id,
                    {CUSTOMER_NAME_SQL} AS customer_name,
                    {INSIGHT_BUTTON_SQL} AS is_insight,
                    {PHONE_BUTTON_SQL} AS is_phone,
                    clicked_at
                FROM swe_html_preview_click_events
                {where_sql}
            ) AS customer_clicks
            WHERE
                (customer_id IS NOT NULL OR customer_name IS NOT NULL)
                AND (is_insight OR is_phone)
            GROUP BY customer_id, customer_name
            ORDER BY
                (SUM(CASE WHEN is_insight THEN 1 ELSE 0 END)
                 + SUM(CASE WHEN is_phone THEN 1 ELSE 0 END)) DESC,
                last_clicked_at DESC
            LIMIT {safe_limit}
        """
        rows = await self.db.fetch_all(query, tuple(params))
        return [self._to_customer_summary_item(row) for row in rows]

    def _build_where_clause(
        self,
        *,
        source_id: Optional[str],
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        bbk_ids: Optional[list[str]] = None,
        cron_task_id: Optional[str] = None,
        file_url: Optional[str] = None,
    ) -> tuple[str, list[Any]]:
        """构造点击查询的公共筛选条件。"""
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
        return where_sql, params
