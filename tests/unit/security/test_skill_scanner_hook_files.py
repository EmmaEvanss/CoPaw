# -*- coding: utf-8 -*-
from __future__ import annotations

from swe.security.skill_scanner.scanner import SkillScanner


def test_skill_scanner_discovers_hooks_and_scripts(tmp_path) -> None:
    skill_root = tmp_path / "demo"
    (skill_root / "hooks").mkdir(parents=True)
    (skill_root / "scripts").mkdir()
    (skill_root / "SKILL.md").write_text(
        "---\nname: demo\ndescription: test\n---\n",
        encoding="utf-8",
    )
    (skill_root / "hooks" / "hooks.json").write_text(
        '{"enabled": true}',
        encoding="utf-8",
    )
    (skill_root / "scripts" / "check.py").write_text(
        "print('{}')\n",
        encoding="utf-8",
    )

    files = SkillScanner(analyzers=[])._discover_files(skill_root)

    assert {item.relative_path for item in files} >= {
        "hooks/hooks.json",
        "scripts/check.py",
    }
