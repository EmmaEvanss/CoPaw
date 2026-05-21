# -*- coding: utf-8 -*-
"""测试 tracing/overview API."""

import asyncio
import sys
import os
import json
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "monitor", "src"))

from monitor.app.database.connection import DatabaseConnection
from monitor.app.database.config import MonitorDatabaseConfig, get_database_config


async def test_overview():
    """测试 overview 查询."""
    print("=== 测试 tracing/overview API ===")

    # 从 ~/.monitor.secret/envs.json 读取数据库配置
    secret_dir = Path.home() / ".monitor.secret"
    envs_path = secret_dir / "envs.json"
    print(f"配置文件路径: {envs_path}")

    if envs_path.exists():
        with open(envs_path, "r", encoding="utf-8") as f:
            envs = json.load(f)
        print(f"数据库配置: host={envs.get('MONITOR_DB_HOST')}, db={envs.get('MONITOR_DB_NAME')}")

        # 设置环境变量
        os.environ["MONITOR_DB_HOST"] = envs.get("MONITOR_DB_HOST", "")
        os.environ["MONITOR_DB_PORT"] = str(envs.get("MONITOR_DB_PORT", 3306))
        os.environ["MONITOR_DB_USER"] = envs.get("MONITOR_DB_USER", "")
        password = envs.get("MONITOR_DB_ACCESS", "")
        # 去掉 BEE_ 前缀
        if password.startswith("BEE_"):
            password = password[4:]
        os.environ["MONITOR_DB_ACCESS"] = password
        os.environ["MONITOR_DB_NAME"] = envs.get("MONITOR_DB_NAME", "")
    else:
        print(f"配置文件不存在: {envs_path}")
        return

    # 获取数据库配置
    db_config = get_database_config()
    print(f"数据库配置: host={db_config.host}, port={db_config.port}, db={db_config.database}")

    # 创建数据库连接
    db = DatabaseConnection(db_config)
    await db.connect()
    print(f"数据库连接状态: {db.is_connected}")

    if not db.is_connected:
        print("数据库未连接，无法测试")
        return

    from monitor.app.services.tracing.query_service import TracingQueryService
    service = TracingQueryService(db)

    if not db.is_connected:
        print("数据库未连接，无法测试")
        return

    service = TracingQueryService(db)

    # 测试参数
    start_date = datetime.now() - timedelta(days=7)
    end_date = datetime.now() + timedelta(days=1)
    source_id = "all"

    print(f"查询参数: source_id={source_id}, start={start_date}, end={end_date}")

    # 直接测试各个查询方法
    print("\n--- 测试 _get_total_users ---")
    total_users = await service._get_total_users(source_id, start_date, end_date)
    print(f"total_users: {total_users}")

    print("\n--- 测试 _get_online_users ---")
    online_result = await service._get_online_users(source_id)
    print(f"online_users: {online_result}")

    print("\n--- 测试 _get_token_stats ---")
    token_row = await service._get_token_stats(source_id, start_date, end_date)
    print(f"token_row: {token_row}")

    print("\n--- 测试 _get_model_distribution ---")
    model_dist = await service._get_model_distribution(source_id, start_date, end_date)
    print(f"model_distribution: {model_dist}")

    print("\n--- 测试 _get_top_tools ---")
    top_tools = await service._get_top_tools(source_id, start_date, end_date)
    print(f"top_tools: {top_tools}")

    print("\n--- 测试 _get_top_skills ---")
    top_skills = await service._get_top_skills(source_id, start_date, end_date)
    print(f"top_skills: {top_skills}")

    print("\n--- 测试 _get_mcp_stats ---")
    mcp_stats = await service._get_mcp_stats(source_id, start_date, end_date)
    print(f"mcp_stats: {mcp_stats}")

    print("\n--- 测试 _get_branch_breakdown ---")
    branch = await service._get_branch_breakdown(source_id, start_date, end_date)
    print(f"branch_breakdown: {branch}")

    print("\n--- 测试 _get_task_status_breakdown ---")
    task_status = await service._get_task_status_breakdown(source_id, start_date, end_date)
    print(f"task_status_breakdown: {task_status}")

    print("\n--- 测试完整 overview ---")
    overview = await service.get_overview_stats(source_id, start_date, end_date)
    print(f"overview stats:")
    print(f"  total_users: {overview.total_users}")
    print(f"  total_tokens: {overview.total_tokens}")
    print(f"  total_sessions: {overview.total_sessions}")
    print(f"  total_conversations: {overview.total_conversations}")
    print(f"  top_skills: {overview.top_skills}")
    print(f"  branch_breakdown: {overview.branch_breakdown}")

    # 关闭连接
    await db.close()


if __name__ == "__main__":
    asyncio.run(test_overview())