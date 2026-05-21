# -*- coding: utf-8 -*-
"""检查技能调用数据."""

import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "monitor", "src"))

from monitor.app.database.connection import init_db_connection, get_db_connection
from monitor.app.database.config import get_database_config


async def check_skill_data():
    """检查技能调用数据."""
    config = get_database_config()
    await init_db_connection(config)
    db = get_db_connection()

    try:
        # 检查 swe_tracing_spans 表是否存在
        check_table_query = """
            SELECT COUNT(*) as cnt
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_SCHEMA = DATABASE()
            AND TABLE_NAME = 'swe_tracing_spans'
        """
        result = await db.fetch_one(check_table_query)
        table_exists = result and result.get("cnt", 0) > 0

        if not table_exists:
            print("表 swe_tracing_spans 不存在")
            return

        # 检查 skill_invocation 数据
        skill_query = """
            SELECT COUNT(*) as cnt
            FROM swe_tracing_spans
            WHERE event_type = 'skill_invocation'
            AND start_time >= '2026-05-17'
            AND start_time < '2026-05-18'
        """
        result = await db.fetch_one(skill_query)
        skill_count = result.get("cnt", 0) if result else 0
        print(f"今天 skill_invocation 数据条数: {skill_count}")

        # 检查所有 event_type 分布
        event_type_query = """
            SELECT event_type, COUNT(*) as cnt
            FROM swe_tracing_spans
            WHERE start_time >= '2026-05-17'
            AND start_time < '2026-05-18'
            GROUP BY event_type
        """
        rows = await db.fetch_all(event_type_query)
        print("\n今天 event_type 分布:")
        for row in rows:
            print(f"  {row['event_type']}: {row['cnt']}")

        # 检查是否有 skill_name 数据
        skill_name_query = """
            SELECT skill_name, COUNT(*) as cnt
            FROM swe_tracing_spans
            WHERE event_type = 'skill_invocation'
            AND skill_name IS NOT NULL
            AND start_time >= '2026-05-17'
            AND start_time < '2026-05-18'
            GROUP BY skill_name
            ORDER BY cnt DESC
            LIMIT 10
        """
        rows = await db.fetch_all(skill_name_query)
        print("\n今天技能调用统计:")
        if rows:
            for row in rows:
                print(f"  {row['skill_name']}: {row['cnt']}")
        else:
            print("  无数据")

    except Exception as e:
        print(f"检查数据失败: {e}")
        raise
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(check_skill_data())
