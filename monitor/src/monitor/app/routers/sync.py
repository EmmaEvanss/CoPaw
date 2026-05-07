# -*- coding: utf-8 -*-
"""Sync API router for cron job data.

Provides endpoints for SWE to sync job definitions and execution records.
"""
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

    This endpoint is called by SWE after executing a job.
    It creates a new execution record in Monitor database.

    Args:
        request: Execution sync request
        service: Sync service

    Returns:
        Record confirmation with execution ID
    """
    try:
        execution_id = await service.record_execution(request)
        if execution_id is None:
            raise HTTPException(
                status_code=500,
                detail="Failed to record execution",
            )
        return RecordExecutionResponse(
            recorded=True,
            execution_id=execution_id,
        )
    except Exception as e:
        logger.error(
            "Failed to record execution for job %s: %s",
            request.job_id,
            e,
        )
        raise HTTPException(status_code=500, detail=str(e))
