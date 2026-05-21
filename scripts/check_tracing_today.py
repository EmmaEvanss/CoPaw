# -*- coding: utf-8 -*-
"""检查今天(2026-05-19)的 tracing 数据."""

import asyncio
import sys
from datetime import datetime

sys.path.insert(0, "src")

from swe.envs import load_envs_into_environ

load_envs_into_environ()

from swe.database import get_database_config, DatabaseConnection


async def check_data() -> None:
    """检查今天的数据库数据."""
    db_config = get_database_config()
    db = DatabaseConnection(db_config)

    try:
        await db.connect()
        print("数据库连接成功\n")

        target_date = "2026-05-19"
        start_date = datetime(2026, 5, 19, 0, 0, 0)
        end_date = datetime(2026, 5, 20, 0, 0, 0)

        # 检查今天的 trace 数量
        print(f"=== 1. {target_date} trace 数量 ===")
        row = await db.fetch_one("""
            SELECT COUNT(*) as cnt
            FROM swe_tracing_traces
            WHERE start_time >= %s AND start_time < %s
              AND user_id != 'default'
        """, (start_date, end_date))
        print(f"  今天 trace: {row['cnt']}")

        # 检查今天的 session 分布
        print(f"\n=== 2. {target_date} Session trace 数量分布 ===")
        rows = await db.fetch_all("""
            SELECT trace_count, COUNT(*) as session_count
            FROM (
                SELECT session_id, COUNT(*) as trace_count
                FROM swe_tracing_traces
                WHERE start_time >= %s AND start_time < %s
                  AND session_id IS NOT NULL AND session_id != ''
                  AND user_id != 'default'
                GROUP BY session_id
            ) AS t
            GROUP BY trace_count
            ORDER BY trace_count
            LIMIT 10
        """, (start_date, end_date))
        for r in rows:
            print(f"  {r['trace_count']}轮: {r['session_count']}个session")

        # 检查今天超过3轮的session数量
        print(f"\n=== 3. {target_date} 多轮session统计 (>3轮) ===")
        row = await db.fetch_one("""
            SELECT COUNT(*) as total_sessions,
                   SUM(CASE WHEN trace_count > 3 THEN 1 ELSE 0 END) as multi_round_sessions
            FROM (
                SELECT session_id, COUNT(*) as trace_count
                FROM swe_tracing_traces
                WHERE start_time >= %s AND start_time < %s
                  AND session_id IS NOT NULL AND session_id != ''
                  AND user_id != 'default'
                GROUP BY session_id
            ) AS session_counts
        """, (start_date, end_date))
        print(f"  总 session: {row['total_sessions']}")
        print(f"  多轮 session (>3): {row['multi_round_sessions']}")
        if row["total_sessions"] and int(row["total_sessions"]) > 0:
            ratio = float(row["multi_round_sessions"]) / float(row["total_sessions"]) * 100
            print(f"  多轮占比: {ratio:.1f}%")

        # 检查今天的用户停留时间分布
        print(f"\n=== 4. {target_date} 用户停留时间分布 (TOP10) ===")
        rows = await db.fetch_all("""
            SELECT user_id,
                   TIMESTAMPDIFF(SECOND, MIN(start_time), MAX(start_time)) as stay_seconds,
                   COUNT(*) as trace_count,
                   MIN(start_time) as first_time,
                   MAX(start_time) as last_time
            FROM swe_tracing_traces
            WHERE start_time >= %s AND start_time < %s
              AND user_id != 'default'
            GROUP BY user_id
            ORDER BY stay_seconds DESC
            LIMIT 10
        """, (start_date, end_date))
        if rows:
            for r in rows:
                print(f"  user={r['user_id']}, traces={r['trace_count']}, stay={r['stay_seconds']}s")
                print(f"    first={r['first_time']}, last={r['last_time']}")
        else:
            print("  无数据")

        # 检查今天的平均停留时间
        print(f"\n=== 5. {target_date} 平均停留时间 ===")
        row = await db.fetch_one("""
            SELECT AVG(stay_seconds) as avg_stay, COUNT(*) as user_count
            FROM (
                SELECT user_id,
                       TIMESTAMPDIFF(SECOND, MIN(start_time), MAX(start_time)) as stay_seconds
                FROM swe_tracing_traces
                WHERE start_time >= %s AND start_time < %s
                  AND user_id != 'default'
                GROUP BY user_id
                HAVING stay_seconds > 0
            ) AS user_stays
        """, (start_date, end_date))
        print(f"  用户数: {row['user_count']}")
        print(f"  平均停留时间: {row['avg_stay']}秒")

        # 检查今天的数据分布
        print(f"\n=== 6. {target_date} 数据按小时分布 ===")
        rows = await db.fetch_all("""
            SELECT HOUR(start_time) as hour, COUNT(*) as cnt
            FROM swe_tracing_traces
            WHERE start_time >= %s AND start_time < %s
              AND user_id != 'default'
            GROUP BY HOUR(start_time)
            ORDER BY hour
        """, (start_date, end_date))
        for r in rows:
            print(f"  {r['hour']:02d}时: {r['cnt']}条")

    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(check_data())