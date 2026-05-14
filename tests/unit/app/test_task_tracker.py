# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio

import pytest

from swe.app.runner.task_tracker import TaskTracker, _RunState


@pytest.mark.asyncio
async def test_request_stop_marks_status_stopping_while_producer_is_cleaning_up():
    tracker = TaskTracker()
    stream_started = asyncio.Event()
    cleanup_started = asyncio.Event()
    release_cleanup = asyncio.Event()

    async def _stream_fn(_payload):
        stream_started.set()
        yield 'data: {"started": true}\n\n'
        try:
            while True:
                await asyncio.sleep(1)
                yield 'data: {"tick": true}\n\n'
        finally:
            cleanup_started.set()
            await release_cleanup.wait()

    _queue, is_new = await tracker.attach_or_start(
        "chat-1",
        {},
        _stream_fn,
    )
    assert is_new is True
    await asyncio.wait_for(stream_started.wait(), timeout=1)
    assert await tracker.get_status("chat-1") == "running"

    assert await tracker.request_stop("chat-1") is True
    await asyncio.wait_for(cleanup_started.wait(), timeout=1)

    assert await tracker.get_status("chat-1") == "stopping"

    release_cleanup.set()
    await asyncio.wait_for(tracker.wait_all_done(timeout=1), timeout=2)
    assert await tracker.get_status("chat-1") == "idle"


@pytest.mark.asyncio
async def test_mark_stopping_marks_status_without_cancelling_producer():
    tracker = TaskTracker()
    release_stream = asyncio.Event()

    async def _stream_fn(_payload):
        yield 'data: {"started": true}\n\n'
        await release_stream.wait()

    _queue, is_new = await tracker.attach_or_start(
        "chat-1",
        {},
        _stream_fn,
    )
    assert is_new is True
    await asyncio.sleep(0)
    assert await tracker.get_status("chat-1") == "running"

    await tracker.mark_stopping("chat-1")

    assert await tracker.get_status("chat-1") == "stopping"

    release_stream.set()
    await asyncio.wait_for(tracker.wait_all_done(timeout=1), timeout=2)
    assert await tracker.get_status("chat-1") == "idle"


@pytest.mark.asyncio
async def test_old_run_cleanup_does_not_remove_new_run_state():
    tracker = TaskTracker()
    first_cleanup_started = asyncio.Event()
    release_first_cleanup = asyncio.Event()

    async def _first_stream(_payload):
        yield 'data: {"run": 1}\n\n'
        try:
            while True:
                await asyncio.sleep(1)
        finally:
            first_cleanup_started.set()
            await release_first_cleanup.wait()

    _queue, is_new = await tracker.attach_or_start(
        "chat-1",
        {},
        _first_stream,
    )
    assert is_new is True
    await asyncio.sleep(0)
    assert await tracker.request_stop("chat-1") is True
    await asyncio.wait_for(first_cleanup_started.wait(), timeout=1)
    assert await tracker.get_status("chat-1") == "stopping"

    second_task = asyncio.Future()
    async with tracker.lock:
        tracker._runs["chat-1"] = _RunState(task=second_task)

    assert await tracker.get_status("chat-1") == "running"

    release_first_cleanup.set()
    await asyncio.sleep(0)
    assert await tracker.get_status("chat-1") == "running"

    second_task.set_result(None)
    async with tracker.lock:
        tracker._runs.pop("chat-1", None)
    assert await tracker.get_status("chat-1") == "idle"
