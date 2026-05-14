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

    def schedule_swe_cron_warmup(
        self,
        start_delay_seconds: float = 5.0,
    ) -> None:
        """Schedule Monitor-side SWE cron warmup in the background."""
        if not self._enabled:
            return

        async def _run_with_delay() -> None:
            if start_delay_seconds > 0:
                # SWE 需要先完成启动并开始接收 /cron/jobs 回调。
                await asyncio.sleep(start_delay_seconds)
            await self.trigger_swe_cron_warmup()

        self._sync_fire_and_forget(_run_with_delay())

    async def trigger_swe_cron_warmup(self) -> None:
        """Trigger Monitor to warm up SWE cron schedules."""
        if not self._enabled:
            return

        client = await self._get_client()
        response = await client.post("/warmup/swe-crons")
        if 200 <= response.status_code < 300:
            logger.info("Triggered Monitor SWE cron warmup")
        else:
            logger.warning(
                "Failed to trigger Monitor SWE cron warmup: status=%d",
                response.status_code,
            )

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

    def _get_or_empty(self, data: Dict[str, Any], key: str) -> str:
        """Get string value from dict or return empty string.

        Args:
            data: Source dictionary
            key: Key to get

        Returns:
            Value or empty string
        """
        return data.get(key) or ""

    def _get_or_default(
        self,
        data: Dict[str, Any],
        key: str,
        default: Any,
    ) -> Any:
        """Get value from dict or return default.

        Args:
            data: Source dictionary
            key: Key to get
            default: Default value if key not found

        Returns:
            Value or default
        """
        return data.get(key, default)

    def _extract_schedule_fields(
        self,
        spec_dict: Dict[str, Any],
    ) -> Dict[str, str]:
        """Extract schedule-related fields.

        Args:
            spec_dict: Full spec dictionary

        Returns:
            Dict with cron_expr and timezone
        """
        schedule = spec_dict.get("schedule", {})
        return {
            "cron_expr": schedule.get("cron") or "",
            "timezone": schedule.get("timezone") or "UTC",
        }

    def _extract_dispatch_fields(
        self,
        spec_dict: Dict[str, Any],
    ) -> Dict[str, str]:
        """Extract dispatch and target-related fields.

        Args:
            spec_dict: Full spec dictionary

        Returns:
            Dict with channel, target_user_id, target_session_id
        """
        dispatch = spec_dict.get("dispatch", {})
        target = dispatch.get("target", {})
        return {
            "channel": dispatch.get("channel") or "",
            "target_user_id": target.get("user_id") or "",
            "target_session_id": target.get("session_id") or "",
        }

    def _extract_runtime_fields(
        self,
        spec_dict: Dict[str, Any],
    ) -> Dict[str, int]:
        """Extract runtime-related fields.

        Args:
            spec_dict: Full spec dictionary

        Returns:
            Dict with timeout_seconds, max_concurrency, misfire_grace_seconds
        """
        runtime = spec_dict.get("runtime", {})
        return {
            "timeout_seconds": runtime.get("timeout_seconds", 7200),
            "max_concurrency": runtime.get("max_concurrency", 1),
            "misfire_grace_seconds": runtime.get("misfire_grace_seconds", 300),
        }

    def _extract_meta_fields(
        self,
        spec_dict: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Extract meta-related fields.

        Args:
            spec_dict: Full spec dictionary

        Returns:
            Dict with meta fields and computed status
        """
        meta = spec_dict.get("meta", {})
        pause_reason = meta.get("pause_reason") or ""
        meta_json = json.dumps(meta, ensure_ascii=False) if meta else ""
        return {
            "creator_user_id": meta.get("creator_user_id") or "",
            "task_chat_id": meta.get("task_chat_id") or "",
            "task_session_id": meta.get("task_session_id") or "",
            "meta": meta_json,
            "status": "paused" if pause_reason else "active",
            "pause_reason": pause_reason,
        }

    def _build_request_input(self, spec_dict: Dict[str, Any]) -> str:
        """Build request_input field.

        Args:
            spec_dict: Full spec dictionary

        Returns:
            JSON string or empty string
        """
        request = spec_dict.get("request", {})
        return json.dumps(request, ensure_ascii=False) if request else ""

    def _build_job_sync_data(self, job: CronJobSpec) -> Dict[str, Any]:
        """Build sync data dict from CronJobSpec.

        Args:
            job: CronJobSpec to convert

        Returns:
            Dict with sync request fields
        """
        spec_dict = job.model_dump(mode="json")

        base_fields = {
            "id": self._get_or_empty(spec_dict, "id"),
            "name": self._get_or_empty(spec_dict, "name"),
            "tenant_id": self._get_or_empty(spec_dict, "tenant_id"),
            "tenant_name": self._get_or_empty(spec_dict, "tenant_name"),
            "bbk_id": self._get_or_empty(spec_dict, "bbk_id"),
            "source_id": self._get_or_empty(spec_dict, "source_id"),
            "enabled": self._get_or_default(spec_dict, "enabled", True),
            "task_type": self._get_or_default(spec_dict, "task_type", "agent"),
            "text_content": self._get_or_empty(spec_dict, "text"),
            "request_input": self._build_request_input(spec_dict),
        }

        return {
            **base_fields,
            **self._extract_schedule_fields(spec_dict),
            **self._extract_dispatch_fields(spec_dict),
            **self._extract_runtime_fields(spec_dict),
            **self._extract_meta_fields(spec_dict),
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

    def _format_optional_time(self, time: Optional[datetime]) -> Optional[str]:
        """Format optional datetime to ISO string.

        Args:
            time: Optional datetime

        Returns:
            ISO format string or None
        """
        return time.isoformat() if time else None

    def _format_optional_json(self, data: Optional[Dict[str, Any]]) -> str:
        """Format optional dict to JSON string.

        Args:
            data: Optional dict

        Returns:
            JSON string or empty string
        """
        return json.dumps(data, ensure_ascii=False) if data else ""

    def _truncate_preview(self, text: str, max_len: int = 100) -> str:
        """Truncate text to max length.

        Args:
            text: Text to truncate
            max_len: Maximum length

        Returns:
            Truncated text or empty string
        """
        return text[:max_len] if text else ""

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

        exec_data = self._build_execution_sync_data(
            job=job,
            status=status,
            actual_time=actual_time,
            end_time=end_time,
            duration_ms=duration_ms,
            error_message=error_message,
            is_manual=is_manual,
            trace_id=trace_id,
            session_id=session_id,
            output_preview=output_preview,
            input_snapshot=input_snapshot,
            instance_id=instance_id,
            executor_leader=executor_leader,
            scheduled_time=scheduled_time,
        )

        # Fire and forget
        self._sync_fire_and_forget(self._do_record_execution(exec_data))

    def _build_execution_sync_data(
        self,
        job: CronJobSpec,
        status: str,
        actual_time: datetime,
        end_time: Optional[datetime],
        duration_ms: int,
        error_message: str,
        is_manual: bool,
        trace_id: str,
        session_id: str,
        output_preview: str,
        input_snapshot: Optional[Dict[str, Any]],
        instance_id: str,
        executor_leader: str,
        scheduled_time: Optional[datetime],
    ) -> Dict[str, Any]:
        """Build execution sync data dict.

        Args:
            job: CronJobSpec that was executed
            status: Execution status
            actual_time: Actual start time
            end_time: End time
            duration_ms: Duration in milliseconds
            error_message: Error message
            is_manual: Whether manually triggered
            trace_id: Trace ID
            session_id: Session ID
            output_preview: Output preview
            input_snapshot: Input snapshot dict
            instance_id: Instance ID
            executor_leader: Executor leader ID
            scheduled_time: Scheduled execution time

        Returns:
            Dict with execution sync fields
        """
        return {
            "job_id": job.id,
            "job_name": job.name,
            "tenant_id": job.tenant_id or "",
            "scheduled_time": self._format_optional_time(scheduled_time),
            "actual_time": actual_time.isoformat(),
            "end_time": self._format_optional_time(end_time),
            "duration_ms": duration_ms,
            "status": status,
            "error_message": error_message,
            "instance_id": instance_id,
            "executor_leader": executor_leader,
            "is_manual": is_manual,
            "trace_id": trace_id,
            "session_id": session_id,
            "input_snapshot": self._format_optional_json(input_snapshot),
            "output_preview": self._truncate_preview(output_preview),
            "meta": "",
        }

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
