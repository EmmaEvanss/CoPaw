# -*- coding: utf-8 -*-
from __future__ import annotations

from types import SimpleNamespace

import pytest

from swe.app.approvals.service import ApprovalService
from swe.app.runner.runner import AgentRunner
from swe.security.tool_guard.approval import ApprovalDecision


def _result():
    return SimpleNamespace(findings=[], findings_count=0)


@pytest.mark.asyncio
async def test_hook_approval_is_not_consumed_as_tool_guard_preapproval() -> (
    None
):
    service = ApprovalService()
    pending = await service.create_pending(
        session_id="session-1",
        user_id="user-1",
        channel="console",
        tool_name="execute_shell_command",
        result=_result(),
        extra={
            "approval_kind": "hook_pre_tool_use",
            "tool_call": {
                "id": "tool-1",
                "name": "execute_shell_command",
                "input": {"cmd": "echo original"},
            },
        },
    )
    await service.resolve_request(
        pending.request_id,
        ApprovalDecision.APPROVED,
    )

    consumed = await service.consume_approval(
        "session-1",
        "execute_shell_command",
        tool_params={"cmd": "echo original"},
    )

    assert consumed is False


@pytest.mark.asyncio
async def test_tool_guard_approval_is_consumed_as_preapproval() -> None:
    service = ApprovalService()
    pending = await service.create_pending(
        session_id="session-1",
        user_id="user-1",
        channel="console",
        tool_name="execute_shell_command",
        result=_result(),
        extra={
            "approval_kind": "tool_guard",
            "tool_call": {
                "id": "tool-1",
                "name": "execute_shell_command",
                "input": {"cmd": "echo original"},
            },
        },
    )
    await service.resolve_request(
        pending.request_id,
        ApprovalDecision.APPROVED,
    )

    consumed = await service.consume_approval(
        "session-1",
        "execute_shell_command",
        tool_params={"cmd": "echo original"},
    )

    assert consumed is True


@pytest.mark.asyncio
async def test_runner_approves_requested_pending_id_not_fifo_head(
    monkeypatch,
) -> None:
    service = ApprovalService()
    first = await service.create_pending(
        session_id="session-1",
        user_id="user-1",
        channel="console",
        tool_name="execute_shell_command",
        result=_result(),
        extra={
            "approval_kind": "tool_guard",
            "tool_call": {
                "id": "tool-1",
                "name": "execute_shell_command",
                "input": {"cmd": "echo first"},
            },
        },
    )
    second = await service.create_pending(
        session_id="session-1",
        user_id="user-1",
        channel="console",
        tool_name="execute_shell_command",
        result=_result(),
        extra={
            "approval_kind": "hook_pre_tool_use",
            "hook_ask_handler_ids": ["hook-a"],
            "tool_call": {
                "id": "tool-2",
                "name": "execute_shell_command",
                "input": {"cmd": "echo second"},
            },
        },
    )
    monkeypatch.setattr(
        "swe.app.approvals.service._approval_service",
        service,
    )
    runner = AgentRunner()

    response, consumed, approved_tool_call = (
        await runner._resolve_pending_approval(
            "session-1",
            f"/approve {second.request_id}",
        )
    )

    assert response is None
    assert consumed is True
    assert approved_tool_call is not None
    assert approved_tool_call["id"] == "tool-2"
    assert approved_tool_call["_approval_replay"]["request_id"] == (
        second.request_id
    )
    assert (await service.get_request(first.request_id)).status == "pending"
    assert (await service.get_request(second.request_id)).status == "approved"
