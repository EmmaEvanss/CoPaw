# -*- coding: utf-8 -*-
"""检查数据库表结构."""

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from swe.envs import load_envs_into_environ
load_envs_into_environ()

from swe.database import get_database_config, DatabaseConnection


async def check_tables():
    """检查表结构."""
    db_config = get_database_config()
    print(f"数据库: {db_config.host}:{db_config.port}/{db_config.database}")

    db = DatabaseConnection(db_config)
    try:
        await db.connect()

        # 检查表是否存在
        tables_query = f"""
            SELECT TABLE_NAME
            FROM information_schema.TABLES
            WHERE TABLE_SCHEMA = '{db_config.database}'
            AND TABLE_NAME LIKE 'swe_tracing%'
            ORDER BY TABLE_NAME
        """
        tables = await db.fetch_all(tables_query)
        print(f"\n=== tracing 相关表 ===")
        for t in tables:
            print(f"  - {t['TABLE_NAME']}")

        # 检查 swe_tracing_traces 表结构
        if tables:
            for table in tables:
                table_name = table['TABLE_NAME']
                columns_query = f"""
                    SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE, COLUMN_DEFAULT
                    FROM information_schema.COLUMNS
                    WHERE TABLE_SCHEMA = '{db_config.database}'
                    AND TABLE_NAME = '{table_name}'
                    ORDER BY ORDINAL_POSITION
                """
                columns = await db.fetch_all(columns_query)
                print(f"\n=== {table_name} 表结构 ===")
                for col in columns:
                    print(f"  {col['COLUMN_NAME']}: {col['DATA_TYPE']} ({col['IS_NULLABLE']})")

    except Exception as e:
        print(f"查询失败: {e}")
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(check_tables())