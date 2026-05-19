#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""检查数据库中的 session 和用户停留数据."""

import asyncio
import sys
sys.path.insert(0, '.')

from monitor.app.database.connection import Database


async def check_data():
    """检查数据库数据."""
    db = Database()
    await db.connect()

    # 检查 swe_tracing_traces 表的基本数据
    print('=== 1. 总 trace 数量 ===')
    row = await db.fetch_one('SELECT COUNT(*) as cnt FROM swe_tracing_traces')
    print(f'总 trace: {row["cnt"]}')

    # 检查 session 分布
    print('\n=== 2. Session trace 数量分布 ===')
    rows = await db.fetch_all('''
        SELECT trace_count, COUNT(*) as session_count
        FROM (
            SELECT session_id, COUNT(*) as trace_count
            FROM swe_tracing_traces
            WHERE session_id IS NOT NULL AND session_id != ''
            GROUP BY session_id
        ) AS t
        GROUP BY trace_count
        ORDER BY trace_count
        LIMIT 10
    ''')
    for r in rows:
        print(f'  {r["trace_count"]}轮: {r["session_count"]}个session')

    # 检查超过3轮的session数量
    print('\n=== 3. 多轮session统计 (>3轮) ===')
    row = await db.fetch_one('''
        SELECT COUNT(*) as total_sessions,
               SUM(CASE WHEN trace_count > 3 THEN 1 ELSE 0 END) as multi_round_sessions
        FROM (
            SELECT session_id, COUNT(*) as trace_count
            FROM swe_tracing_traces
            WHERE session_id IS NOT NULL AND session_id != ''
            GROUP BY session_id
        ) AS session_counts
    ''')
    print(f'  总 session: {row["total_sessions"]}')
    print(f'  多轮 session (>3): {row["multi_round_sessions"]}')
    if row["total_sessions"] > 0:
        ratio = float(row["multi_round_sessions"]) / float(row["total_sessions"]) * 100
        print(f'  多轮占比: {ratio:.1f}%')

    # 检查用户停留时间分布
    print('\n=== 4. 用户停留时间分布 ===')
    rows = await db.fetch_all('''
        SELECT user_id,
               TIMESTAMPDIFF(SECOND, MIN(start_time), MAX(start_time)) as stay_seconds,
               COUNT(*) as trace_count,
               MIN(start_time) as first_time,
               MAX(start_time) as last_time
        FROM swe_tracing_traces
        WHERE user_id != 'default'
        GROUP BY user_id
        ORDER BY stay_seconds DESC
        LIMIT 10
    ''')
    for r in rows:
        print(f'  user={r["user_id"]}, traces={r["trace_count"]}, stay={r["stay_seconds"]}s')
        print(f'    first={r["first_time"]}, last={r["last_time"]}')

    # 检查平均停留时间
    print('\n=== 5. 平均停留时间 ===')
    row = await db.fetch_one('''
        SELECT AVG(stay_seconds) as avg_stay
        FROM (
            SELECT user_id,
                   TIMESTAMPDIFF(SECOND, MIN(start_time), MAX(start_time)) as stay_seconds
            FROM swe_tracing_traces
            WHERE user_id != 'default'
            GROUP BY user_id
            HAVING stay_seconds > 0
        ) AS user_stays
    ''')
    print(f'  平均停留时间: {row["avg_stay"]}秒')

    await db.close()


if __name__ == '__main__':
    asyncio.run(check_data())