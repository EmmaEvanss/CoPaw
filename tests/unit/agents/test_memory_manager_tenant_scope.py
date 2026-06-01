# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from swe.agents.memory.base_memory_manager import BaseMemoryManager
from swe.agents.memory.reme_light_memory_manager import ReMeLightMemoryManager
from swe.app.workspace import Workspace
from swe.config.config import ToolResultCompactConfig


class _ConcreteMemoryManager(BaseMemoryManager):
    async def start(self) -> None:  # pragma: no cover - test stub
        return None

    async def close(self) -> bool:  # pragma: no cover - test stub
        return True

    async def compact_tool_result(
        self,
        **kwargs,
    ) -> None:  # pragma: no cover - test stub
        return None

    async def check_context(
        self,
        **kwargs,
    ) -> tuple:  # pragma: no cover - test stub
        return (), (), True

    async def compact_memory(
        self,
        messages,
        previous_summary="",
        **kwargs,
    ) -> str:  # pragma: no cover - test stub
        return ""

    async def summary_memory(
        self,
        messages,
        **kwargs,
    ) -> str:  # pragma: no cover - test stub
        return ""

    async def dream_memory(
        self,
        tenant_id: str | None = None,
        **kwargs,
    ) -> None:  # pragma: no cover - test stub
        return None

    async def memory_search(
        self,
        query: str,
        max_results: int = 5,
        min_score: float = 0.1,
    ):  # pragma: no cover - test stub
        return None

    def get_in_memory_memory(self, **kwargs):  # pragma: no cover - test stub
        return None


def test_base_memory_manager_constructor_accepts_tenant_id() -> None:
    manager = _ConcreteMemoryManager(
        working_dir="/tmp/ws",
        agent_id="default",
        tenant_id="tenant-a",
    )

    assert manager.working_dir == "/tmp/ws"
    assert manager.agent_id == "default"
    assert manager.tenant_id == "tenant-a"


def test_memory_manager_load_agent_config_prefers_explicit_tenant_id(
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

    config = manager._load_agent_config(tenant_id="tenant-b")

    assert config.running.embedding_config.base_url == "https://tenant.example"
    assert calls == [("default", "tenant-b")]


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


def test_workspace_registers_tenant_id_for_memory_manager(
    tmp_path: Path,
) -> None:
    workspace = Workspace(
        agent_id="default",
        workspace_dir=str(tmp_path / "ws"),
        tenant_id="tenant-a",
    )

    descriptor = workspace._service_manager.descriptors[
        "memory_manager"
    ]  # pylint: disable=protected-access

    assert descriptor.init_args is not None
    assert descriptor.init_args(workspace) == {
        "working_dir": str(workspace.workspace_dir),
        "agent_id": "default",
        "tenant_id": "tenant-a",
    }


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
