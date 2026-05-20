# -*- coding: utf-8 -*-
"""生成定时任务测试数据.

用于填充 swe_cron_jobs 和 swe_cron_executions 表，
验证定时任务概览页面的 UI 展示。

使用方法：
    python scripts/generate_cron_test_data.py
"""

import asyncio
import os
import random
import sys
import uuid
from datetime import datetime, timedelta

# 添加路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# 加载用户配置的环境变量（从 ~/.swe.secret/envs.json）
from swe.envs import load_envs_into_environ

load_envs_into_environ()

from swe.database import get_database_config, DatabaseConnection

# 测试数据配置 - 复用 swe_tracing_traces 的 source_id 和 bbk_id
SOURCE_IDS = [
    "CMSJY",  # 远程RM助手Claw
    "UPPCLAW",  # 智像助手CLAW
    "copilotClaw",  # 数据赋能助手CLAW
    "ruice",  # 睿策助手Claw
    "privatebanking",  # 私行助手Claw
    "SZLS",  # 数智零售Claw
]

# 与前端 console/src/constants/bbk.ts 保持一致
BBK_IDS = [
    ("100", "总行"),
    ("200", "北京分行"),
    ("201", "上海分行"),
    ("202", "深圳分行"),
    ("203", "广州分行"),
]

# 任务模板
TASK_TEMPLATES = [
    # (name_prefix, task_type, cron_expr, text_content, request_input)
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
    ("跨境业务日报", "agent", "0 18 * * *", "", "生成今日跨境业务处理日报"),
    ("同业授信监控", "agent", "0 9 * * *", "", "检查同业授信额度使用情况"),
    ("科技企业走访", "agent", "0 9 * * 1,3,5", "", "生成今日科技企业走访计划"),
    ("跨境结算监控", "agent", "0 10 * * *", "", "检查待处理的跨境结算业务"),
    ("政策速递", "text", "0 8 * * 1-5", "请汇总最新的金融政策动态", ""),
    ("普惠金融日报", "agent", "0 18 * * *", "", "生成今日普惠金融业务日报"),
    ("商户巡检计划", "agent", "0 8 * * 1", "", "生成本周商户巡检计划"),
    (
        "社保卡服务统计",
        "agent",
        "0 20 * * *",
        "",
        "统计今日社保卡业务办理情况",
    ),
    ("信用卡营销分析", "agent", "0 15 * * *", "", "分析今日信用卡营销数据"),
    ("反洗钱监控", "agent", "0 */4 * * *", "", "执行反洗钱交易监控检查"),
]

# 执行状态及概率
EXECUTION_STATUSES = [
    ("success", 0.85),
    ("error", 0.08),
    ("timeout", 0.03),
    ("cancelled", 0.02),
    ("skipped", 0.02),
]

# 错误消息模板
ERROR_MESSAGES = [
    "LLM API 调用超时",
    "数据库连接池已满",
    "网络连接中断",
    "模型服务不可用",
    "请求参数验证失败",
    "并发限制已达到上限",
    "存储空间不足",
    "认证令牌已过期",
]

# 输出预览模板
OUTPUT_PREVIEWS = [
    "查询到{count}笔即将到期存款，总金额{amount}亿元",
    "今日新增存款客户{count}户，存款金额{amount}万元",
    "报表生成完成：新增用户{count}人，活跃用户{active}人",
    "今日A股早盘{direction}，沪指{change}0.{point}%",
    "今日走访计划：{count}家科技企业，预计融资需求{amount}万元",
    "今日普惠贷款发放{count}笔，金额{amount}万元",
    "检查到{count}笔待处理交易，涉及金额{amount}万元",
    "客户回访完成：成功{success}户，待跟进{pending}户",
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


def generate_jobs(count: int = 20) -> list[dict]:
    """生成定时任务定义.

    Args:
        count: 任务数量

    Returns:
        任务列表
    """
    jobs = []
    now = datetime.now()

    for i in range(count):
        bbk_code, bbk_name = random.choice(BBK_IDS)
        source_id = random.choice(SOURCE_IDS)
        template = random.choice(TASK_TEMPLATES)
        name_prefix, task_type, cron_expr, text_content, request_input = (
            template
        )

        # 生成租户ID和用户ID
        tenant_id = f"tenant_{bbk_code}"
        user_id = f"user_{bbk_code}_{random.randint(100, 999)}"
        user_name = f"{bbk_name}{random.choice(['经理', '主管', '分析师', '客户经理'])}"

        job_id = f"cron-{uuid.uuid4().hex[:12]}"
        created_at = now - timedelta(days=random.randint(5, 30))

        job = {
            "id": job_id,
            "name": f"{bbk_name}{name_prefix}",
            "tenant_id": tenant_id,
            "tenant_name": user_name,
            "bbk_id": bbk_code,
            "source_id": source_id,
            "enabled": 1 if random.random() > 0.15 else 0,  # 85% 启用
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
            "status": "active" if random.random() > 0.1 else "paused",
            "pause_reason": "",
            "created_at": created_at.strftime("%Y-%m-%d %H:%M:%S"),
        }
        jobs.append(job)

    return jobs


def generate_executions(
    jobs: list[dict],
    start_date: str = "2026-05-18",
    end_date: str = "2026-05-31",
    executions_per_day: int = 250,
) -> list[dict]:
    """生成定时任务执行历史.

    Args:
        jobs: 任务列表
        start_date: 开始日期
        end_date: 结束日期
        executions_per_day: 每天执行记录数

    Returns:
        执行记录列表
    """
    executions = []
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    current = start

    # 只使用启用的任务
    active_jobs = [
        j for j in jobs if j["enabled"] == 1 and j["status"] == "active"
    ]
    if not active_jobs:
        active_jobs = jobs[:10]  # 至少使用前10个任务

    while current <= end:
        # 为每天生成指定数量的执行记录
        daily_count = executions_per_day + random.randint(-30, 30)

        for _ in range(daily_count):
            job = random.choice(active_jobs)

            # 生成执行时间
            hour = random.randint(0, 23)
            minute = random.randint(0, 59)
            second = random.randint(0, 59)
            actual_time = current.replace(
                hour=hour,
                minute=minute,
                second=second,
            )

            # 计划时间（可能比实际时间早几秒）
            scheduled_time = actual_time - timedelta(
                seconds=random.randint(0, 60),
            )

            # 执行时长
            duration_ms = random.randint(10000, 600000)  # 10秒到10分钟

            # 结束时间
            end_time = actual_time + timedelta(milliseconds=duration_ms)

            # 执行状态
            status = choose_status()

            # 错误消息
            error_message = (
                random.choice(ERROR_MESSAGES)
                if status in ("error", "timeout")
                else ""
            )

            # 输出预览
            if status == "success":
                preview_template = random.choice(OUTPUT_PREVIEWS)
                output_preview = preview_template.format(
                    count=random.randint(5, 50),
                    amount=round(random.uniform(0.5, 5.0), 1),
                    active=random.randint(100, 1000),
                    direction=random.choice(["高开", "低开", "震荡"]),
                    change=random.choice(["涨", "跌"]),
                    point=random.randint(1, 15),
                    success=random.randint(3, 20),
                    pending=random.randint(1, 10),
                )
            else:
                output_preview = ""

            execution = {
                "job_id": job["id"],
                "job_name": job["name"],
                "tenant_id": job["tenant_id"],
                "scheduled_time": scheduled_time.strftime("%Y-%m-%d %H:%M:%S"),
                "actual_time": actual_time.strftime("%Y-%m-%d %H:%M:%S"),
                "end_time": end_time.strftime("%Y-%m-%d %H:%M:%S"),
                "duration_ms": duration_ms,
                "status": status,
                "error_message": error_message,
                "instance_id": f"instance-{random.randint(1, 5):03d}",
                "executor_leader": "",
                "is_manual": 1 if random.random() < 0.05 else 0,  # 5% 手动触发
                "trace_id": f"trace-{uuid.uuid4().hex[:16]}",
                "session_id": f"sess-{uuid.uuid4().hex[:16]}",
                "input_snapshot": "",
                "output_preview": output_preview[:500],  # 截断到500字符
                "meta": "",
            }
            executions.append(execution)

        current += timedelta(days=1)

    return executions


def generate_sql(jobs: list[dict], executions: list[dict]) -> str:
    """生成 SQL 插入语句.

    Args:
        jobs: 任务列表
        executions: 执行记录列表

    Returns:
        SQL 语句
    """
    lines = [
        "-- ============================================================",
        "-- Cron Test Data - 定时任务测试数据",
        f"-- 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"-- 任务数: {len(jobs)}",
        f"-- 执行记录数: {len(executions)}",
        "-- ============================================================",
        "",
        "SET NAMES utf8mb4;",
        "SET FOREIGN_KEY_CHECKS = 0;",
        "",
        "-- 清理旧测试数据",
        "DELETE FROM swe_cron_executions WHERE job_id LIKE 'cron-%';",
        "DELETE FROM swe_cron_jobs WHERE id LIKE 'cron-%';",
        "",
        "-- -----------------------------------------------------------",
        "-- 插入定时任务定义",
        "-- -----------------------------------------------------------",
        "INSERT INTO `swe_cron_jobs` (`id`, `name`, `tenant_id`, `tenant_name`, `bbk_id`, `source_id`, `enabled`, `task_type`, `cron_expr`, `timezone`, `channel`, `target_user_id`, `target_session_id`, `timeout_seconds`, `max_concurrency`, `misfire_grace_seconds`, `text_content`, `request_input`, `creator_user_id`, `task_chat_id`, `task_session_id`, `meta`, `status`, `pause_reason`, `created_at`) VALUES",
    ]

    # 生成任务插入语句
    job_values = []
    for job in jobs:
        value = (
            f"('{job['id']}', '{job['name']}', '{job['tenant_id']}', '{job['tenant_name']}', "
            f"'{job['bbk_id']}', '{job['source_id']}', {job['enabled']}, '{job['task_type']}', "
            f"'{job['cron_expr']}', '{job['timezone']}', '{job['channel']}', '{job['target_user_id']}', "
            f"'{job['target_session_id']}', {job['timeout_seconds']}, {job['max_concurrency']}, "
            f"{job['misfire_grace_seconds']}, '{job['text_content']}', '{job['request_input']}', "
            f"'{job['creator_user_id']}', '{job['task_chat_id']}', '{job['task_session_id']}', "
            f"'{job['meta']}', '{job['status']}', '{job['pause_reason']}', '{job['created_at']}')"
        )
        job_values.append(value)

    lines.append(",\n".join(job_values) + ";")
    lines.append("")
    lines.append(
        "-- -----------------------------------------------------------",
    )
    lines.append("-- 插入定时任务执行历史")
    lines.append(
        "-- -----------------------------------------------------------",
    )

    # 分批插入执行记录（每批100条）
    batch_size = 100
    for i in range(0, len(executions), batch_size):
        batch = executions[i : i + batch_size]
        lines.append(
            f"INSERT INTO `swe_cron_executions` (`job_id`, `job_name`, `tenant_id`, `scheduled_time`, `actual_time`, `end_time`, `duration_ms`, `status`, `error_message`, `instance_id`, `executor_leader`, `is_manual`, `trace_id`, `session_id`, `input_snapshot`, `output_preview`, `meta`) VALUES",
        )

        exec_values = []
        for exec_item in batch:
            value = (
                f"('{exec_item['job_id']}', '{exec_item['job_name']}', '{exec_item['tenant_id']}', "
                f"'{exec_item['scheduled_time']}', '{exec_item['actual_time']}', '{exec_item['end_time']}', "
                f"{exec_item['duration_ms']}, '{exec_item['status']}', '{exec_item['error_message']}', "
                f"'{exec_item['instance_id']}', '{exec_item['executor_leader']}', {exec_item['is_manual']}, "
                f"'{exec_item['trace_id']}', '{exec_item['session_id']}', '{exec_item['input_snapshot']}', "
                f"'{exec_item['output_preview']}', '{exec_item['meta']}')"
            )
            exec_values.append(value)

        lines.append(",\n".join(exec_values) + ";")
        lines.append("")

    lines.append("SET FOREIGN_KEY_CHECKS = 1;")
    lines.append("")
    lines.append(
        "-- -----------------------------------------------------------",
    )
    lines.append("-- 验证数据")
    lines.append(
        "-- -----------------------------------------------------------",
    )
    lines.append(
        "SELECT 'swe_cron_jobs 记录数' as table_name, COUNT(*) as count FROM swe_cron_jobs WHERE id LIKE 'cron-%';",
    )
    lines.append(
        "SELECT 'swe_cron_executions 记录数' as table_name, COUNT(*) as count FROM swe_cron_executions WHERE job_id LIKE 'cron-%';",
    )
    lines.append("")
    lines.append("-- 查看每天的执行记录数量")
    lines.append(
        "SELECT DATE(actual_time) as exec_date, COUNT(*) as exec_count",
    )
    lines.append("FROM swe_cron_executions WHERE job_id LIKE 'cron-%'")
    lines.append("GROUP BY DATE(actual_time) ORDER BY exec_date;")

    return "\n".join(lines)


async def insert_to_database(jobs: list[dict], executions: list[dict]) -> None:
    """直接插入到数据库.

    Args:
        jobs: 任务列表
        executions: 执行记录列表
    """
    db_config = get_database_config()
    db = DatabaseConnection(db_config)

    try:
        # 插入任务
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
            await db.execute(
                job_sql,
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
        print(f"✓ 插入 {len(jobs)} 条任务定义")

        # 插入执行记录
        exec_sql = """
            INSERT INTO swe_cron_executions
            (job_id, job_name, tenant_id, scheduled_time, actual_time, end_time,
             duration_ms, status, error_message, instance_id, executor_leader,
             is_manual, trace_id, session_id, input_snapshot, output_preview, meta)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        batch_size = 100
        for i in range(0, len(executions), batch_size):
            batch = executions[i : i + batch_size]
            for exec_item in batch:
                await db.execute(
                    exec_sql,
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
            print(f"✓ 插入执行记录 {i + len(batch)}/{len(executions)}")

        print(f"✓ 完成！共插入 {len(executions)} 条执行记录")

    finally:
        await db.close()


def main():
    """主函数."""
    print("=" * 60)
    print("定时任务测试数据生成器")
    print("=" * 60)

    # 生成数据
    print("\n1. 生成任务定义...")
    jobs = generate_jobs(count=20)
    print(f"   生成 {len(jobs)} 个任务")

    print("\n2. 生成执行历史 (2026-05-18 ~ 2026-05-31)...")
    executions = generate_executions(
        jobs=jobs,
        start_date="2026-05-18",
        end_date="2026-05-31",
        executions_per_day=250,
    )
    print(f"   生成 {len(executions)} 条执行记录")

    # 统计每天的数据量
    daily_stats = {}
    for exec_item in executions:
        date = exec_item["actual_time"][:10]
        daily_stats[date] = daily_stats.get(date, 0) + 1
    print("\n3. 每天执行记录统计：")
    for date in sorted(daily_stats.keys()):
        print(f"   {date}: {daily_stats[date]} 条")

    # 选择输出方式
    print("\n4. 选择输出方式：")
    print("   [1] 生成 SQL 文件")
    print("   [2] 直接插入数据库")
    print("   [3] 两者都执行")

    choice = input("\n请选择 (1/2/3): ").strip()

    if choice in ("1", "3"):
        # 生成 SQL 文件
        sql_content = generate_sql(jobs, executions)
        output_file = os.path.join(
            os.path.dirname(__file__),
            "sql",
            "cron_test_data_insert.sql",
        )
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(sql_content)
        print(f"\n✓ SQL 文件已生成: {output_file}")

    if choice in ("2", "3"):
        # 直接插入数据库
        print("\n5. 插入数据库...")
        asyncio.run(insert_to_database(jobs, executions))

    print("\n" + "=" * 60)
    print("完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()
