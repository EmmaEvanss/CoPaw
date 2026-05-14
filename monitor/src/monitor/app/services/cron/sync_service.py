# -*- coding: utf-8 -*-
"""Sync service for cron job and execution data.

Provides methods to sync job definitions and execution records
from SWE to Monitor database.
"""

import logging
from datetime import datetime
from typing import Optional

from ...database import get_db_connection
from ...models.cron import CronJobSyncRequest, ExecutionSyncRequest

logger = logging.getLogger(__name__)


class SyncService:
    """Service for syncing cron data from SWE."""

    def __init__(self) -> None:
        """Initialize sync service."""
        pass

    async def sync_job(self, request: CronJobSyncRequest) -> bool:
        """Sync or update a cron job definition.

        This method upserts a job definition into the database.
        If the job already exists, it updates all fields.
        If the job was previously soft-deleted, it restores it.

        Args:
            request: Sync request from SWE

        Returns:
            True if sync succeeded
        """
        db = get_db_connection()

        # Check if job exists and was deleted
        existing = await db.fetch_one(
            "SELECT id, deleted_at FROM swe_cron_jobs WHERE id = %s",
            (request.id,),
        )

        now = datetime.utcnow()

        if existing:
            # Update existing job, clear deleted_at if it was deleted
            deleted_at_value = (
                None
                if existing.get("deleted_at")
                else existing.get("deleted_at")
            )

            await db.execute(
                """
                UPDATE swe_cron_jobs SET
                    name = %s,
                    tenant_id = %s,
                    tenant_name = %s,
                    bbk_id = %s,
                    source_id = %s,
                    enabled = %s,
                    task_type = %s,
                    cron_expr = %s,
                    timezone = %s,
                    channel = %s,
                    target_user_id = %s,
                    target_session_id = %s,
                    timeout_seconds = %s,
                    max_concurrency = %s,
                    misfire_grace_seconds = %s,
                    text_content = %s,
                    request_input = %s,
                    creator_user_id = %s,
                    task_chat_id = %s,
                    task_session_id = %s,
                    meta = %s,
                    status = %s,
                    pause_reason = %s,
                    updated_at = %s,
                    deleted_at = %s
                WHERE id = %s
                """,
                (
                    request.name,
                    request.tenant_id,
                    request.tenant_name,
                    request.bbk_id,
                    request.source_id,
                    request.enabled,
                    request.task_type,
                    request.cron_expr,
                    request.timezone,
                    request.channel,
                    request.target_user_id,
                    request.target_session_id,
                    request.timeout_seconds,
                    request.max_concurrency,
                    request.misfire_grace_seconds,
                    request.text_content,
                    request.request_input,
                    request.creator_user_id,
                    request.task_chat_id,
                    request.task_session_id,
                    request.meta,
                    request.status,
                    request.pause_reason,
                    now,
                    deleted_at_value,
                    request.id,
                ),
            )
            logger.info(
                "Updated cron job: id=%s name=%s",
                request.id,
                request.name,
            )
        else:
            # Insert new job
            await db.execute(
                """
                INSERT INTO swe_cron_jobs (
                    id, name, tenant_id, tenant_name, bbk_id, source_id, enabled, task_type,
                    cron_expr, timezone, channel, target_user_id, target_session_id,
                    timeout_seconds, max_concurrency, misfire_grace_seconds,
                    text_content, request_input,
                    creator_user_id, task_chat_id, task_session_id, meta,
                    status, pause_reason, created_at, updated_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                """,
                (
                    request.id,
                    request.name,
                    request.tenant_id,
                    request.tenant_name,
                    request.bbk_id,
                    request.source_id,
                    request.enabled,
                    request.task_type,
                    request.cron_expr,
                    request.timezone,
                    request.channel,
                    request.target_user_id,
                    request.target_session_id,
                    request.timeout_seconds,
                    request.max_concurrency,
                    request.misfire_grace_seconds,
                    request.text_content,
                    request.request_input,
                    request.creator_user_id,
                    request.task_chat_id,
                    request.task_session_id,
                    request.meta,
                    request.status,
                    request.pause_reason,
                    now,
                    now,
                ),
            )
            logger.info(
                "Inserted cron job: id=%s name=%s",
                request.id,
                request.name,
            )

        return True

    async def delete_job(self, job_id: str) -> bool:
        """Soft delete a cron job.

        Marks the job as deleted by setting deleted_at timestamp.
        The job remains in the database for historical reference.

        Args:
            job_id: Job ID to delete

        Returns:
            True if deletion succeeded, False if job not found
        """
        db = get_db_connection()

        # Check if job exists and is not already deleted
        existing = await db.fetch_one(
            "SELECT id, deleted_at FROM swe_cron_jobs WHERE id = %s",
            (job_id,),
        )

        if not existing:
            logger.warning("Job not found for deletion: id=%s", job_id)
            return False

        if existing.get("deleted_at"):
            logger.info("Job already deleted: id=%s", job_id)
            return True

        # Soft delete
        now = datetime.utcnow()
        await db.execute(
            """
            UPDATE swe_cron_jobs SET
                status = 'deleted',
                enabled = 0,
                deleted_at = %s,
                updated_at = %s
            WHERE id = %s
            """,
            (now, now, job_id),
        )

        logger.info("Soft deleted cron job: id=%s", job_id)
        return True

    async def record_execution(
        self,
        request: ExecutionSyncRequest,
    ) -> Optional[int]:
        """Record an execution history entry.

        Args:
            request: Execution sync request from SWE

        Returns:
            Execution record ID if succeeded, None if failed
        """
        db = get_db_connection()

        now = datetime.utcnow()

        await db.execute(
            """
            INSERT INTO swe_cron_executions (
                job_id, job_name, tenant_id,
                scheduled_time, actual_time, end_time, duration_ms,
                status, error_message,
                instance_id, executor_leader, is_manual,
                trace_id, session_id,
                input_snapshot, output_preview, meta,
                created_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            """,
            (
                request.job_id,
                request.job_name,
                request.tenant_id,
                request.scheduled_time,
                request.actual_time,
                request.end_time,
                request.duration_ms,
                request.status,
                request.error_message,
                request.instance_id,
                request.executor_leader,
                request.is_manual,
                request.trace_id,
                request.session_id,
                request.input_snapshot,
                request.output_preview,
                request.meta,
                now,
            ),
        )

        # Get the inserted ID
        result = await db.fetch_one("SELECT LAST_INSERT_ID() as id")
        execution_id = result.get("id") if result else None

        logger.info(
            "Recorded execution: job_id=%s execution_id=%s status=%s",
            request.job_id,
            execution_id,
            request.status,
        )

        return execution_id


# Global sync service instance
_sync_service: Optional[SyncService] = None


def get_sync_service() -> SyncService:
    """Get the sync service instance.

    Returns:
        SyncService instance
    """
    global _sync_service
    if _sync_service is None:
        _sync_service = SyncService()
    return _sync_service
