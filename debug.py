# -*- coding: utf-8 -*-
from swe.cli.cron_cmd import list_jobs
from swe.cli.app_cmd import app_cmd

if __name__ == "__main__":
    app_cmd(
        host="0.0.0.0",
        port=8088,
        reload=True,
        workers=1,
        log_level="debug",
        hide_access_paths=tuple("/console/push-messages"),
    )
