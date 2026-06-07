# -*- coding: utf-8 -*-

from types import SimpleNamespace
from unittest.mock import Mock, patch

from swe.config.config import ChannelConfig, ConsoleConfig
from swe.app.routers.config import get_channel, list_channels, put_channel


async def test_list_channels_materializes_console_when_channels_missing():
    request = Mock()
    agent_config = SimpleNamespace(channels=None)

    with (
        patch(
            "swe.app.agent_context.get_agent_and_config_for_request",
            return_value=(SimpleNamespace(), agent_config),
        ),
        patch(
            "swe.app.routers.config.get_available_channels",
            return_value=["console"],
        ),
    ):
        result = await list_channels(request)

    assert result["console"]["enabled"] is True
    assert result["console"]["isBuiltin"] is True
    assert result["console"]["_constraints"]["enabled"]["readOnly"] is True


async def test_get_channel_returns_synthesized_console_payload_when_missing():
    request = Mock()
    agent_config = SimpleNamespace(channels=None)

    with (
        patch(
            "swe.app.agent_context.get_agent_and_config_for_request",
            return_value=(SimpleNamespace(), agent_config),
        ),
        patch(
            "swe.app.routers.config.get_available_channels",
            return_value=["console"],
        ),
    ):
        result = await get_channel(request, "console")

    assert result["enabled"] is True
    assert result["_constraints"]["enabled"]["enforcedValue"] is True


async def test_put_channel_ignores_constraints_and_forces_console_enabled():
    request = Mock()
    agent = SimpleNamespace(agent_id="default", tenant_id="tenant-a")
    agent_config = SimpleNamespace(
        channels=ChannelConfig(console=ConsoleConfig(enabled=True)),
    )

    with (
        patch(
            "swe.app.agent_context.get_agent_and_config_for_request",
            return_value=(agent, agent_config),
        ),
        patch(
            "swe.app.routers.config.get_available_channels",
            return_value=["console"],
        ),
        patch(
            "swe.app.routers.config.schedule_agent_reload",
        ),
        patch(
            "swe.config.config.save_agent_config",
        ),
    ):
        result = await put_channel(
            request,
            "console",
            {
                "enabled": False,
                "bot_prefix": "[BOT]",
                "_constraints": {
                    "enabled": {"readOnly": False, "enforcedValue": False},
                },
            },
        )

    assert agent_config.channels.console.enabled is True
    assert result["enabled"] is True
    assert result["bot_prefix"] == "[BOT]"
    assert result["_constraints"]["enabled"]["reasonKey"] == (
        "channels.constraints.console_enabled_mandatory"
    )
