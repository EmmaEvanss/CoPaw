# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

import httpx

from .auth_state import resolve_auth_token_for_execution
from .models import CronJobSpec
from ..tenant_context import bind_tenant_context
from ..console_push_store import append as push_store_append
from ...config.llm_workload import LLM_WORKLOAD_CRON, bind_llm_workload
from ...tracing import has_trace_manager, get_trace_manager
from ...tracing.models import TraceStatus

logger = logging.getLogger(__name__)

CONSOLE_CHANNEL = "console"


async def _index_model_output_to_monitor(
    trace_id: str,
    model_output: str,
) -> None:
    """通过 Monitor API 写入 model_output 到 ES.

    Args:
        trace_id: 追踪 ID
        model_output: 模型输出文本
    """
    monitor_url = os.environ.get(
        "SWE_MONITOR_API_URL",
        "http://127.0.0.1:9090",
    )
    url = f"{monitor_url}/monitor/tracing/model-output"

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(
                url,
                json={
                    "trace_id": trace_id,
                    "model_output": model_output,
                },
            )
            if response.status_code == 200:
                result = response.json()
                if result.get("status") == "success":
                    logger.info(
                        "Model output indexed via Monitor API: trace_id=%s",
                        trace_id,
                    )
                else:
                    logger.info(
                        "Model output write skipped: trace_id=%s, reason=%s",
                        trace_id,
                        result.get("reason", "unknown"),
                    )
            else:
                logger.warning(
                    "Monitor API returned %s: trace_id=%s",
                    response.status_code,
                    trace_id,
                )
    except httpx.TimeoutException:
        logger.warning("Monitor API timeout: trace_id=%s", trace_id)
    except Exception as e:
        logger.warning(
            "Failed to call Monitor API for model_output: %s",
            e,
        )


class CronExecutor:
    def __init__(self, *, runner: Any, channel_manager: Any):
        self._runner = runner
        self._channel_manager = channel_manager

    async def execute(self, job: CronJobSpec) -> None:
        """Execute one job once with tenant context.

        - task_type text: send fixed text to channel
        - task_type agent: ask agent with prompt, send reply to channel (
            stream_query + send_event)

        Job execution is wrapped in tenant context to ensure proper isolation.
        """
        target_user_id = job.dispatch.target.user_id
        target_session_id = job.dispatch.target.session_id
        dispatch_meta: Dict[str, Any] = dict(job.dispatch.meta or {})
        workspace_dir_value = dispatch_meta.get("workspace_dir")
        workspace_dir = None
        if workspace_dir_value:
            workspace_dir = Path(workspace_dir_value)

        # Extract tenant_id from job spec (added for tenant isolation)
        tenant_id = getattr(job, "tenant_id", None)
        if tenant_id:
            dispatch_meta["tenant_id"] = tenant_id

        logger.info(
            "cron execute: job_id=%s channel=%s task_type=%s "
            "target_user_id=%s target_session_id=%s tenant_id=%s",
            job.id,
            job.dispatch.channel,
            job.task_type,
            target_user_id[:40] if target_user_id else "",
            target_session_id[:40] if target_session_id else "",
            tenant_id or "default",
        )

        # Wrap execution in tenant context
        with (
            bind_tenant_context(
                tenant_id=tenant_id,
                user_id=target_user_id,
                workspace_dir=workspace_dir,
            ),
            bind_llm_workload(LLM_WORKLOAD_CRON),
        ):
            await self._execute_job(
                job,
                target_user_id,
                target_session_id,
                dispatch_meta,
            )

    async def _execute_job(
        self,
        job: CronJobSpec,
        target_user_id: str,
        target_session_id: str,
        dispatch_meta: Dict[str, Any],
    ) -> None:
        """Internal: execute job logic (called within tenant context)."""
        if job.task_type == "text" and job.text:
            await self._execute_text_job(
                job,
                target_user_id,
                target_session_id,
                dispatch_meta,
            )
        else:
            await self._execute_agent_job(
                job,
                target_user_id,
                target_session_id,
                dispatch_meta,
            )

    async def _execute_text_job(
        self,
        job: CronJobSpec,
        target_user_id: str,
        target_session_id: str,
        dispatch_meta: Dict[str, Any],
    ) -> None:
        """Execute text-type job: send fixed text to channel."""
        tenant_id = dispatch_meta.get("tenant_id") or "default"
        logger.info(
            "cron send_text: job_id=%s channel=%s len=%s",
            job.id,
            job.dispatch.channel,
            len(job.text or ""),
        )

        # 为 text 类型任务也创建 trace 记录
        trace_id = None
        if has_trace_manager():
            try:
                trace_mgr = get_trace_manager()
                if trace_mgr.enabled:
                    source_id = job.source_id or "default"
                    trace_id = await trace_mgr.start_trace(
                        user_id=target_user_id or "cron",
                        session_id=target_session_id or f"cron:{job.id}",
                        channel=job.dispatch.channel,
                        source_id=source_id,
                        user_message=None,  # text 任务无用户输入
                        user_name=job.tenant_name,
                        bbk_id=job.bbk_id,
                        session_name=job.name,  # 使用任务名称作为会话名称
                    )
                    # 写入 model_output 到 ES
                    if trace_id and job.text:
                        await _index_model_output_to_monitor(
                            trace_id,
                            job.text.strip(),
                        )
            except Exception as e:
                logger.warning("Failed to start trace for text job: %s", e)

        try:
            await self._channel_manager.send_text(
                channel=job.dispatch.channel,
                user_id=target_user_id,
                session_id=target_session_id,
                text=job.text.strip(),
                meta=dispatch_meta,
            )
            task_chat_id: Optional[str] = (job.meta or {}).get("task_chat_id")
            if job.dispatch.channel != CONSOLE_CHANNEL and task_chat_id:
                await self._push_to_console(
                    task_chat_id,
                    job.text.strip(),
                    tenant_id,
                )
        finally:
            # 结束 trace
            if trace_id and has_trace_manager():
                try:
                    trace_mgr = get_trace_manager()
                    await trace_mgr.end_trace(trace_id, TraceStatus.COMPLETED)
                except Exception as e:
                    logger.warning("Failed to end trace for text job: %s", e)

    async def _execute_agent_job(
        self,
        job: CronJobSpec,
        target_user_id: str,
        target_session_id: str,
        dispatch_meta: Dict[str, Any],
    ) -> None:
        """Execute agent-type job: run agent query and send events."""
        tenant_id = dispatch_meta.get("tenant_id") or "default"
        logger.info(
            "cron agent: job_id=%s channel=%s timeout=%ss",
            job.id,
            job.dispatch.channel,
            job.runtime.timeout_seconds,
        )
        assert job.request is not None
        req = self._build_agent_request(job, target_user_id, target_session_id)
        self._apply_auth_token(job, dispatch_meta, req)

        console_text_parts: list[str] = []
        try:
            # Wrap the entire agent execution in a timeout so that
            # initialization delays + streaming are both covered.
            if hasattr(asyncio, "timeout"):
                async with asyncio.timeout(job.runtime.timeout_seconds):
                    await self._run_agent_stream(
                        job,
                        target_user_id,
                        target_session_id,
                        dispatch_meta,
                        req,
                        console_text_parts,
                    )
            else:
                await asyncio.wait_for(
                    self._run_agent_stream(
                        job,
                        target_user_id,
                        target_session_id,
                        dispatch_meta,
                        req,
                        console_text_parts,
                    ),
                    timeout=job.runtime.timeout_seconds,
                )
            task_chat_id: Optional[str] = (job.meta or {}).get("task_chat_id")
            if (
                job.dispatch.channel != CONSOLE_CHANNEL
                and console_text_parts
                and task_chat_id
            ):
                await self._push_to_console(
                    task_chat_id,
                    "\n".join(console_text_parts),
                    tenant_id,
                )
        except asyncio.TimeoutError:
            logger.warning(
                "cron execute: job_id=%s timed out after %ss",
                job.id,
                job.runtime.timeout_seconds,
            )
            await self._notify_timeout(job, tenant_id)
            raise
        except asyncio.CancelledError:
            logger.info("cron execute: job_id=%s cancelled", job.id)
            raise

    def _build_agent_request(
        self,
        job: CronJobSpec,
        target_user_id: str,
        target_session_id: str,
    ) -> Dict[str, Any]:
        """Build agent request dict from job spec."""
        req: Dict[str, Any] = job.request.model_dump(mode="json")
        req["user_id"] = req.get("user_id") or target_user_id or "cron"
        req["session_id"] = (
            req.get("session_id") or target_session_id or f"cron:{job.id}"
        )
        req["skip_history"] = True  # 标记定时任务不加载历史会话
        # 传递 source_id 用于 tracing 数据隔离
        if job.source_id:
            req["source_id"] = job.source_id
        # 传递 bbk_id 用于 tracing 用户标识
        if job.bbk_id:
            req["bbk_id"] = job.bbk_id
        # 传递 user_name（从 tenant_name 字段获取）
        if job.tenant_name:
            req["user_name"] = job.tenant_name
        return req

    def _apply_auth_token(
        self,
        job: CronJobSpec,
        dispatch_meta: Dict[str, Any],
        req: Dict[str, Any],
    ) -> None:
        """Resolve and apply auth token to request."""
        try:
            resolved = resolve_auth_token_for_execution(
                tenant_id=getattr(job, "tenant_id", None),
                workspace_dir=dispatch_meta.get("workspace_dir"),
            )
        except ValueError as exc:
            logger.warning(
                "cron agent aborted: job_id=%s auth_state_error=%s",
                job.id,
                repr(exc),
            )
            raise RuntimeError(
                "cron auth user_info is expired; "
                "please refresh cron auth configuration",
            ) from exc
        if resolved.token:
            req["auth_token"] = resolved.token
        if resolved.cookie_header:
            req["cookie"] = resolved.cookie_header

    async def _run_agent_stream(
        self,
        job: CronJobSpec,
        target_user_id: str,
        target_session_id: str,
        dispatch_meta: Dict[str, Any],
        req: Dict[str, Any],
        console_text_parts: list[str],
    ) -> None:
        """Run agent stream query and send events to channel."""

        async def _stream() -> None:
            async for event in self._runner.stream_query(req):
                await self._channel_manager.send_event(
                    channel=job.dispatch.channel,
                    user_id=target_user_id,
                    session_id=target_session_id,
                    event=event,
                    meta=dispatch_meta,
                )
                text = self._extract_text_from_event(event)
                if text:
                    console_text_parts.append(text)

        # Timeout is handled by _execute_agent_job which wraps this call
        await _stream()

    async def _notify_timeout(self, job: CronJobSpec, tenant_id: str) -> None:
        """Push a timeout notification to the console so the user is aware.

        Falls back to logging if the push fails; never raises.
        """
        task_chat_id: Optional[str] = (job.meta or {}).get("task_chat_id")
        target_session_id = task_chat_id or job.dispatch.target.session_id
        if not target_session_id:
            logger.warning(
                "cron timeout: no session_id for job_id=%s",
                job.id,
            )
            return
        timeout_text = (
            f"⏰ 定时任务 [{job.name}] 执行超时"
            f"（{job.runtime.timeout_seconds}s），已自动终止。"
        )
        try:
            await self._push_to_console(
                target_session_id,
                timeout_text,
                tenant_id,
            )
        except Exception:  # pylint: disable=broad-except
            logger.warning(
                "Failed to push timeout notification for job_id=%s",
                job.id,
                exc_info=True,
            )

    async def _push_to_console(
        self,
        session_id: str,
        text: str,
        tenant_id: str,
    ) -> None:
        """Push message to console channel for frontend notification."""
        if not session_id or not text:
            return
        logger.info(
            "cron push_to_console: session_id=%s text_len=%s tenant_id=%s",
            session_id[:40] if session_id else "",
            len(text),
            tenant_id,
        )
        await push_store_append(session_id, text.strip(), tenant_id=tenant_id)

    def _extract_text_from_event(self, event: Any) -> str:
        """Extract text content from a runner event.

        Args:
            event: Runner event (from stream_query)

        Returns:
            Extracted text string, empty if no text found
        """
        from agentscope_runtime.engine.schemas.agent_schemas import RunStatus

        obj = getattr(event, "object", None)
        status = getattr(event, "status", None)

        # Only extract from completed message events
        if obj != "message" or status != RunStatus.Completed:
            return ""

        # Extract text from message content
        content = getattr(event, "content", None) or []
        text_parts: list[str] = []
        for part in content:
            part_type = getattr(part, "type", None)
            if part_type == "text":
                text = getattr(part, "text", None)
                if text:
                    text_parts.append(text)
            elif part_type == "refusal":
                refusal = getattr(part, "refusal", None)
                if refusal:
                    text_parts.append(refusal)

        return "\n".join(text_parts) if text_parts else ""
