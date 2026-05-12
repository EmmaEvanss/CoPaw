# -*- coding: utf-8 -*-
# pylint: disable=too-many-branches too-many-statements too-many-locals
"""Tracing API router for operational dashboard.

提供运营看板的数据查询和导出 API 端点。
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Query, HTTPException, Request
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)

from ..models.tracing import (
    OverviewStats,
    TraceDetail,
    TraceDetailWithTimeline,
    SessionStats,
    UserStats,
    ModelOutputRequest,
)
from ..services.tracing import TracingQueryService, TracingExportService
from ..database import get_es_client


def _get_source_id(
    request: Request,
    query_source_id: Optional[str] = None,
) -> str:
    """获取 source_id.

    优先级：
    1. 查询参数 source_id
    2. X-Source-Id 请求头
    3. 默认值 "default"

    查询参数优先级更高，因为 UI 中用户显式选择平台时使用查询参数，
    请求头来自 iframe 上下文，仅作为回退。

    Args:
        request: FastAPI 请求对象
        query_source_id: 查询参数中的 source_id

    Returns:
        数据源标识字符串
    """
    if query_source_id:
        return query_source_id
    header_source_id = request.headers.get("X-Source-Id")
    if header_source_id:
        return header_source_id
    return "default"


def _parse_date(
    date_str: Optional[str],
    field_name: str,
    add_day: bool = False,
) -> Optional[datetime]:
    """解析日期字符串为 datetime.

    Args:
        date_str: YYYY-MM-DD 格式的日期字符串
        field_name: 字段名，用于错误消息
        add_day: 是否增加一天以包含结束日期

    Returns:
        解析后的 datetime 或 None

    Raises:
        HTTPException: 日期格式无效时抛出
    """
    if not date_str:
        return None
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        if add_day:
            dt = dt + timedelta(days=1)
        return dt
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid {field_name} format",
        ) from exc


router = APIRouter(prefix="/monitor/tracing", tags=["tracing"])


# ===== 运营概览 =====


@router.get("/overview", response_model=OverviewStats)
async def get_overview(
    request: Request,
    source_id: Optional[str] = Query(
        None,
        description="数据源标识，使用 'all' 查询所有平台",
    ),
    start_date: Optional[str] = Query(
        None,
        description="开始日期 (YYYY-MM-DD)",
    ),
    end_date: Optional[str] = Query(None, description="结束日期 (YYYY-MM-DD)"),
) -> OverviewStats:
    """获取运营概览统计.

    Args:
        source_id: 数据源标识（使用 'all' 或留空查询所有平台）
        start_date: 可选的开始日期筛选
        end_date: 可选的结束日期筛选

    Returns:
        运营概览统计，包括用户数、Token 使用量、模型分布等
    """
    # 未指定时使用 'all' 获取所有平台数据
    actual_source_id = source_id or "all"
    service = TracingQueryService.get_instance()

    start = _parse_date(start_date, "start_date")
    end = _parse_date(end_date, "end_date", add_day=True)

    return await service.get_overview_stats(actual_source_id, start, end)


# ===== 用户分析 =====


@router.get("/users", response_model=dict)
async def get_users(
    request: Request,
    source_id: Optional[str] = Query(
        None,
        description="数据源标识，使用 'all' 查询所有平台",
    ),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    user_id: Optional[str] = Query(
        None,
        description="按用户 ID 筛选（模糊匹配）",
    ),
    start_date: Optional[str] = Query(
        None,
        description="开始日期 (YYYY-MM-DD)",
    ),
    end_date: Optional[str] = Query(None, description="结束日期 (YYYY-MM-DD)"),
    sort_by: Optional[str] = Query(
        None,
        description="排序字段: conversations, last_active",
    ),
    filter_user_type: Optional[str] = Query(
        "filtered",
        description="用户过滤类型: filtered(过滤80/IT开头用户), all(仅过滤default用户)",
    ),
    bbk_id: Optional[str] = Query(None, description="按分行号筛选"),
) -> dict:
    """获取用户列表及其统计信息.

    Args:
        source_id: 数据源标识（使用 'all' 或留空查询所有平台）
        page: 页码
        page_size: 每页数量
        user_id: 按用户 ID 筛选
        start_date: 开始日期筛选
        end_date: 结束日期筛选
        sort_by: 排序字段（conversations, last_active）
        filter_user_type: 用户过滤类型（filtered/all）

    Returns:
        分页的用户列表及统计信息
    """
    actual_source_id = source_id or "all"
    service = TracingQueryService.get_instance()

    start = _parse_date(start_date, "start_date")
    end = _parse_date(end_date, "end_date", add_day=True)

    users, total = await service.get_users(
        actual_source_id,
        page,
        page_size,
        user_id,
        start,
        end,
        sort_by,
        filter_user_type,
        bbk_id,
    )
    return {
        "items": [u.model_dump() for u in users],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/users/{user_id}", response_model=UserStats)
async def get_user_stats(
    user_id: str,
    request: Request,
    source_id: Optional[str] = Query(None, description="数据源标识"),
    start_date: Optional[str] = Query(
        None,
        description="开始日期 (YYYY-MM-DD)",
    ),
    end_date: Optional[str] = Query(None, description="结束日期 (YYYY-MM-DD)"),
) -> UserStats:
    """获取指定用户的统计详情.

    Args:
        user_id: 用户标识
        source_id: 数据源标识（可选，默认从请求头获取）
        start_date: 可选的开始日期筛选
        end_date: 可选的结束日期筛选

    Returns:
        用户统计信息
    """
    actual_source_id = _get_source_id(request, source_id)
    service = TracingQueryService.get_instance()

    start = _parse_date(start_date, "start_date")
    end = _parse_date(end_date, "end_date", add_day=True)

    return await service.get_user_stats(actual_source_id, user_id, start, end)


# ===== 对话分析 =====


@router.get("/traces", response_model=dict)
async def get_traces(
    request: Request,
    source_id: Optional[str] = Query(None, description="数据源标识"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    user_id: Optional[str] = Query(None, description="按用户 ID 筛选"),
    session_id: Optional[str] = Query(
        None,
        description="按会话 ID 筛选",
    ),
    status: Optional[str] = Query(None, description="按状态筛选"),
    start_date: Optional[str] = Query(
        None,
        description="开始日期 (YYYY-MM-DD)",
    ),
    end_date: Optional[str] = Query(None, description="结束日期 (YYYY-MM-DD)"),
    bbk_id: Optional[str] = Query(None, description="按分行号筛选"),
) -> dict:
    """获取对话列表.

    Args:
        source_id: 数据源标识（可选，默认从请求头获取）
        page: 页码
        page_size: 每页数量
        user_id: 按用户 ID 筛选
        session_id: 按会话 ID 筛选
        status: 按状态筛选（running, completed, error, cancelled）
        start_date: 开始日期筛选
        end_date: 结束日期筛选

    Returns:
        分页的对话列表
    """
    actual_source_id = _get_source_id(request, source_id)
    service = TracingQueryService.get_instance()

    start = _parse_date(start_date, "start_date")
    end = _parse_date(end_date, "end_date", add_day=True)

    traces, total = await service.get_traces(
        source_id=actual_source_id,
        page=page,
        page_size=page_size,
        user_id=user_id,
        session_id=session_id,
        status=status,
        start_date=start,
        end_date=end,
        bbk_id=bbk_id,
    )
    return {
        "items": [t.model_dump() for t in traces],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/traces/{trace_id}", response_model=TraceDetail)
async def get_trace_detail(
    trace_id: str,
    request: Request,
    source_id: Optional[str] = Query(None, description="数据源标识"),
) -> TraceDetail:
    """获取对话详情（包含 Span）.

    Args:
        trace_id: 对话标识
        source_id: 数据源标识（可选）。未提供时仅按 trace_id 查询，
            因为 trace_id 是全局唯一的

    Returns:
        对话详情及所有 Span

    Raises:
        HTTPException: 对话未找到时抛出
    """
    # trace_id 是全局唯一的，仅在显式提供时使用 source_id
    actual_source_id = source_id if source_id else None
    service = TracingQueryService.get_instance()

    detail = await service.get_trace_detail(trace_id, actual_source_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Trace not found")

    return detail


@router.get(
    "/traces/{trace_id}/timeline",
    response_model=TraceDetailWithTimeline,
)
async def get_trace_timeline(
    trace_id: str,
    request: Request,
    source_id: Optional[str] = Query(None, description="数据源标识"),
) -> TraceDetailWithTimeline:
    """获取对话详情（带时间线）.

    返回分层时间线，其中技能调用是父节点，包含其工具调用作为子节点。

    Args:
        trace_id: 对话标识
        source_id: 数据源标识（可选）。未提供时仅按 trace_id 查询，
            因为 trace_id 是全局唯一的

    Returns:
        对话详情及分层时间线

    Raises:
        HTTPException: 对话未找到时抛出
    """
    actual_source_id = source_id if source_id else None
    service = TracingQueryService.get_instance()

    detail = await service.get_trace_detail_with_timeline(
        trace_id,
        actual_source_id,
    )
    if detail is None:
        raise HTTPException(status_code=404, detail="Trace not found")

    return detail


# ===== 会话分析 =====


@router.get("/sessions", response_model=dict)
async def get_sessions(
    request: Request,
    source_id: Optional[str] = Query(None, description="数据源标识"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    user_id: Optional[str] = Query(None, description="按用户 ID 筛选"),
    session_id: Optional[str] = Query(
        None,
        description="按会话 ID 筛选（模糊匹配）",
    ),
    start_date: Optional[str] = Query(
        None,
        description="开始日期 (YYYY-MM-DD)",
    ),
    end_date: Optional[str] = Query(None, description="结束日期 (YYYY-MM-DD)"),
    bbk_id: Optional[str] = Query(None, description="按分行号筛选"),
) -> dict:
    """获取会话列表及其统计信息.

    Args:
        source_id: 数据源标识（可选，默认从请求头获取）
        page: 页码
        page_size: 每页数量
        user_id: 按用户 ID 筛选
        session_id: 按会话 ID 筛选（模糊匹配）
        start_date: 开始日期筛选
        end_date: 结束日期筛选

    Returns:
        分页的会话列表及统计信息
    """
    actual_source_id = _get_source_id(request, source_id)
    service = TracingQueryService.get_instance()

    start = _parse_date(start_date, "start_date")
    end = _parse_date(end_date, "end_date", add_day=True)

    sessions, total = await service.get_sessions(
        source_id=actual_source_id,
        page=page,
        page_size=page_size,
        user_id=user_id,
        session_id=session_id,
        start_date=start,
        end_date=end,
        bbk_id=bbk_id,
    )
    return {
        "items": [s.model_dump() for s in sessions],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/sessions/{session_id:path}", response_model=SessionStats)
async def get_session_stats(
    session_id: str,
    request: Request,
    source_id: Optional[str] = Query(None, description="数据源标识"),
    start_date: Optional[str] = Query(
        None,
        description="开始日期 (YYYY-MM-DD)",
    ),
    end_date: Optional[str] = Query(None, description="结束日期 (YYYY-MM-DD)"),
) -> SessionStats:
    """获取指定会话的统计详情.

    Args:
        session_id: 会话标识
        source_id: 数据源标识（可选，默认从请求头获取）
        start_date: 可选的开始日期筛选
        end_date: 可选的结束日期筛选

    Returns:
        会话统计信息
    """
    actual_source_id = _get_source_id(request, source_id)
    service = TracingQueryService.get_instance()

    start = _parse_date(start_date, "start_date")
    end = _parse_date(end_date, "end_date", add_day=True)

    return await service.get_session_stats(
        actual_source_id,
        session_id,
        start,
        end,
    )


# ===== 用户消息 =====


@router.get("/user-messages", response_model=dict)
async def get_user_messages(
    request: Request,
    source_id: Optional[str] = Query(None, description="数据源标识"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    user_id: Optional[str] = Query(None, description="按用户 ID 筛选"),
    session_id: Optional[str] = Query(
        None,
        description="按会话 ID 筛选",
    ),
    start_date: Optional[str] = Query(
        None,
        description="开始日期 (YYYY-MM-DD)",
    ),
    end_date: Optional[str] = Query(None, description="结束日期 (YYYY-MM-DD)"),
    query: Optional[str] = Query(
        None,
        description="搜索用户消息内容",
    ),
    bbk_id: Optional[str] = Query(None, description="按分行号筛选"),
) -> dict:
    """获取用户消息列表（含 Token 信息）.

    用于成本分析和消息内容查询。

    Args:
        source_id: 数据源标识（可选，默认从请求头获取）
        page: 页码
        page_size: 每页数量
        user_id: 按用户 ID 筛选
        session_id: 按会话 ID 筛选
        start_date: 开始日期筛选
        end_date: 结束日期筛选
        query: 搜索用户消息内容（模糊匹配）

    Returns:
        分页的用户消息列表及 Token 使用量
    """
    actual_source_id = _get_source_id(request, source_id)
    service = TracingQueryService.get_instance()

    start = _parse_date(start_date, "start_date")
    end = _parse_date(end_date, "end_date", add_day=True)

    messages, total = await service.get_user_messages(
        source_id=actual_source_id,
        page=page,
        page_size=page_size,
        user_id=user_id,
        session_id=session_id,
        start_date=start,
        end_date=end,
        query_text=query,
        export=False,
        bbk_id=bbk_id,
    )
    return {
        "items": [m.model_dump() for m in messages],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/user-messages/export")
async def export_user_messages(
    request: Request,
    source_id: Optional[str] = Query(None, description="数据源标识"),
    user_id: Optional[str] = Query(None, description="按用户 ID 筛选"),
    session_id: Optional[str] = Query(
        None,
        description="按会话 ID 筛选",
    ),
    start_date: Optional[str] = Query(
        None,
        description="开始日期 (YYYY-MM-DD)",
    ),
    end_date: Optional[str] = Query(None, description="结束日期 (YYYY-MM-DD)"),
    query: Optional[str] = Query(
        None,
        description="搜索用户消息内容",
    ),
    export_format: str = Query(
        "csv",
        description="导出格式: csv, json 或 xlsx",
        alias="format",
    ),
    bbk_id: Optional[str] = Query(None, description="按分行号筛选"),
) -> StreamingResponse:
    """导出用户消息.

    Args:
        source_id: 数据源标识（可选，默认从请求头获取）
        user_id: 按用户 ID 筛选
        session_id: 按会话 ID 筛选
        start_date: 开始日期筛选
        end_date: 结束日期筛选
        query: 搜索用户消息内容（模糊匹配）
        export_format: 导出格式（csv, json 或 xlsx）

    Returns:
        StreamingResponse 包含导出文件
    """
    actual_source_id = _get_source_id(request, source_id)
    export_service = TracingExportService.get_instance()

    start = _parse_date(start_date, "start_date")
    end = _parse_date(end_date, "end_date", add_day=True)

    if export_format == "json":
        return await export_service.export_user_messages_json(
            source_id=actual_source_id,
            user_id=user_id,
            session_id=session_id,
            start_date=start,
            end_date=end,
            query_text=query,
            bbk_id=bbk_id,
        )
    if export_format == "xlsx":
        return await export_service.export_user_messages_xlsx(
            source_id=actual_source_id,
            user_id=user_id,
            session_id=session_id,
            start_date=start,
            end_date=end,
            query_text=query,
            bbk_id=bbk_id,
        )
    return await export_service.export_user_messages_csv(
        source_id=actual_source_id,
        user_id=user_id,
        session_id=session_id,
        start_date=start,
        end_date=end,
        query_text=query,
        bbk_id=bbk_id,
    )


# ===== 平台来源 =====


@router.get("/sources", response_model=dict)
async def get_sources(
    request: Request,
    start_date: Optional[str] = Query(
        None,
        description="开始日期 (YYYY-MM-DD)",
    ),
    end_date: Optional[str] = Query(None, description="结束日期 (YYYY-MM-DD)"),
) -> dict:
    """获取平台来源列表.

    Args:
        start_date: 开始日期筛选
        end_date: 结束日期筛选

    Returns:
        source_id 字符串列表
    """
    service = TracingQueryService.get_instance()

    start = _parse_date(start_date, "start_date")
    end = _parse_date(end_date, "end_date", add_day=True)

    sources = await service.get_sources(start, end)
    return {"sources": sources}


# ===== 渠道分布 =====


@router.get("/channel-distribution", response_model=dict)
async def get_channel_distribution(
    request: Request,
    source_id: Optional[str] = Query(
        None,
        description="数据源标识，使用 'all' 查询所有平台",
    ),
    start_date: Optional[str] = Query(
        None,
        description="开始日期 (YYYY-MM-DD)",
    ),
    end_date: Optional[str] = Query(None, description="结束日期 (YYYY-MM-DD)"),
) -> dict:
    """获取渠道分布统计.

    Args:
        source_id: 数据源标识（可选，使用 'all' 获取所有平台的分布）
        start_date: 开始日期筛选
        end_date: 结束日期筛选

    Returns:
        渠道分布：platformUserDistribution, platformCallDistribution, totalPlatforms
    """
    actual_source_id = source_id or "all"
    service = TracingQueryService.get_instance()

    start = _parse_date(start_date, "start_date")
    end = _parse_date(end_date, "end_date", add_day=True)

    return await service.get_channel_distribution(actual_source_id, start, end)


# ===== 环比增长 =====


@router.get("/growth-stats", response_model=dict)
async def get_growth_stats(
    request: Request,
    source_id: Optional[str] = Query(
        None,
        description="数据源标识，使用 'all' 查询所有平台",
    ),
    start_date: str = Query(..., description="开始日期 (YYYY-MM-DD)"),
    end_date: str = Query(..., description="结束日期 (YYYY-MM-DD)"),
    time_range: str = Query(
        "day",
        description="时间范围: day, week, month, custom",
    ),
) -> dict:
    """获取环比增长统计.

    Args:
        source_id: 数据源标识（使用 'all' 或留空查询所有平台）
        start_date: 当前周期开始日期 (YYYY-MM-DD)
        end_date: 当前周期结束日期 (YYYY-MM-DD)
        time_range: 时间范围类型，用于计算上一周期

    Returns:
        环比增长：callsGrowth, tokensGrowth, sessionGrowth, userGrowth, platformGrowth, avgDurationGrowth
    """
    actual_source_id = source_id or "all"
    service = TracingQueryService.get_instance()

    start = _parse_date(start_date, "start_date")
    end = _parse_date(end_date, "end_date", add_day=True)
    if start is None or end is None:
        raise HTTPException(
            status_code=400,
            detail="start_date and end_date are required",
        )

    return await service.get_growth_stats(
        actual_source_id,
        start,
        end,
        time_range,
    )


# ===== 日趋势 =====


@router.get("/daily-trend", response_model=dict)
async def get_daily_trend(
    request: Request,
    source_id: Optional[str] = Query(
        None,
        description="数据源标识，使用 'all' 查询所有平台",
    ),
    start_date: Optional[str] = Query(
        None,
        description="开始日期 (YYYY-MM-DD)",
    ),
    end_date: Optional[str] = Query(None, description="结束日期 (YYYY-MM-DD)"),
) -> dict:
    """获取日趋势数据.

    Args:
        source_id: 数据源标识（使用 'all' 或留空查询所有平台）
        start_date: 开始日期筛选
        end_date: 结束日期筛选

    Returns:
        趋势数据列表：{ date, calls, tokens, users }
    """
    actual_source_id = source_id or "all"
    service = TracingQueryService.get_instance()

    start = _parse_date(start_date, "start_date")
    end = _parse_date(end_date, "end_date", add_day=True)

    trend = await service.get_daily_trend(actual_source_id, start, end)
    return {"trendData": trend}


# ===== 模型使用 =====


@router.get("/models", response_model=dict)
async def get_model_usage(
    request: Request,
    source_id: Optional[str] = Query(None, description="数据源标识"),
    start_date: Optional[str] = Query(
        None,
        description="开始日期 (YYYY-MM-DD)",
    ),
    end_date: Optional[str] = Query(None, description="结束日期 (YYYY-MM-DD)"),
) -> dict:
    """获取模型使用统计.

    Args:
        source_id: 数据源标识（可选，默认从请求头获取）
        start_date: 开始日期筛选
        end_date: 结束日期筛选

    Returns:
        模型使用统计
    """
    actual_source_id = _get_source_id(request, source_id)
    service = TracingQueryService.get_instance()

    start = _parse_date(start_date, "start_date")
    end = _parse_date(end_date, "end_date", add_day=True)

    stats = await service.get_overview_stats(actual_source_id, start, end)
    return {"models": [m.model_dump() for m in stats.model_distribution]}


# ===== 工具使用 =====


@router.get("/tools", response_model=dict)
async def get_tool_usage(
    request: Request,
    source_id: Optional[str] = Query(None, description="数据源标识"),
    start_date: Optional[str] = Query(
        None,
        description="开始日期 (YYYY-MM-DD)",
    ),
    end_date: Optional[str] = Query(None, description="结束日期 (YYYY-MM-DD)"),
) -> dict:
    """获取工具使用统计.

    Args:
        source_id: 数据源标识（可选，默认从请求头获取）
        start_date: 开始日期筛选
        end_date: 结束日期筛选

    Returns:
        工具使用统计
    """
    actual_source_id = _get_source_id(request, source_id)
    service = TracingQueryService.get_instance()

    start = _parse_date(start_date, "start_date")
    end = _parse_date(end_date, "end_date", add_day=True)

    stats = await service.get_overview_stats(actual_source_id, start, end)
    return {"tools": [t.model_dump() for t in stats.top_tools]}


# ===== 技能使用 =====


@router.get("/skills", response_model=dict)
async def get_skill_usage(
    request: Request,
    source_id: Optional[str] = Query(
        None,
        description="数据源标识，使用 'all' 查询所有平台",
    ),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=100, description="每页数量"),
    start_date: Optional[str] = Query(
        None,
        description="开始日期 (YYYY-MM-DD)",
    ),
    end_date: Optional[str] = Query(None, description="结束日期 (YYYY-MM-DD)"),
) -> dict:
    """获取技能调用排行榜（分页）.

    Args:
        source_id: 数据源标识（使用 'all' 或留空查询所有平台）
        page: 页码
        page_size: 每页数量
        start_date: 开始日期筛选
        end_date: 结束日期筛选

    Returns:
        分页的技能调用排行榜
    """
    actual_source_id = source_id or "all"
    service = TracingQueryService.get_instance()

    start = _parse_date(start_date, "start_date")
    end = _parse_date(end_date, "end_date", add_day=True)

    skills, total = await service.get_skills_paginated(
        actual_source_id,
        page,
        page_size,
        start,
        end,
    )
    return {
        "items": [s.model_dump() for s in skills],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/skills/{skill_name}/traces", response_model=dict)
async def get_skill_traces(
    skill_name: str,
    request: Request,
    source_id: Optional[str] = Query(
        None,
        description="数据源标识，使用 'all' 查询所有平台",
    ),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    start_date: Optional[str] = Query(
        None,
        description="开始日期 (YYYY-MM-DD)",
    ),
    end_date: Optional[str] = Query(None, description="结束日期 (YYYY-MM-DD)"),
) -> dict:
    """获取指定技能调用的对话列表（分页）.

    Args:
        skill_name: 技能名称
        source_id: 数据源标识（使用 'all' 或留空查询所有平台）
        page: 页码
        page_size: 每页数量
        start_date: 开始日期筛选
        end_date: 结束日期筛选

    Returns:
        分页的对话列表
    """
    actual_source_id = source_id or "all"
    service = TracingQueryService.get_instance()

    start = _parse_date(start_date, "start_date")
    end = _parse_date(end_date, "end_date", add_day=True)

    traces, total = await service.get_skill_traces(
        skill_name,
        actual_source_id,
        page,
        page_size,
        start,
        end,
    )
    return {
        "items": [t.model_dump() for t in traces],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


# ===== MCP 使用 =====


@router.get("/mcp", response_model=dict)
async def get_mcp_usage(
    request: Request,
    source_id: Optional[str] = Query(
        None,
        description="数据源标识，使用 'all' 查询所有平台",
    ),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=100, description="每页数量"),
    start_date: Optional[str] = Query(
        None,
        description="开始日期 (YYYY-MM-DD)",
    ),
    end_date: Optional[str] = Query(None, description="结束日期 (YYYY-MM-DD)"),
) -> dict:
    """获取 MCP 服务调用排行榜（分页）.

    Args:
        source_id: 数据源标识（使用 'all' 或留空查询所有平台）
        page: 页码
        page_size: 每页数量
        start_date: 开始日期筛选
        end_date: 结束日期筛选

    Returns:
        分页的 MCP 服务调用排行榜
    """
    actual_source_id = source_id or "all"
    service = TracingQueryService.get_instance()

    start = _parse_date(start_date, "start_date")
    end = _parse_date(end_date, "end_date", add_day=True)

    servers, total = await service.get_mcp_servers_paginated(
        actual_source_id,
        page,
        page_size,
        start,
        end,
    )
    return {
        "items": [s.model_dump() for s in servers],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


# ===== Model Output 写入 =====


@router.post("/model-output")
async def index_model_output(
    request: Request,
    body: ModelOutputRequest,
):
    """写入 model_output 到 ES.

    由 SWE 服务调用，将 model_output 写入 Elasticsearch。

    Args:
        body: 包含 trace_id 和 model_output

    Returns:
        写入结果
    """
    es_client = get_es_client()
    if es_client is None or not es_client.is_connected:
        # ES 未配置，静默跳过（与原 SWE 行为一致）
        logger.info("ES not configured, skipping model_output write")
        return {"status": "skipped", "reason": "ES not configured"}

    try:
        success = await es_client.index_message(
            body.trace_id,
            body.model_output,
        )
        if success:
            return {"status": "success"}
        else:
            return {"status": "failed"}
    except Exception as e:
        logger.warning("Failed to write model_output: %s", e)
        return {"status": "failed", "error": str(e)}
