# -*- coding: utf-8 -*-

from pathlib import Path
import sys
from unittest.mock import patch

from click.testing import CliRunner

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from swe.cli.channels_cmd import channels_group, configure_console
from swe.config.config import AgentProfileConfig, ConsoleConfig


def test_configure_console_prints_system_managed_notice(capsys):
    config = ConsoleConfig(enabled=False, bot_prefix="")

    with (
        patch("swe.cli.channels_cmd.click.prompt", return_value="[BOT]"),
        patch(
            "swe.cli.channels_cmd.prompt_confirm",
        ) as mock_confirm,
    ):
        updated = configure_console(config)

    captured = capsys.readouterr()
    assert updated.enabled is True
    assert updated.bot_prefix == "[BOT]"
    assert "system-managed" in captured.out
    mock_confirm.assert_not_called()


def test_channels_list_shows_console_enabled_when_agent_channels_missing():
    runner = CliRunner()
    agent_config = AgentProfileConfig(
        id="default",
        name="Default Agent",
        workspace_dir="/tmp/default",
        channels=None,
    )

    with (
        patch(
            "swe.cli.channels_cmd.load_agent_config",
            return_value=agent_config,
        ),
        patch(
            "swe.cli.channels_cmd.get_available_channels",
            return_value=["console"],
        ),
    ):
        result = runner.invoke(channels_group, ["list"])

    assert result.exit_code == 0
    assert "Console" in result.output
    assert "enabled" in result.output
    assert "always enabled" in result.output
