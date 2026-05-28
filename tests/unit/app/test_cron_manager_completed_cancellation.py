# -*- coding: utf-8 -*-
"""Cron Agent 完成输出后的取消状态回归测试。"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

from agentscope_runtime.engine.schemas.agent_schemas import RunStatus

from swe.app.crons.manager import CronManager
from swe.app.crons.models import (
    CronJobRequest,
    CronJobSpec,
    DispatchSpec,
    DispatchTarget,
    JobRuntimeSpec,
    ScheduleSpec,
)


class _Repo:
    def __init__(self, job: CronJobSpec) -> None:
        self._job = job

    async def get_job(self, job_id: str) -> CronJobSpec | None:
        return self._job if job_id == self._job.id else None

    async def list_jobs(self) -> list[CronJobSpec]:
        return [self._job]


class _Runner:
    async def stream_query(self, _req):
        yield SimpleNamespace(
            object="message",
            status=RunStatus.Completed,
            content=[SimpleNamespace(type="text", text="done output")],
        )
        await asyncio.sleep(30)


class _PendingRunner:
    async def stream_query(self, _req):
        # 需要使用 yield 使其成为异步生成器，否则 async for 会报 TypeError
        await asyncio.sleep(30)
        yield


class _ChannelManager:
    def __init__(self) -> None:
        self.events: list[object] = []

    async def send_event(self, **kwargs) -> None:
        self.events.append(kwargs["event"])


class _SlowSendChannelManager(_ChannelManager):
    def __init__(self, send_started: asyncio.Event) -> None:
        super().__init__()
        self.send_started = send_started

    async def send_event(self, **kwargs) -> None:
        self.events.append(kwargs["event"])
        self.send_started.set()
        await asyncio.sleep(30)


class _MonitorSyncClient:
    def __init__(self) -> None:
        self.records: list[dict] = []

    async def record_execution(self, **kwargs) -> None:
        self.records.append(kwargs)


def _build_agent_job() -> CronJobSpec:
    return CronJobSpec(
        id="job-cancel-after-output",
        name="agent job",
        schedule=ScheduleSpec(cron="* * * * *"),
        task_type="agent",
        request=CronJobRequest(
            input=[{"content": [{"type": "text", "text": "ping"}]}],
        ),
        dispatch=DispatchSpec(
            channel="console",
            target=DispatchTarget(user_id="user-a", session_id="session-a"),
            meta={},
        ),
        runtime=JobRuntimeSpec(timeout_seconds=60),
    )


def test_completed_agent_output_cancelled_before_stream_close_keeps_success(
    monkeypatch,
):
    """Agent 已输出完成消息后被取消，最终状态仍应保留为成功。"""
    info_messages: list[str] = []

    def fake_executor_info(message, *args, **_kwargs) -> None:
        try:
            text = str(message) % args if args else str(message)
        except TypeError:
            text = str(message)
        info_messages.append(text)

    monkeypatch.setattr(
        "swe.app.crons.executor.logger.info",
        fake_executor_info,
    )

    async def _run():
        job = _build_agent_job()
        channel_manager = _ChannelManager()
        monitor = _MonitorSyncClient()
        manager = CronManager(
            repo=_Repo(job),
            runner=_Runner(),
            channel_manager=channel_manager,
        )
        manager._monitor_sync_client = (
            monitor  # pylint: disable=protected-access
        )
        # executor 也需要使用同一个 monitor
        manager._executor._monitor_sync_client = (
            monitor  # pylint: disable=protected-access
        )

        task = asyncio.create_task(
            manager._execute_once(  # pylint: disable=protected-access
                job,
                is_manual=False,
            ),
        )
        await asyncio.sleep(0.05)
        assert len(channel_manager.events) == 1

        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        return manager, channel_manager, monitor

    manager, channel_manager, monitor = asyncio.run(_run())

    state = manager.get_state("job-cancel-after-output")
    assert len(channel_manager.events) == 1
    assert state.last_status == "success"
    assert state.last_error is None
    assert monitor.records[-1]["status"] == "success"
    assert any(
        "cancellation after completed output" in message
        for message in info_messages
    )


def test_completed_agent_event_cancelled_during_send_keeps_success():
    """Agent 完成事件发送过程中被取消，也应按已完成任务处理。"""

    async def _run():
        job = _build_agent_job()
        send_started = asyncio.Event()
        channel_manager = _SlowSendChannelManager(send_started)
        monitor = _MonitorSyncClient()
        manager = CronManager(
            repo=_Repo(job),
            runner=_Runner(),
            channel_manager=channel_manager,
        )
        manager._monitor_sync_client = (
            monitor  # pylint: disable=protected-access
        )
        # executor 也需要使用同一个 monitor
        manager._executor._monitor_sync_client = (
            monitor  # pylint: disable=protected-access
        )

        task = asyncio.create_task(
            manager._execute_once(  # pylint: disable=protected-access
                job,
                is_manual=False,
            ),
        )
        await send_started.wait()

        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        return manager, channel_manager, monitor

    manager, channel_manager, monitor = asyncio.run(_run())

    state = manager.get_state("job-cancel-after-output")
    assert len(channel_manager.events) == 1
    assert state.last_status == "success"
    assert state.last_error is None
    assert monitor.records[-1]["status"] == "success"


def test_agent_cancelled_before_completed_output_keeps_cancelled():
    """Agent 完成消息前被取消时，仍应记录为真正取消。"""

    async def _run():
        job = _build_agent_job()
        channel_manager = _ChannelManager()
        monitor = _MonitorSyncClient()
        manager = CronManager(
            repo=_Repo(job),
            runner=_PendingRunner(),
            channel_manager=channel_manager,
        )
        manager._monitor_sync_client = (
            monitor  # pylint: disable=protected-access
        )
        # executor 也需要使用同一个 monitor
        manager._executor._monitor_sync_client = (
            monitor  # pylint: disable=protected-access
        )

        task = asyncio.create_task(
            manager._execute_once(  # pylint: disable=protected-access
                job,
                is_manual=False,
            ),
        )
        await asyncio.sleep(0.05)
        assert channel_manager.events == []

        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        return manager, channel_manager, monitor

    manager, channel_manager, monitor = asyncio.run(_run())

    state = manager.get_state("job-cancel-after-output")
    assert channel_manager.events == []
    assert state.last_status == "cancelled"
    assert state.last_error == "Job was cancelled"
    assert monitor.records[-1]["status"] == "cancelled"
