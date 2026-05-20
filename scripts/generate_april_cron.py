# -*- coding: utf-8 -*-
"""生成4月定时任务数据（环比下降场景）.

用于验证 BusinessOverview 页面环比下降场景的展示。
- 4月数据量大（上一周期）
- 5月数据量小（当前周期）
"""

import asyncio
import random
import sys
import uuid
from datetime import datetime, timedelta

sys.path.insert(0, "src")
from swe.envs import load_envs_into_environ

load_envs_into_environ()
from swe.database import get_database_config, DatabaseConnection

SOURCE_IDS = [
    "CMSJY",
    "UPPCLAW",
    "copilotClaw",
    "ruice",
    "privatebanking",
    "SZLS",
]
BBK_IDS = [
    ("100", "总行"),
    ("200", "北京分行"),
    ("201", "上海分行"),
    ("202", "深圳分行"),
    ("203", "广州分行"),
]


async def generate_april_cron():
    db_config = get_database_config()
    db = DatabaseConnection(db_config)
    await db.connect()

    # 生成jobs
    jobs = []
    for i in range(15):
        bbk_code, bbk_name = random.choice(BBK_IDS)
        source_id = random.choice(SOURCE_IDS)
        tenant_id = f"tenant_{bbk_code}"
        user_id = f"user_{bbk_code}_{random.randint(100,999)}"

        jobs.append(
            {
                "id": f"cron-apr-{uuid.uuid4().hex[:12]}",
                "name": f"{bbk_name}日报任务",
                "tenant_id": tenant_id,
                "tenant_name": f"{bbk_name}经理",
                "bbk_id": bbk_code,
                "source_id": source_id,
                "enabled": 1,
                "task_type": "agent",
                "cron_expr": "0 9 * * *",
                "timezone": "Asia/Shanghai",
                "channel": "console",
                "target_user_id": user_id,
                "target_session_id": "",
                "timeout_seconds": 7200,
                "max_concurrency": 1,
                "misfire_grace_seconds": 300,
                "text_content": "",
                "request_input": "生成日报",
                "creator_user_id": user_id,
                "task_chat_id": "",
                "task_session_id": "",
                "meta": "",
                "status": "active",
                "pause_reason": "",
                "created_at": "2026-03-01 10:00:00",
            },
        )

    # Insert jobs
    job_sql = """
        INSERT INTO swe_cron_jobs
        (id, name, tenant_id, tenant_name, bbk_id, source_id, enabled, task_type,
         cron_expr, timezone, channel, target_user_id, target_session_id,
         timeout_seconds, max_concurrency, misfire_grace_seconds,
         text_content, request_input, creator_user_id, task_chat_id, task_session_id,
         meta, status, pause_reason, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    for job in jobs:
        await db.execute(job_sql, tuple(job.values()))
    print(f"Inserted {len(jobs)} jobs")

    # 生成4月执行记录（每天150条，共约2550条）
    start = datetime(2026, 4, 1)
    end = datetime(2026, 4, 18)
    current = start

    exec_count = 0
    while current <= end:
        daily = 150 + random.randint(-30, 30)

        for _ in range(daily):
            job = random.choice(jobs)
            actual = current.replace(
                hour=random.randint(0, 23),
                minute=random.randint(0, 59),
                second=random.randint(0, 59),
            )
            scheduled = actual - timedelta(seconds=random.randint(0, 60))
            duration = random.randint(10000, 600000)
            status = random.choices(
                ["success", "error", "timeout"],
                weights=[0.85, 0.10, 0.05],
            )[0]

            exec_sql = """
                INSERT INTO swe_cron_executions
                (job_id, job_name, tenant_id, scheduled_time, actual_time, end_time,
                 duration_ms, status, error_message, instance_id, executor_leader,
                 is_manual, trace_id, session_id, input_snapshot, output_preview, meta)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            await db.execute(
                exec_sql,
                (
                    job["id"],
                    job["name"],
                    job["tenant_id"],
                    scheduled.strftime("%Y-%m-%d %H:%M:%S"),
                    actual.strftime("%Y-%m-%d %H:%M:%S"),
                    (actual + timedelta(milliseconds=duration)).strftime(
                        "%Y-%m-%d %H:%M:%S",
                    ),
                    duration,
                    status,
                    "" if status == "success" else "Timeout",
                    f"inst-{random.randint(1,3):02d}",
                    "",
                    0,
                    f"trace-{uuid.uuid4().hex[:16]}",
                    f"sess-{uuid.uuid4().hex[:16]}",
                    "",
                    "",
                    "",
                ),
            )
            exec_count += 1

        current += timedelta(days=1)

    print(f"Inserted {exec_count} April cron executions")

    # 生成5月执行记录（每天50条，共约850条，比4月少）
    start = datetime(2026, 5, 1)
    end = datetime(2026, 5, 18)
    current = start

    exec_may = 0
    while current <= end:
        daily = 50 + random.randint(-10, 10)

        for _ in range(daily):
            job = random.choice(jobs)
            actual = current.replace(
                hour=random.randint(0, 23),
                minute=random.randint(0, 59),
                second=random.randint(0, 59),
            )
            scheduled = actual - timedelta(seconds=random.randint(0, 60))
            duration = random.randint(10000, 300000)
            status = random.choices(
                ["success", "error"],
                weights=[0.90, 0.10],
            )[0]

            await db.execute(
                exec_sql,
                (
                    job["id"],
                    job["name"],
                    job["tenant_id"],
                    scheduled.strftime("%Y-%m-%d %H:%M:%S"),
                    actual.strftime("%Y-%m-%d %H:%M:%S"),
                    (actual + timedelta(milliseconds=duration)).strftime(
                        "%Y-%m-%d %H:%M:%S",
                    ),
                    duration,
                    status,
                    "" if status == "success" else "Error",
                    f"inst-{random.randint(1,2):02d}",
                    "",
                    0,
                    f"trace-{uuid.uuid4().hex[:16]}",
                    f"sess-{uuid.uuid4().hex[:16]}",
                    "",
                    "",
                    "",
                ),
            )
            exec_may += 1

        current += timedelta(days=1)

    print(f"Inserted {exec_may} May cron executions")

    # 验证
    apr = await db.fetch_one(
        "SELECT COUNT(*) as c FROM swe_cron_executions WHERE actual_time >= '2026-04-01' AND actual_time < '2026-05-01'",
    )
    may = await db.fetch_one(
        "SELECT COUNT(*) as c FROM swe_cron_executions WHERE actual_time >= '2026-05-01' AND actual_time < '2026-06-01'",
    )

    print(f"\nApril cron: {apr['c']}")
    print(f"May cron: {may['c']}")
    print(f"Growth: {((may['c'] - apr['c']) / apr['c'] * 100):.1f}%")

    await db.close()


asyncio.run(generate_april_cron())
