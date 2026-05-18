# -*- coding: utf-8 -*-
"""插入技能调用测试数据.

用于验证"技能调用次数"卡片的数据展示。
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


async def insert_skill_data():
    """插入技能调用测试数据."""
    config = get_database_config()
    await init_db_connection(config)
    db = get_db_connection()

    try:
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        source_id = "all"

        # 技能名称列表
        skill_names = [
            "对话问答",
            "票务分析",
            "智能检索",
            "图像分析",
            "任务管理",
            "数据分析",
            "报告生成",
            "风险评估",
        ]

        # 分行数据
        branches = [
            ("201", "上海分行"),
            ("204", "杭州分行"),
            ("202", "深圳分行"),
            ("205", "苏州分行"),
            ("206", "南京分行"),
        ]

        insert_count = 0

        # 先获取今天的 trace_id 列表
        trace_query = """
            SELECT trace_id, user_id, session_id, bbk_id
            FROM swe_tracing_traces
            WHERE start_time >= %s AND start_time < %s
            LIMIT 100
        """
        traces = await db.fetch_all(trace_query, (today, today + timedelta(days=1)))

        if not traces:
            print("没有找到今天的 trace 数据，请先运行 insert_hourly_test_data.py")
            return

        print(f"找到 {len(traces)} 条 trace 数据")

        for hour in range(24):
            hour_start = today + timedelta(hours=hour)

            # 模拟不同小时的技能调用活跃度
            if 9 <= hour <= 18:
                # 工作时间：高活跃度
                skill_count = random.randint(20, 50)
            elif 7 <= hour <= 21:
                # 一般时间：中等活跃度
                skill_count = random.randint(8, 20)
            else:
                # 深夜/凌晨：低活跃度
                skill_count = random.randint(2, 8)

            for _ in range(skill_count):
                # 随机选择一个 trace
                trace = random.choice(traces)

                # 随机选择一个技能
                skill_name = random.choice(skill_names)

                span_id = str(uuid.uuid4())
                minute_offset = random.randint(0, 59)
                second_offset = random.randint(0, 59)
                start_time = hour_start + timedelta(minutes=minute_offset, seconds=second_offset)
                duration_ms = random.randint(500, 30000)

                query = """
                    INSERT INTO swe_tracing_spans (
                        span_id, trace_id, source_id, name, event_type,
                        start_time, end_time, duration_ms, user_id,
                        bbk_id, session_id, channel, skill_name
                    ) VALUES (
                        %s, %s, %s, %s, %s,
                        %s, %s, %s, %s,
                        %s, %s, %s, %s
                    )
                """
                await db.execute(
                    query,
                    (
                        span_id,
                        trace["trace_id"],
                        source_id,
                        f"skill_{skill_name}",
                        "skill_invocation",
                        start_time,
                        start_time + timedelta(milliseconds=duration_ms),
                        duration_ms,
                        trace["user_id"],
                        trace["bbk_id"],
                        trace["session_id"],
                        "web",
                        skill_name,
                    ),
                )
                insert_count += 1

            print(f"已插入 {hour:02d}:00 时的技能调用数据")

        print(f"\n共插入 {insert_count} 条技能调用测试数据")
        print(f"时间范围: {today.strftime('%Y-%m-%d')} 00:00 - 23:59")

    except Exception as e:
        print(f"插入数据失败: {e}")
        raise
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(insert_skill_data())
