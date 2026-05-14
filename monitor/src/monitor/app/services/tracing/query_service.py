# -*- coding: utf-8 -*-
"""Tracing query service for operational dashboard."""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Optional

from ...database import get_db_connection, DatabaseConnection
from ...models.tracing import (
    EventType,
    ModelUsage,
    MCPToolUsage,
    MCPServerUsage,
    OverviewStats,
    SessionListItem,
    SessionStats,
    SkillCallTimeline,
    SkillUsage,
    Span,
    TimelineEvent,
    ToolCallInSkill,
    ToolUsage,
    Trace,
    TraceDetail,
    TraceDetailWithTimeline,
    TraceListItem,
    TraceStatus,
    UserListItem,
    UserMessageItem,
    UserStats,
)

logger = logging.getLogger(__name__)

# 需要从统计中排除的 source_id（测试平台等）
EXCLUDED_SOURCE_IDS = ["default"]


class TracingQueryService:
    """运营看板查询服务."""

    def __init__(self, db: DatabaseConnection):
        """初始化查询服务.

        Args:
            db: 数据库连接实例
        """
        self._db = db

    @classmethod
    def get_instance(cls) -> "TracingQueryService":
        """获取服务实例（使用全局数据库连接）."""
        db = get_db_connection()
        return cls(db)

    # ===== 运营概览 =====

    async def get_overview_stats(
        self,
        source_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> OverviewStats:
        """获取运营概览统计."""
        if start_date is None:
            start_date = datetime.now() - timedelta(days=30)
        if end_date is None:
            end_date = datetime.now() + timedelta(days=1)

        # 并行获取各项统计数据
        (
            total_users,
            (online_users, online_user_ids),
            token_row,
            model_distribution,
            top_tools,
            top_skills,
            (top_mcp_tools, mcp_servers),
        ) = await self._fetch_overview_data(source_id, start_date, end_date)

        return self._build_overview_stats(
            online_users=online_users,
            online_user_ids=online_user_ids,
            total_users=total_users,
            model_distribution=model_distribution,
            token_row=token_row,
            top_tools=top_tools,
            top_skills=top_skills,
            top_mcp_tools=top_mcp_tools,
            mcp_servers=mcp_servers,
        )

    async def _fetch_overview_data(
        self,
        source_id: str,
        start_date: datetime,
        end_date: datetime,
    ) -> list:
        """并行获取运营概览的各项数据."""
        return await asyncio.gather(
            self._get_total_users(source_id, start_date, end_date),
            self._get_online_users(source_id),
            self._get_token_stats(source_id, start_date, end_date),
            self._get_model_distribution(source_id, start_date, end_date),
            self._get_top_tools(source_id, start_date, end_date),
            self._get_top_skills(source_id, start_date, end_date),
            self._get_mcp_stats(source_id, start_date, end_date),
        )

    def _build_overview_stats(
        self,
        online_users: int,
        online_user_ids: list[str],
        total_users: int,
        model_distribution: list,
        token_row: Optional[dict],
        top_tools: list,
        top_skills: list,
        top_mcp_tools: list,
        mcp_servers: list,
    ) -> OverviewStats:
        """构建运营概览统计对象."""
        return OverviewStats(
            online_users=online_users,
            online_user_ids=online_user_ids,
            total_users=total_users,
            model_distribution=model_distribution,
            total_tokens=token_row["total_tokens"] or 0 if token_row else 0,
            input_tokens=token_row["input_tokens"] or 0 if token_row else 0,
            output_tokens=token_row["output_tokens"] or 0 if token_row else 0,
            total_sessions=(
                token_row["total_sessions"] or 0 if token_row else 0
            ),
            total_conversations=(
                token_row["total_traces"] or 0 if token_row else 0
            ),
            avg_duration_ms=self._extract_avg_duration(token_row),
            top_tools=top_tools,
            top_skills=top_skills,
            top_mcp_tools=top_mcp_tools,
            mcp_servers=mcp_servers,
            daily_trend=[],
        )

    def _extract_avg_duration(self, token_row: Optional[dict]) -> int:
        """从 token 统计行中提取平均时长."""
        if token_row and token_row.get("avg_duration"):
            return int(token_row["avg_duration"] or 0)
        return 0

    async def get_growth_stats(
        self,
        source_id: str,
        start_date: datetime,
        end_date: datetime,
        time_range: str = "day",
    ) -> dict[str, Any]:
        """获取环比增长统计."""
        # Calculate previous period based on time_range
        period_days = 1
        if time_range == "week":
            period_days = 7
        elif time_range == "month":
            period_days = 30
        elif time_range == "custom":
            period_days = (end_date - start_date).days

        prev_start = start_date - timedelta(days=period_days)
        # 使用 start_date 作为上一周期的结束时间，配合 SQL 的 < 比较
        # 避免使用 timedelta(seconds=1) 造成的时间间隙问题
        prev_end = start_date

        async def get_stats(
            s: datetime,
            e: datetime,
            is_prev: bool = False,
        ) -> dict:
            # 对于上一周期，使用 < 比较；对于当前周期，使用 <= 比较
            time_compare = "<" if is_prev else "<="
            if source_id == "all":
                exclude_placeholders = ", ".join(
                    ["%s"] * len(EXCLUDED_SOURCE_IDS),
                )
                query = f"""
                    SELECT
                        COUNT(*) as calls,
                        COALESCE(SUM(total_tokens), 0) as tokens,
                        COUNT(DISTINCT session_id) as sessions,
                        COUNT(DISTINCT user_id) as users,
                        COUNT(DISTINCT source_id) as platforms,
                        AVG(duration_ms) as avg_duration
                    FROM swe_tracing_traces
                    WHERE start_time >= %s AND start_time {time_compare} %s
                      AND source_id NOT IN ({exclude_placeholders})
                      AND user_id != 'default'
                """
                row = await self._db.fetch_one(
                    query,
                    (s, e, *EXCLUDED_SOURCE_IDS),
                )
            else:
                query = f"""
                    SELECT
                        COUNT(*) as calls,
                        COALESCE(SUM(total_tokens), 0) as tokens,
                        COUNT(DISTINCT session_id) as sessions,
                        COUNT(DISTINCT user_id) as users,
                        COUNT(DISTINCT channel) as platforms,
                        AVG(duration_ms) as avg_duration
                    FROM swe_tracing_traces
                    WHERE source_id = %s AND start_time >= %s AND start_time {time_compare} %s
                      AND user_id != 'default'
                """
                row = await self._db.fetch_one(query, (source_id, s, e))

            if row is None:
                return {
                    "calls": 0,
                    "tokens": 0.0,
                    "sessions": 0,
                    "users": 0,
                    "platforms": 0,
                    "avg_duration": 0.0,
                }
            return {
                "calls": row["calls"] or 0,
                "tokens": float(row["tokens"] or 0),
                "sessions": row["sessions"] or 0,
                "users": row["users"] or 0,
                "platforms": row["platforms"] or 0,
                "avg_duration": float(row["avg_duration"] or 0),
            }

        curr = await get_stats(start_date, end_date, is_prev=False)
        prev = await get_stats(prev_start, prev_end, is_prev=True)

        def calc_growth(curr_val: float, prev_val: float) -> float:
            if prev_val == 0:
                return 100.0 if curr_val > 0 else 0.0
            return round(((curr_val - prev_val) / prev_val) * 100, 1)

        return {
            "callsGrowth": calc_growth(curr["calls"], prev["calls"]),
            "tokensGrowth": calc_growth(curr["tokens"], prev["tokens"]),
            "sessionGrowth": calc_growth(curr["sessions"], prev["sessions"]),
            "userGrowth": calc_growth(curr["users"], prev["users"]),
            "platformGrowth": calc_growth(
                curr["platforms"],
                prev["platforms"],
            ),
            "avgDurationGrowth": calc_growth(
                curr["avg_duration"],
                prev["avg_duration"],
            ),
        }

    async def get_daily_trend(
        self,
        source_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> list[dict[str, Any]]:
        """获取日趋势数据."""
        if start_date is None:
            start_date = datetime.now() - timedelta(days=30)
        if end_date is None:
            end_date = datetime.now() + timedelta(days=1)

        if source_id == "all":
            exclude_placeholders = ", ".join(["%s"] * len(EXCLUDED_SOURCE_IDS))
            query = f"""
                SELECT
                    DATE(start_time) as date,
                    COUNT(*) as calls,
                    COALESCE(SUM(total_tokens), 0) as tokens,
                    COUNT(DISTINCT user_id) as users
                FROM swe_tracing_traces
                WHERE start_time >= %s AND start_time <= %s
                  AND source_id NOT IN ({exclude_placeholders})
                  AND user_id != 'default'
                GROUP BY DATE(start_time)
                ORDER BY date
            """
            rows = await self._db.fetch_all(
                query,
                (start_date, end_date, *EXCLUDED_SOURCE_IDS),
            )
        else:
            query = """
                SELECT
                    DATE(start_time) as date,
                    COUNT(*) as calls,
                    COALESCE(SUM(total_tokens), 0) as tokens,
                    COUNT(DISTINCT user_id) as users
                FROM swe_tracing_traces
                WHERE source_id = %s AND start_time >= %s AND start_time <= %s
                  AND user_id != 'default'
                GROUP BY DATE(start_time)
                ORDER BY date
            """
            rows = await self._db.fetch_all(
                query,
                (source_id, start_date, end_date),
            )

        return [
            {
                "date": (
                    row["date"].strftime("%Y-%m-%d") if row["date"] else ""
                ),
                "calls": row["calls"] or 0,
                "tokens": row["tokens"] or 0,
                "users": row["users"] or 0,
            }
            for row in rows
        ]

    async def get_channel_distribution(
        self,
        source_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> dict[str, Any]:
        """获取渠道分布统计."""
        if start_date is None:
            start_date = datetime.now() - timedelta(days=30)
        if end_date is None:
            end_date = datetime.now() + timedelta(days=1)

        if source_id == "all":
            exclude_placeholders = ", ".join(["%s"] * len(EXCLUDED_SOURCE_IDS))
            query = f"""
                SELECT
                    source_id,
                    COUNT(DISTINCT user_id) as user_count,
                    COUNT(*) as call_count,
                    SUM(total_tokens) as token_count
                FROM swe_tracing_traces
                WHERE start_time >= %s AND start_time <= %s
                  AND source_id IS NOT NULL AND source_id != ''
                  AND source_id NOT IN ({exclude_placeholders})
                  AND user_id != 'default'
                GROUP BY source_id
                ORDER BY call_count DESC
            """
            rows = await self._db.fetch_all(
                query,
                (start_date, end_date, *EXCLUDED_SOURCE_IDS),
            )
        else:
            query = """
                SELECT
                    source_id,
                    COUNT(DISTINCT user_id) as user_count,
                    COUNT(*) as call_count,
                    SUM(total_tokens) as token_count
                FROM swe_tracing_traces
                WHERE source_id = %s AND start_time >= %s AND start_time <= %s
                  AND user_id != 'default'
                GROUP BY source_id
                ORDER BY call_count DESC
            """
            rows = await self._db.fetch_all(
                query,
                (source_id, start_date, end_date),
            )

        platform_user_dist = []
        platform_call_dist = []
        sources = []

        for row in rows:
            src_id = row["source_id"]
            sources.append(src_id)
            platform_user_dist.append(
                {"name": src_id, "value": row["user_count"] or 0},
            )
            platform_call_dist.append(
                {"name": src_id, "value": row["call_count"] or 0},
            )

        return {
            "platformUserDistribution": platform_user_dist,
            "platformCallDistribution": platform_call_dist,
            "totalPlatforms": len(sources),
        }

    async def get_sources(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> list[str]:
        """获取平台来源列表."""
        if start_date is None:
            start_date = datetime.now() - timedelta(days=30)
        if end_date is None:
            end_date = datetime.now() + timedelta(days=1)

        exclude_placeholders = ", ".join(["%s"] * len(EXCLUDED_SOURCE_IDS))
        query = f"""
            SELECT DISTINCT source_id
            FROM swe_tracing_traces
            WHERE start_time >= %s AND start_time <= %s
              AND source_id IS NOT NULL AND source_id != ''
              AND source_id NOT IN ({exclude_placeholders})
            ORDER BY source_id
        """
        rows = await self._db.fetch_all(
            query,
            (start_date, end_date, *EXCLUDED_SOURCE_IDS),
        )
        return [row["source_id"] for row in rows]

    # ===== 用户分析 =====

    async def get_users(
        self,
        source_id: str,
        page: int = 1,
        page_size: int = 20,
        user_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        sort_by: Optional[str] = None,
        filter_user_type: Optional[str] = "filtered",
        bbk_id: Optional[str] = None,
    ) -> tuple[list[UserListItem], int]:
        """获取用户列表.

        Args:
            filter_user_type: 'filtered' 过滤80/IT开头用户，'all' 仅过滤default用户
        """
        order_by = "last_active DESC"
        if sort_by == "conversations":
            order_by = "total_conversations DESC"
        elif sort_by == "last_active":
            order_by = "last_active DESC"

        if source_id == "all":
            exclude_placeholders = ", ".join(["%s"] * len(EXCLUDED_SOURCE_IDS))
            where_clauses = [f"source_id NOT IN ({exclude_placeholders})"]
            params: list[Any] = list(EXCLUDED_SOURCE_IDS)
        else:
            where_clauses = ["source_id = %s"]
            params = [source_id]

        # 用户过滤逻辑
        where_clauses.append("user_id != %s")
        params.append("default")
        if filter_user_type == "filtered":
            # 过滤掉以 80 开头或以 IT 开头的用户
            where_clauses.append(
                "(user_id NOT LIKE %s AND user_id NOT LIKE %s)",
            )
            params.append("80%")
            params.append("IT%")

        if user_id:
            where_clauses.append("user_id LIKE %s")
            params.append(f"%{user_id}%")
        if bbk_id:
            where_clauses.append("bbk_id = %s")
            params.append(bbk_id)
        if start_date:
            where_clauses.append("start_time >= %s")
            params.append(start_date)
        if end_date:
            where_clauses.append("start_time <= %s")
            params.append(end_date)

        where_sql = " AND ".join(where_clauses)

        count_query = f"SELECT COUNT(DISTINCT user_id) as total FROM swe_tracing_traces WHERE {where_sql}"
        count_row = await self._db.fetch_one(count_query, tuple(params))
        total = count_row["total"] if count_row else 0

        offset = (page - 1) * page_size
        if source_id == "all":
            query = f"""
                SELECT t.user_id,
                       COUNT(DISTINCT t.session_id) as total_sessions,
                       COUNT(*) as total_conversations,
                       SUM(t.total_tokens) as total_tokens,
                       MAX(t.start_time) as last_active,
                       (SELECT COUNT(*) FROM swe_tracing_spans s
                        WHERE s.trace_id IN (SELECT trace_id FROM swe_tracing_traces WHERE user_id = t.user_id)
                        AND s.event_type = 'skill_invocation') as total_skills,
                       (SELECT user_name FROM swe_tracing_traces t2
                        WHERE t2.user_id = t.user_id AND t2.user_name IS NOT NULL
                        ORDER BY t2.start_time DESC LIMIT 1) as user_name,
                       (SELECT bbk_id FROM swe_tracing_traces t3
                        WHERE t3.user_id = t.user_id AND t3.bbk_id IS NOT NULL
                        ORDER BY t3.start_time DESC LIMIT 1) as bbk_id
                FROM swe_tracing_traces t
                WHERE {where_sql}
                GROUP BY t.user_id
                ORDER BY {order_by}
                LIMIT %s OFFSET %s
            """
            params.extend([page_size, offset])
        else:
            query = f"""
                SELECT t.user_id,
                       COUNT(DISTINCT t.session_id) as total_sessions,
                       COUNT(*) as total_conversations,
                       SUM(t.total_tokens) as total_tokens,
                       MAX(t.start_time) as last_active,
                       (SELECT COUNT(*) FROM swe_tracing_spans s
                        WHERE s.source_id = %s
                        AND s.trace_id IN (SELECT trace_id FROM swe_tracing_traces WHERE user_id = t.user_id AND source_id = %s)
                        AND s.event_type = 'skill_invocation') as total_skills,
                       (SELECT user_name FROM swe_tracing_traces t2
                        WHERE t2.user_id = t.user_id AND t2.source_id = %s AND t2.user_name IS NOT NULL
                        ORDER BY t2.start_time DESC LIMIT 1) as user_name,
                       (SELECT bbk_id FROM swe_tracing_traces t3
                        WHERE t3.user_id = t.user_id AND t3.source_id = %s AND t3.bbk_id IS NOT NULL
                        ORDER BY t3.start_time DESC LIMIT 1) as bbk_id
                FROM swe_tracing_traces t
                WHERE {where_sql}
                GROUP BY t.user_id
                ORDER BY {order_by}
                LIMIT %s OFFSET %s
            """
            params = (
                [source_id, source_id, source_id, source_id]
                + params
                + [page_size, offset]
            )

        rows = await self._db.fetch_all(query, tuple(params))
        users = [
            UserListItem(
                user_id=row["user_id"],
                user_name=row["user_name"],
                bbk_id=row["bbk_id"],
                total_sessions=row["total_sessions"] or 0,
                total_conversations=row["total_conversations"] or 0,
                total_tokens=row["total_tokens"] or 0,
                total_skills=row["total_skills"] or 0,
                last_active=row["last_active"],
            )
            for row in rows
        ]
        return users, total

    async def get_user_stats(
        self,
        source_id: str,
        user_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> UserStats:
        """获取用户统计详情."""
        if start_date is None:
            start_date = datetime.now() - timedelta(days=30)
        if end_date is None:
            end_date = datetime.now()

        stats_row = await self._fetch_user_stats_row(
            source_id,
            user_id,
            start_date,
            end_date,
        )
        model_usage, tools_used, skills_used, mcp_tools_used = (
            await self._fetch_user_usage_data(
                source_id,
                user_id,
                start_date,
                end_date,
            )
        )

        return self._build_user_stats(
            user_id=user_id,
            stats_row=stats_row,
            model_usage=model_usage,
            tools_used=tools_used,
            skills_used=skills_used,
            mcp_tools_used=mcp_tools_used,
        )

    async def _fetch_user_stats_row(
        self,
        source_id: str,
        user_id: str,
        start_date: datetime,
        end_date: datetime,
    ) -> Optional[dict]:
        """获取用户统计行数据."""
        if source_id == "all":
            query = """
                SELECT
                    COUNT(DISTINCT session_id) as total_sessions,
                    COUNT(*) as total_conversations,
                    SUM(total_input_tokens) as input_tokens,
                    SUM(total_output_tokens) as output_tokens,
                    SUM(total_tokens) as total_tokens,
                    AVG(duration_ms) as avg_duration
                FROM swe_tracing_traces
                WHERE user_id = %s AND start_time >= %s AND start_time <= %s
            """
            return await self._db.fetch_one(
                query,
                (user_id, start_date, end_date),
            )

        query = """
            SELECT
                COUNT(DISTINCT session_id) as total_sessions,
                COUNT(*) as total_conversations,
                SUM(total_input_tokens) as input_tokens,
                SUM(total_output_tokens) as output_tokens,
                SUM(total_tokens) as total_tokens,
                AVG(duration_ms) as avg_duration
            FROM swe_tracing_traces
            WHERE source_id = %s AND user_id = %s AND start_time >= %s AND start_time <= %s
        """
        return await self._db.fetch_one(
            query,
            (source_id, user_id, start_date, end_date),
        )

    async def _fetch_user_usage_data(
        self,
        source_id: str,
        user_id: str,
        start_date: datetime,
        end_date: datetime,
    ) -> tuple:
        """并行获取用户使用数据."""
        return await asyncio.gather(
            self._get_user_model_usage(
                source_id,
                user_id,
                start_date,
                end_date,
            ),
            self._get_user_tool_usage(
                source_id,
                user_id,
                start_date,
                end_date,
            ),
            self._get_user_skill_usage(
                source_id,
                user_id,
                start_date,
                end_date,
            ),
            self._get_user_mcp_tool_usage(
                source_id,
                user_id,
                start_date,
                end_date,
            ),
        )

    def _build_user_stats(
        self,
        user_id: str,
        stats_row: Optional[dict],
        model_usage: list,
        tools_used: list,
        skills_used: list,
        mcp_tools_used: list,
    ) -> UserStats:
        """构建用户统计对象."""
        return UserStats(
            user_id=user_id,
            model_usage=model_usage,
            total_tokens=stats_row["total_tokens"] or 0 if stats_row else 0,
            input_tokens=stats_row["input_tokens"] or 0 if stats_row else 0,
            output_tokens=stats_row["output_tokens"] or 0 if stats_row else 0,
            total_sessions=(
                stats_row["total_sessions"] or 0 if stats_row else 0
            ),
            total_conversations=(
                stats_row["total_conversations"] or 0 if stats_row else 0
            ),
            avg_duration_ms=self._extract_avg_duration(stats_row),
            tools_used=tools_used,
            skills_used=skills_used,
            mcp_tools_used=mcp_tools_used,
        )

    # ===== 私有辅助方法 =====

    async def _get_total_users(
        self,
        source_id: str,
        start_date: datetime,
        end_date: datetime,
    ) -> int:
        """获取用户总数."""
        if source_id == "all":
            exclude_placeholders = ", ".join(["%s"] * len(EXCLUDED_SOURCE_IDS))
            query = f"""
                SELECT COUNT(DISTINCT user_id) as total_users
                FROM swe_tracing_traces
                WHERE start_time >= %s AND start_time <= %s
                  AND source_id NOT IN ({exclude_placeholders})
                  AND user_id != 'default'
            """
            row = await self._db.fetch_one(
                query,
                (start_date, end_date, *EXCLUDED_SOURCE_IDS),
            )
        else:
            query = """
                SELECT COUNT(DISTINCT user_id) as total_users
                FROM swe_tracing_traces
                WHERE source_id = %s AND start_time >= %s AND start_time <= %s
                  AND user_id != 'default'
            """
            row = await self._db.fetch_one(
                query,
                (source_id, start_date, end_date),
            )
        return row["total_users"] if row else 0

    async def _get_online_users(self, source_id: str) -> tuple[int, list[str]]:
        """获取在线用户."""
        online_threshold = datetime.now() - timedelta(minutes=5)
        if source_id == "all":
            query = """
                SELECT DISTINCT user_id
                FROM swe_tracing_spans
                WHERE start_time >= %s AND user_id IS NOT NULL AND user_id != ''
            """
            rows = await self._db.fetch_all(query, (online_threshold,))
        else:
            query = """
                SELECT DISTINCT user_id
                FROM swe_tracing_spans
                WHERE source_id = %s AND start_time >= %s AND user_id IS NOT NULL AND user_id != ''
            """
            rows = await self._db.fetch_all(
                query,
                (source_id, online_threshold),
            )
        user_ids = [row["user_id"] for row in rows if row["user_id"]]
        return len(user_ids), user_ids

    async def _get_token_stats(
        self,
        source_id: str,
        start_date: datetime,
        end_date: datetime,
    ) -> Optional[dict]:
        """获取 Token 统计."""
        if source_id == "all":
            exclude_placeholders = ", ".join(["%s"] * len(EXCLUDED_SOURCE_IDS))
            query = f"""
                SELECT
                    SUM(total_input_tokens) as input_tokens,
                    SUM(total_output_tokens) as output_tokens,
                    SUM(total_tokens) as total_tokens,
                    COUNT(*) as total_traces,
                    COUNT(DISTINCT session_id) as total_sessions,
                    AVG(duration_ms) as avg_duration
                FROM swe_tracing_traces
                WHERE start_time >= %s AND start_time <= %s
                  AND source_id NOT IN ({exclude_placeholders})
                  AND user_id != 'default'
            """
            return await self._db.fetch_one(
                query,
                (start_date, end_date, *EXCLUDED_SOURCE_IDS),
            )
        else:
            query = """
                SELECT
                    SUM(total_input_tokens) as input_tokens,
                    SUM(total_output_tokens) as output_tokens,
                    SUM(total_tokens) as total_tokens,
                    COUNT(*) as total_traces,
                    COUNT(DISTINCT session_id) as total_sessions,
                    AVG(duration_ms) as avg_duration
                FROM swe_tracing_traces
                WHERE source_id = %s AND start_time >= %s AND start_time <= %s
                  AND user_id != 'default'
            """
            return await self._db.fetch_one(
                query,
                (source_id, start_date, end_date),
            )

    async def _get_model_distribution(
        self,
        source_id: str,
        start_date: datetime,
        end_date: datetime,
    ) -> list[ModelUsage]:
        """获取模型分布."""
        if source_id == "all":
            exclude_placeholders = ", ".join(["%s"] * len(EXCLUDED_SOURCE_IDS))
            query = f"""
                SELECT model_name, COUNT(*) as count,
                       SUM(total_input_tokens) as input_tokens,
                       SUM(total_output_tokens) as output_tokens,
                       SUM(total_tokens) as total_tokens
                FROM swe_tracing_traces
                WHERE start_time >= %s AND start_time <= %s AND model_name IS NOT NULL
                  AND source_id NOT IN ({exclude_placeholders})
                  AND user_id != 'default'
                GROUP BY model_name
                ORDER BY count DESC
                LIMIT 10
            """
            rows = await self._db.fetch_all(
                query,
                (start_date, end_date, *EXCLUDED_SOURCE_IDS),
            )
        else:
            query = """
                SELECT model_name, COUNT(*) as count,
                       SUM(total_input_tokens) as input_tokens,
                       SUM(total_output_tokens) as output_tokens,
                       SUM(total_tokens) as total_tokens
                FROM swe_tracing_traces
                WHERE source_id = %s AND start_time >= %s AND start_time <= %s AND model_name IS NOT NULL
                  AND user_id != 'default'
                GROUP BY model_name
                ORDER BY count DESC
                LIMIT 10
            """
            rows = await self._db.fetch_all(
                query,
                (source_id, start_date, end_date),
            )
        return [
            ModelUsage(
                model_name=row["model_name"],
                count=row["count"] or 0,
                total_tokens=row["total_tokens"] or 0,
                input_tokens=row["input_tokens"] or 0,
                output_tokens=row["output_tokens"] or 0,
            )
            for row in rows
        ]

    async def _get_top_tools(
        self,
        source_id: str,
        start_date: datetime,
        end_date: datetime,
    ) -> list[ToolUsage]:
        """获取热门工具."""
        if source_id == "all":
            exclude_placeholders = ", ".join(["%s"] * len(EXCLUDED_SOURCE_IDS))
            query = f"""
                SELECT tool_name, COUNT(*) as count,
                       AVG(duration_ms) as avg_duration,
                       SUM(CASE WHEN error IS NOT NULL THEN 1 ELSE 0 END) as error_count
                FROM swe_tracing_spans
                WHERE start_time >= %s AND start_time <= %s
                  AND event_type = 'tool_call_end'
                  AND tool_name IS NOT NULL
                  AND mcp_server IS NULL
                  AND source_id NOT IN ({exclude_placeholders})
                  AND user_id != 'default'
                GROUP BY tool_name
                ORDER BY count DESC
                LIMIT 10
            """
            rows = await self._db.fetch_all(
                query,
                (start_date, end_date, *EXCLUDED_SOURCE_IDS),
            )
        else:
            query = """
                SELECT tool_name, COUNT(*) as count,
                       AVG(duration_ms) as avg_duration,
                       SUM(CASE WHEN error IS NOT NULL THEN 1 ELSE 0 END) as error_count
                FROM swe_tracing_spans
                WHERE source_id = %s AND start_time >= %s AND start_time <= %s
                  AND event_type = 'tool_call_end'
                  AND tool_name IS NOT NULL
                  AND mcp_server IS NULL
                  AND user_id != 'default'
                GROUP BY tool_name
                ORDER BY count DESC
                LIMIT 10
            """
            rows = await self._db.fetch_all(
                query,
                (source_id, start_date, end_date),
            )
        return [
            ToolUsage(
                tool_name=row["tool_name"],
                count=row["count"] or 0,
                avg_duration_ms=int(row["avg_duration"] or 0),
                error_count=row["error_count"] or 0,
            )
            for row in rows
        ]

    async def _get_top_skills(
        self,
        source_id: str,
        start_date: datetime,
        end_date: datetime,
    ) -> list[SkillUsage]:
        """获取热门技能."""
        if source_id == "all":
            exclude_placeholders = ", ".join(["%s"] * len(EXCLUDED_SOURCE_IDS))
            query = f"""
                SELECT skill_name, COUNT(*) as count,
                       AVG(duration_ms) as avg_duration
                FROM swe_tracing_spans
                WHERE start_time >= %s AND start_time <= %s
                  AND event_type = 'skill_invocation'
                  AND skill_name IS NOT NULL
                  AND source_id NOT IN ({exclude_placeholders})
                  AND user_id != 'default'
                GROUP BY skill_name
                ORDER BY count DESC
                LIMIT 10
            """
            rows = await self._db.fetch_all(
                query,
                (start_date, end_date, *EXCLUDED_SOURCE_IDS),
            )
        else:
            query = """
                SELECT skill_name, COUNT(*) as count,
                       AVG(duration_ms) as avg_duration
                FROM swe_tracing_spans
                WHERE source_id = %s AND start_time >= %s AND start_time <= %s
                  AND event_type = 'skill_invocation'
                  AND skill_name IS NOT NULL
                  AND user_id != 'default'
                GROUP BY skill_name
                ORDER BY count DESC
                LIMIT 10
            """
            rows = await self._db.fetch_all(
                query,
                (source_id, start_date, end_date),
            )
        return [
            SkillUsage(
                skill_name=row["skill_name"],
                count=row["count"] or 0,
                avg_duration_ms=int(row["avg_duration"] or 0),
            )
            for row in rows
        ]

    async def get_skills_paginated(
        self,
        source_id: str,
        page: int = 1,
        page_size: int = 10,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> tuple[list[SkillUsage], int]:
        """获取技能调用排行榜（分页）."""
        if start_date is None:
            start_date = datetime.now() - timedelta(days=30)
        if end_date is None:
            end_date = datetime.now() + timedelta(days=1)

        # 构建基础查询条件
        if source_id == "all":
            exclude_placeholders = ", ".join(["%s"] * len(EXCLUDED_SOURCE_IDS))
            base_where = f"""
                start_time >= %s AND start_time <= %s
                AND event_type = 'skill_invocation'
                AND skill_name IS NOT NULL
                AND source_id NOT IN ({exclude_placeholders})
                AND user_id != 'default'
            """
            count_params = [start_date, end_date, *EXCLUDED_SOURCE_IDS]
        else:
            base_where = """
                source_id = %s AND start_time >= %s AND start_time <= %s
                AND event_type = 'skill_invocation'
                AND skill_name IS NOT NULL
                AND user_id != 'default'
            """
            count_params = [source_id, start_date, end_date]

        # 查询总数
        count_query = f"""
            SELECT COUNT(DISTINCT skill_name) as total
            FROM swe_tracing_spans
            WHERE {base_where}
        """
        count_row = await self._db.fetch_one(count_query, tuple(count_params))
        total = count_row["total"] if count_row else 0

        # 分页查询
        offset = (page - 1) * page_size
        data_query = f"""
            SELECT skill_name, COUNT(*) as count,
                   AVG(duration_ms) as avg_duration
            FROM swe_tracing_spans
            WHERE {base_where}
            GROUP BY skill_name
            ORDER BY count DESC
            LIMIT %s OFFSET %s
        """
        params = count_params + [page_size, offset]
        rows = await self._db.fetch_all(data_query, tuple(params))

        skills = [
            SkillUsage(
                skill_name=row["skill_name"],
                count=row["count"] or 0,
                avg_duration_ms=int(row["avg_duration"] or 0),
            )
            for row in rows
        ]
        return skills, total

    async def get_mcp_servers_paginated(
        self,
        source_id: str,
        page: int = 1,
        page_size: int = 10,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> tuple[list[MCPServerUsage], int]:
        """获取 MCP 服务调用排行榜（分页）."""
        if start_date is None:
            start_date = datetime.now() - timedelta(days=30)
        if end_date is None:
            end_date = datetime.now() + timedelta(days=1)

        # 构建基础查询条件
        if source_id == "all":
            exclude_placeholders = ", ".join(["%s"] * len(EXCLUDED_SOURCE_IDS))
            base_where = f"""
                start_time >= %s AND start_time <= %s
                AND event_type = 'tool_call_end'
                AND mcp_server IS NOT NULL
                AND source_id NOT IN ({exclude_placeholders})
                AND user_id != 'default'
            """
            count_params = [start_date, end_date, *EXCLUDED_SOURCE_IDS]
        else:
            base_where = """
                source_id = %s AND start_time >= %s AND start_time <= %s
                AND event_type = 'tool_call_end'
                AND mcp_server IS NOT NULL
                AND user_id != 'default'
            """
            count_params = [source_id, start_date, end_date]

        # 查询总数
        count_query = f"""
            SELECT COUNT(DISTINCT mcp_server) as total
            FROM swe_tracing_spans
            WHERE {base_where}
        """
        count_row = await self._db.fetch_one(count_query, tuple(count_params))
        total = count_row["total"] if count_row else 0

        # 分页查询
        offset = (page - 1) * page_size
        server_query = f"""
            SELECT mcp_server,
                   COUNT(DISTINCT tool_name) as tool_count,
                   COUNT(*) as total_calls,
                   AVG(duration_ms) as avg_duration,
                   SUM(CASE WHEN error IS NOT NULL THEN 1 ELSE 0 END) as error_count
            FROM swe_tracing_spans
            WHERE {base_where}
            GROUP BY mcp_server
            ORDER BY total_calls DESC
            LIMIT %s OFFSET %s
        """
        params = count_params + [page_size, offset]
        server_rows = await self._db.fetch_all(server_query, tuple(params))

        mcp_servers = []
        for server_row in server_rows:
            server_name = server_row["mcp_server"]
            mcp_servers.append(
                MCPServerUsage(
                    server_name=server_name,
                    tool_count=server_row["tool_count"] or 0,
                    total_calls=server_row["total_calls"] or 0,
                    avg_duration_ms=int(server_row["avg_duration"] or 0),
                    error_count=server_row["error_count"] or 0,
                    tools=[],  # 分页查询不返回工具详情
                ),
            )
        return mcp_servers, total

    async def get_skill_traces(
        self,
        skill_name: str,
        source_id: str,
        page: int = 1,
        page_size: int = 20,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> tuple[list[TraceListItem], int]:
        """获取指定技能调用的对话列表（分页）."""
        if start_date is None:
            start_date = datetime.now() - timedelta(days=30)
        if end_date is None:
            end_date = datetime.now() + timedelta(days=1)

        # 构建查询条件
        if source_id == "all":
            exclude_placeholders = ", ".join(["%s"] * len(EXCLUDED_SOURCE_IDS))
            base_where = f"""
                s.start_time >= %s AND s.start_time <= %s
                AND s.event_type = 'skill_invocation'
                AND s.skill_name = %s
                AND s.source_id NOT IN ({exclude_placeholders})
                AND s.user_id != 'default'
            """
            count_params = [
                start_date,
                end_date,
                skill_name,
                *EXCLUDED_SOURCE_IDS,
            ]
        else:
            base_where = """
                s.source_id = %s AND s.start_time >= %s AND s.start_time <= %s
                AND s.event_type = 'skill_invocation'
                AND s.skill_name = %s
                AND s.user_id != 'default'
            """
            count_params = [source_id, start_date, end_date, skill_name]

        # 查询总数
        count_query = f"""
            SELECT COUNT(DISTINCT s.trace_id) as total
            FROM swe_tracing_spans s
            WHERE {base_where}
        """
        count_row = await self._db.fetch_one(count_query, tuple(count_params))
        total = count_row["total"] if count_row else 0

        # 分页查询对话列表
        offset = (page - 1) * page_size
        if source_id == "all":
            data_query = f"""
                SELECT DISTINCT t.trace_id, t.source_id, t.user_id, t.session_id,
                       t.channel, t.start_time, t.duration_ms, t.total_tokens,
                       t.total_input_tokens, t.total_output_tokens, t.model_name,
                       t.status, JSON_LENGTH(t.skills_used) as skills_count,
                       (SELECT t2.user_name FROM swe_tracing_traces t2
                        WHERE t2.user_id = t.user_id AND t2.user_name IS NOT NULL
                        ORDER BY t2.start_time DESC LIMIT 1) as user_name,
                       (SELECT t3.bbk_id FROM swe_tracing_traces t3
                        WHERE t3.user_id = t.user_id AND t3.bbk_id IS NOT NULL
                        ORDER BY t3.start_time DESC LIMIT 1) as bbk_id
                FROM swe_tracing_spans s
                JOIN swe_tracing_traces t ON s.trace_id = t.trace_id
                WHERE {base_where}
                ORDER BY t.start_time ASC
                LIMIT %s OFFSET %s
            """
            params = list(count_params) + [page_size, offset]
        else:
            data_query = f"""
                SELECT DISTINCT t.trace_id, t.source_id, t.user_id, t.session_id,
                       t.channel, t.start_time, t.duration_ms, t.total_tokens,
                       t.total_input_tokens, t.total_output_tokens, t.model_name,
                       t.status, JSON_LENGTH(t.skills_used) as skills_count,
                       (SELECT t2.user_name FROM swe_tracing_traces t2
                        WHERE t2.user_id = t.user_id AND t2.source_id = %s
                          AND t2.user_name IS NOT NULL
                        ORDER BY t2.start_time DESC LIMIT 1) as user_name,
                       (SELECT t3.bbk_id FROM swe_tracing_traces t3
                        WHERE t3.user_id = t.user_id AND t3.source_id = %s
                          AND t3.bbk_id IS NOT NULL
                        ORDER BY t3.start_time DESC LIMIT 1) as bbk_id
                FROM swe_tracing_spans s
                JOIN swe_tracing_traces t ON s.trace_id = t.trace_id
                WHERE {base_where}
                ORDER BY t.start_time ASC
                LIMIT %s OFFSET %s
            """
            params = (
                [source_id, source_id]
                + list(count_params)
                + [page_size, offset]
            )

        rows = await self._db.fetch_all(data_query, tuple(params))

        traces = [
            TraceListItem(
                trace_id=row["trace_id"],
                source_id=row["source_id"],
                user_id=row["user_id"],
                user_name=row["user_name"],
                bbk_id=row["bbk_id"],
                session_id=row["session_id"],
                channel=row["channel"],
                start_time=row["start_time"],
                duration_ms=row["duration_ms"],
                total_tokens=row["total_tokens"] or 0,
                total_input_tokens=row["total_input_tokens"] or 0,
                total_output_tokens=row["total_output_tokens"] or 0,
                model_name=row["model_name"],
                status=row["status"],
                skills_count=row["skills_count"] or 0,
            )
            for row in rows
        ]
        return traces, total

    async def _get_mcp_stats(
        self,
        source_id: str,
        start_date: datetime,
        end_date: datetime,
    ) -> tuple[list[MCPToolUsage], list[MCPServerUsage]]:
        """获取 MCP 统计."""
        if source_id == "all":
            exclude_placeholders = ", ".join(["%s"] * len(EXCLUDED_SOURCE_IDS))
            mcp_tool_query = f"""
                SELECT tool_name, mcp_server, COUNT(*) as count,
                       AVG(duration_ms) as avg_duration,
                       SUM(CASE WHEN error IS NOT NULL THEN 1 ELSE 0 END) as error_count
                FROM swe_tracing_spans
                WHERE start_time >= %s AND start_time <= %s
                  AND event_type = 'tool_call_end'
                  AND mcp_server IS NOT NULL
                  AND source_id NOT IN ({exclude_placeholders})
                  AND user_id != 'default'
                GROUP BY tool_name, mcp_server
                ORDER BY count DESC
                LIMIT 10
            """
            mcp_tool_rows = await self._db.fetch_all(
                query=mcp_tool_query,
                params=(start_date, end_date, *EXCLUDED_SOURCE_IDS),
            )
        else:
            mcp_tool_query = """
                SELECT tool_name, mcp_server, COUNT(*) as count,
                       AVG(duration_ms) as avg_duration,
                       SUM(CASE WHEN error IS NOT NULL THEN 1 ELSE 0 END) as error_count
                FROM swe_tracing_spans
                WHERE source_id = %s AND start_time >= %s AND start_time <= %s
                  AND event_type = 'tool_call_end'
                  AND mcp_server IS NOT NULL
                  AND user_id != 'default'
                GROUP BY tool_name, mcp_server
                ORDER BY count DESC
                LIMIT 10
            """
            mcp_tool_rows = await self._db.fetch_all(
                query=mcp_tool_query,
                params=(source_id, start_date, end_date),
            )

        top_mcp_tools = [
            MCPToolUsage(
                tool_name=row["tool_name"],
                mcp_server=row["mcp_server"],
                count=row["count"] or 0,
                avg_duration_ms=int(row["avg_duration"] or 0),
                error_count=row["error_count"] or 0,
            )
            for row in mcp_tool_rows
        ]

        # 获取 MCP 服务器统计（简化版本）
        mcp_servers = await self._get_mcp_servers(
            source_id,
            start_date,
            end_date,
        )
        return top_mcp_tools, mcp_servers

    async def _get_mcp_servers(
        self,
        source_id: str,
        start_date: datetime,
        end_date: datetime,
    ) -> list[MCPServerUsage]:
        """获取 MCP 服务器统计."""
        if source_id == "all":
            exclude_placeholders = ", ".join(["%s"] * len(EXCLUDED_SOURCE_IDS))
            query = f"""
                SELECT mcp_server,
                       COUNT(DISTINCT tool_name) as tool_count,
                       COUNT(*) as total_calls,
                       AVG(duration_ms) as avg_duration,
                       SUM(CASE WHEN error IS NOT NULL THEN 1 ELSE 0 END) as error_count
                FROM swe_tracing_spans
                WHERE start_time >= %s AND start_time <= %s
                  AND event_type = 'tool_call_end'
                  AND mcp_server IS NOT NULL
                  AND source_id NOT IN ({exclude_placeholders})
                  AND user_id != 'default'
                GROUP BY mcp_server
                ORDER BY total_calls DESC
            """
            server_rows = await self._db.fetch_all(
                query,
                (start_date, end_date, *EXCLUDED_SOURCE_IDS),
            )
        else:
            query = """
                SELECT mcp_server,
                       COUNT(DISTINCT tool_name) as tool_count,
                       COUNT(*) as total_calls,
                       AVG(duration_ms) as avg_duration,
                       SUM(CASE WHEN error IS NOT NULL THEN 1 ELSE 0 END) as error_count
                FROM swe_tracing_spans
                WHERE source_id = %s AND start_time >= %s AND start_time <= %s
                  AND event_type = 'tool_call_end'
                  AND mcp_server IS NOT NULL
                  AND user_id != 'default'
                GROUP BY mcp_server
                ORDER BY total_calls DESC
            """
            server_rows = await self._db.fetch_all(
                query,
                (source_id, start_date, end_date),
            )

        mcp_servers = []
        for server_row in server_rows:
            server_name = server_row["mcp_server"]
            tools = await self._get_server_tools(
                source_id,
                start_date,
                end_date,
                server_name,
            )
            mcp_servers.append(
                MCPServerUsage(
                    server_name=server_name,
                    tool_count=server_row["tool_count"] or 0,
                    total_calls=server_row["total_calls"] or 0,
                    avg_duration_ms=int(server_row["avg_duration"] or 0),
                    error_count=server_row["error_count"] or 0,
                    tools=tools,
                ),
            )
        return mcp_servers

    async def _get_server_tools(
        self,
        source_id: str,
        start_date: datetime,
        end_date: datetime,
        server_name: str,
    ) -> list[MCPToolUsage]:
        """获取服务器工具统计."""
        if source_id == "all":
            query = """
                SELECT tool_name, mcp_server, COUNT(*) as count,
                       AVG(duration_ms) as avg_duration,
                       SUM(CASE WHEN error IS NOT NULL THEN 1 ELSE 0 END) as error_count
                FROM swe_tracing_spans
                WHERE start_time >= %s AND start_time <= %s
                  AND event_type = 'tool_call_end'
                  AND mcp_server = %s
                GROUP BY tool_name, mcp_server
                ORDER BY count DESC
            """
            rows = await self._db.fetch_all(
                query,
                (start_date, end_date, server_name),
            )
        else:
            query = """
                SELECT tool_name, mcp_server, COUNT(*) as count,
                       AVG(duration_ms) as avg_duration,
                       SUM(CASE WHEN error IS NOT NULL THEN 1 ELSE 0 END) as error_count
                FROM swe_tracing_spans
                WHERE source_id = %s AND start_time >= %s AND start_time <= %s
                  AND event_type = 'tool_call_end'
                  AND mcp_server = %s
                GROUP BY tool_name, mcp_server
                ORDER BY count DESC
            """
            rows = await self._db.fetch_all(
                query,
                (source_id, start_date, end_date, server_name),
            )
        return [
            MCPToolUsage(
                tool_name=r["tool_name"],
                mcp_server=r["mcp_server"],
                count=r["count"] or 0,
                avg_duration_ms=int(r["avg_duration"] or 0),
                error_count=r["error_count"] or 0,
            )
            for r in rows
        ]

    async def _get_user_model_usage(
        self,
        source_id: str,
        user_id: str,
        start_date: datetime,
        end_date: datetime,
    ) -> list[ModelUsage]:
        """获取用户模型使用."""
        if source_id == "all":
            model_query = """
                SELECT model_name, COUNT(*) as count,
                       SUM(total_input_tokens) as input_tokens,
                       SUM(total_output_tokens) as output_tokens,
                       SUM(total_tokens) as total_tokens
                FROM swe_tracing_traces
                WHERE user_id = %s AND start_time >= %s AND start_time <= %s
                      AND model_name IS NOT NULL
                GROUP BY model_name
                ORDER BY count DESC
            """
            model_rows = await self._db.fetch_all(
                model_query,
                (user_id, start_date, end_date),
            )
        else:
            model_query = """
                SELECT model_name, COUNT(*) as count,
                       SUM(total_input_tokens) as input_tokens,
                       SUM(total_output_tokens) as output_tokens,
                       SUM(total_tokens) as total_tokens
                FROM swe_tracing_traces
                WHERE source_id = %s AND user_id = %s AND start_time >= %s AND start_time <= %s
                      AND model_name IS NOT NULL
                GROUP BY model_name
                ORDER BY count DESC
            """
            model_rows = await self._db.fetch_all(
                model_query,
                (source_id, user_id, start_date, end_date),
            )
        return [
            ModelUsage(
                model_name=row["model_name"],
                count=row["count"],
                total_tokens=row["total_tokens"] or 0,
                input_tokens=row["input_tokens"] or 0,
                output_tokens=row["output_tokens"] or 0,
            )
            for row in model_rows
        ]

    async def _get_user_tool_usage(
        self,
        source_id: str,
        user_id: str,
        start_date: datetime,
        end_date: datetime,
    ) -> list[ToolUsage]:
        """获取用户工具使用."""
        if source_id == "all":
            tool_query = """
                SELECT tool_name, COUNT(*) as count,
                       AVG(duration_ms) as avg_duration,
                       SUM(CASE WHEN error IS NOT NULL THEN 1 ELSE 0 END) as error_count
                FROM swe_tracing_spans
                WHERE user_id = %s AND start_time >= %s AND start_time <= %s
                  AND event_type = 'tool_call_end'
                  AND tool_name IS NOT NULL
                GROUP BY tool_name
                ORDER BY count DESC
            """
            tool_rows = await self._db.fetch_all(
                tool_query,
                (user_id, start_date, end_date),
            )
        else:
            tool_query = """
                SELECT tool_name, COUNT(*) as count,
                       AVG(duration_ms) as avg_duration,
                       SUM(CASE WHEN error IS NOT NULL THEN 1 ELSE 0 END) as error_count
                FROM swe_tracing_spans
                WHERE source_id = %s AND user_id = %s AND start_time >= %s AND start_time <= %s
                  AND event_type = 'tool_call_end'
                  AND tool_name IS NOT NULL
                GROUP BY tool_name
                ORDER BY count DESC
            """
            tool_rows = await self._db.fetch_all(
                tool_query,
                (source_id, user_id, start_date, end_date),
            )
        return [
            ToolUsage(
                tool_name=row["tool_name"],
                count=row["count"],
                avg_duration_ms=int(row["avg_duration"] or 0),
                error_count=row["error_count"] or 0,
            )
            for row in tool_rows
        ]

    async def _get_user_skill_usage(
        self,
        source_id: str,
        user_id: str,
        start_date: datetime,
        end_date: datetime,
    ) -> list[SkillUsage]:
        """获取用户技能使用."""
        if source_id == "all":
            skill_query = """
                SELECT skill_name, COUNT(*) as count,
                       AVG(duration_ms) as avg_duration
                FROM swe_tracing_spans
                WHERE user_id = %s AND start_time >= %s AND start_time <= %s
                  AND event_type = 'skill_invocation'
                  AND skill_name IS NOT NULL
                GROUP BY skill_name
                ORDER BY count DESC
            """
            skill_rows = await self._db.fetch_all(
                skill_query,
                (user_id, start_date, end_date),
            )
        else:
            skill_query = """
                SELECT skill_name, COUNT(*) as count,
                       AVG(duration_ms) as avg_duration
                FROM swe_tracing_spans
                WHERE source_id = %s AND user_id = %s AND start_time >= %s AND start_time <= %s
                  AND event_type = 'skill_invocation'
                  AND skill_name IS NOT NULL
                GROUP BY skill_name
                ORDER BY count DESC
            """
            skill_rows = await self._db.fetch_all(
                skill_query,
                (source_id, user_id, start_date, end_date),
            )
        return [
            SkillUsage(
                skill_name=row["skill_name"],
                count=row["count"],
                avg_duration_ms=int(row["avg_duration"] or 0),
            )
            for row in skill_rows
        ]

    async def _get_user_mcp_tool_usage(
        self,
        source_id: str,
        user_id: str,
        start_date: datetime,
        end_date: datetime,
    ) -> list[MCPToolUsage]:
        """获取用户 MCP 工具使用."""
        if source_id == "all":
            query = """
                SELECT tool_name, mcp_server, COUNT(*) as count,
                       AVG(duration_ms) as avg_duration,
                       SUM(CASE WHEN error IS NOT NULL THEN 1 ELSE 0 END) as error_count
                FROM swe_tracing_spans
                WHERE user_id = %s AND start_time >= %s AND start_time <= %s
                  AND event_type = 'tool_call_end'
                  AND mcp_server IS NOT NULL
                  AND tool_name IS NOT NULL
                GROUP BY tool_name, mcp_server
                ORDER BY count DESC
            """
            rows = await self._db.fetch_all(
                query,
                (user_id, start_date, end_date),
            )
        else:
            query = """
                SELECT tool_name, mcp_server, COUNT(*) as count,
                       AVG(duration_ms) as avg_duration,
                       SUM(CASE WHEN error IS NOT NULL THEN 1 ELSE 0 END) as error_count
                FROM swe_tracing_spans
                WHERE source_id = %s AND user_id = %s AND start_time >= %s AND start_time <= %s
                  AND event_type = 'tool_call_end'
                  AND mcp_server IS NOT NULL
                  AND tool_name IS NOT NULL
                GROUP BY tool_name, mcp_server
                ORDER BY count DESC
            """
            rows = await self._db.fetch_all(
                query,
                (source_id, user_id, start_date, end_date),
            )
        return [
            MCPToolUsage(
                tool_name=row["tool_name"],
                mcp_server=row["mcp_server"],
                count=row["count"],
                avg_duration_ms=int(row["avg_duration"] or 0),
                error_count=row["error_count"] or 0,
            )
            for row in rows
        ]

    # ===== 会话分析 =====

    async def get_sessions(
        self,
        source_id: str,
        page: int = 1,
        page_size: int = 20,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        bbk_id: Optional[str] = None,
    ) -> tuple[list[SessionListItem], int]:
        """获取会话列表."""
        if source_id == "all":
            exclude_placeholders = ", ".join(
                ["%s"] * len(EXCLUDED_SOURCE_IDS),
            )
            where_clauses: list[str] = [
                f"source_id NOT IN ({exclude_placeholders})",
            ]
            params: list[Any] = list(EXCLUDED_SOURCE_IDS)
        else:
            where_clauses = ["source_id = %s"]
            params = [source_id]

        if user_id:
            where_clauses.append("user_id = %s")
            params.append(user_id)
        if session_id:
            where_clauses.append("session_id LIKE %s")
            params.append(f"%{session_id}%")
        if bbk_id:
            where_clauses.append("bbk_id = %s")
            params.append(bbk_id)
        if start_date:
            where_clauses.append("start_time >= %s")
            params.append(start_date)
        if end_date:
            where_clauses.append("start_time <= %s")
            params.append(end_date)

        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

        # 构建技能统计子查询的日期筛选条件
        skill_date_conditions = "s.event_type = 'skill_invocation'"
        skill_params: list[Any] = []
        if start_date:
            skill_date_conditions += " AND s.start_time >= %s"
            skill_params.append(start_date)
        if end_date:
            skill_date_conditions += " AND s.start_time <= %s"
            skill_params.append(end_date)

        count_query = f"SELECT COUNT(DISTINCT session_id) as total FROM swe_tracing_traces WHERE {where_sql}"
        count_row = await self._db.fetch_one(count_query, tuple(params))
        total = count_row["total"] if count_row else 0

        offset = (page - 1) * page_size
        exclude_placeholders = ", ".join(["%s"] * len(EXCLUDED_SOURCE_IDS))
        if source_id == "all":
            # SQL 占位符顺序（按在 SQL 字符串中出现顺序）：
            # 1. SELECT 子查询1: s.source_id NOT IN (...)
            # 2. SELECT 子查询1: {skill_date_conditions} 的日期参数
            # 3. SELECT 子查询2: t2.source_id NOT IN (...)
            # 4. SELECT 子查询3: t3.source_id NOT IN (...)
            # 5. SELECT 子查询4: t4.source_id NOT IN (...) (session_name)
            # 6. SELECT 子查询5: t5.source_id NOT IN (...) (user_message fallback)
            # 7. WHERE {where_sql} 的参数
            # 8. LIMIT %s OFFSET %s
            query = f"""
                SELECT t.session_id,
                       t.user_id,
                       t.channel,
                       COUNT(*) as total_traces,
                       SUM(t.total_tokens) as total_tokens,
                       MIN(t.start_time) as first_active,
                       MAX(t.start_time) as last_active,
                       (SELECT COUNT(*) FROM swe_tracing_spans s
                        WHERE s.session_id = t.session_id
                        AND s.source_id NOT IN ({exclude_placeholders})
                        AND {skill_date_conditions}) as total_skills,
                       (SELECT t2.user_name FROM swe_tracing_traces t2
                        WHERE t2.user_id = t.user_id AND t2.user_name IS NOT NULL
                        AND t2.source_id NOT IN ({exclude_placeholders})
                        ORDER BY t2.start_time DESC LIMIT 1) as user_name,
                       (SELECT t3.bbk_id FROM swe_tracing_traces t3
                        WHERE t3.user_id = t.user_id AND t3.bbk_id IS NOT NULL
                        AND t3.source_id NOT IN ({exclude_placeholders})
                        ORDER BY t3.start_time DESC LIMIT 1) as bbk_id,
                       COALESCE(
                           (SELECT t4.session_name FROM swe_tracing_traces t4
                            WHERE t4.session_id = t.session_id AND t4.session_name IS NOT NULL
                            AND t4.source_id NOT IN ({exclude_placeholders})
                            ORDER BY t4.start_time ASC LIMIT 1),
                           SUBSTRING(
                               (SELECT t5.user_message FROM swe_tracing_traces t5
                                WHERE t5.session_id = t.session_id AND t5.user_message IS NOT NULL
                                AND t5.source_id NOT IN ({exclude_placeholders})
                                ORDER BY t5.start_time ASC LIMIT 1),
                               1, 10
                           )
                       ) as session_name
                FROM swe_tracing_traces t
                WHERE {where_sql}
                GROUP BY t.session_id, t.user_id, t.channel
                ORDER BY last_active DESC
                LIMIT %s OFFSET %s
            """
            # 参数按 SQL 占位符出现顺序构建：
            # 子查询1参数 + 子查询2参数 + 子查询3参数 + 子查询4参数 + 子查询5参数 + WHERE参数 + LIMIT/OFFSET
            params = (
                list(EXCLUDED_SOURCE_IDS)  # 子查询1: s.source_id NOT IN
                + skill_params  # 子查询1: 日期条件
                + list(EXCLUDED_SOURCE_IDS)  # 子查询2: t2.source_id NOT IN
                + list(EXCLUDED_SOURCE_IDS)  # 子查询3: t3.source_id NOT IN
                + list(
                    EXCLUDED_SOURCE_IDS,
                )  # 子查询4: t4.source_id NOT IN (session_name)
                + list(
                    EXCLUDED_SOURCE_IDS,
                )  # 子查询5: t5.source_id NOT IN (user_message fallback)
                + params  # WHERE 子句参数
                + [page_size, offset]
            )
        else:
            query = f"""
                SELECT t.session_id,
                       t.user_id,
                       t.channel,
                       COUNT(*) as total_traces,
                       SUM(t.total_tokens) as total_tokens,
                       MIN(t.start_time) as first_active,
                       MAX(t.start_time) as last_active,
                       (SELECT COUNT(*) FROM swe_tracing_spans s
                        WHERE s.source_id = %s
                        AND s.session_id = t.session_id
                        AND {skill_date_conditions}) as total_skills,
                       (SELECT t2.user_name FROM swe_tracing_traces t2
                        WHERE t2.user_id = t.user_id AND t2.source_id = %s AND t2.user_name IS NOT NULL
                        ORDER BY t2.start_time DESC LIMIT 1) as user_name,
                       (SELECT t3.bbk_id FROM swe_tracing_traces t3
                        WHERE t3.user_id = t.user_id AND t3.source_id = %s AND t3.bbk_id IS NOT NULL
                        ORDER BY t3.start_time DESC LIMIT 1) as bbk_id,
                       COALESCE(
                           (SELECT t4.session_name FROM swe_tracing_traces t4
                            WHERE t4.session_id = t.session_id AND t4.session_name IS NOT NULL
                            AND t4.source_id = %s
                            ORDER BY t4.start_time ASC LIMIT 1),
                           SUBSTRING(
                               (SELECT t5.user_message FROM swe_tracing_traces t5
                                WHERE t5.session_id = t.session_id AND t5.user_message IS NOT NULL
                                AND t5.source_id = %s
                                ORDER BY t5.start_time ASC LIMIT 1),
                               1, 10
                           )
                       ) as session_name
                FROM swe_tracing_traces t
                WHERE {where_sql}
                GROUP BY t.session_id, t.user_id, t.channel
                ORDER BY last_active DESC
                LIMIT %s OFFSET %s
            """
            # 参数顺序: 子查询1 + 子查询2 + 子查询3 + 子查询4 + 子查询5 + WHERE参数 + LIMIT/OFFSET
            params = (
                [source_id]
                + skill_params
                + [source_id, source_id, source_id, source_id]
                + params
                + [page_size, offset]
            )

        rows = await self._db.fetch_all(query, tuple(params))
        sessions = [
            SessionListItem(
                session_id=row["session_id"],
                session_name=row.get("session_name"),
                user_id=row["user_id"],
                user_name=row["user_name"],
                bbk_id=row["bbk_id"],
                channel=row["channel"],
                total_traces=row["total_traces"] or 0,
                total_tokens=row["total_tokens"] or 0,
                total_skills=row["total_skills"] or 0,
                first_active=row["first_active"],
                last_active=row["last_active"],
            )
            for row in rows
        ]
        return sessions, total

    async def get_session_stats(
        self,
        source_id: str,
        session_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> SessionStats:
        """获取会话统计详情."""
        if start_date is None:
            start_date = datetime.now() - timedelta(days=30)
        if end_date is None:
            end_date = datetime.now()

        stats_row = await self._fetch_session_stats_row(
            source_id,
            session_id,
            start_date,
            end_date,
        )

        if not stats_row or not stats_row.get("user_id"):
            return SessionStats(session_id=session_id, user_id="", channel="")

        user_id = stats_row["user_id"]
        channel = stats_row["channel"] or ""

        model_usage, tools_used, skills_used, mcp_tools_used = (
            await asyncio.gather(
                self._fetch_session_model_usage(
                    source_id,
                    session_id,
                    start_date,
                    end_date,
                ),
                self._fetch_session_tools_used(
                    source_id,
                    session_id,
                    start_date,
                    end_date,
                ),
                self._fetch_session_skills_used(
                    source_id,
                    session_id,
                    start_date,
                    end_date,
                ),
                self._fetch_session_mcp_tools(
                    source_id,
                    session_id,
                    start_date,
                    end_date,
                ),
            )
        )

        return self._build_session_stats(
            session_id=session_id,
            user_id=user_id,
            channel=channel,
            stats_row=stats_row,
            model_usage_rows=model_usage,
            tools_used_rows=tools_used,
            skills_used_rows=skills_used,
            mcp_tools_rows=mcp_tools_used,
        )

    async def _fetch_session_stats_row(
        self,
        source_id: str,
        session_id: str,
        start_date: datetime,
        end_date: datetime,
    ) -> Optional[dict]:
        """获取会话统计行数据."""
        if source_id == "all":
            exclude_placeholders = ", ".join(
                ["%s"] * len(EXCLUDED_SOURCE_IDS),
            )
            query = f"""
                SELECT
                    user_id,
                    channel,
                    COUNT(*) as total_traces,
                    SUM(total_input_tokens) as input_tokens,
                    SUM(total_output_tokens) as output_tokens,
                    SUM(total_tokens) as total_tokens,
                    AVG(duration_ms) as avg_duration,
                    MIN(start_time) as first_active,
                    MAX(start_time) as last_active
                FROM swe_tracing_traces
                WHERE source_id NOT IN ({exclude_placeholders})
                      AND session_id = %s AND start_time >= %s AND start_time <= %s
                GROUP BY user_id, channel
            """
            return await self._db.fetch_one(
                query,
                (*EXCLUDED_SOURCE_IDS, session_id, start_date, end_date),
            )
        return await self._db.fetch_one(
            """
            SELECT
                user_id,
                channel,
                COUNT(*) as total_traces,
                SUM(total_input_tokens) as input_tokens,
                SUM(total_output_tokens) as output_tokens,
                SUM(total_tokens) as total_tokens,
                AVG(duration_ms) as avg_duration,
                MIN(start_time) as first_active,
                MAX(start_time) as last_active
            FROM swe_tracing_traces
            WHERE source_id = %s AND session_id = %s AND start_time >= %s AND start_time <= %s
            GROUP BY user_id, channel
            """,
            (source_id, session_id, start_date, end_date),
        )

    async def _fetch_session_model_usage(
        self,
        source_id: str,
        session_id: str,
        start_date: datetime,
        end_date: datetime,
    ) -> list:
        """获取会话模型使用数据."""
        if source_id == "all":
            exclude_placeholders = ", ".join(
                ["%s"] * len(EXCLUDED_SOURCE_IDS),
            )
            query = f"""
                SELECT model_name, COUNT(*) as count,
                       SUM(total_input_tokens) as input_tokens,
                       SUM(total_output_tokens) as output_tokens,
                       SUM(total_tokens) as total_tokens
                FROM swe_tracing_traces
                WHERE source_id NOT IN ({exclude_placeholders})
                      AND session_id = %s AND start_time >= %s AND start_time <= %s
                      AND model_name IS NOT NULL
                GROUP BY model_name
                ORDER BY count DESC
            """
            return await self._db.fetch_all(
                query,
                (*EXCLUDED_SOURCE_IDS, session_id, start_date, end_date),
            )
        return await self._db.fetch_all(
            """
            SELECT model_name, COUNT(*) as count,
                   SUM(total_input_tokens) as input_tokens,
                   SUM(total_output_tokens) as output_tokens,
                   SUM(total_tokens) as total_tokens
            FROM swe_tracing_traces
            WHERE source_id = %s AND session_id = %s AND start_time >= %s AND start_time <= %s
                  AND model_name IS NOT NULL
            GROUP BY model_name
            ORDER BY count DESC
            """,
            (source_id, session_id, start_date, end_date),
        )

    async def _fetch_session_tools_used(
        self,
        source_id: str,
        session_id: str,
        start_date: datetime,
        end_date: datetime,
    ) -> list:
        """获取会话工具使用数据."""
        if source_id == "all":
            exclude_placeholders = ", ".join(
                ["%s"] * len(EXCLUDED_SOURCE_IDS),
            )
            query = f"""
                SELECT tool_name, COUNT(*) as count,
                       AVG(duration_ms) as avg_duration,
                       SUM(CASE WHEN error IS NOT NULL THEN 1 ELSE 0 END) as error_count
                FROM swe_tracing_spans
                WHERE source_id NOT IN ({exclude_placeholders})
                      AND session_id = %s AND start_time >= %s AND start_time <= %s
                  AND event_type = 'tool_call_end'
                  AND tool_name IS NOT NULL
                  AND mcp_server IS NULL
                GROUP BY tool_name
                ORDER BY count DESC
            """
            return await self._db.fetch_all(
                query,
                (*EXCLUDED_SOURCE_IDS, session_id, start_date, end_date),
            )
        return await self._db.fetch_all(
            """
            SELECT tool_name, COUNT(*) as count,
                   AVG(duration_ms) as avg_duration,
                   SUM(CASE WHEN error IS NOT NULL THEN 1 ELSE 0 END) as error_count
            FROM swe_tracing_spans
            WHERE source_id = %s AND session_id = %s AND start_time >= %s AND start_time <= %s
              AND event_type = 'tool_call_end'
              AND tool_name IS NOT NULL
              AND mcp_server IS NULL
            GROUP BY tool_name
            ORDER BY count DESC
            """,
            (source_id, session_id, start_date, end_date),
        )

    async def _fetch_session_skills_used(
        self,
        source_id: str,
        session_id: str,
        start_date: datetime,
        end_date: datetime,
    ) -> list:
        """获取会话技能使用数据."""
        if source_id == "all":
            exclude_placeholders = ", ".join(
                ["%s"] * len(EXCLUDED_SOURCE_IDS),
            )
            query = f"""
                SELECT skill_name, COUNT(*) as count,
                       AVG(duration_ms) as avg_duration
                FROM swe_tracing_spans
                WHERE source_id NOT IN ({exclude_placeholders})
                      AND session_id = %s AND start_time >= %s AND start_time <= %s
                  AND event_type = 'skill_invocation'
                  AND skill_name IS NOT NULL
                GROUP BY skill_name
                ORDER BY count DESC
            """
            return await self._db.fetch_all(
                query,
                (*EXCLUDED_SOURCE_IDS, session_id, start_date, end_date),
            )
        return await self._db.fetch_all(
            """
            SELECT skill_name, COUNT(*) as count,
                   AVG(duration_ms) as avg_duration
            FROM swe_tracing_spans
            WHERE source_id = %s AND session_id = %s AND start_time >= %s AND start_time <= %s
              AND event_type = 'skill_invocation'
              AND skill_name IS NOT NULL
            GROUP BY skill_name
            ORDER BY count DESC
            """,
            (source_id, session_id, start_date, end_date),
        )

    async def _fetch_session_mcp_tools(
        self,
        source_id: str,
        session_id: str,
        start_date: datetime,
        end_date: datetime,
    ) -> list:
        """获取会话 MCP 工具使用数据."""
        if source_id == "all":
            exclude_placeholders = ", ".join(
                ["%s"] * len(EXCLUDED_SOURCE_IDS),
            )
            query = f"""
                SELECT tool_name, mcp_server, COUNT(*) as count,
                       AVG(duration_ms) as avg_duration,
                       SUM(CASE WHEN error IS NOT NULL THEN 1 ELSE 0 END) as error_count
                FROM swe_tracing_spans
                WHERE source_id NOT IN ({exclude_placeholders})
                      AND session_id = %s AND start_time >= %s AND start_time <= %s
                  AND event_type = 'tool_call_end'
                  AND mcp_server IS NOT NULL
                GROUP BY tool_name, mcp_server
                ORDER BY count DESC
            """
            return await self._db.fetch_all(
                query,
                (*EXCLUDED_SOURCE_IDS, session_id, start_date, end_date),
            )
        return await self._db.fetch_all(
            """
            SELECT tool_name, mcp_server, COUNT(*) as count,
                   AVG(duration_ms) as avg_duration,
                   SUM(CASE WHEN error IS NOT NULL THEN 1 ELSE 0 END) as error_count
            FROM swe_tracing_spans
            WHERE source_id = %s AND session_id = %s AND start_time >= %s AND start_time <= %s
              AND event_type = 'tool_call_end'
              AND mcp_server IS NOT NULL
            GROUP BY tool_name, mcp_server
            ORDER BY count DESC
            """,
            (source_id, session_id, start_date, end_date),
        )

    def _build_session_stats(
        self,
        session_id: str,
        user_id: str,
        channel: str,
        stats_row: dict,
        model_usage_rows: list,
        tools_used_rows: list,
        skills_used_rows: list,
        mcp_tools_rows: list,
    ) -> SessionStats:
        """构建会话统计对象."""
        return SessionStats(
            session_id=session_id,
            user_id=user_id,
            channel=channel,
            model_usage=self._build_model_usage_list(model_usage_rows),
            total_tokens=stats_row["total_tokens"] or 0,
            input_tokens=stats_row["input_tokens"] or 0,
            output_tokens=stats_row["output_tokens"] or 0,
            total_traces=stats_row["total_traces"] or 0,
            avg_duration_ms=self._extract_avg_duration(stats_row),
            tools_used=self._build_tool_usage_list(tools_used_rows),
            skills_used=self._build_skill_usage_list(skills_used_rows),
            mcp_tools_used=self._build_mcp_tool_usage_list(mcp_tools_rows),
            first_active=stats_row["first_active"],
            last_active=stats_row["last_active"],
        )

    def _build_model_usage_list(self, rows: list) -> list[ModelUsage]:
        """构建模型使用列表."""
        return [
            ModelUsage(
                model_name=row["model_name"],
                count=row["count"],
                total_tokens=row["total_tokens"] or 0,
                input_tokens=row["input_tokens"] or 0,
                output_tokens=row["output_tokens"] or 0,
            )
            for row in rows
        ]

    def _build_tool_usage_list(self, rows: list) -> list[ToolUsage]:
        """构建工具使用列表."""
        return [
            ToolUsage(
                tool_name=row["tool_name"],
                count=row["count"],
                avg_duration_ms=int(row["avg_duration"] or 0),
                error_count=row["error_count"] or 0,
            )
            for row in rows
        ]

    def _build_skill_usage_list(self, rows: list) -> list[SkillUsage]:
        """构建技能使用列表."""
        return [
            SkillUsage(
                skill_name=row["skill_name"],
                count=row["count"],
                avg_duration_ms=int(row["avg_duration"] or 0),
            )
            for row in rows
        ]

    def _build_mcp_tool_usage_list(self, rows: list) -> list[MCPToolUsage]:
        """构建 MCP 工具使用列表."""
        return [
            MCPToolUsage(
                tool_name=row["tool_name"],
                mcp_server=row["mcp_server"],
                count=row["count"],
                avg_duration_ms=int(row["avg_duration"] or 0),
                error_count=row["error_count"] or 0,
            )
            for row in rows
        ]

    # ===== 对话分析 =====

    async def get_traces(
        self,
        source_id: str,
        page: int = 1,
        page_size: int = 20,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        status: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        bbk_id: Optional[str] = None,
    ) -> tuple[list[TraceListItem], int]:
        """获取对话列表."""
        if source_id == "all":
            exclude_placeholders = ", ".join(
                ["%s"] * len(EXCLUDED_SOURCE_IDS),
            )
            where_clauses: list[str] = [
                f"source_id NOT IN ({exclude_placeholders})",
            ]
            params: list[Any] = list(EXCLUDED_SOURCE_IDS)
        else:
            where_clauses = ["source_id = %s"]
            params = [source_id]

        if user_id:
            where_clauses.append("user_id = %s")
            params.append(user_id)
        if session_id:
            where_clauses.append("session_id = %s")
            params.append(session_id)
        if status:
            where_clauses.append("status = %s")
            params.append(status)
        if bbk_id:
            where_clauses.append("bbk_id = %s")
            params.append(bbk_id)
        if start_date:
            where_clauses.append("start_time >= %s")
            params.append(start_date)
        if end_date:
            where_clauses.append("start_time <= %s")
            params.append(end_date)

        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

        count_query = f"SELECT COUNT(*) as total FROM swe_tracing_traces WHERE {where_sql}"
        count_row = await self._db.fetch_one(count_query, tuple(params))
        total = count_row["total"] if count_row else 0

        offset = (page - 1) * page_size
        exclude_placeholders = ", ".join(["%s"] * len(EXCLUDED_SOURCE_IDS))
        if source_id == "all":
            query = f"""
                SELECT t.trace_id, t.source_id, t.user_id, t.session_id, t.channel, t.start_time,
                       t.duration_ms, t.total_tokens, t.total_input_tokens, t.total_output_tokens,
                       t.model_name, t.status,
                       JSON_LENGTH(t.skills_used) as skills_count,
                       COALESCE(t.user_name, (
                           SELECT t2.user_name FROM swe_tracing_traces t2
                           WHERE t2.user_id = t.user_id AND t2.user_name IS NOT NULL
                           AND t2.source_id NOT IN ({exclude_placeholders})
                           ORDER BY t2.start_time DESC LIMIT 1
                       )) as user_name,
                       COALESCE(t.bbk_id, (
                           SELECT t3.bbk_id FROM swe_tracing_traces t3
                           WHERE t3.user_id = t.user_id AND t3.bbk_id IS NOT NULL
                           AND t3.source_id NOT IN ({exclude_placeholders})
                           ORDER BY t3.start_time DESC LIMIT 1
                       )) as bbk_id
                FROM swe_tracing_traces t
                WHERE {where_sql}
                ORDER BY t.start_time DESC
                LIMIT %s OFFSET %s
            """
            # 参数顺序：子查询参数（按 SQL 出现顺序）+ WHERE 参数 + LIMIT/OFFSET
            params = (
                list(EXCLUDED_SOURCE_IDS)  # 子查询1: t2.source_id NOT IN
                + list(EXCLUDED_SOURCE_IDS)  # 子查询2: t3.source_id NOT IN
                + params  # WHERE 子句参数
                + [page_size, offset]
            )
        else:
            query = f"""
                SELECT t.trace_id, t.source_id, t.user_id, t.session_id, t.channel, t.start_time,
                       t.duration_ms, t.total_tokens, t.total_input_tokens, t.total_output_tokens,
                       t.model_name, t.status,
                       JSON_LENGTH(t.skills_used) as skills_count,
                       COALESCE(t.user_name, (
                           SELECT t2.user_name FROM swe_tracing_traces t2
                           WHERE t2.source_id = %s AND t2.user_id = t.user_id AND t2.user_name IS NOT NULL
                           ORDER BY t2.start_time DESC LIMIT 1
                       )) as user_name,
                       COALESCE(t.bbk_id, (
                           SELECT t3.bbk_id FROM swe_tracing_traces t3
                           WHERE t3.source_id = %s AND t3.user_id = t.user_id AND t3.bbk_id IS NOT NULL
                           ORDER BY t3.start_time DESC LIMIT 1
                       )) as bbk_id
                FROM swe_tracing_traces t
                WHERE {where_sql}
                ORDER BY t.start_time DESC
                LIMIT %s OFFSET %s
            """
            params = [source_id, source_id] + params + [page_size, offset]
        rows = await self._db.fetch_all(query, tuple(params))
        traces = [
            TraceListItem(
                trace_id=row["trace_id"],
                source_id=row["source_id"],
                user_id=row["user_id"],
                user_name=row["user_name"],
                bbk_id=row["bbk_id"],
                session_id=row["session_id"],
                channel=row["channel"],
                start_time=row["start_time"],
                duration_ms=row["duration_ms"],
                total_tokens=row["total_tokens"] or 0,
                total_input_tokens=row["total_input_tokens"] or 0,
                total_output_tokens=row["total_output_tokens"] or 0,
                model_name=row["model_name"],
                status=row["status"],
                skills_count=row["skills_count"] or 0,
            )
            for row in rows
        ]
        return traces, total

    async def get_trace(
        self,
        trace_id: str,
        source_id: Optional[str] = None,
    ) -> Optional[Trace]:
        """获取单个对话."""
        if source_id:
            query = "SELECT * FROM swe_tracing_traces WHERE trace_id = %s AND source_id = %s"
            row = await self._db.fetch_one(query, (trace_id, source_id))
        else:
            query = "SELECT * FROM swe_tracing_traces WHERE trace_id = %s"
            row = await self._db.fetch_one(query, (trace_id,))
        if row is None:
            return None
        return self._row_to_trace(row)

    async def get_spans(self, trace_id: str) -> list[Span]:
        """获取对话的所有 Span."""
        query = "SELECT * FROM swe_tracing_spans WHERE trace_id = %s ORDER BY start_time"
        rows = await self._db.fetch_all(query, (trace_id,))
        return [self._row_to_span(row) for row in rows]

    async def get_trace_detail(
        self,
        trace_id: str,
        source_id: Optional[str] = None,
    ) -> Optional[TraceDetail]:
        """获取对话详情."""
        trace = await self.get_trace(trace_id, source_id)
        if trace is None:
            return None

        spans = await self.get_spans(trace_id)

        # 从 ES 获取 model_output
        from ...database.elasticsearch import get_es_client

        es_client = get_es_client()
        if es_client and es_client.is_connected:
            trace.model_output = await es_client.get_message(trace_id)

        llm_duration = sum(
            s.duration_ms or 0
            for s in spans
            if s.event_type in (EventType.LLM_INPUT, EventType.LLM_OUTPUT)
        )
        tool_duration = sum(
            s.duration_ms or 0
            for s in spans
            if s.event_type
            in (EventType.TOOL_CALL_START, EventType.TOOL_CALL_END)
        )

        tools_called = []
        tool_spans = [
            s for s in spans if s.event_type == EventType.TOOL_CALL_END
        ]
        for span in tool_spans:
            tools_called.append(
                {
                    "tool_name": span.tool_name or span.name,
                    "tool_input": span.tool_input,
                    "tool_output": span.tool_output,
                    "duration_ms": span.duration_ms,
                    "error": span.error,
                },
            )

        return TraceDetail(
            trace=trace,
            spans=spans,
            llm_duration_ms=llm_duration,
            tool_duration_ms=tool_duration,
            tools_called=tools_called,
        )

    async def get_trace_detail_with_timeline(
        self,
        trace_id: str,
        source_id: Optional[str] = None,
    ) -> Optional[TraceDetailWithTimeline]:
        """获取对话详情（带时间线）."""
        trace = await self.get_trace(trace_id, source_id)
        if trace is None:
            return None

        spans = await self.get_spans(trace_id)

        # 从 ES 获取 model_output
        from ...database.elasticsearch import get_es_client

        es_client = get_es_client()
        if es_client and es_client.is_connected:
            trace.model_output = await es_client.get_message(trace_id)

        timeline = self._build_timeline(spans)
        skill_invocations = self._build_skill_invocations(spans)

        llm_duration = sum(
            s.duration_ms or 0
            for s in spans
            if s.event_type in (EventType.LLM_INPUT, EventType.LLM_OUTPUT)
        )
        tool_duration = sum(
            s.duration_ms or 0
            for s in spans
            if s.event_type
            in (EventType.TOOL_CALL_START, EventType.TOOL_CALL_END)
        )
        skill_duration = sum(inv.duration_ms for inv in skill_invocations)

        return TraceDetailWithTimeline(
            trace=trace,
            spans=spans,
            timeline=timeline,
            skill_invocations=skill_invocations,
            llm_duration_ms=llm_duration,
            tool_duration_ms=tool_duration,
            skill_duration_ms=skill_duration,
            total_skills=len(skill_invocations),
            total_tools=len(
                [s for s in spans if s.event_type == EventType.TOOL_CALL_END],
            ),
            total_llm_calls=len(
                [s for s in spans if s.event_type == EventType.LLM_INPUT],
            ),
        )

    # ===== 用户消息 =====

    async def get_user_messages(
        self,
        source_id: str,
        page: int = 1,
        page_size: int = 20,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        query_text: Optional[str] = None,
        export: bool = False,
        bbk_id: Optional[str] = None,
    ) -> tuple[list[UserMessageItem], int]:
        """获取用户消息列表."""
        if start_date is None:
            start_date = datetime.now() - timedelta(days=7)
        if end_date is None:
            end_date = datetime.now()

        if source_id == "all":
            where_clauses = [
                "start_time >= %s",
                "start_time <= %s",
            ]
            params: list[Any] = [start_date, end_date]
        else:
            where_clauses = [
                "source_id = %s",
                "start_time >= %s",
                "start_time <= %s",
            ]
            params = [source_id, start_date, end_date]

        if user_id:
            where_clauses.append("user_id = %s")
            params.append(user_id)
        if session_id:
            where_clauses.append("session_id = %s")
            params.append(session_id)
        if query_text:
            where_clauses.append("user_message LIKE %s")
            params.append(f"%{query_text}%")
        if bbk_id:
            where_clauses.append("bbk_id = %s")
            params.append(bbk_id)

        where_sql = " AND ".join(where_clauses)

        count_query = f"SELECT COUNT(*) as total FROM swe_tracing_traces WHERE {where_sql}"
        count_row = await self._db.fetch_one(count_query, tuple(params))
        total = count_row["total"] if count_row else 0

        if export:
            sql_query = f"""
                SELECT t.trace_id, t.source_id, t.user_id, t.session_id, t.channel, t.user_message,
                       t.model_name,
                       t.start_time, t.duration_ms,
                       COALESCE(t.user_name, (
                           SELECT t2.user_name FROM swe_tracing_traces t2
                           WHERE t2.user_id = t.user_id AND t2.user_name IS NOT NULL
                           ORDER BY t2.start_time DESC LIMIT 1
                       )) as user_name,
                       COALESCE(t.bbk_id, (
                           SELECT t3.bbk_id FROM swe_tracing_traces t3
                           WHERE t3.user_id = t.user_id AND t3.bbk_id IS NOT NULL
                           ORDER BY t3.start_time DESC LIMIT 1
                       )) as bbk_id
                FROM swe_tracing_traces t
                WHERE {where_sql}
                ORDER BY t.start_time DESC
            """
            rows = await self._db.fetch_all(sql_query, tuple(params))
        else:
            offset = (page - 1) * page_size
            sql_query = f"""
                SELECT t.trace_id, t.source_id, t.user_id, t.session_id, t.channel, t.user_message,
                       t.model_name,
                       t.start_time, t.duration_ms,
                       COALESCE(t.user_name, (
                           SELECT t2.user_name FROM swe_tracing_traces t2
                           WHERE t2.user_id = t.user_id AND t2.user_name IS NOT NULL
                           ORDER BY t2.start_time DESC LIMIT 1
                       )) as user_name,
                       COALESCE(t.bbk_id, (
                           SELECT t3.bbk_id FROM swe_tracing_traces t3
                           WHERE t3.user_id = t.user_id AND t3.bbk_id IS NOT NULL
                           ORDER BY t3.start_time DESC LIMIT 1
                       )) as bbk_id
                FROM swe_tracing_traces t
                WHERE {where_sql}
                ORDER BY t.start_time DESC
                LIMIT %s OFFSET %s
            """
            params.extend([page_size, offset])
            rows = await self._db.fetch_all(sql_query, tuple(params))

        messages = [
            UserMessageItem(
                trace_id=row["trace_id"],
                source_id=row["source_id"],
                user_id=row["user_id"],
                user_name=row["user_name"],
                bbk_id=row["bbk_id"],
                session_id=row["session_id"],
                channel=row["channel"],
                user_message=row["user_message"],
                model_name=row["model_name"],
                start_time=row["start_time"],
                duration_ms=row["duration_ms"],
            )
            for row in rows
        ]
        return messages, total

    # ===== 辅助方法 =====

    def _build_timeline(self, spans: list[Span]) -> list[TimelineEvent]:
        """构建时间线（只展示技能调用和LLM调用）."""
        spans = sorted(spans, key=lambda s: s.start_time)

        timeline: list[TimelineEvent] = []
        skill_stack: list[TimelineEvent] = []

        for span in spans:
            if span.event_type == EventType.SKILL_INVOCATION:
                event = TimelineEvent(
                    event_type="skill_invocation",
                    span_id=span.span_id,
                    start_time=span.start_time,
                    end_time=span.end_time,
                    duration_ms=span.duration_ms or 0,
                    skill_name=span.skill_name,
                    confidence=1.0,
                    trigger_reason="declared",
                    children=[],
                )

                if skill_stack:
                    skill_stack[-1].children.append(event)
                else:
                    timeline.append(event)

                skill_stack.append(event)

            elif span.event_type == EventType.SKILL_END:
                # 技能结束时弹出栈
                if skill_stack:
                    skill_stack.pop()

            elif span.event_type == EventType.LLM_INPUT:
                event = TimelineEvent(
                    event_type="llm_call",
                    span_id=span.span_id,
                    start_time=span.start_time,
                    end_time=span.end_time,
                    duration_ms=span.duration_ms or 0,
                    model_name=span.model_name,
                    input_tokens=span.input_tokens,
                    output_tokens=span.output_tokens,
                    children=[],
                )

                if skill_stack:
                    skill_stack[-1].children.append(event)
                else:
                    timeline.append(event)

        return timeline

    def _build_skill_invocations(
        self,
        spans: list[Span],
    ) -> list[SkillCallTimeline]:
        """构建技能调用摘要."""
        skill_spans = [
            s for s in spans if s.event_type == EventType.SKILL_INVOCATION
        ]

        invocations: list[SkillCallTimeline] = []
        skill_tools: dict[str, list[ToolCallInSkill]] = {}

        for span in spans:
            if span.event_type == EventType.TOOL_CALL_END and span.skill_name:
                skill_name = span.skill_name
                if skill_name not in skill_tools:
                    skill_tools[skill_name] = []

                skill_tools[skill_name].append(
                    ToolCallInSkill(
                        span_id=span.span_id,
                        tool_name=span.tool_name or "",
                        mcp_server=span.mcp_server,
                        start_time=span.start_time,
                        end_time=span.end_time,
                        duration_ms=span.duration_ms or 0,
                        status="error" if span.error else "success",
                        error=span.error,
                        skill_weight=None,
                    ),
                )

        for skill_span in skill_spans:
            skill_name = skill_span.skill_name or ""
            tools = skill_tools.get(skill_name, [])

            invocations.append(
                SkillCallTimeline(
                    span_id=skill_span.span_id,
                    skill_name=skill_name,
                    start_time=skill_span.start_time,
                    end_time=skill_span.end_time,
                    duration_ms=skill_span.duration_ms or 0,
                    confidence=1.0,
                    trigger_reason="declared",
                    tools=tools,
                    total_tool_calls=len(tools),
                    tool_duration_ms=sum(t.duration_ms for t in tools),
                ),
            )

        return invocations

    def _row_to_trace(self, row: dict) -> Trace:
        """转换数据库行为 Trace 模型."""
        return Trace(
            trace_id=row["trace_id"],
            source_id=row["source_id"],
            user_id=row["user_id"],
            user_name=row.get("user_name"),
            bbk_id=row.get("bbk_id"),
            session_id=row["session_id"],
            channel=row["channel"],
            start_time=row["start_time"],
            end_time=row["end_time"],
            duration_ms=row["duration_ms"],
            model_name=row["model_name"],
            total_input_tokens=row["total_input_tokens"] or 0,
            total_output_tokens=row["total_output_tokens"] or 0,
            tools_used=(
                json.loads(row["tools_used"]) if row["tools_used"] else []
            ),
            skills_used=(
                json.loads(row["skills_used"]) if row["skills_used"] else []
            ),
            status=(
                TraceStatus(row["status"])
                if row["status"]
                else TraceStatus.RUNNING
            ),
            error=row["error"],
            user_message=row.get("user_message"),
        )

    def _row_to_span(self, row: dict) -> Span:
        """转换数据库行为 Span 模型."""
        return Span(
            span_id=row["span_id"],
            trace_id=row["trace_id"],
            source_id=row["source_id"],
            name=row["name"],
            event_type=EventType(row["event_type"]),
            start_time=row["start_time"],
            end_time=row["end_time"],
            duration_ms=row["duration_ms"],
            user_id=row.get("user_id") or "",
            user_name=row.get("user_name"),
            bbk_id=row.get("bbk_id"),
            session_id=row.get("session_id") or "",
            channel=row.get("channel") or "",
            model_name=row["model_name"],
            input_tokens=row["input_tokens"],
            output_tokens=row["output_tokens"],
            tool_name=row["tool_name"],
            skill_name=row["skill_name"],
            mcp_server=row.get("mcp_server"),
            tool_input=(
                json.loads(row["tool_input"]) if row["tool_input"] else None
            ),
            tool_output=row["tool_output"],
            error=row["error"],
        )
