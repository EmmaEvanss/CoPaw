# -*- coding: utf-8 -*-
"""Cron query API router for frontend.

Provides endpoints for frontend to query job definitions and execution history.
"""

import logging
from datetime import datetime
from io import BytesIO
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from ..models.cron import (
    CronJobModel,
    CronJobQueryParams,
    ExecutionModel,
    ExecutionQueryParams,
    PaginatedResponse,
    ExecutionDetailResponse,
)
from ..services.cron import QueryService, get_query_service
from ..services.cron.export_service import ExportService, get_export_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/monitor/cron", tags=["cron"])


@router.get("/jobs", response_model=PaginatedResponse[CronJobModel])
async def list_jobs(
    tenant_id: str | None = Query(default=None, description="租户ID筛选"),
    bbk_id: str | None = Query(default=None, description="分行号筛选"),
    source_id: str | None = Query(default=None, description="来源标识筛选"),
    creator_user_id: str | None = Query(
        default=None, description="创建者ID筛选"
    ),
    status: str | None = Query(default=None, description="状态筛选"),
    enabled: bool | None = Query(default=None, description="是否启用筛选"),
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=10, ge=1, le=100, description="每页数量"),
    service: QueryService = Depends(get_query_service),
) -> PaginatedResponse[CronJobModel]:
    """List cron jobs with pagination and filters.

    Args:
        tenant_id: Tenant ID filter
        bbk_id: BBK ID filter (分行号)
        source_id: Source ID filter (来源标识)
        creator_user_id: Creator user ID filter
        status: Status filter
        enabled: Enabled filter
        page: Page number
        page_size: Page size
        service: Query service

    Returns:
        Paginated job list
    """
    params = CronJobQueryParams(
        tenant_id=tenant_id,
        bbk_id=bbk_id,
        source_id=source_id,
        creator_user_id=creator_user_id,
        status=status,
        enabled=enabled,
        page=page,
        page_size=page_size,
    )
    return await service.list_jobs(params)


@router.get("/jobs/{job_id}", response_model=CronJobModel)
async def get_job(
    job_id: str,
    service: QueryService = Depends(get_query_service),
) -> CronJobModel:
    """Get a single job by ID.

    Args:
        job_id: Job ID
        service: Query service

    Returns:
        Job details

    Raises:
        HTTPException: If job not found
    """
    job = await service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/executions", response_model=PaginatedResponse[ExecutionModel])
async def list_executions(
    job_id: str | None = Query(default=None, description="任务ID筛选"),
    tenant_id: str | None = Query(default=None, description="租户ID筛选"),
    status: str | None = Query(default=None, description="执行状态筛选"),
    start_time: datetime | None = Query(
        default=None, description="开始时间范围"
    ),
    end_time: datetime | None = Query(
        default=None, description="结束时间范围"
    ),
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=10, ge=1, le=100, description="每页数量"),
    service: QueryService = Depends(get_query_service),
) -> PaginatedResponse[ExecutionModel]:
    """List execution history with pagination and filters.

    Args:
        job_id: Job ID filter
        tenant_id: Tenant ID filter
        status: Status filter
        start_time: Start time filter
        end_time: End time filter
        page: Page number
        page_size: Page size
        service: Query service

    Returns:
        Paginated execution list
    """
    params = ExecutionQueryParams(
        job_id=job_id,
        tenant_id=tenant_id,
        status=status,
        start_time=start_time,
        end_time=end_time,
        page=page,
        page_size=page_size,
    )
    return await service.list_executions(params)


@router.get(
    "/executions/{execution_id}",
    response_model=ExecutionDetailResponse,
)
async def get_execution(
    execution_id: int,
    service: QueryService = Depends(get_query_service),
) -> ExecutionDetailResponse:
    """Get a single execution by ID.

    Args:
        execution_id: Execution ID
        service: Query service

    Returns:
        Execution details

    Raises:
        HTTPException: If execution not found
    """
    execution = await service.get_execution(execution_id)
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    return ExecutionDetailResponse.model_validate(execution)


@router.get("/export")
async def export_data(
    job_id: str | None = Query(default=None, description="任务ID筛选"),
    tenant_id: str | None = Query(default=None, description="租户ID筛选"),
    bbk_id: str | None = Query(default=None, description="分行号筛选"),
    source_id: str | None = Query(default=None, description="来源标识筛选"),
    enabled: bool | None = Query(default=None, description="是否启用筛选"),
    status: str | None = Query(default=None, description="状态筛选"),
    start_time: datetime | None = Query(
        default=None, description="开始时间范围"
    ),
    end_time: datetime | None = Query(
        default=None, description="结束时间范围"
    ),
    export_type: str = Query(
        default="executions",
        description="导出类型: jobs/executions",
    ),
    query_service: QueryService = Depends(get_query_service),
    export_service: ExportService = Depends(get_export_service),
) -> StreamingResponse:
    """Export cron data to Excel.

    Args:
        job_id: Job ID filter (for executions)
        tenant_id: Tenant ID filter
        bbk_id: BBK ID filter (分行号)
        source_id: Source ID filter (来源标识)
        enabled: Enabled filter (是否启用)
        status: Status filter
        start_time: Start time filter (for executions)
        end_time: End time filter (for executions)
        export_type: Export type (jobs or executions)
        query_service: Query service
        export_service: Export service

    Returns:
        Excel file download
    """
    try:
        if export_type == "jobs":
            jobs = await query_service.get_jobs_for_export(
                tenant_id=tenant_id,
                bbk_id=bbk_id,
                source_id=source_id,
                enabled=enabled,
                status=status,
            )
            excel_bytes = export_service.export_jobs(jobs)
            filename = "定时任务.xlsx"
        else:
            executions = await query_service.get_executions_for_export(
                job_id=job_id,
                tenant_id=tenant_id,
                status=status,
                start_time=start_time,
                end_time=end_time,
            )
            excel_bytes = export_service.export_executions(executions)
            filename = "定时任务执行情况.xlsx"

        # RFC 5987: 使用filename*参数支持中文文件名
        encoded_filename = quote(filename)
        return StreamingResponse(
            BytesIO(excel_bytes),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}",
            },
        )
    except Exception as e:
        logger.error("Failed to export data: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
