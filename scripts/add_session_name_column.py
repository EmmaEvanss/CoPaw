# -*- coding: utf-8 -*-
"""添加 session_name 字段到 swe_tracing_traces 表.

解决 (1054, "Unknown column 't4.session_name' in 'field list'") 错误。
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "monitor", "src"))

from monitor.app.database.connection import init_db_connection, get_db_connection
from monitor.app.database.config import get_database_config


async def add_session_name_column():
    """添加 session_name 字段."""
    config = get_database_config()
    await init_db_connection(config)
    db = get_db_connection()

    try:
        # 检查字段是否已存在
        check_query = """
            SELECT COUNT(*) as cnt
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
            AND TABLE_NAME = 'swe_tracing_traces'
            AND COLUMN_NAME = 'session_name'
        """
        result = await db.fetch_one(check_query)
        exists = result and result.get("cnt", 0) > 0

        if exists:
            print("字段 session_name 已存在，无需添加")
            return

        # 添加 session_name 字段
        alter_query = """
            ALTER TABLE `swe_tracing_traces`
            ADD COLUMN `session_name` VARCHAR(256) DEFAULT NULL
            COMMENT '会话名称（从第一条消息提取）'
            AFTER `session_id`
        """
        await db.execute(alter_query)
        print("成功添加 session_name 字段")

        # 验证字段已添加
        verify_query = """
            SELECT COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE, COLUMN_DEFAULT
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
            AND TABLE_NAME = 'swe_tracing_traces'
            AND COLUMN_NAME = 'session_name'
        """
        result = await db.fetch_one(verify_query)
        if result:
            print(f"验证成功：字段类型={result['COLUMN_TYPE']}, "
                  f"可为空={result['IS_NULLABLE']}, "
                  f"默认值={result['COLUMN_DEFAULT']}")

    except Exception as e:
        print(f"添加字段失败: {e}")
        raise
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(add_session_name_column())
