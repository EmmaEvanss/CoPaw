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

CUSTOMER_SUMMARY_SCAN_LIMIT = 10000


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
    def _get_customer_identity(
        cls,
        customer_info: Any,
    ) -> tuple[Optional[str], Optional[str]]:
        """从客户信息中提取客户 ID 和展示姓名。"""
        info = cls._decode_customer_info(customer_info) or {}
        customer_id = cls._clean_text(info.get("customer_id"))
        customer_name = (
            cls._clean_text(info.get("name"))
            or cls._clean_text(info.get("customer_name"))
            or cls._clean_text(info.get("客户姓名"))
            or cls._clean_text(info.get("客户名称"))
            or cls._clean_text(info.get("姓名"))
        )
        return customer_id, customer_name

    @classmethod
    def _classify_button(cls, row: dict[str, Any]) -> Optional[str]:
        """把按钮点击归类为洞察或电访。"""
        button_id = (cls._clean_text(row.get("button_id")) or "").lower()
        button_name = cls._clean_text(row.get("button_name")) or ""
        button_text = cls._clean_text(row.get("button_text")) or ""
        if (
            "phone" in button_id
            or "电访" in button_name
            or "电访" in button_text
        ):
            return "phone"
        if "电话访问" in button_name or "电话访问" in button_text:
            return "phone"
        if (
            "insight" in button_id
            or "洞察" in button_name
            or "洞察" in button_text
        ):
            return "insight"
        return None

    @classmethod
    def _build_customer_summary_items(
        cls,
        rows: list[dict[str, Any]],
        limit: int,
    ) -> list[HtmlPreviewCustomerClickSummaryItem]:
        """基于点击明细在应用层聚合客户维度统计。"""
        grouped: dict[str, dict[str, Any]] = {}
        for row in rows:
            button_type = cls._classify_button(row)
            if button_type is None:
                continue

            customer_id, customer_name = cls._get_customer_identity(
                row.get("customer_info"),
            )
            if not customer_id and not customer_name:
                continue

            group_key = customer_id or f"name:{customer_name}"
            item = grouped.setdefault(
                group_key,
                {
                    "customer_id": customer_id,
                    "customer_name": customer_name or "未知客户",
                    "insight_count": 0,
                    "phone_count": 0,
                    "last_clicked_at": row.get("clicked_at"),
                },
            )
            if customer_name and not item.get("customer_name"):
                item["customer_name"] = customer_name
            if button_type == "insight":
                item["insight_count"] += 1
            elif button_type == "phone":
                item["phone_count"] += 1

            clicked_at = row.get("clicked_at")
            last_clicked_at = item.get("last_clicked_at")
            if clicked_at and (
                not last_clicked_at or clicked_at > last_clicked_at
            ):
                item["last_clicked_at"] = clicked_at
                if customer_name:
                    item["customer_name"] = customer_name

        sorted_rows = sorted(
            grouped.values(),
            key=lambda item: (
                item["insight_count"] + item["phone_count"],
                item.get("last_clicked_at") or datetime.min,
            ),
            reverse=True,
        )
        return [
            cls._to_customer_summary_item(row)
            for row in sorted_rows[: max(1, min(limit, 200))]
        ]

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
        scan_limit = max(CUSTOMER_SUMMARY_SCAN_LIMIT, safe_limit)

        query = f"""
            SELECT
                button_id,
                button_name,
                button_text,
                customer_info,
                clicked_at
            FROM swe_html_preview_click_events
            {where_sql}
            ORDER BY clicked_at DESC, id DESC
            LIMIT {scan_limit}
        """
        rows = await self.db.fetch_all(query, tuple(params))
        return self._build_customer_summary_items(rows, safe_limit)

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
