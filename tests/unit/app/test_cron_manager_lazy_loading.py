# -*- coding: utf-8 -*-
"""Regression tests for CronManager lazy imports."""

import subprocess
import sys


def test_importing_cron_manager_does_not_import_heavy_runtime_modules():
    """CronManager import should not drag full app bootstrap modules."""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; "
                "import swe.app.crons.manager; "
                "raise SystemExit("
                "0 if 'swe.app._app' not in sys.modules "
                "and not any(name.startswith('swe.app.workspace') for name in sys.modules) "
                "and 'swe.app.multi_agent_manager' not in sys.modules "
                "and 'swe.app.runner.runner' not in sys.modules "
                "and 'swe.agents.react_agent' not in sys.modules "
                "else 1)"
            ),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout
