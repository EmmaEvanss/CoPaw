# -*- coding: utf-8 -*-
"""验证复制到静态目录工具返回可访问的公开链接。"""

import json
import re
from pathlib import Path
from urllib.parse import urlparse

import pytest
from fastapi.testclient import TestClient

import swe.app._app as app_module
import swe.constant as constant_module
from swe.agents.tools.copy_file_to_static import copy_file_to_static
from swe.app.agent_context import set_current_agent_id
from swe.config.context import (
    encode_scope_id,
    reset_current_scope_id,
    reset_current_source_id,
    reset_current_user_id,
    reset_current_workspace_dir,
    set_current_scope_id,
    set_current_source_id,
    set_current_user_id,
    set_current_workspace_dir,
)


def _tool_payload(response):
    return json.loads(response.content[0]["text"])


def _extract_markdown_url(markdown: str) -> str:
    match = re.search(r"\]\((?P<url>[^)]+)\)", markdown)
    assert match is not None
    return match.group("url")


@pytest.mark.asyncio
async def test_copy_file_to_static_returns_scope_static_url(
    monkeypatch,
    tmp_path: Path,
) -> None:
    source_file = tmp_path / "report.html"
    source_file.write_text("<p>ok</p>", encoding="utf-8")
    scope_id = encode_scope_id("alice", "portal")
    workspace_dir = tmp_path / scope_id / "workspaces" / "agent-a"
    monkeypatch.setenv("FILE_URL", "https://files.example/")
    set_current_agent_id("agent-a")

    user_token = set_current_user_id("alice")
    source_token = set_current_source_id("portal")
    scope_token = set_current_scope_id(scope_id)
    workspace_token = set_current_workspace_dir(workspace_dir)
    try:
        response = await copy_file_to_static(str(source_file))
    finally:
        reset_current_workspace_dir(workspace_token)
        reset_current_scope_id(scope_token)
        reset_current_source_id(source_token)
        reset_current_user_id(user_token)
        set_current_agent_id("default")

    payload = _tool_payload(response)

    assert payload["ok"] is True
    assert (workspace_dir / "static" / "report.html").read_text(
        encoding="utf-8",
    ) == "<p>ok</p>"
    assert re.search(
        rf"\(https://files\.example/static/{re.escape(scope_id)}/agent-a/"
        r"report\.html\)",
        payload["path"],
    )
    monkeypatch.setattr(constant_module, "WORKING_DIR", tmp_path)
    public_url = _extract_markdown_url(payload["path"])

    with TestClient(
        app_module.app,
        raise_server_exceptions=False,
    ) as client:
        response = client.get(urlparse(public_url).path)

    assert response.status_code == 200
    assert response.text == "<p>ok</p>"
