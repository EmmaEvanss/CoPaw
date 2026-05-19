# -*- coding: utf-8 -*-
"""直接插入定时任务测试数据到数据库."""

import asyncio
import random
import sys
import uuid
from datetime import datetime, timedelta

sys.path.insert(0, "src")

from swe.envs import load_envs_into_environ

load_envs_into_environ()

from swe.database import get_database_config, DatabaseConnection

# 数据配置
SOURCE_IDS = ["CMSJY", "UPPCLAW", "copilotClaw", "ruice", "privatebanking", "SZLS"]
BBK_IDS = [
    ("100", "总行"),
    ("200", "北京分行"),
    ("201", "上海分行"),
    ("202", "深圳分行"),
    ("203", "广州分行"),
]

TASK_TEMPLATES = [
    ("每日存款到期提醒", "agent", "0 9 * * *", "", "查询今日到期的存款客户名单"),
    ("周度业务报表生成", "agent", "0 8 * * 1", "", "生成上周业务汇总报表"),
    ("月度风险评估", "agent", "0 10 1 * *", "", "执行月度风险评估分析"),
    ("每日市场行情播报", "text", "30 8 * * *", "请播报今日A股市场早盘概况", ""),
    ("客户画像更新", "agent", "0 2 * * *", "", "更新VIP客户画像数据"),
    ("存款营销日报", "agent", "0 18 * * *", "", "生成今日存款营销日报"),
    ("客户回访提醒", "agent", "0 9 * * *", "", "查询需要回访的客户列表"),
    ("理财到期通知", "agent", "0 10 * * *", "", "查询本周到期理财产品客户"),
]

EXECUTION_STATUSES = [
    ("success", 0.85),
    ("error", 0.08),
    ("timeout", 0.03),
    ("cancelled", 0.02),
    ("skipped", 0.02),
]

ERROR_MESSAGES = [
    "LLM API 调用超时",
    "数据库连接池已满",
    "网络连接中断",
    "模型服务不可用",
]


def choose_status() -> str:
    """根据概率选择执行状态."""
    r = random.random()
    cumulative = 0.0
    for status, prob in EXECUTION_STATUSES:
        cumulative += prob
        if r <= cumulative:
            return status
    return "success"


async def insert_data() -> None:
    """插入测试数据到数据库."""
    db_config = get_database_config()
    db = DatabaseConnection(db_config)

    try:
        # 先连接数据库
        await db.connect()
        print("数据库连接成功")

        # 清理旧测试数据
        await db.execute(
            "DELETE FROM swe_cron_executions WHERE job_id LIKE 'cron-%'",
        )
        await db.execute("DELETE FROM swe_cron_jobs WHERE id LIKE 'cron-%'")
        print("已清理旧测试数据")

        # 生成任务定义
        jobs = []
        job_sql = """
            INSERT INTO swe_cron_jobs
            (id, name, tenant_id, tenant_name, bbk_id, source_id, enabled, task_type,
             cron_expr, timezone, channel, target_user_id, target_session_id,
             timeout_seconds, max_concurrency, misfire_grace_seconds,
             text_content, request_input, creator_user_id, task_chat_id, task_session_id,
             meta, status, pause_reason, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """

        now = datetime.now()
        for i in range(20):
            bbk_code, bbk_name = random.choice(BBK_IDS)
            source_id = random.choice(SOURCE_IDS)
            template = random.choice(TASK_TEMPLATES)

            tenant_id = f"tenant_{bbk_code}"
            user_id = f"user_{bbk_code}_{random.randint(100, 999)}"
            user_name = f"{bbk_name}{random.choice(['经理', '主管', '分析师'])}"
            job_id = f"cron-{uuid.uuid4().hex[:12]}"

            job_data = {
                "id": job_id,
                "name": f"{bbk_name}{template[0]}",
                "tenant_id": tenant_id,
                "tenant_name": user_name,
                "bbk_id": bbk_code,
                "source_id": source_id,
                "enabled": 1,
                "task_type": template[1],
                "cron_expr": template[2],
                "timezone": "Asia/Shanghai",
                "channel": "console",
                "target_user_id": user_id,
                "target_session_id": "",
                "timeout_seconds": 7200,
                "max_concurrency": 1,
                "misfire_grace_seconds": 300,
                "text_content": template[3],
                "request_input": template[4],
                "creator_user_id": user_id,
                "task_chat_id": "",
                "task_session_id": "",
                "meta": "",
                "status": "active",
                "pause_reason": "",
                "created_at": (now - timedelta(days=random.randint(5, 30))).strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
            }
            jobs.append(job_data)

            await db.execute(
                job_sql,
                (
                    job_data["id"],
                    job_data["name"],
                    job_data["tenant_id"],
                    job_data["tenant_name"],
                    job_data["bbk_id"],
                    job_data["source_id"],
                    job_data["enabled"],
                    job_data["task_type"],
                    job_data["cron_expr"],
                    job_data["timezone"],
                    job_data["channel"],
                    job_data["target_user_id"],
                    job_data["target_session_id"],
                    job_data["timeout_seconds"],
                    job_data["max_concurrency"],
                    job_data["misfire_grace_seconds"],
                    job_data["text_content"],
                    job_data["request_input"],
                    job_data["creator_user_id"],
                    job_data["task_chat_id"],
                    job_data["task_session_id"],
                    job_data["meta"],
                    job_data["status"],
                    job_data["pause_reason"],
                    job_data["created_at"],
                ),
            )

        print(f"已插入 {len(jobs)} 条任务定义")

        # 生成执行记录 (包含今天 2026-05-19)
        exec_sql = """
            INSERT INTO swe_cron_executions
            (job_id, job_name, tenant_id, scheduled_time, actual_time, end_time,
             duration_ms, status, error_message, instance_id, executor_leader,
             is_manual, trace_id, session_id, input_snapshot, output_preview, meta)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """

        # 时间范围: 2026-05-18 到 2026-05-20 (包含今天)
        start = datetime(2026, 5, 18)
        end = datetime(2026, 5, 20)
        current = start
        exec_count = 0

        while current <= end:
            daily_count = 250 + random.randint(-30, 30)
            for _ in range(daily_count):
                job = random.choice(jobs)
                hour = random.randint(0, 23)
                minute = random.randint(0, 59)
                second = random.randint(0, 59)
                actual_time = current.replace(
                    hour=hour, minute=minute, second=second
                )
                scheduled_time = actual_time - timedelta(
                    seconds=random.randint(0, 60)
                )
                duration_ms = random.randint(10000, 600000)
                end_time = actual_time + timedelta(milliseconds=duration_ms)
                status = choose_status()
                error_message = (
                    random.choice(ERROR_MESSAGES)
                    if status in ("error", "timeout")
                    else ""
                )

                await db.execute(
                    exec_sql,
                    (
                        job["id"],
                        job["name"],
                        job["tenant_id"],
                        scheduled_time.strftime("%Y-%m-%d %H:%M:%S"),
                        actual_time.strftime("%Y-%m-%d %H:%M:%S"),
                        end_time.strftime("%Y-%m-%d %H:%M:%S"),
                        duration_ms,
                        status,
                        error_message,
                        f"instance-{random.randint(1, 5):03d}",
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
            print(f"{current.strftime('%Y-%m-%d')}: {daily_count} 条执行记录")
            current += timedelta(days=1)

        print(f"总计插入 {exec_count} 条执行记录")

        # 验证数据
        row = await db.fetch_one(
            "SELECT COUNT(*) as count FROM swe_cron_jobs WHERE id LIKE 'cron-%'"
        )
        print(f"swe_cron_jobs 记录数: {row['count']}")
        row = await db.fetch_one(
            "SELECT COUNT(*) as count FROM swe_cron_executions WHERE job_id LIKE 'cron-%'"
        )
        print(f"swe_cron_executions 记录数: {row['count']}")

        # 检查今天的数据
        row = await db.fetch_one(
            """
            SELECT COUNT(*) as count
            FROM swe_cron_executions e
            INNER JOIN swe_cron_jobs j ON e.job_id = j.id
            WHERE DATE(e.actual_time) = '2026-05-19'
              AND j.status != 'deleted'
              AND j.deleted_at IS NULL
            """
        )
        print(f"2026-05-19 的有效执行记录数: {row['count']}")

        print("完成!")

    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(insert_data())