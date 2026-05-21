# -*- coding: utf-8 -*-
"""修复技能调用数据的 bbk_id 字段.

删除 bbk_id 为空的数据，重新插入带有正确 bbk_id 的数据。
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


async def fix_skill_data():
    """修复技能调用数据的 bbk_id 字段."""
    config = get_database_config()
    await init_db_connection(config)
    db = get_db_connection()

    try:
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        source_id = "all"

        # 1. 删除之前插入的错误数据
        delete_query = """
            DELETE FROM swe_tracing_spans
            WHERE event_type = 'skill_invocation'
            AND start_time >= %s AND start_time < %s
        """
        await db.execute(delete_query, (today, today + timedelta(days=1)))
        print("已删除之前的技能调用数据")

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

        # 2. 获取今天的 trace 数据（包含 bbk_id）
        trace_query = """
            SELECT trace_id, user_id, session_id, bbk_id
            FROM swe_tracing_traces
            WHERE start_time >= %s AND start_time < %s
            AND bbk_id IS NOT NULL AND bbk_id != ''
            LIMIT 100
        """
        traces = await db.fetch_all(trace_query, (today, today + timedelta(days=1)))

        if not traces:
            print("没有找到带有 bbk_id 的 trace 数据")
            return

        print(f"找到 {len(traces)} 条带有 bbk_id 的 trace 数据")

        insert_count = 0

        for hour in range(24):
            hour_start = today + timedelta(hours=hour)

            # 模拟不同小时的技能调用活跃度
            if 9 <= hour <= 18:
                skill_count = random.randint(20, 50)
            elif 7 <= hour <= 21:
                skill_count = random.randint(8, 20)
            else:
                skill_count = random.randint(2, 8)

            for _ in range(skill_count):
                trace = random.choice(traces)
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

        # 3. 验证数据
        verify_query = """
            SELECT bbk_id, COUNT(*) as cnt
            FROM swe_tracing_spans
            WHERE event_type = 'skill_invocation'
            AND start_time >= %s AND start_time < %s
            GROUP BY bbk_id
        """
        rows = await db.fetch_all(verify_query, (today, today + timedelta(days=1)))
        print("\n验证数据 - bbk_id 分布:")
        for row in rows:
            print(f"  {row['bbk_id']}: {row['cnt']} 条")

    except Exception as e:
        print(f"修复数据失败: {e}")
        raise
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(fix_skill_data())
