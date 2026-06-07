# -*- coding: utf-8 -*-

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from swe.app.channels.console.channel import ConsoleChannel
from swe.app.channels.manager import ChannelManager
from swe.config.config import ChannelConfig, Config, ConsoleConfig


class _FakeConsoleChannel:
    channel = "console"

    @classmethod
    def from_env(cls, process, on_reply_sent=None):
        return SimpleNamespace(
            channel=cls.channel,
            process=process,
            on_reply_sent=on_reply_sent,
        )

    @classmethod
    def from_config(cls, **kwargs):
        return SimpleNamespace(
            channel=cls.channel,
            config=kwargs["config"],
        )


class _FakeZhaohuChannel:
    channel = "zhaohu"

    @classmethod
    def from_env(cls, process, on_reply_sent=None):
        return SimpleNamespace(
            channel=cls.channel,
            process=process,
            on_reply_sent=on_reply_sent,
        )

    @classmethod
    def from_config(cls, **kwargs):
        return SimpleNamespace(
            channel=cls.channel,
            config=kwargs["config"],
        )


def test_channel_manager_from_env_keeps_console_when_env_filter_excludes_it():
    with (
        patch(
            "swe.app.channels.manager.get_available_channels",
            return_value=("zhaohu",),
        ),
        patch(
            "swe.app.channels.manager.get_channel_registry",
            return_value={
                "console": _FakeConsoleChannel,
                "zhaohu": _FakeZhaohuChannel,
            },
        ),
    ):
        manager = ChannelManager.from_env(process=Mock())

    assert [channel.channel for channel in manager.channels] == [
        "console",
        "zhaohu",
    ]


def test_channel_manager_from_config_keeps_console_when_env_filter_excludes_it():
    config = Config(channels=ChannelConfig())

    with (
        patch(
            "swe.app.channels.manager.get_available_channels",
            return_value=("zhaohu",),
        ),
        patch(
            "swe.app.channels.manager.get_channel_registry",
            return_value={
                "console": _FakeConsoleChannel,
                "zhaohu": _FakeZhaohuChannel,
            },
        ),
    ):
        manager = ChannelManager.from_config(
            process=Mock(),
            config=config,
        )

    assert [channel.channel for channel in manager.channels] == [
        "console",
        "zhaohu",
    ]
    assert manager.channels[0].config.enabled is True


def test_console_channel_from_env_ignores_disable_env(monkeypatch, tmp_path):
    monkeypatch.setenv("CONSOLE_CHANNEL_ENABLED", "0")
    monkeypatch.setenv("CONSOLE_MEDIA_DIR", str(tmp_path))

    channel = ConsoleChannel.from_env(process=Mock())

    assert channel.enabled is True


def test_console_channel_from_config_ignores_disabled_config(tmp_path):
    channel = ConsoleChannel.from_config(
        process=Mock(),
        config=ConsoleConfig(enabled=False, media_dir=str(tmp_path)),
    )

    assert channel.enabled is True


class _ReloadableFakeChannel:
    uses_manager_queue = True

    def __init__(self, channel: str):
        self.channel = channel
        self.start = AsyncMock()
        self.stop = AsyncMock()
        self.set_enqueue = Mock()
        self._workspace = None
        self._command_registry = None

    def set_workspace(self, workspace, command_registry=None):
        self._workspace = workspace
        self._command_registry = command_registry


async def test_replace_channel_preserves_workspace_binding():
    old_channel = _ReloadableFakeChannel("console")
    manager = ChannelManager([old_channel])
    workspace = SimpleNamespace(tenant_id="tenant-a")
    manager.set_workspace(workspace)

    new_channel = _ReloadableFakeChannel("console")

    await manager.replace_channel(new_channel)

    assert new_channel._workspace is workspace
    assert new_channel._command_registry is not None
