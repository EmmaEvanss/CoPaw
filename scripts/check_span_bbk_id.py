# -*- coding: utf-8 -*-
"""检查 swe_tracing_spans 表中的 bbk_id 数据."""

import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "monitor", "src"))

from monitor.app.database.connection import init_db_connection, get_db_connection
from monitor.app.database.config import get_database_config


async def check_span_bbk_id():
    """检查 swe_tracing_spans 表中的 bbk_id 数据."""
    config = get_database_config()
    await init_db_connection(config)
    db = get_db_connection()

    try:
        # 检查技能调用数据的 bbk_id 分布
        query = """
            SELECT bbk_id, COUNT(*) as cnt
            FROM swe_tracing_spans
            WHERE event_type = 'skill_invocation'
            AND start_time >= '2026-05-17'
            AND start_time < '2026-05-18'
            GROUP BY bbk_id
        """
        rows = await db.fetch_all(query)
        print("技能调用数据的 bbk_id 分布:")
        for row in rows:
            print(f"  bbk_id='{row['bbk_id']}': {row['cnt']} 条")

        # 检查是否有 bbk_id 为空的数据
        null_query = """
            SELECT COUNT(*) as cnt
            FROM swe_tracing_spans
            WHERE event_type = 'skill_invocation'
            AND start_time >= '2026-05-17'
            AND start_time < '2026-05-18'
            AND (bbk_id IS NULL OR bbk_id = '')
        """
        result = await db.fetch_one(null_query)
        null_count = result.get("cnt", 0) if result else 0
        print(f"\nbbk_id 为空的数据: {null_count} 条")

    except Exception as e:
        print(f"检查数据失败: {e}")
        raise
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(check_span_bbk_id())
