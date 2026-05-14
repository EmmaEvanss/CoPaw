# -*- coding: utf-8 -*-
"""Tests for the injected Python runtime tenant path guard."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from swe.security.python_runtime_path_guard import (
    prepare_python_runtime_path_guard_env,
)


def test_runtime_guard_allows_imports_from_existing_pythonpath_roots(
    tmp_path: Path,
) -> None:
    """Editable/local packages outside the tenant root must remain importable."""
    tenant_root = tmp_path / "tenant"
    tenant_root.mkdir()
    package_root = tmp_path / "package_src"
    package_root.mkdir()
    (package_root / "outside_package.py").write_text(
        "VALUE = 'imported from package root'\n",
        encoding="utf-8",
    )

    env = os.environ.copy()
    env["PYTHONPATH"] = str(package_root)
    guard_dir = prepare_python_runtime_path_guard_env(
        env,
        tenant_root=tenant_root,
        base_dir=tenant_root,
    )

    with guard_dir:
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import outside_package; print(outside_package.VALUE)",
            ],
            cwd=tenant_root,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "imported from package root"


def test_runtime_guard_allows_trusted_swe_entrypoint_to_read_trusted_file(
    tmp_path: Path,
) -> None:
    """Trusted SWE launchers may read explicit app metadata files."""
    tenant_root = tmp_path / "tenant"
    tenant_root.mkdir()
    config_path = tmp_path / ".swe" / "config.json"
    config_path.parent.mkdir()
    config_path.write_text(
        '{"last_api": {"host": "127.0.0.1", "port": 8088}}\n',
        encoding="utf-8",
    )
    trusted_bin = tmp_path / "venv" / "Scripts"
    trusted_bin.mkdir(parents=True)
    swe_entrypoint = trusted_bin / "swe"
    swe_entrypoint.write_text(
        (
            "from pathlib import Path\n"
            f"path = Path({str(config_path)!r})\n"
            "print(path.is_file())\n"
            "print(path.read_text(encoding='utf-8'))\n"
        ),
        encoding="utf-8",
    )

    env = os.environ.copy()
    guard_dir = prepare_python_runtime_path_guard_env(
        env,
        tenant_root=tenant_root,
        base_dir=tenant_root,
        trusted_paths=[config_path],
        trusted_entrypoint_roots=[trusted_bin],
    )

    with guard_dir:
        result = subprocess.run(
            [sys.executable, str(swe_entrypoint)],
            cwd=tenant_root,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    assert result.returncode == 0, result.stderr
    assert "True" in result.stdout
    assert '"last_api"' in result.stdout


def test_runtime_guard_denies_untrusted_python_access_to_trusted_file(
    tmp_path: Path,
) -> None:
    """Trusted metadata files are not a general escape hatch for python -c."""
    tenant_root = tmp_path / "tenant"
    tenant_root.mkdir()
    config_path = tmp_path / ".swe" / "config.json"
    config_path.parent.mkdir()
    config_path.write_text('{"secretish": true}\n', encoding="utf-8")
    trusted_bin = tmp_path / "venv" / "Scripts"
    trusted_bin.mkdir(parents=True)

    env = os.environ.copy()
    guard_dir = prepare_python_runtime_path_guard_env(
        env,
        tenant_root=tenant_root,
        base_dir=tenant_root,
        trusted_paths=[config_path],
        trusted_entrypoint_roots=[trusted_bin],
    )

    with guard_dir:
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                f"from pathlib import Path; print(Path({str(config_path)!r}).read_text())",
            ],
            cwd=tenant_root,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    assert result.returncode != 0
    assert "outside the allowed workspace" in result.stderr
