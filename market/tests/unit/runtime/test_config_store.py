# -*- coding: utf-8 -*-
"""market runtime config store 回归测试。"""

from __future__ import annotations

import json


def test_load_root_config_keeps_legacy_scope_directory_untouched(tmp_path):
    from market.runtime.config_store import load_root_config
    from market.runtime.context import encode_scope_id

    canonical_scope_id = encode_scope_id("tenant-a", "source-a")
    canonical_scope_dir = tmp_path / canonical_scope_id
    legacy_scope_dir = tmp_path / f"scope.v1.{canonical_scope_id}"
    canonical_scope_dir.mkdir(parents=True)
    legacy_scope_dir.mkdir(parents=True)
    (canonical_scope_dir / "config.json").write_text(
        json.dumps(
            {
                "agents": {
                    "active_agent": "default",
                    "profiles": {
                        "default": {
                            "id": "default",
                            "workspace_dir": str(
                                canonical_scope_dir / "workspaces" / "default",
                            ),
                            "enabled": True,
                        },
                    },
                },
            },
        ),
        encoding="utf-8",
    )

    config = load_root_config(tmp_path, canonical_scope_id)

    assert config.agents.active_agent == "default"
    assert legacy_scope_dir.exists()
    assert (canonical_scope_dir / "config.json").exists()
    assert config.agents.profiles["default"].workspace_dir == str(
        canonical_scope_dir / "workspaces" / "default",
    )
