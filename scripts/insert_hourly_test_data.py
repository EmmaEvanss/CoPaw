# -*- coding: utf-8 -*-
"""插入今天的小时级测试数据.

用于验证趋势图在同一天内显示24小时数据的效果。
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


async def insert_hourly_data():
    """插入今天每小时的测试数据."""
    # 初始化数据库连接
    config = get_database_config()
    await init_db_connection(config)
    db = get_db_connection()

    try:
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        source_id = "all"  # 使用 all 作为 source_id

        # 分行数据
        branches = [
            ("201", "上海分行"),
            ("204", "杭州分行"),
            ("202", "深圳分行"),
            ("205", "苏州分行"),
            ("206", "南京分行"),
        ]

        insert_count = 0

        for hour in range(24):
            hour_start = today + timedelta(hours=hour)

            # 模拟不同小时的活跃度（白天高，晚上低）
            if 9 <= hour <= 18:
                # 工作时间：高活跃度
                base_count = random.randint(15, 30)
            elif 7 <= hour <= 21:
                # 一般时间：中等活跃度
                base_count = random.randint(5, 15)
            else:
                # 深夜/凌晨：低活跃度
                base_count = random.randint(1, 5)

            # 为每个分行插入数据
            for bbk_id, bbk_name in branches:
                # 每个分行在这个小时有若干会话
                branch_count = max(1, base_count // len(branches) + random.randint(-2, 3))

                for _ in range(branch_count):
                    trace_id = str(uuid.uuid4())
                    user_id = f"user_{random.randint(1000, 9999)}"
                    session_id = str(uuid.uuid4())
                    total_tokens = random.randint(100, 5000)
                    duration_ms = random.randint(1000, 60000)

                    # 随机偏移分钟和秒
                    minute_offset = random.randint(0, 59)
                    second_offset = random.randint(0, 59)
                    start_time = hour_start + timedelta(minutes=minute_offset, seconds=second_offset)

                    query = """
                        INSERT INTO swe_tracing_traces (
                            trace_id, source_id, user_id, session_id,
                            channel, start_time, duration_ms, total_tokens,
                            status, bbk_id
                        ) VALUES (
                            %s, %s, %s, %s,
                            %s, %s, %s, %s,
                            %s, %s
                        )
                    """
                    await db.execute(
                        query,
                        (
                            trace_id,
                            source_id,
                            user_id,
                            session_id,
                            "web",
                            start_time,
                            duration_ms,
                            total_tokens,
                            "completed",
                            bbk_id,
                        ),
                    )
                    insert_count += 1

            print(f"已插入 {hour:02d}:00 时的数据")

        print(f"\n共插入 {insert_count} 条测试数据")
        print(f"时间范围: {today.strftime('%Y-%m-%d')} 00:00 - 23:59")

    except Exception as e:
        print(f"插入数据失败: {e}")
        raise
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(insert_hourly_data())
