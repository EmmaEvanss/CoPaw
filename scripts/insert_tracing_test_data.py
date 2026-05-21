# -*- coding: utf-8 -*-
"""插入从今天(2026-05-19)到月底(2026-05-31)的多轮会话和用户停留测试数据."""

import asyncio
import json
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
BBK_IDS = ["100", "200", "201", "202", "203"]

# 每天 trace 数量范围
DAILY_TRACE_RANGE = (150, 250)


async def insert_data() -> None:
    """插入测试数据."""
    db_config = get_database_config()
    db = DatabaseConnection(db_config)

    try:
        await db.connect()
        print("数据库连接成功\n")

        # 清理测试数据（标记 test- 开头的）
        await db.execute(
            "DELETE FROM swe_tracing_traces WHERE trace_id LIKE 'test-%'"
        )
        print("已清理旧测试数据\n")

        # 从 2026-05-19 到 2026-05-31，共13天
        start_day = datetime(2026, 5, 19)
        end_day = datetime(2026, 5, 31)
        current_day = start_day

        total_traces = 0
        total_multi_round_sessions = 0
        total_stay_users = 0

        while current_day <= end_day:
            day_str = current_day.strftime("%Y-%m-%d")
            print(f"=== 处理 {day_str} ===")

            daily_trace_count = random.randint(*DAILY_TRACE_RANGE)
            day_traces = 0
            day_multi_round = 0
            day_stay_users = 0

            # 插入多轮会话数据 (每天 15-25 个多轮会话)
            multi_round_sql = """
                INSERT INTO swe_tracing_traces
                (trace_id, source_id, user_id, session_id, session_name, channel,
                 start_time, end_time, duration_ms, model_name, total_input_tokens,
                 total_output_tokens, total_tokens, tools_used, skills_used,
                 status, error, user_message, user_name, bbk_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """

            multi_round_sessions = random.randint(15, 25)
            for i in range(multi_round_sessions):
                session_id = f"test-session-multi-{uuid.uuid4().hex[:12]}"
                session_name = f"多轮测试会话{current_day.day}-{i+1}"
                user_id = f"test-user-{current_day.day}-{random.randint(1000, 9999)}"
                user_name = f"测试用户{random.randint(100, 999)}"
                bbk_id = random.choice(BBK_IDS)
                source_id = random.choice(SOURCE_IDS)
                rounds = random.randint(4, 8)  # 4-8轮对话

                base_hour = random.randint(8, 18)
                for r in range(rounds):
                    # 每轮间隔 2-5 分钟
                    start_time = current_day.replace(
                        hour=base_hour,
                        minute=random.randint(0, 59),
                        second=random.randint(0, 59),
                    ) + timedelta(minutes=r * random.randint(2, 5))
                    end_time = start_time + timedelta(seconds=random.randint(10, 60))
                    duration_ms = int((end_time - start_time).total_seconds() * 1000)

                    trace_id = f"test-{uuid.uuid4().hex[:16]}"
                    input_tokens = random.randint(100, 500)
                    output_tokens = random.randint(50, 200)

                    await db.execute(
                        multi_round_sql,
                        (
                            trace_id,
                            source_id,
                            user_id,
                            session_id,
                            session_name,
                            "console",
                            start_time.strftime("%Y-%m-%d %H:%M:%S"),
                            end_time.strftime("%Y-%m-%d %H:%M:%S"),
                            duration_ms,
                            random.choice(["claude-3-5-sonnet", "gpt-4o", "glm-4"]),
                            input_tokens,
                            output_tokens,
                            input_tokens + output_tokens,
                            json.dumps(["search", "analyze"]),
                            json.dumps(["查询技能", "分析技能"]),
                            "completed",
                            "",
                            f"测试消息{r+1}",
                            user_name,
                            bbk_id,
                        ),
                    )
                    day_traces += 1

            day_multi_round = multi_round_sessions

            # 插入用户停留时间数据 (每天 10-20 个有停留的用户)
            stay_sql = """
                INSERT INTO swe_tracing_traces
                (trace_id, source_id, user_id, session_id, session_name, channel,
                 start_time, end_time, duration_ms, model_name, total_input_tokens,
                 total_output_tokens, total_tokens, tools_used, skills_used,
                 status, error, user_message, user_name, bbk_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """

            stay_users = random.randint(10, 20)
            for i in range(stay_users):
                user_id = f"test-stay-user-{current_day.day}-{random.randint(1000, 9999)}"
                user_name = f"停留用户{random.randint(100, 999)}"
                bbk_id = random.choice(BBK_IDS)
                source_id = random.choice(SOURCE_IDS)

                # 用户跨度时间：1-8 小时
                stay_hours = random.randint(1, 8)
                first_hour = random.randint(8, 18 - stay_hours)
                trace_count = random.randint(3, 6)

                for t in range(trace_count):
                    # 在跨度内随机分布请求
                    hour_offset = int(stay_hours * t / trace_count)
                    start_time = current_day.replace(
                        hour=first_hour + hour_offset,
                        minute=random.randint(0, 59),
                        second=random.randint(0, 59),
                    )
                    end_time = start_time + timedelta(seconds=random.randint(15, 90))
                    duration_ms = int((end_time - start_time).total_seconds() * 1000)

                    # 每次请求创建新的 session
                    session_id = f"test-session-stay-{uuid.uuid4().hex[:12]}"
                    session_name = f"停留测试会话{current_day.day}-{i+1}-{t+1}"
                    trace_id = f"test-{uuid.uuid4().hex[:16]}"
                    input_tokens = random.randint(80, 400)
                    output_tokens = random.randint(40, 150)

                    await db.execute(
                        stay_sql,
                        (
                            trace_id,
                            source_id,
                            user_id,
                            session_id,
                            session_name,
                            "console",
                            start_time.strftime("%Y-%m-%d %H:%M:%S"),
                            end_time.strftime("%Y-%m-%d %H:%M:%S"),
                            duration_ms,
                            random.choice(["claude-3-5-sonnet", "gpt-4o"]),
                            input_tokens,
                            output_tokens,
                            input_tokens + output_tokens,
                            json.dumps(["search"]),
                            json.dumps(["查询技能"]),
                            "completed",
                            "",
                            f"停留测试消息{t+1}",
                            user_name,
                            bbk_id,
                        ),
                    )
                    day_traces += 1

            day_stay_users = stay_users

            # 补充单轮对话数据（剩余的 trace）
            single_sql = """
                INSERT INTO swe_tracing_traces
                (trace_id, source_id, user_id, session_id, session_name, channel,
                 start_time, end_time, duration_ms, model_name, total_input_tokens,
                 total_output_tokens, total_tokens, tools_used, skills_used,
                 status, error, user_message, user_name, bbk_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """

            remaining_traces = daily_trace_count - day_traces
            for i in range(max(0, remaining_traces)):
                user_id = f"test-single-user-{current_day.day}-{random.randint(1000, 9999)}"
                user_name = f"单轮用户{random.randint(100, 999)}"
                bbk_id = random.choice(BBK_IDS)
                source_id = random.choice(SOURCE_IDS)
                session_id = f"test-session-single-{uuid.uuid4().hex[:12]}"
                session_name = f"单轮测试会话{current_day.day}-{i+1}"

                hour = random.randint(0, 23)
                minute = random.randint(0, 59)
                second = random.randint(0, 59)
                start_time = current_day.replace(hour=hour, minute=minute, second=second)
                end_time = start_time + timedelta(seconds=random.randint(10, 60))
                duration_ms = int((end_time - start_time).total_seconds() * 1000)

                trace_id = f"test-{uuid.uuid4().hex[:16]}"
                input_tokens = random.randint(50, 300)
                output_tokens = random.randint(30, 150)

                await db.execute(
                    single_sql,
                    (
                        trace_id,
                        source_id,
                        user_id,
                        session_id,
                        session_name,
                        "console",
                        start_time.strftime("%Y-%m-%d %H:%M:%S"),
                        end_time.strftime("%Y-%m-%d %H:%M:%S"),
                        duration_ms,
                        random.choice(["claude-3-5-sonnet", "gpt-4o"]),
                        input_tokens,
                        output_tokens,
                        input_tokens + output_tokens,
                        json.dumps(["search"]),
                        json.dumps(["查询技能"]),
                        "completed",
                        "",
                        f"单轮测试消息{i+1}",
                        user_name,
                        bbk_id,
                    ),
                )
                day_traces += 1

            print(f"  插入 trace: {day_traces} 条")
            print(f"  多轮会话: {day_multi_round} 个")
            print(f"  停留用户: {day_stay_users} 个")

            total_traces += day_traces
            total_multi_round_sessions += day_multi_round
            total_stay_users += day_stay_users

            current_day += timedelta(days=1)

        # 验证数据
        print("\n=== 验证总体数据 ===")
        row = await db.fetch_one(
            "SELECT COUNT(*) as count FROM swe_tracing_traces WHERE trace_id LIKE 'test-%'"
        )
        print(f"测试 trace 总数: {row['count']}")

        # 检查多轮会话统计（所有测试数据）
        row = await db.fetch_one("""
            SELECT COUNT(*) as total_sessions,
                   SUM(CASE WHEN trace_count > 3 THEN 1 ELSE 0 END) as multi_round_sessions
            FROM (
                SELECT session_id, COUNT(*) as trace_count
                FROM swe_tracing_traces
                WHERE start_time >= '2026-05-19 00:00:00' AND start_time < '2026-06-01 00:00:00'
                  AND session_id IS NOT NULL AND session_id != ''
                  AND session_id LIKE 'test-session-%'
                GROUP BY session_id
            ) AS session_counts
        """)
        total_sessions = int(row['total_sessions'] or 0)
        multi_round_sessions = int(row['multi_round_sessions'] or 0)
        if total_sessions > 0:
            ratio = multi_round_sessions / total_sessions * 100
            print(f"总 session: {total_sessions} 个")
            print(f"多轮会话 (>3轮): {multi_round_sessions} 个, 占比 {ratio:.1f}%")

        # 检查用户停留时间
        row = await db.fetch_one("""
            SELECT AVG(stay_seconds) as avg_stay, COUNT(*) as user_count
            FROM (
                SELECT user_id,
                       TIMESTAMPDIFF(SECOND, MIN(start_time), MAX(start_time)) as stay_seconds
                FROM swe_tracing_traces
                WHERE start_time >= '2026-05-19 00:00:00' AND start_time < '2026-06-01 00:00:00'
                  AND user_id LIKE 'test-stay-user-%'
                GROUP BY user_id
                HAVING stay_seconds > 0
            ) AS user_stays
        """)
        avg_stay_seconds = float(row['avg_stay'] or 0)
        avg_stay_minutes = avg_stay_seconds / 60
        print(f"有停留的用户: {row['user_count']} 个")
        print(f"平均停留时间: {avg_stay_minutes:.1f} 分钟 ({avg_stay_seconds:.0f} 秒)")

        # 检查数据时间范围
        row = await db.fetch_one("""
            SELECT MIN(start_time) as min_time, MAX(start_time) as max_time
            FROM swe_tracing_traces
            WHERE trace_id LIKE 'test-%'
        """)
        print(f"\n数据时间范围: {row['min_time']} ~ {row['max_time']}")

        print("\n完成!")

    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(insert_data())