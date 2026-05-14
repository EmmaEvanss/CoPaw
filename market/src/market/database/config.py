# -*- coding: utf-8 -*-
"""数据库配置模块."""

from typing import Optional
from pydantic import BaseModel, Field


class DatabaseConfig(BaseModel):
    """Database connection configuration."""

    host: str = Field(default="localhost", description="Database host")
    port: int = Field(default=3306, description="Database port")
    user: str = Field(default="root", description="Database user")
    password: str = Field(default="", description="Database password")
    database: str = Field(default="swe", description="Database name")
    min_connections: int = Field(
        default=2,
        description="Minimum connection pool size",
    )
    max_connections: int = Field(
        default=10,
        description="Maximum connection pool size",
    )
    charset: str = Field(default="utf8mb4", description="Character set")


def get_database_config(
    host: Optional[str] = None,
    port: Optional[int] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    database: Optional[str] = None,
    min_connections: Optional[int] = None,
    max_connections: Optional[int] = None,
) -> DatabaseConfig:
    """获取数据库配置，优先级：参数 > 环境变量 > 默认值."""
    from ..config.constant import (
        DB_HOST,
        DB_PORT,
        DB_USER,
        DB_ACCESS,
        DB_NAME,
        DB_MIN_CONN,
        DB_MAX_CONN,
    )

    return DatabaseConfig(
        host=host if host is not None else DB_HOST,
        port=port if port is not None else DB_PORT,
        user=user if user is not None else DB_USER,
        password=password if password is not None else DB_ACCESS,
        database=database if database is not None else DB_NAME,
        min_connections=(
            min_connections if min_connections is not None else DB_MIN_CONN
        ),
        max_connections=(
            max_connections if max_connections is not None else DB_MAX_CONN
        ),
    )
