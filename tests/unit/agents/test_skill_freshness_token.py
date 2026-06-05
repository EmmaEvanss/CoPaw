# -*- coding: utf-8 -*-

import os
from pathlib import Path

from swe.agents.skills_manager import get_skill_freshness_token


def _set_mtime(path: Path, timestamp: float) -> None:
    os.utime(path, (timestamp, timestamp))


def test_get_skill_freshness_token_ignores_directory_mtimes_from_ignored_artifacts(
    tmp_path: Path,
) -> None:
    skill_dir = tmp_path / "demo-skill"
    references_dir = skill_dir / "references"
    ignored_dir = references_dir / "__pycache__"
    references_dir.mkdir(parents=True)
    ignored_dir.mkdir(parents=True)

    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text(
        "---\nname: demo-skill\ndescription: demo\n---\n",
        encoding="utf-8",
    )
    notes_md = references_dir / "notes.md"
    notes_md.write_text("real content", encoding="utf-8")
    ignored_file = ignored_dir / "notes.cpython-312.pyc"
    ignored_file.write_bytes(b"compiled")

    _set_mtime(skill_md, 100.0)
    _set_mtime(notes_md, 200.0)
    _set_mtime(ignored_file, 800.0)
    _set_mtime(ignored_dir, 850.0)
    _set_mtime(references_dir, 900.0)
    _set_mtime(skill_dir, 950.0)

    assert get_skill_freshness_token(skill_dir) == 200.0
