# -*- coding: utf-8 -*-
"""检查 bbk_id 数据."""

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from swe.envs import load_envs_into_environ
load_envs_into_environ()

from swe.database import get_database_config, DatabaseConnection


async def check():
    """检查数据."""
    db_config = get_database_config()
    db = DatabaseConnection(db_config)
    await db.connect()

    # 检查 traces 表的 bbk_id 分布
    query = """
        SELECT bbk_id, COUNT(*) as count
        FROM swe_tracing_traces
        WHERE bbk_id IS NOT NULL AND bbk_id != ''
        GROUP BY bbk_id
        ORDER BY count DESC
        LIMIT 10
    """
    rows = await db.fetch_all(query)
    print("=== swe_tracing_traces bbk_id 分布 ===")
    for row in rows:
        print(f"  bbk_id={row['bbk_id']}, count={row['count']}")

    # 检查 spans 表的 bbk_id 分布
    query2 = """
        SELECT bbk_id, COUNT(*) as count
        FROM swe_tracing_spans
        WHERE bbk_id IS NOT NULL AND bbk_id != ''
        GROUP BY bbk_id
        ORDER BY count DESC
        LIMIT 10
    """
    rows2 = await db.fetch_all(query2)
    print("\n=== swe_tracing_spans bbk_id 分布 ===")
    for row in rows2:
        print(f"  bbk_id={row['bbk_id']}, count={row['count']}")

    # 检查 traces 表样本数据
    query3 = """
        SELECT source_id, user_id, bbk_id, start_time
        FROM swe_tracing_traces
        ORDER BY start_time DESC
        LIMIT 5
    """
    rows3 = await db.fetch_all(query3)
    print("\n=== traces 样本数据 ===")
    for row in rows3:
        print(
            f"  source={row['source_id']}, user={row['user_id']}, "
            f"bbk={row['bbk_id']}, time={row['start_time']}"
        )

    # 检查 spans 表样本数据
    query4 = """
        SELECT source_id, user_id, bbk_id, event_type, skill_name
        FROM swe_tracing_spans
        WHERE event_type = 'skill_invocation'
        ORDER BY start_time DESC
        LIMIT 5
    """
    rows4 = await db.fetch_all(query4)
    print("\n=== skill_invocation spans 样本 ===")
    for row in rows4:
        print(
            f"  source={row['source_id']}, user={row['user_id']}, "
            f"bbk={row['bbk_id']}, skill={row['skill_name']}"
        )

    await db.close()


if __name__ == "__main__":
    asyncio.run(check())