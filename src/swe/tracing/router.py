# -*- coding: utf-8 -*-
"""Tracing API router for Business Overview dashboard."""

import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Query

from .models import (
    DailyStats,
    MCPServerUsage,
    OverviewStats,
    SkillUsage,
    TaskStatusBreakdown,
    TraceListItem,
    UserListItem,
)
from .store import TraceStore, EXCLUDED_SOURCE_IDS

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/monitor/tracing", tags=["tracing"])

# Global store instance
_store: Optional[TraceStore] = None


def init_tracing_router(store: TraceStore):
    """Initialize tracing router with store instance.

    Args:
        store: TraceStore instance for database operations.
    """
    global _store
    _store = store
    logger.info("Tracing router initialized")


def get_store() -> TraceStore:
    """Get trace store instance."""
    global _store
    if _store is None:
        raise RuntimeError(
            "Trace store not available. Tracing must be enabled with database.",
        )
    return _store


# ==================== Overview ====================


@router.get("/overview", response_model=OverviewStats)
async def get_overview(
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    source_id: Optional[str] = Query(None, description="Source ID filter"),
):
    """Get overview statistics for dashboard."""
    store = get_store()

    # Parse dates
    if start_date:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    else:
        start_dt = datetime.now() - timedelta(days=30)

    if end_date:
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        # Include the full end date
        end_dt = end_dt.replace(hour=23, minute=59, second=59)
    else:
        end_dt = datetime.now()

    # Default source_id to "all" if not provided
    effective_source_id = source_id or "all"

    return await store.get_overview_stats(
        source_id=effective_source_id,
        start_date=start_dt,
        end_date=end_dt,
    )


# ==================== Sources ====================


@router.get("/sources")
async def get_sources(
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
):
    """Get all available source IDs."""
    store = get_store()

    if start_date:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    else:
        start_dt = datetime.now() - timedelta(days=30)

    if end_date:
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    else:
        end_dt = datetime.now()

    sources = await store.get_sources(start_dt, end_dt)
    return {"sources": sources}


# ==================== Users ====================


@router.get("/users")
async def get_users(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Page size"),
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    source_id: Optional[str] = Query(None, description="Source ID filter"),
    sort_by: Optional[str] = Query(None, description="Sort by field"),
    filter_user_type: Optional[str] = Query(None, description="Filter user type"),
    bbk_id: Optional[str] = Query(None, description="Filter by BBK ID"),
):
    """Get users with usage statistics."""
    store = get_store()

    # Parse dates
    if start_date:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    else:
        start_dt = datetime.now() - timedelta(days=30)

    if end_date:
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    else:
        end_dt = datetime.now()

    effective_source_id = source_id or "all"

    items, total = await store.get_users(
        page=page,
        page_size=page_size,
        user_id=user_id,
        start_date=start_dt,
        end_date=end_dt,
        source_id=effective_source_id,
        sort_by=sort_by,
        filter_user_type=filter_user_type,
        bbk_id=bbk_id,
    )

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


# ==================== Skills ====================


@router.get("/skills")
async def get_skills(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Page size"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    source_id: Optional[str] = Query(None, description="Source ID filter"),
):
    """Get skill usage statistics."""
    store = get_store()

    if start_date:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    else:
        start_dt = datetime.now() - timedelta(days=30)

    if end_date:
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    else:
        end_dt = datetime.now()

    effective_source_id = source_id or "all"

    items, total = await store.get_skills_usage(
        page=page,
        page_size=page_size,
        start_date=start_dt,
        end_date=end_dt,
        source_id=effective_source_id,
    )

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


# ==================== MCP Servers ====================


@router.get("/mcp")
async def get_mcp_servers(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Page size"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    source_id: Optional[str] = Query(None, description="Source ID filter"),
):
    """Get MCP server usage statistics."""
    store = get_store()

    if start_date:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    else:
        start_dt = datetime.now() - timedelta(days=30)

    if end_date:
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    else:
        end_dt = datetime.now()

    effective_source_id = source_id or "all"

    items, total = await store.get_mcp_servers_usage(
        page=page,
        page_size=page_size,
        start_date=start_dt,
        end_date=end_dt,
        source_id=effective_source_id,
    )

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


# ==================== Growth Stats ====================


@router.get("/growth-stats")
async def get_growth_stats(
    start_date: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: str = Query(..., description="End date (YYYY-MM-DD)"),
    time_range: str = Query("day", description="Time range type"),
    source_id: Optional[str] = Query(None, description="Source ID filter"),
):
    """Get growth statistics compared to previous period."""
    store = get_store()

    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")

    effective_source_id = source_id or "all"

    return await store.get_growth_stats(
        start_date=start_dt,
        end_date=end_dt,
        time_range=time_range,
        source_id=effective_source_id,
    )


# ==================== Daily Trend ====================


@router.get("/daily-trend")
async def get_daily_trend(
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    source_id: Optional[str] = Query(None, description="Source ID filter"),
):
    """Get daily trend data for charts."""
    store = get_store()

    if start_date:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    else:
        start_dt = datetime.now() - timedelta(days=7)

    if end_date:
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    else:
        end_dt = datetime.now()

    effective_source_id = source_id or "all"

    trend_data = await store.get_daily_trend(
        start_date=start_dt,
        end_date=end_dt,
        source_id=effective_source_id,
    )

    return {"trendData": trend_data}
