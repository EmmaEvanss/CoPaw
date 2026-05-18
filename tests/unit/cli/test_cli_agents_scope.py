# -*- coding: utf-8 -*-
"""Agent CLI scope-header regression tests."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from swe.cli.agents_cmd import agents_group


class _Response:
    status_code = 200

    def raise_for_status(self):
        return None

    def json(self):
        return {
            "task_id": "task-1",
            "agents": [],
        }


def test_agents_list_passes_source_header():
    runner = CliRunner()

    with patch("swe.cli.agents_cmd.client") as mock_client:
        mock_http = MagicMock()
        mock_http.__enter__.return_value = mock_http
        mock_http.get.return_value = _Response()
        mock_client.return_value = mock_http

        result = runner.invoke(
            agents_group,
            [
                "list",
                "--tenant-id",
                "tenant-a",
                "--source-id",
                "source-a",
            ],
        )

    assert result.exit_code == 0
    _, kwargs = mock_http.get.call_args
    assert kwargs["headers"]["X-Tenant-Id"] == "tenant-a"
    assert kwargs["headers"]["X-Source-Id"] == "source-a"


def test_agents_chat_background_passes_source_header():
    runner = CliRunner()

    with patch("swe.cli.agents_cmd.client") as mock_client:
        mock_http = MagicMock()
        mock_http.__enter__.return_value = mock_http
        mock_http.post.return_value = _Response()
        mock_client.return_value = mock_http

        result = runner.invoke(
            agents_group,
            [
                "chat",
                "--from-agent",
                "bot-a",
                "--to-agent",
                "bot-b",
                "--text",
                "hello",
                "--background",
                "--tenant-id",
                "tenant-a",
                "--source-id",
                "source-a",
            ],
        )

    assert result.exit_code == 0
    _, kwargs = mock_http.post.call_args
    assert kwargs["headers"]["X-Tenant-Id"] == "tenant-a"
    assert kwargs["headers"]["X-Source-Id"] == "source-a"
