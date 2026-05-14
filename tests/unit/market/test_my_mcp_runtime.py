# -*- coding: utf-8 -*-
"""测试 market 内置 MyMCP runtime 的最小行为。"""

from __future__ import annotations

import json

from market.runtime.config_store import (
    AgentProfileConfig,
    AgentProfileRef,
    AgentsRootConfig,
    MCPClientConfig,
    MCPConfig,
    RootAgentsSection,
    load_agent_config,
    save_agent_config,
    save_root_config,
)
from market.runtime.context import resolve_effective_tenant_id


def test_resolve_effective_tenant_id_keeps_non_default_tenant() -> None:
    """非 default tenant 不应继续附加 source。"""
    assert resolve_effective_tenant_id("user_a", "SRC_A") == "user_a"


def test_resolve_effective_tenant_id_scopes_default_with_source() -> None:
    """default tenant 应按 source 进入隔离目录。"""
    assert resolve_effective_tenant_id("default", "SRC_A") == "default_SRC_A"


def test_load_and_save_agent_config_under_market_runtime(tmp_path) -> None:
    """market runtime 应能独立读写 tenant 下的 agent.json。"""
    swe_root = tmp_path / ".swe"
    workspace_dir = swe_root / "default_SRC_A" / "workspaces" / "default"
    workspace_dir.mkdir(parents=True, exist_ok=True)

    root_config = AgentsRootConfig(
        agents=RootAgentsSection(
            active_agent="default",
            profiles={
                "default": AgentProfileRef(
                    id="default",
                    workspace_dir=str(workspace_dir),
                ),
            },
        ),
    )
    save_root_config(swe_root, "default_SRC_A", root_config)

    agent_config = AgentProfileConfig(
        id="default",
        name="Default Agent",
        workspace_dir=str(workspace_dir),
        mcp=MCPConfig(
            clients={
                "weather-tool": MCPClientConfig(
                    name="weather-tool",
                    transport="stdio",
                    command="npx",
                    args=["-y", "weather-mcp"],
                ),
            },
        ),
    )
    save_agent_config(swe_root, "default_SRC_A", "default", agent_config)

    loaded = load_agent_config(swe_root, "default_SRC_A", "default")

    assert loaded.id == "default"
    assert loaded.name == "Default Agent"
    assert "weather-tool" in loaded.mcp.clients
    assert loaded.mcp.clients["weather-tool"].command == "npx"

    raw = json.loads(
        (workspace_dir / "agent.json").read_text(encoding="utf-8"),
    )
    assert raw["mcp"]["clients"]["weather-tool"]["name"] == "weather-tool"
