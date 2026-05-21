# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from swe.agents.tools.file_io import _resolve_file_path
from swe.config.context import tenant_context
from swe.security.tenant_path_boundary import (
    AbsolutePathDeniedError,
    PathTraversalError,
    get_current_tool_base_dir,
)


def test_current_tool_base_dir_uses_workspace_dir(tmp_path: Path):
    tenant_dir = tmp_path / "tenant_a"
    workspace_dir = tenant_dir / "workspaces" / "agent_a"
    workspace_dir.mkdir(parents=True)

    with patch("swe.security.tenant_path_boundary.WORKING_DIR", tmp_path):
        with tenant_context(
            tenant_id="tenant_a",
            workspace_dir=workspace_dir,
        ):
            resolved = get_current_tool_base_dir()

    assert resolved == workspace_dir


def test_current_tool_base_dir_uses_tenant_root_when_workspace_missing(
    tmp_path: Path,
):
    tenant_dir = tmp_path / "tenant_a"

    with patch("swe.security.tenant_path_boundary.WORKING_DIR", tmp_path):
        with tenant_context(tenant_id="tenant_a"):
            resolved = get_current_tool_base_dir()

    assert resolved == tenant_dir


def test_file_io_resolve_path_falls_back_to_global_tenant_root(
    tmp_path: Path,
):
    tenant_dir = tmp_path / "tenant_a"
    tenant_dir.mkdir(parents=True)

    with patch("swe.security.tenant_path_boundary.WORKING_DIR", tmp_path):
        with tenant_context(tenant_id="tenant_a"):
            resolved = _resolve_file_path("notes.txt")

    assert resolved == str(tenant_dir / "notes.txt")


def test_file_io_resolve_path_uses_workspace_dir_when_present(
    tmp_path: Path,
):
    tenant_dir = tmp_path / "tenant_a"
    workspace_dir = tenant_dir / "workspaces" / "agent_a"
    workspace_dir.mkdir(parents=True)

    with patch("swe.security.tenant_path_boundary.WORKING_DIR", tmp_path):
        with tenant_context(
            tenant_id="tenant_a",
            workspace_dir=workspace_dir,
        ):
            resolved = _resolve_file_path("notes.txt")

    assert resolved == str(workspace_dir / "notes.txt")


def test_current_tool_base_dir_fails_closed_on_workspace_boundary_violation(
    tmp_path: Path,
):
    tenant_dir = tmp_path / "tenant_a"
    tenant_dir.mkdir(parents=True)
    outside_workspace = tmp_path / "outside" / "agent_a"
    outside_workspace.mkdir(parents=True)

    with patch("swe.security.tenant_path_boundary.WORKING_DIR", tmp_path):
        with tenant_context(
            tenant_id="tenant_a",
            workspace_dir=outside_workspace,
        ):
            with pytest.raises(PathTraversalError):
                get_current_tool_base_dir()


def test_file_io_resolve_path_denies_relative_traversal_outside_tenant(
    tmp_path: Path,
):
    tenant_dir = tmp_path / "tenant_a"
    workspace_dir = tenant_dir / "workspaces" / "agent_a"
    workspace_dir.mkdir(parents=True)

    with patch("swe.security.tenant_path_boundary.WORKING_DIR", tmp_path):
        with tenant_context(tenant_id="tenant_a", workspace_dir=workspace_dir):
            with pytest.raises(PathTraversalError):
                _resolve_file_path("../../../../outside.png")


def test_file_io_resolve_path_denies_absolute_path_outside_tenant(
    tmp_path: Path,
):
    tenant_dir = tmp_path / "tenant_a"
    workspace_dir = tenant_dir / "workspaces" / "agent_a"
    workspace_dir.mkdir(parents=True)
    outside = tmp_path / "outside.png"

    with patch("swe.security.tenant_path_boundary.WORKING_DIR", tmp_path):
        with tenant_context(tenant_id="tenant_a", workspace_dir=workspace_dir):
            with pytest.raises(AbsolutePathDeniedError):
                _resolve_file_path(str(outside))
