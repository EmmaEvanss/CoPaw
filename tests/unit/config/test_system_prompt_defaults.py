# -*- coding: utf-8 -*-
"""Tests for system prompt default file compatibility."""

import json

import swe.app.migration as migration_module
from swe.app.migration import _do_migrate_legacy_workspace
from swe.config.config import (
    AgentProfileConfig,
    AgentProfileRef,
    AgentsConfig,
    Config,
    load_agent_config,
)
from swe.config.utils import save_config


def test_agent_profile_config_defaults_include_memory():
    """Agent profile defaults should include MEMORY.md."""
    config = AgentProfileConfig(
        id="default",
        name="Default Agent",
    )

    assert config.system_prompt_files == [
        "AGENTS.md",
        "SOUL.md",
        "PROFILE.md",
        "MEMORY.md",
    ]


def test_agents_config_defaults_include_memory():
    """Root agents config defaults should include MEMORY.md."""
    config = AgentsConfig()

    assert config.system_prompt_files == [
        "AGENTS.md",
        "SOUL.md",
        "PROFILE.md",
        "MEMORY.md",
    ]


def test_agent_profile_config_preserves_explicit_empty_prompt_files():
    """Explicit empty prompt-file selections should disable all files."""
    config = AgentProfileConfig(
        id="default",
        name="Default Agent",
        system_prompt_files=[],
    )

    assert config.system_prompt_files == []


def test_agents_config_preserves_explicit_empty_prompt_files():
    """Explicit empty root prompt-file selections should disable all files."""
    config = AgentsConfig(system_prompt_files=[])

    assert config.system_prompt_files == []


def test_load_agent_config_upgrades_legacy_default_prompt_files(tmp_path):
    """Legacy default prompt files should pick up MEMORY.md on fallback."""
    tenant_dir = tmp_path / "tenant-a"
    workspace_dir = tenant_dir / "workspaces" / "default"
    save_config(
        Config(
            agents=AgentsConfig(
                active_agent="default",
                profiles={
                    "default": AgentProfileRef(
                        id="default",
                        workspace_dir=str(workspace_dir),
                    ),
                },
                language="en",
                system_prompt_files=[
                    "AGENTS.md",
                    "SOUL.md",
                    "PROFILE.md",
                ],
            ),
        ),
        tenant_dir / "config.json",
    )

    agent_config = load_agent_config(
        "default",
        config_path=tenant_dir / "config.json",
    )

    assert agent_config.system_prompt_files == [
        "AGENTS.md",
        "SOUL.md",
        "PROFILE.md",
        "MEMORY.md",
    ]


def test_load_agent_config_preserves_custom_prompt_files(tmp_path):
    """Custom prompt file selections should stay unchanged."""
    tenant_dir = tmp_path / "tenant-b"
    workspace_dir = tenant_dir / "workspaces" / "default"
    save_config(
        Config(
            agents=AgentsConfig(
                active_agent="default",
                profiles={
                    "default": AgentProfileRef(
                        id="default",
                        workspace_dir=str(workspace_dir),
                    ),
                },
                language="en",
                system_prompt_files=[
                    "AGENTS.md",
                    "PROFILE.md",
                ],
            ),
        ),
        tenant_dir / "config.json",
    )

    agent_config = load_agent_config(
        "default",
        config_path=tenant_dir / "config.json",
    )

    assert agent_config.system_prompt_files == [
        "AGENTS.md",
        "PROFILE.md",
    ]


def test_load_agent_config_preserves_empty_prompt_files(tmp_path):
    """Empty prompt file selections should stay empty when loading fallback."""
    tenant_dir = tmp_path / "tenant-c"
    workspace_dir = tenant_dir / "workspaces" / "default"
    save_config(
        Config(
            agents=AgentsConfig(
                active_agent="default",
                profiles={
                    "default": AgentProfileRef(
                        id="default",
                        workspace_dir=str(workspace_dir),
                    ),
                },
                language="en",
                system_prompt_files=[],
            ),
        ),
        tenant_dir / "config.json",
    )

    agent_config = load_agent_config(
        "default",
        config_path=tenant_dir / "config.json",
    )

    assert agent_config.system_prompt_files == []
    agent_data = json.loads(
        (workspace_dir / "agent.json").read_text(encoding="utf-8"),
    )
    assert agent_data["system_prompt_files"] == []


def test_legacy_workspace_migration_upgrades_historical_default_prompt_files(
    tmp_path,
    monkeypatch,
):
    """Legacy workspace migration should upgrade the historical default set."""
    workspace_dir = tmp_path / "workspaces" / "default"
    workspace_dir.mkdir(parents=True)

    config = Config(
        agents=AgentsConfig(
            active_agent="default",
            profiles={
                "default": AgentProfileRef(
                    id="default",
                    workspace_dir=str(workspace_dir),
                ),
            },
            language="en",
            system_prompt_files=[
                "AGENTS.md",
                "SOUL.md",
                "PROFILE.md",
            ],
        ),
    )

    monkeypatch.setattr(migration_module, "WORKING_DIR", tmp_path)
    monkeypatch.setattr(migration_module, "load_config", lambda: config)
    monkeypatch.setattr(migration_module, "save_config", lambda _: None)

    assert _do_migrate_legacy_workspace() is True

    agent_data = json.loads(
        (workspace_dir / "agent.json").read_text(encoding="utf-8"),
    )
    assert agent_data["system_prompt_files"] == [
        "AGENTS.md",
        "SOUL.md",
        "PROFILE.md",
        "MEMORY.md",
    ]


def test_legacy_workspace_migration_preserves_empty_prompt_files(
    tmp_path,
    monkeypatch,
):
    """Legacy workspace migration should preserve disabled prompt files."""
    workspace_dir = tmp_path / "workspaces" / "default"
    workspace_dir.mkdir(parents=True)

    config = Config(
        agents=AgentsConfig(
            active_agent="default",
            profiles={
                "default": AgentProfileRef(
                    id="default",
                    workspace_dir=str(workspace_dir),
                ),
            },
            language="en",
            system_prompt_files=[],
        ),
    )

    monkeypatch.setattr(migration_module, "WORKING_DIR", tmp_path)
    monkeypatch.setattr(migration_module, "load_config", lambda: config)
    monkeypatch.setattr(migration_module, "save_config", lambda _: None)

    assert _do_migrate_legacy_workspace() is True

    agent_data = json.loads(
        (workspace_dir / "agent.json").read_text(encoding="utf-8"),
    )
    assert agent_data["system_prompt_files"] == []
