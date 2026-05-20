# -*- coding: utf-8 -*-
"""生成环比下降测试数据.

用于验证 BusinessOverview 页面环比下降场景的展示。
基于现有 generate_cron_test_data.py 复用配置。
设计思路：
- 5月已有数据（上一周期，数据量大）
- 只生成6月数据（当前周期，数据量小），实现环比下降

使用方法：
    python scripts/generate_growth_down_data.py
"""

import asyncio
import json
import os
import random
import sys
import uuid
from datetime import datetime, timedelta

# 添加路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# 加载用户配置的环境变量
from swe.envs import load_envs_into_environ

load_envs_into_environ()

from swe.database import get_database_config, DatabaseConnection

# ===== 复用 generate_cron_test_data.py 的配置 =====

SOURCE_IDS = [
    "CMSJY",  # 远程RM助手Claw
    "UPPCLAW",  # 智像助手CLAW
    "copilotClaw",  # 数据赋能助手CLAW
    "ruice",  # 睿策助手Claw
    "privatebanking",  # 私行助手Claw
    "SZLS",  # 数智零售Claw
]

BBK_IDS = [
    ("100", "总行"),
    ("200", "北京分行"),
    ("201", "上海分行"),
    ("202", "深圳分行"),
    ("203", "广州分行"),
]

# 技能列表 - 用于 spans 数据
SKILL_NAMES = [
    "数据查询",
    "报表生成",
    "客户画像",
    "风险分析",
    "营销推荐",
    "文档处理",
    "知识检索",
    "代码辅助",
]

# 任务模板 - 复用
TASK_TEMPLATES = [
    (
        "每日存款到期提醒",
        "agent",
        "0 9 * * *",
        "",
        "查询今日到期的存款客户名单并发送提醒",
    ),
    ("周度业务报表生成", "agent", "0 8 * * 1", "", "生成上周业务汇总报表"),
    ("月度风险评估", "agent", "0 10 1 * *", "", "执行月度风险评估分析"),
    (
        "每日市场行情播报",
        "text",
        "30 8 * * *",
        "请播报今日A股市场早盘概况",
        "",
    ),
    ("客户画像更新", "agent", "0 2 * * *", "", "更新VIP客户画像数据"),
    ("存款营销日报", "agent", "0 18 * * *", "", "生成今日存款营销日报"),
    ("客户回访提醒", "agent", "0 9 * * *", "", "查询需要回访的客户列表"),
    ("理财到期通知", "agent", "0 10 * * *", "", "查询本周到期理财产品客户"),
    ("信贷审批周报", "agent", "0 17 * * 5", "", "生成本周信贷审批统计周报"),
    (
        "外汇行情监控",
        "text",
        "*/30 9-17 * * 1-5",
        "请汇报当前主要外汇对汇率变动情况",
        "",
    ),
]

# 执行状态 - 复用
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

OUTPUT_PREVIEWS = [
    "查询到{count}笔即将到期存款，总金额{amount}亿元",
    "今日新增存款客户{count}户，存款金额{amount}万元",
    "报表生成完成：新增用户{count}人，活跃用户{active}人",
]


def choose_status() -> str:
    """根据概率选择执行状态."""
    r = random.random()
    cumulative = 0
    for status, prob in EXECUTION_STATUSES:
        cumulative += prob
        if r <= cumulative:
            return status
    return "success"


def generate_cron_jobs(count: int = 15) -> list[dict]:
    """生成定时任务定义."""
    jobs = []
    now = datetime.now()

    for i in range(count):
        bbk_code, bbk_name = random.choice(BBK_IDS)
        source_id = random.choice(SOURCE_IDS)
        template = random.choice(TASK_TEMPLATES)
        name_prefix, task_type, cron_expr, text_content, request_input = (
            template
        )

        tenant_id = f"tenant_{bbk_code}"
        user_id = f"user_{bbk_code}_{random.randint(100, 999)}"
        user_name = f"{bbk_name}{random.choice(['经理', '主管', '分析师'])}"

        job_id = f"cron-gd-{uuid.uuid4().hex[:12]}"
        created_at = now - timedelta(days=random.randint(30, 60))

        jobs.append(
            {
                "id": job_id,
                "name": f"{bbk_name}{name_prefix}",
                "tenant_id": tenant_id,
                "tenant_name": user_name,
                "bbk_id": bbk_code,
                "source_id": source_id,
                "enabled": 1,
                "task_type": task_type,
                "cron_expr": cron_expr,
                "timezone": "Asia/Shanghai",
                "channel": random.choice(["console", "webhook"]),
                "target_user_id": user_id,
                "target_session_id": "",
                "timeout_seconds": 7200,
                "max_concurrency": 1,
                "misfire_grace_seconds": 300,
                "text_content": text_content,
                "request_input": request_input,
                "creator_user_id": user_id,
                "task_chat_id": "",
                "task_session_id": "",
                "meta": "",
                "status": "active",
                "pause_reason": "",
                "created_at": created_at.strftime("%Y-%m-%d %H:%M:%S"),
            },
        )

    return jobs


def generate_cron_executions(
    jobs: list[dict],
    start_date: str = "2026-06-01",
    end_date: str = "2026-06-17",
    executions_per_day: int = 80,
) -> list[dict]:
    """生成定时任务执行历史（数据量较少，实现环比下降）."""
    executions = []
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    current = start

    active_jobs = [
        j for j in jobs if j["enabled"] == 1 and j["status"] == "active"
    ]

    while current <= end:
        daily_count = executions_per_day + random.randint(-15, 15)

        for _ in range(daily_count):
            job = random.choice(active_jobs)
            hour = random.randint(0, 23)
            minute = random.randint(0, 59)
            second = random.randint(0, 59)
            actual_time = current.replace(
                hour=hour,
                minute=minute,
                second=second,
            )
            scheduled_time = actual_time - timedelta(
                seconds=random.randint(0, 60),
            )
            duration_ms = random.randint(10000, 600000)
            end_time = actual_time + timedelta(milliseconds=duration_ms)
            status = choose_status()
            error_message = (
                random.choice(ERROR_MESSAGES)
                if status in ("error", "timeout")
                else ""
            )

            if status == "success":
                preview_template = random.choice(OUTPUT_PREVIEWS)
                output_preview = preview_template.format(
                    count=random.randint(5, 30),
                    amount=round(random.uniform(0.5, 3.0), 1),
                    active=random.randint(50, 500),
                )
            else:
                output_preview = ""

            executions.append(
                {
                    "job_id": job["id"],
                    "job_name": job["name"],
                    "tenant_id": job["tenant_id"],
                    "scheduled_time": scheduled_time.strftime(
                        "%Y-%m-%d %H:%M:%S",
                    ),
                    "actual_time": actual_time.strftime("%Y-%m-%d %H:%M:%S"),
                    "end_time": end_time.strftime("%Y-%m-%d %H:%M:%S"),
                    "duration_ms": duration_ms,
                    "status": status,
                    "error_message": error_message,
                    "instance_id": f"instance-{random.randint(1, 5):03d}",
                    "executor_leader": "",
                    "is_manual": 0,
                    "trace_id": f"trace-{uuid.uuid4().hex[:16]}",
                    "session_id": f"sess-{uuid.uuid4().hex[:16]}",
                    "input_snapshot": "",
                    "output_preview": output_preview[:500],
                    "meta": "",
                },
            )

        current += timedelta(days=1)

    return executions


def generate_traces_for_period(
    start_date: datetime,
    end_date: datetime,
    traces_per_day: int,
) -> tuple[list[tuple], list[tuple]]:
    """生成 trace 和 span 数据."""
    traces_data = []
    spans_data = []
    current = start_date

    while current < end_date:
        daily_count = traces_per_day + random.randint(-10, 10)

        for _ in range(daily_count):
            source_id = random.choice(SOURCE_IDS)
            bbk_code, bbk_name = random.choice(BBK_IDS)
            user_id = f"user_{bbk_code}_{random.randint(100, 999)}"
            user_name = f"{bbk_name}用户{random.randint(1, 20)}"

            trace_id = str(uuid.uuid4())
            session_id = str(uuid.uuid4())

            hour = random.randint(8, 20)
            minute = random.randint(0, 59)
            second = random.randint(0, 59)
            start_time = current.replace(
                hour=hour,
                minute=minute,
                second=second,
            )
            duration_seconds = random.randint(30, 180)
            end_time = start_time + timedelta(seconds=duration_seconds)
            duration_ms = duration_seconds * 1000

            input_tokens = random.randint(100, 1500)
            output_tokens = random.randint(100, 800)
            total_tokens = input_tokens + output_tokens

            skills_used_count = random.randint(0, 2)
            skills_used = (
                random.sample(SKILL_NAMES, skills_used_count)
                if skills_used_count > 0
                else []
            )

            traces_data.append(
                (
                    trace_id,
                    source_id,
                    user_id,
                    user_name,
                    bbk_code,
                    session_id,
                    "console",
                    start_time,
                    end_time,
                    duration_ms,
                    "claude-3-5-sonnet",
                    input_tokens,
                    output_tokens,
                    total_tokens,
                    "[]",
                    json.dumps(skills_used),
                    "completed",
                    None,
                    f"测试请求 - {start_time.strftime('%Y-%m-%d')}",
                ),
            )

            for skill_name in skills_used:
                span_id = str(uuid.uuid4())
                skill_start = start_time + timedelta(
                    seconds=random.randint(5, 30),
                )
                skill_duration = random.randint(100, 3000)
                skill_end = skill_start + timedelta(
                    milliseconds=skill_duration,
                )

                spans_data.append(
                    (
                        span_id,
                        trace_id,
                        source_id,
                        f"skill_{skill_name}",
                        "skill_invocation",
                        skill_start,
                        skill_end,
                        skill_duration,
                        user_id,
                        user_name,
                        bbk_code,
                        session_id,
                        "console",
                        None,
                        None,
                        None,
                        None,
                        skill_name,
                        None,
                        None,
                        None,
                        None,
                    ),
                )

        current += timedelta(days=1)

    return traces_data, spans_data


async def insert_cron_jobs(db: DatabaseConnection, jobs: list[dict]) -> None:
    """插入定时任务."""
    sql = """
        INSERT INTO swe_cron_jobs
        (id, name, tenant_id, tenant_name, bbk_id, source_id, enabled, task_type,
         cron_expr, timezone, channel, target_user_id, target_session_id,
         timeout_seconds, max_concurrency, misfire_grace_seconds,
         text_content, request_input, creator_user_id, task_chat_id, task_session_id,
         meta, status, pause_reason, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    for job in jobs:
        await db.execute(
            sql,
            (
                job["id"],
                job["name"],
                job["tenant_id"],
                job["tenant_name"],
                job["bbk_id"],
                job["source_id"],
                job["enabled"],
                job["task_type"],
                job["cron_expr"],
                job["timezone"],
                job["channel"],
                job["target_user_id"],
                job["target_session_id"],
                job["timeout_seconds"],
                job["max_concurrency"],
                job["misfire_grace_seconds"],
                job["text_content"],
                job["request_input"],
                job["creator_user_id"],
                job["task_chat_id"],
                job["task_session_id"],
                job["meta"],
                job["status"],
                job["pause_reason"],
                job["created_at"],
            ),
        )
    print(f"[OK] 插入 {len(jobs)} 条定时任务")


async def insert_cron_executions(
    db: DatabaseConnection,
    executions: list[dict],
) -> None:
    """插入执行记录."""
    sql = """
        INSERT INTO swe_cron_executions
        (job_id, job_name, tenant_id, scheduled_time, actual_time, end_time,
         duration_ms, status, error_message, instance_id, executor_leader,
         is_manual, trace_id, session_id, input_snapshot, output_preview, meta)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    batch_size = 50
    for i in range(0, len(executions), batch_size):
        batch = executions[i : i + batch_size]
        for exec_item in batch:
            await db.execute(
                sql,
                (
                    exec_item["job_id"],
                    exec_item["job_name"],
                    exec_item["tenant_id"],
                    exec_item["scheduled_time"],
                    exec_item["actual_time"],
                    exec_item["end_time"],
                    exec_item["duration_ms"],
                    exec_item["status"],
                    exec_item["error_message"],
                    exec_item["instance_id"],
                    exec_item["executor_leader"],
                    exec_item["is_manual"],
                    exec_item["trace_id"],
                    exec_item["session_id"],
                    exec_item["input_snapshot"],
                    exec_item["output_preview"],
                    exec_item["meta"],
                ),
            )
        print(f"[OK] 插入执行记录 {i + len(batch)}/{len(executions)}")


async def insert_traces(db: DatabaseConnection, traces: list[tuple]) -> None:
    """插入 trace 数据."""
    sql = """
        INSERT INTO swe_tracing_traces
        (trace_id, source_id, user_id, user_name, bbk_id, session_id, channel,
         start_time, end_time, duration_ms, model_name,
         total_input_tokens, total_output_tokens, total_tokens,
         tools_used, skills_used, status, error, user_message)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    batch_size = 50
    for i in range(0, len(traces), batch_size):
        batch = traces[i : i + batch_size]
        await db.execute_many(sql, batch)
        print(f"[OK] 插入 trace {i + len(batch)}/{len(traces)}")


async def insert_spans(db: DatabaseConnection, spans: list[tuple]) -> None:
    """插入 span 数据."""
    sql = """
        INSERT INTO swe_tracing_spans
        (span_id, trace_id, source_id, name, event_type, start_time, end_time, duration_ms,
         user_id, user_name, bbk_id, session_id, channel, model_name,
         input_tokens, output_tokens, tool_name, skill_name, mcp_server,
         tool_input, tool_output, error)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    batch_size = 50
    for i in range(0, len(spans), batch_size):
        batch = spans[i : i + batch_size]
        await db.execute_many(sql, batch)
        print(f"[OK] 插入 span {i + len(batch)}/{len(spans)}")


async def verify_data(db: DatabaseConnection) -> None:
    """验证插入的数据."""
    print("\n=== 数据验证 ===")

    # Traces 每日统计
    trace_stats = await db.fetch_all("""
        SELECT DATE(start_time) as date, COUNT(*) as count
        FROM swe_tracing_traces
        WHERE source_id IN ('CMSJY', 'UPPCLAW', 'copilotClaw', 'ruice', 'privatebanking', 'SZLS')
          AND start_time >= '2026-06-01'
        GROUP BY DATE(start_time)
        ORDER BY date
    """)
    print("Traces 每日统计:")
    for row in trace_stats:
        print(f"  {row['date']}: {row['count']} 条")

    # Spans skill_invocation 统计
    skill_stats = await db.fetch_all("""
        SELECT DATE(start_time) as date, COUNT(*) as count
        FROM swe_tracing_spans
        WHERE event_type = 'skill_invocation'
          AND source_id IN ('CMSJY', 'UPPCLAW', 'copilotClaw', 'ruice', 'privatebanking', 'SZLS')
          AND start_time >= '2026-06-01'
        GROUP BY DATE(start_time)
        ORDER BY date
    """)
    print("Skills 每日统计:")
    for row in skill_stats:
        print(f"  {row['date']}: {row['count']} 条")

    # Cron executions 统计
    cron_stats = await db.fetch_all("""
        SELECT DATE(actual_time) as date, COUNT(*) as count
        FROM swe_cron_executions e
        INNER JOIN swe_cron_jobs j ON e.job_id = j.id
        WHERE j.id LIKE 'cron-gd-%'
          AND e.actual_time >= '2026-06-01'
        GROUP BY DATE(actual_time)
        ORDER BY date
    """)
    print("Cron executions 每日统计:")
    for row in cron_stats:
        print(f"  {row['date']}: {row['count']} 条")


async def main():
    """主函数."""
    print("=" * 60)
    print("环比下降测试数据生成器")
    print("只生成6月数据（数据量少），与5月已有数据对比实现环比下降")
    print("=" * 60)

    # 时间配置：6月
    june_start = datetime(2026, 6, 1)
    june_end = datetime(2026, 6, 18)

    # 数据量配置（较少，实现环比下降）
    # 6月数据量约为5月数据量的40-50%
    traces_per_day = 80  # 每天约80条 trace
    executions_per_day = 80  # 每天约80条 cron execution

    print(
        f"\n时间范围: {june_start.strftime('%Y-%m-%d')} ~ {june_end.strftime('%Y-%m-%d')}",
    )
    print(f"每日 traces: ~{traces_per_day}")
    print(f"每日 cron executions: ~{executions_per_day}")

    # 连接数据库
    db_config = get_database_config()
    db = DatabaseConnection(db_config)

    try:
        await db.connect()
        if not db.is_connected:
            print("\n数据库连接失败")
            return

        print("\n数据库连接成功")

        # 生成数据
        print("\n=== 生成6月数据 ===")

        # 1. Traces 和 Spans
        traces, spans = generate_traces_for_period(
            june_start,
            june_end,
            traces_per_day,
        )
        print(f"生成 {len(traces)} traces, {len(spans)} spans")

        # 2. Cron 数据
        cron_jobs = generate_cron_jobs(15)
        cron_executions = generate_cron_executions(
            cron_jobs,
            "2026-06-01",
            "2026-06-17",
            executions_per_day,
        )
        print(
            f"生成 {len(cron_jobs)} cron jobs, {len(cron_executions)} executions",
        )

        # 插入数据
        print("\n=== 插入数据 ===")
        await insert_traces(db, traces)
        await insert_spans(db, spans)
        await insert_cron_jobs(db, cron_jobs)
        await insert_cron_executions(db, cron_executions)

        # 验证
        await verify_data(db)

        print("\n" + "=" * 60)
        print("完成！")
        print("=" * 60)
        print("\n验证说明:")
        print("  在 BusinessOverview 页面选择日期 2026-06-01 ~ 2026-06-17")
        print("  环比将对比5月数据，预期显示下降趋势")

    except Exception as e:
        print(f"\n执行失败: {e}")
        import traceback

        traceback.print_exc()
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())
