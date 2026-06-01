# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from swe.agents.memory.reme_light_memory_manager import ReMeLightMemoryManager
from swe.config.config import ToolResultCompactConfig


def test_memory_manager_load_agent_config_uses_instance_tenant_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str | None]] = []

    def fake_load_agent_config(agent_id: str, tenant_id: str | None = None):
        calls.append((agent_id, tenant_id))
        return SimpleNamespace(
            running=SimpleNamespace(
                embedding_config=SimpleNamespace(
                    backend="openai",
                    api_key="",
                    base_url="https://tenant.example",
                    model_name="embed-tenant",
                    dimensions=1024,
                    enable_cache=True,
                    use_dimensions=True,
                    max_cache_size=256,
                    max_input_length=8192,
                    max_batch_size=32,
                ),
            ),
        )

    monkeypatch.setattr(
        "swe.agents.memory.reme_light_memory_manager.load_agent_config",
        fake_load_agent_config,
    )

    manager = object.__new__(ReMeLightMemoryManager)
    manager.agent_id = "default"
    manager.tenant_id = "tenant-a"
    manager._warn_if_version_mismatch = lambda: None

    config = manager.get_embedding_config()

    assert config["base_url"] == "https://tenant.example"
    assert calls == [("default", "tenant-a")]


@pytest.mark.asyncio
async def test_summary_memory_uses_tenant_scoped_tool_result_compact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, int] = {}

    monkeypatch.setattr(
        "swe.agents.memory.reme_light_memory_manager.load_agent_config",
        lambda agent_id, tenant_id=None: SimpleNamespace(
            agent_id=agent_id,
            language="zh",
            running=SimpleNamespace(
                max_input_length=128000,
                context_compact=SimpleNamespace(
                    memory_compact_ratio=0.8,
                    compact_with_thinking_block=False,
                ),
                tool_result_compact=ToolResultCompactConfig(
                    enabled=True,
                    recent_n=10 if tenant_id == "tenant-a" else 2,
                    old_max_bytes=50000 if tenant_id == "tenant-a" else 3000,
                    recent_max_bytes=(
                        50000 if tenant_id == "tenant-a" else 3000
                    ),
                    retention_days=5,
                ),
            ),
        ),
    )
    monkeypatch.setattr(
        "swe.agents.memory.reme_light_memory_manager.get_swe_token_counter",
        lambda _config: object(),
    )
    monkeypatch.setattr(
        "swe.agents.memory.reme_light_memory_manager.set_current_recent_max_bytes",
        lambda value: observed.setdefault("recent_max_bytes", value),
    )
    monkeypatch.setattr(
        "swe.agents.memory.reme_light_memory_manager.set_current_workspace_dir",
        lambda _path: None,
    )

    manager = object.__new__(ReMeLightMemoryManager)
    manager.agent_id = "default"
    manager.tenant_id = "tenant-a"
    manager.working_dir = str(Path("/tmp/ws"))
    manager._warn_if_version_mismatch = lambda: None
    manager._prepare_model_formatter = lambda: None
    manager.chat_model = object()
    manager.formatter = object()
    manager.summary_toolkit = object()
    manager._reme = SimpleNamespace(
        summary_memory=AsyncMock(return_value="ok"),
    )

    await manager.summary_memory(messages=[])

    assert observed["recent_max_bytes"] == 50000
