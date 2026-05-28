# -*- coding: utf-8 -*-
"""Sync API router for cron job data.

Provides endpoints for SWE to sync job definitions and execution records.
"""

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException

from ..models.cron import (
    CronJobSyncRequest,
    ExecutionSyncRequest,
    SyncJobResponse,
    DeleteJobResponse,
    RecordExecutionResponse,
)
from ..services.cron import SyncService, get_sync_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/monitor/sync", tags=["sync"])


@router.post("/job", response_model=SyncJobResponse)
async def sync_job(
    request: CronJobSyncRequest,
    service: SyncService = Depends(get_sync_service),
) -> SyncJobResponse:
    """Sync a cron job definition from SWE.

    This endpoint is called by SWE after creating or updating a job.
    It upserts the job into Monitor database.

    Args:
        request: Job sync request
        service: Sync service

    Returns:
        Sync confirmation
    """
    try:
        success = await service.sync_job(request)
        if not success:
            raise HTTPException(status_code=500, detail="Sync failed")
        return SyncJobResponse(synced=True)
    except Exception as e:
        logger.error("Failed to sync job %s: %s", request.id, e)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/job/{job_id}", response_model=DeleteJobResponse)
async def delete_job(
    job_id: str,
    service: SyncService = Depends(get_sync_service),
) -> DeleteJobResponse:
    """Soft delete a cron job.

    This endpoint is called by SWE after deleting a job.
    It marks the job as deleted in Monitor database.

    Args:
        job_id: Job ID to delete
        service: Sync service

    Returns:
        Delete confirmation
    """
    try:
        success = await service.delete_job(job_id)
        if not success:
            raise HTTPException(status_code=404, detail="Job not found")
        return DeleteJobResponse(deleted=True)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to delete job %s: %s", job_id, e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/execution", response_model=RecordExecutionResponse)
async def record_execution(
    request: ExecutionSyncRequest,
    service: SyncService = Depends(get_sync_service),
) -> RecordExecutionResponse:
    """Record an execution history entry.

    接口收到请求后立即返回 success，然后在后台异步处理数据库写入。
    这种设计确保 SWE 服务不会因 Monitor 数据库写入延迟而阻塞。

    Args:
        request: Execution sync request
        service: Sync service

    Returns:
        立即返回成功响应，execution_id 为 None（实际 ID 在后台写入后生成）
    """

    # 创建后台任务异步处理数据库写入
    async def _background_record() -> None:
        try:
            execution_id = await service.record_execution(request)
            if execution_id:
                logger.info(
                    "Background recorded execution: job_id=%s execution_id=%s status=%s",
                    request.job_id,
                    execution_id,
                    request.status,
                )
            else:
                logger.warning(
                    "Background record execution returned None: job_id=%s",
                    request.job_id,
                )
        except Exception as e:
            logger.error(
                "Background record execution failed for job %s: %s",
                request.job_id,
                e,
                exc_info=True,
            )

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_background_record())
    except RuntimeError:
        # 如果没有运行中的事件循环，直接同步执行（罕见情况）
        logger.warning(
            "No running loop, executing record synchronously: job_id=%s",
            request.job_id,
        )
        try:
            await service.record_execution(request)
        except Exception as e:
            logger.error(
                "Fallback sync record execution failed for job %s: %s",
                request.job_id,
                e,
                exc_info=True,
            )

    # 立即返回成功响应
    return RecordExecutionResponse(recorded=True, execution_id=None)
