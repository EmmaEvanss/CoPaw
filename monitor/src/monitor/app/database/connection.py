# -*- coding: utf-8 -*-
"""Database connection module for Monitor service.

Provides async connection pool management for MySQL-compatible databases.
"""

import logging
from contextlib import asynccontextmanager
from typing import Any, Optional

from .config import MonitorDatabaseConfig

logger = logging.getLogger(__name__)

# Try to import aiomysql, fall back to None if not available
try:
    import aiomysql

    AIOMYSQL_AVAILABLE = True
except ImportError:
    AIOMYSQL_AVAILABLE = False
    logger.debug(
        "aiomysql not installed, database features will be unavailable",
    )


class DatabaseConnection:
    """Database connection with async connection pool.

    Uses aiomysql for async MySQL operations.
    """

    def __init__(self, config: MonitorDatabaseConfig):
        """Initialize database connection.

        Args:
            config: Database configuration
        """
        self.config = config
        self._pool: Optional[Any] = None
        self._connected = False

    @property
    def is_connected(self) -> bool:
        """Check if database is connected."""
        return self._connected and self._pool is not None

    async def connect(self) -> None:
        """Create connection pool."""
        if not AIOMYSQL_AVAILABLE:
            raise RuntimeError(
                "aiomysql is not installed. Please install it with: pip install aiomysql",
            )

        if self._pool is not None:
            return

        try:
            self._pool = await aiomysql.create_pool(
                host=self.config.host,
                port=self.config.port,
                user=self.config.user,
                password=self.config.password,
                db=self.config.database,
                charset=self.config.charset,
                minsize=self.config.min_connections,
                maxsize=self.config.max_connections,
                autocommit=True,
            )
            self._connected = True
            logger.info(
                "Monitor database connection pool created: %s:%s/%s",
                self.config.host,
                self.config.port,
                self.config.database,
            )
        except Exception as e:
            logger.error("Failed to create database connection pool: %s", e)
            self._connected = False
            raise

    async def close(self) -> None:
        """Close connection pool."""
        if self._pool is not None:
            self._pool.close()
            await self._pool.wait_closed()
            self._pool = None
            self._connected = False
            logger.info("Monitor database connection pool closed")

    @asynccontextmanager
    async def acquire(self):
        """Acquire a connection from the pool.

        Yields:
            aiomysql.Connection: Database connection
        """
        if self._pool is None:
            raise RuntimeError("Database not connected")
        async with self._pool.acquire() as conn:
            yield conn

    async def execute(
        self,
        query: str,
        params: Optional[tuple] = None,
    ) -> int:
        """Execute a query and return affected rows.

        Args:
            query: SQL query
            params: Query parameters

        Returns:
            Number of affected rows
        """
        async with self.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, params)
                return cur.rowcount

    async def execute_many(
        self,
        query: str,
        params_list: list[tuple],
    ) -> int:
        """Execute a query multiple times with different parameters.

        Args:
            query: SQL query
            params_list: List of parameter tuples

        Returns:
            Number of affected rows
        """
        if not params_list:
            return 0
        async with self.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.executemany(query, params_list)
                return cur.rowcount

    async def fetch_one(
        self,
        query: str,
        params: Optional[tuple] = None,
    ) -> Optional[dict]:
        """Fetch a single row.

        Args:
            query: SQL query
            params: Query parameters

        Returns:
            Row as dict or None
        """
        async with self.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(query, params)
                row = await cur.fetchone()
                return dict(row) if row else None

    async def fetch_all(
        self,
        query: str,
        params: Optional[tuple] = None,
    ) -> list[dict]:
        """Fetch all rows.

        Args:
            query: SQL query
            params: Query parameters

        Returns:
            List of rows as dicts
        """
        async with self.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(query, params)
                rows = await cur.fetchall()
                return [dict(row) for row in rows] if rows else []

    async def fetch_count(
        self,
        query: str,
        params: Optional[tuple] = None,
    ) -> int:
        """Fetch count from a COUNT query.

        Args:
            query: SQL query (should be a COUNT query)
            params: Query parameters

        Returns:
            Count value
        """
        row = await self.fetch_one(query, params)
        if row:
            # Handle both 'COUNT(*)' and 'count' column names
            for key in row:
                if key.lower().startswith("count"):
                    return int(row[key])
        return 0


# Global database connection instance
_db_connection: Optional[DatabaseConnection] = None


def get_db_connection() -> DatabaseConnection:
    """Get the global database connection instance.

    Raises:
        RuntimeError: If database is not initialized

    Returns:
        DatabaseConnection instance
    """
    if _db_connection is None:
        raise RuntimeError(
            "Database connection not initialized. "
            "Call init_db_connection() first.",
        )
    return _db_connection


async def init_db_connection(
    config: Optional[MonitorDatabaseConfig] = None,
) -> DatabaseConnection:
    """Initialize the global database connection.

    Args:
        config: Database configuration. If None, uses get_database_config().

    Returns:
        DatabaseConnection instance
    """
    global _db_connection

    if config is None:
        from .config import get_database_config

        config = get_database_config()

    _db_connection = DatabaseConnection(config)
    await _db_connection.connect()
    return _db_connection


async def close_db_connection() -> None:
    """Close the global database connection."""
    global _db_connection

    if _db_connection is not None:
        await _db_connection.close()
        _db_connection = None
