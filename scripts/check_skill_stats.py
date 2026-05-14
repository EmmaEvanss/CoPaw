# -*- coding: utf-8 -*-
"""检查技能统计数据."""

import asyncio
import os
import sys

# 添加路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(
    0,
    os.path.join(os.path.dirname(__file__), "..", "market", "src"),
)

from swe.database import get_database_config, DatabaseConnection


async def check_stats():
    """执行统计查询."""
    db_config = get_database_config()
    print(
        f"数据库配置: host={db_config.host}, port={db_config.port}, db={db_config.database}",
    )

    db = DatabaseConnection(db_config)
    try:
        await db.connect()
        print(f"数据库连接状态: {db.is_connected}")

        if not db.is_connected:
            print("数据库未连接，无法查询")
            return

        # 1. 检查数据库中所有表
        tables_query = f"""
            SELECT TABLE_NAME
            FROM information_schema.TABLES
            WHERE TABLE_SCHEMA = '{db_config.database}'
            ORDER BY TABLE_NAME
        """
        tables = await db.fetch_all(tables_query)
        print(f"\n=== 数据库表 ===")
        for t in tables:
            print(f"  - {t['TABLE_NAME']}")

        # 2. 检查 skill_invocation 数据
        skill_inv_query = """
            SELECT source_id, skill_name, COUNT(*) as call_count, COUNT(DISTINCT user_id) as user_count
            FROM swe_tracing_spans
            WHERE event_type = 'skill_invocation'
            GROUP BY source_id, skill_name
            ORDER BY call_count DESC
            LIMIT 20
        """
        skill_inv_rows = await db.fetch_all(skill_inv_query)
        print(f"\n=== skill_invocation 数据 ===")
        if skill_inv_rows:
            for row in skill_inv_rows:
                print(
                    f"  source_id={row['source_id']}, skill_name={row['skill_name']}, call_count={row['call_count']}, user_count={row['user_count']}",
                )
        else:
            print("  无数据")

        # 3. 检查所有 event_type 分布
        event_type_query = """
            SELECT event_type, COUNT(*) as count
            FROM swe_tracing_spans
            GROUP BY event_type
            ORDER BY count DESC
        """
        event_rows = await db.fetch_all(event_type_query)
        print(f"\n=== event_type 分布 ===")
        for row in event_rows:
            print(f"  {row['event_type']}: {row['count']}")

        # 4. 检查所有 source_id 分布
        source_id_query = """
            SELECT source_id, COUNT(*) as count
            FROM swe_tracing_spans
            GROUP BY source_id
            ORDER BY count DESC
            LIMIT 20
        """
        source_rows = await db.fetch_all(source_id_query)
        print(f"\n=== source_id 分布 ===")
        for row in source_rows:
            print(f"  {row['source_id']}: {row['count']}")

        # 5. 检查 mcp_server 字段数据（用于 MCP 统计）
        mcp_query = """
            SELECT mcp_server, COUNT(*) as count
            FROM swe_tracing_spans
            WHERE mcp_server IS NOT NULL AND mcp_server != ''
            GROUP BY mcp_server
            ORDER BY count DESC
            LIMIT 20
        """
        mcp_rows = await db.fetch_all(mcp_query)
        print(f"\n=== mcp_server 分布 ===")
        if mcp_rows:
            for row in mcp_rows:
                print(f"  {row['mcp_server']}: {row['count']}")
        else:
            print("  无数据")

        # 6. 检查最近10条 skill_invocation 记录详情
        recent_query = """
            SELECT span_id, source_id, skill_name, user_id, start_time, event_type
            FROM swe_tracing_spans
            WHERE event_type = 'skill_invocation'
            ORDER BY start_time DESC
            LIMIT 10
        """
        recent_rows = await db.fetch_all(recent_query)
        print(f"\n=== 最近 skill_invocation 记录 ===")
        if recent_rows:
            for row in recent_rows:
                print(
                    f"  [{row['start_time']}] skill={row['skill_name']}, source={row['source_id']}, user={row['user_id']}",
                )
        else:
            print("  无数据")

    except Exception as e:
        print(f"查询失败: {e}")
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(check_stats())
