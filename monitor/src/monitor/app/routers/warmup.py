# -*- coding: utf-8 -*-
"""SWE 定时任务预热接口."""

from fastapi import APIRouter

from ..services.cron.warmup_service import (
    WarmupStatus,
    get_swe_cron_warmup_service,
)

router = APIRouter(prefix="/warmup", tags=["warmup"])


@router.post("/swe-crons", response_model=WarmupStatus)
async def start_swe_cron_warmup() -> WarmupStatus:
    """手动触发 SWE 定时任务恢复预热."""
    # 自动预热失败或 SWE 稍后恢复时，运维可通过该接口补跑，不需要重启服务。
    service = get_swe_cron_warmup_service()
    return await service.start_background()


@router.get("/swe-crons/status", response_model=WarmupStatus)
async def get_swe_cron_warmup_status() -> WarmupStatus:
    """查询最近一次 SWE 定时任务恢复预热状态."""
    # 返回内存中的最近一次结果，用于确认哪些租户已经成功触发加载。
    service = get_swe_cron_warmup_service()
    return service.get_status()
