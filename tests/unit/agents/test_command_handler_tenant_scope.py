# -*- coding: utf-8 -*-
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from swe.agents.command_handler import CommandHandler


def test_command_handler_get_agent_config_uses_memory_manager_tenant_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str | None]] = []

    def fake_load_agent_config(agent_id: str, tenant_id: str | None = None):
        calls.append((agent_id, tenant_id))
        return SimpleNamespace(
            running=SimpleNamespace(
                max_input_length=8192,
                history_max_length=4096,
            ),
        )

    monkeypatch.setattr(
        "swe.agents.command_handler.load_agent_config",
        fake_load_agent_config,
    )

    handler = CommandHandler(
        agent_name="agent",
        memory=SimpleNamespace(),
        memory_manager=SimpleNamespace(
            agent_id="default",
            tenant_id="tenant-a",
        ),
    )

    config = handler._get_agent_config()

    assert config.running.max_input_length == 8192
    assert config.running.history_max_length == 4096
    assert calls == [("default", "tenant-a")]


@pytest.mark.asyncio
async def test_process_history_uses_tenant_scoped_agent_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str | None]] = []

    def fake_load_agent_config(agent_id: str, tenant_id: str | None = None):
        calls.append((agent_id, tenant_id))
        return SimpleNamespace(
            running=SimpleNamespace(
                max_input_length=8192,
                history_max_length=4096,
            ),
        )

    monkeypatch.setattr(
        "swe.agents.command_handler.load_agent_config",
        fake_load_agent_config,
    )

    memory = SimpleNamespace(
        get_history_str=AsyncMock(return_value="history payload"),
        get_compressed_summary=lambda: "",
    )
    handler = CommandHandler(
        agent_name="agent",
        memory=memory,
        memory_manager=SimpleNamespace(
            agent_id="default",
            tenant_id="tenant-a",
        ),
    )

    result = await handler._process_history([], "")

    memory.get_history_str.assert_awaited_once_with(max_input_length=8192)
    assert calls == [("default", "tenant-a")]
    assert result.content[0]["text"] == (
        "history payload\n\n---\n\n- Use /message <index> to view full message content"
    )
