# -*- coding: utf-8 -*-
"""Monitor sync client for dual-write to Monitor service.

This module provides an async HTTP client that syncs cron job definitions
and execution records to the Monitor service database.

The sync is asynchronous and non-blocking - failures are logged but do not
affect the main SWE service operation.
"""

import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, Optional

import httpx

from .models import CronJobSpec

logger = logging.getLogger(__name__)

# Default Monitor API URL
DEFAULT_MONITOR_API_URL = "http://localhost:9090/api"

# Environment variable for Monitor API URL
MONITOR_API_URL_ENV = "SWE_MONITOR_API_URL"


def get_monitor_api_url() -> str:
    """Get Monitor API URL from environment or default.

    Returns:
        Monitor API base URL
    """
    url = os.environ.get(MONITOR_API_URL_ENV)
    if url:
        return url.rstrip("/")
    return DEFAULT_MONITOR_API_URL


class MonitorSyncClient:
    """HTTP client for syncing cron data to Monitor service.

    All sync operations are asynchronous and non-blocking.
    Failures are logged but do not raise exceptions.
    """

    def __init__(self, base_url: Optional[str] = None) -> None:
        """Initialize sync client.

        Args:
            base_url: Monitor API base URL. If None, uses get_monitor_api_url().
        """
        self._base_url = base_url or get_monitor_api_url()
        self._client: Optional[httpx.AsyncClient] = None
        self._enabled = bool(self._base_url)

        if not self._enabled:
            logger.info("Monitor sync disabled: no API URL configured")

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client.

        Returns:
            httpx.AsyncClient instance
        """
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=5.0,  # Short timeout to avoid blocking
            )
        return self._client

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def _sync_fire_and_forget(self, coro: Any) -> None:
        """Fire and forget - run coroutine in background.

        Creates a task that runs the coroutine and logs any errors.
        Does not block the caller.

        Args:
            coro: Coroutine to run
        """
        if not self._enabled:
            return

        async def _run_with_logging() -> None:
            try:
                await coro
            except asyncio.CancelledError:
                logger.debug("Monitor sync cancelled")
            except Exception as e:
                logger.warning("Monitor sync failed: %s", repr(e))

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(_run_with_logging())
        except RuntimeError:
            # No event loop running - this shouldn't happen in normal async operation
            logger.warning("Cannot schedule monitor sync: no event loop")

    async def sync_job(self, job: CronJobSpec) -> None:
        """Sync a cron job definition to Monitor.

        This is called after creating or updating a job in SWE.

        Args:
            job: CronJobSpec to sync
        """
        if not self._enabled:
            return

        sync_data = self._build_job_sync_data(job)

        # Fire and forget
        self._sync_fire_and_forget(self._do_sync_job(sync_data))

    def _build_job_sync_data(self, job: CronJobSpec) -> Dict[str, Any]:
        """Build sync data dict from CronJobSpec.

        Args:
            job: CronJobSpec to convert

        Returns:
            Dict with sync request fields
        """
        spec_dict = job.model_dump(mode="json")

        schedule = spec_dict.get("schedule", {})
        dispatch = spec_dict.get("dispatch", {})
        target = dispatch.get("target", {})
        runtime = spec_dict.get("runtime", {})
        meta = spec_dict.get("meta", {})
        request = spec_dict.get("request", {})

        return {
            "id": spec_dict.get("id") or "",
            "name": spec_dict.get("name") or "",
            "tenant_id": spec_dict.get("tenant_id") or "",
            "bbk_id": spec_dict.get("bbk_id") or "",
            "source_id": spec_dict.get("source_id") or "",
            "enabled": spec_dict.get("enabled", True),
            "task_type": spec_dict.get("task_type") or "agent",
            "cron_expr": schedule.get("cron") or "",
            "timezone": schedule.get("timezone") or "UTC",
            "channel": dispatch.get("channel") or "",
            "target_user_id": target.get("user_id") or "",
            "target_session_id": target.get("session_id") or "",
            "timeout_seconds": runtime.get("timeout_seconds", 7200),
            "max_concurrency": runtime.get("max_concurrency", 1),
            "misfire_grace_seconds": runtime.get("misfire_grace_seconds", 300),
            "text_content": spec_dict.get("text") or "",
            "request_input": (
                json.dumps(request, ensure_ascii=False) if request else ""
            ),
            "creator_user_id": meta.get("creator_user_id") or "",
            "task_chat_id": meta.get("task_chat_id") or "",
            "task_session_id": meta.get("task_session_id") or "",
            "meta": json.dumps(meta, ensure_ascii=False) if meta else "",
            "status": "paused" if meta.get("pause_reason") else "active",
            "pause_reason": meta.get("pause_reason") or "",
        }

    async def _do_sync_job(self, sync_data: Dict[str, Any]) -> None:
        """Actually perform the sync job HTTP call.

        Args:
            sync_data: Sync request body
        """
        client = await self._get_client()
        logger.debug("Syncing job to monitor: data=%s", sync_data)
        response = await client.post("/monitor/sync/job", json=sync_data)

        if response.status_code == 200:
            logger.debug("Synced job to monitor: id=%s", sync_data.get("id"))
        else:
            logger.warning(
                "Failed to sync job to monitor: id=%s status=%d response=%s",
                sync_data.get("id"),
                response.status_code,
                response.text,
            )

    async def delete_job(self, job_id: str) -> None:
        """Sync job deletion to Monitor.

        This is called after deleting a job in SWE.

        Args:
            job_id: Job ID to delete
        """
        if not self._enabled:
            return

        # Fire and forget
        self._sync_fire_and_forget(self._do_delete_job(job_id))

    async def _do_delete_job(self, job_id: str) -> None:
        """Actually perform the delete job HTTP call.

        Args:
            job_id: Job ID to delete
        """
        client = await self._get_client()
        response = await client.delete(f"/monitor/sync/job/{job_id}")

        if response.status_code == 200:
            logger.debug("Deleted job from monitor: id=%s", job_id)
        else:
            logger.warning(
                "Failed to delete job from monitor: id=%s status=%d",
                job_id,
                response.status_code,
            )

    async def record_execution(
        self,
        job: CronJobSpec,
        status: str,
        actual_time: datetime,
        end_time: Optional[datetime] = None,
        duration_ms: int = 0,
        error_message: str = "",
        is_manual: bool = False,
        trace_id: str = "",
        session_id: str = "",
        output_preview: str = "",
        input_snapshot: Optional[Dict[str, Any]] = None,
        instance_id: str = "",
        executor_leader: str = "",
        scheduled_time: Optional[datetime] = None,
    ) -> None:
        """Record an execution to Monitor.

        This is called after executing a job in SWE.

        Args:
            job: CronJobSpec that was executed
            status: Execution status (success/error/cancelled/timeout/skipped)
            actual_time: Actual start time
            end_time: End time (optional)
            duration_ms: Duration in milliseconds
            error_message: Error message if failed
            is_manual: Whether this was manually triggered
            trace_id: Trace ID for tracing
            session_id: Session ID
            output_preview: Output preview (first 100 chars)
            input_snapshot: Input snapshot dict
            instance_id: Instance ID
            executor_leader: Executor leader ID
            scheduled_time: Scheduled execution time
        """
        if not self._enabled:
            return

        exec_data = {
            "job_id": job.id,
            "job_name": job.name,
            "tenant_id": job.tenant_id or "",
            "scheduled_time": (
                scheduled_time.isoformat() if scheduled_time else None
            ),
            "actual_time": actual_time.isoformat(),
            "end_time": end_time.isoformat() if end_time else None,
            "duration_ms": duration_ms,
            "status": status,
            "error_message": error_message,
            "instance_id": instance_id,
            "executor_leader": executor_leader,
            "is_manual": is_manual,
            "trace_id": trace_id,
            "session_id": session_id,
            "input_snapshot": (
                json.dumps(input_snapshot, ensure_ascii=False)
                if input_snapshot
                else ""
            ),
            "output_preview": output_preview[:100] if output_preview else "",
            "meta": "",
        }

        # Fire and forget
        self._sync_fire_and_forget(self._do_record_execution(exec_data))

    async def _do_record_execution(self, exec_data: Dict[str, Any]) -> None:
        """Actually perform the record execution HTTP call.

        Args:
            exec_data: Execution sync request body
        """
        client = await self._get_client()
        response = await client.post("/monitor/sync/execution", json=exec_data)

        if response.status_code == 200:
            logger.debug(
                "Recorded execution to monitor: job_id=%s status=%s",
                exec_data.get("job_id"),
                exec_data.get("status"),
            )
        else:
            logger.warning(
                "Failed to record execution to monitor: job_id=%s status=%d",
                exec_data.get("job_id"),
                response.status_code,
            )


# Global sync client instance
_sync_client: Optional[MonitorSyncClient] = None


def get_monitor_sync_client() -> MonitorSyncClient:
    """Get the global MonitorSyncClient instance.

    Returns:
        MonitorSyncClient instance
    """
    global _sync_client
    if _sync_client is None:
        _sync_client = MonitorSyncClient()
    return _sync_client
