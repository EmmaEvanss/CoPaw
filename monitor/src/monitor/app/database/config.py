# -*- coding: utf-8 -*-
"""Monitor database configuration module.

Defines configuration classes for database connections.
"""

import logging
from typing import Optional

from pydantic import BaseModel, Field

from ...config.constant import (
    DB_HOST,
    DB_PORT,
    DB_USER,
    DB_ACCESS,
    DB_NAME,
    DB_MIN_CONN,
    DB_MAX_CONN,
)

logger = logging.getLogger(__name__)


class MonitorDatabaseConfig(BaseModel):
    """Database connection configuration for Monitor service."""

    host: str = Field(default="localhost", description="Database host")
    port: int = Field(default=3306, description="Database port")
    user: str = Field(default="root", description="Database user")
    password: str = Field(default="", description="Database password")
    database: str = Field(default="monitor", description="Database name")
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
) -> MonitorDatabaseConfig:
    """Get database configuration with unified loading logic.

    Configuration priority (highest to lowest):
    1. Explicitly passed parameters
    2. MONITOR_DB_* environment variables (via constant.py)
    3. MonitorDatabaseConfig model defaults

    Args:
        host: Database host
        port: Database port
        user: Database user
        password: Database password
        database: Database name
        min_connections: Minimum connection pool size
        max_connections: Maximum connection pool size

    Returns:
        MonitorDatabaseConfig instance
    """
    # Use constants from constant.py (which read from env vars)
    # Fall back to defaults if env vars are not set

    actual_host = host if host is not None else (DB_HOST or "localhost")
    actual_port = port if port is not None else DB_PORT
    actual_user = user if user is not None else (DB_USER or "root")
    actual_password = password if password is not None else DB_ACCESS
    actual_database = (
        database if database is not None else (DB_NAME or "monitor")
    )
    actual_min_conn = (
        min_connections if min_connections is not None else DB_MIN_CONN
    )
    actual_max_conn = (
        max_connections if max_connections is not None else DB_MAX_CONN
    )

    config = MonitorDatabaseConfig(
        host=actual_host,
        port=actual_port,
        user=actual_user,
        password=actual_password,
        database=actual_database,
        min_connections=actual_min_conn,
        max_connections=actual_max_conn,
    )

    logger.info(
        "Monitor database config: host=%s port=%s database=%s",
        config.host,
        config.port,
        config.database,
    )

    return config
