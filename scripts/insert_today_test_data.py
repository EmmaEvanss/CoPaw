# -*- coding: utf-8 -*-
"""插入今天的测试数据（traces + spans）.

使用数据库中已有的 source_id，覆盖24小时，包含分行和技能调用数据。
"""

import asyncio
import random
import uuid
from datetime import datetime, timedelta

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "monitor", "src"))

from monitor.app.database.connection import init_db_connection, get_db_connection
from monitor.app.database.config import get_database_config


SOURCE_IDS = ["CMSJY", "UPPCLAW", "copilotClaw", "ruice", "privatebanking", "SZLS"]

BRANCHES = [
    ("200", "北京分行"),
    ("201", "上海分行"),
    ("202", "深圳分行"),
    ("203", "广州分行"),
    ("100", "总行"),
]

SKILL_NAMES = [
    "对话问答", "票务分析", "智能检索", "图像分析",
    "任务管理", "数据分析", "报告生成", "风险评估",
]

TOOL_NAMES = [
    "read_file", "write_file", "search_code", "run_command",
    "web_search", "database_query", "send_email", "create_report",
]

MCP_SERVERS = [
    "filesystem", "web-browser", "database", "email-service",
]


async def insert_data_for_range(start_str: str, end_str: str):
    """插入指定日期范围的测试数据."""
    config = get_database_config()
    await init_db_connection(config)
    db = get_db_connection()

    try:
        start_date = datetime.strptime(start_str, "%Y-%m-%d")
        end_date = datetime.strptime(end_str, "%Y-%m-%d") + timedelta(days=1)
        current_date = start_date

        total_traces = 0
        total_spans = 0

        while current_date < end_date:
            today = current_date.replace(hour=0, minute=0, second=0, microsecond=0)
            trace_count = 0
            span_count = 0
        tomorrow = today + timedelta(days=1)

        trace_count = 0
        span_count = 0

        # 每个小时插入数据
        for hour in range(24):
            hour_start = today + timedelta(hours=hour)

            # 按时段模拟活跃度
            if 9 <= hour <= 18:
                base_count = random.randint(12, 25)
            elif 7 <= hour <= 21:
                base_count = random.randint(4, 12)
            else:
                base_count = random.randint(1, 4)

            # 为每个平台生成若干 trace
            for source_id in SOURCE_IDS:
                source_count = max(1, base_count // len(SOURCE_IDS) + random.randint(-1, 2))

                for _ in range(source_count):
                    trace_id = str(uuid.uuid4())
                    bbk_id = random.choice(BRANCHES)[0]
                    user_id = f"user_{random.randint(1000, 9999)}"
                    session_id = str(uuid.uuid4())
                    total_tokens = random.randint(200, 8000)
                    input_tokens = int(total_tokens * random.uniform(0.3, 0.7))
                    output_tokens = total_tokens - input_tokens
                    duration_ms = random.randint(2000, 120000)
                    minute = random.randint(0, 59)
                    second = random.randint(0, 59)
                    start_time = hour_start + timedelta(minutes=minute, seconds=second)
                    end_time = start_time + timedelta(milliseconds=duration_ms)

                    status = random.choices(
                        ["completed", "error", "running"],
                        weights=[85, 10, 5],
                    )[0]

                    await db.execute(
                        """INSERT INTO swe_tracing_traces
                        (trace_id, source_id, user_id, session_id, channel,
                         start_time, end_time, duration_ms,
                         total_tokens, total_input_tokens, total_output_tokens,
                         status, bbk_id, model_name)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                        (
                            trace_id, source_id, user_id, session_id, "web",
                            start_time, end_time, duration_ms,
                            total_tokens, input_tokens, output_tokens,
                            status, bbk_id, "claude-sonnet-4-20250514",
                        ),
                    )
                    trace_count += 1

                    # 为每个 trace 生成 1~3 个技能调用 span
                    skill_count = random.randint(1, 3)
                    for _ in range(skill_count):
                        span_id = str(uuid.uuid4())
                        skill_name = random.choice(SKILL_NAMES)
                        skill_duration = random.randint(500, 30000)
                        span_start = start_time + timedelta(milliseconds=random.randint(0, max(1, duration_ms - skill_duration)))
                        span_end = span_start + timedelta(milliseconds=skill_duration)

                        await db.execute(
                            """INSERT INTO swe_tracing_spans
                            (span_id, trace_id, source_id, name, event_type,
                             start_time, end_time, duration_ms,
                             user_id, bbk_id, session_id, channel,
                             skill_name, model_name)
                            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                            (
                                span_id, trace_id, source_id,
                                f"skill_{skill_name}", "skill_invocation",
                                span_start, span_end, skill_duration,
                                user_id, bbk_id, session_id, "web",
                                skill_name, "claude-sonnet-4-20250514",
                            ),
                        )
                        span_count += 1

                    # 为每个 trace 生成 2~5 个工具调用 span
                    tool_count = random.randint(2, 5)
                    for _ in range(tool_count):
                        span_id = str(uuid.uuid4())
                        tool_name = random.choice(TOOL_NAMES)
                        tool_duration = random.randint(100, 5000)
                        span_start = start_time + timedelta(milliseconds=random.randint(0, max(1, duration_ms - tool_duration)))
                        span_end = span_start + timedelta(milliseconds=tool_duration)
                        has_error = random.random() < 0.05
                        # 约 30% 的工具调用关联 MCP 服务
                        mcp_server = random.choice(MCP_SERVERS) if random.random() < 0.3 else None

                        await db.execute(
                            """INSERT INTO swe_tracing_spans
                            (span_id, trace_id, source_id, name, event_type,
                             start_time, end_time, duration_ms,
                             user_id, bbk_id, session_id, channel,
                             tool_name, mcp_server, error, model_name)
                            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                            (
                                span_id, trace_id, source_id,
                                f"tool_{tool_name}", "tool_call_end",
                                span_start, span_end, tool_duration,
                                user_id, bbk_id, session_id, "web",
                                tool_name, mcp_server,
                                "test error" if has_error else None,
                                "claude-sonnet-4-20250514",
                            ),
                        )
                        span_count += 1

            print(f"  {hour:02d}:00 完成")

            total_traces += trace_count
            total_spans += span_count
            print(f"  {today.strftime('%Y-%m-%d')} 完成: traces={trace_count}, spans={span_count}")

            current_date += timedelta(days=1)

        print(f"\n全部完成: traces={total_traces}, spans={total_spans}")
        print(f"时间范围: {start_str} ~ {end_str}")
        print(f"平台: {', '.join(SOURCE_IDS)}")

    except Exception as e:
        print(f"插入失败: {e}")
        raise
    finally:
        await db.close()


if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 3:
        start = sys.argv[1]
        end = sys.argv[2]
    else:
        start = datetime.now().strftime("%Y-%m-%d")
        end = start
    asyncio.run(insert_data_for_range(start, end))
