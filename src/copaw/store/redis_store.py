# -*- coding: utf-8 -*-
"""Redis-based temporary data storage with TTL."""
from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, List, Optional

from redis.asyncio import Redis

logger = logging.getLogger(__name__)


class RedisHashStore:
    """Hash-based storage with automatic TTL expiration.

    Uses Redis Hash for field storage with TTL on the entire key.
    Suitable for temporary data like console_push, download_tasks.
    """

    def __init__(self, redis: Redis, key_prefix: str, default_ttl: int):
        """Initialize store.

        Args:
            redis: Redis client.
            key_prefix: Key prefix for namespacing.
            default_ttl: Default TTL in seconds.
        """
        self.redis = redis
        self.key_prefix = key_prefix
        self.default_ttl = default_ttl

    def _make_key(self, identifier: str) -> str:
        """Generate storage key."""
        return f"{self.key_prefix}:{identifier}"

    async def set(
        self,
        identifier: str,
        field: str,
        value: Any,
        ttl: Optional[int] = None,
    ) -> None:
        """Set field value with TTL.

        Args:
            identifier: Resource identifier.
            field: Hash field name.
            value: Value to store (will be JSON serialized).
            ttl: TTL in seconds (uses default if None).
        """
        key = self._make_key(identifier)
        ttl = ttl or self.default_ttl

        await self.redis.hset(key, field, json.dumps(value))
        await self.redis.expire(key, ttl)

    async def get(self, identifier: str, field: str) -> Optional[Any]:
        """Get field value.

        Args:
            identifier: Resource identifier.
            field: Hash field name.

        Returns:
            Deserialized value or None if not found/expired.
        """
        key = self._make_key(identifier)
        result = await self.redis.hget(key, field)

        if result is None:
            return None

        return json.loads(result)

    async def get_all(self, identifier: str) -> dict[str, Any]:
        """Get all fields for identifier.

        Args:
            identifier: Resource identifier.

        Returns:
            Dictionary of field -> value.
        """
        key = self._make_key(identifier)
        result = await self.redis.hgetall(key)

        return {k.decode(): json.loads(v) for k, v in result.items()}

    async def delete(self, identifier: str, field: str) -> None:
        """Delete field.

        Args:
            identifier: Resource identifier.
            field: Hash field name.
        """
        key = self._make_key(identifier)
        await self.redis.hdel(key, field)

    async def clear(self, identifier: str) -> None:
        """Delete entire key.

        Args:
            identifier: Resource identifier.
        """
        key = self._make_key(identifier)
        await self.redis.delete(key)


class ConsolePushStore:
    """Store for console push messages with user isolation."""

    def __init__(self, redis: Redis, ttl: int = 60):
        """Initialize store.

        Args:
            redis: Redis client.
            ttl: TTL in seconds for messages.
        """
        self._store = RedisHashStore(
            redis=redis,
            key_prefix="copaw:console:push",
            default_ttl=ttl,
        )
        self._ttl = ttl

    def _make_session_key(self, user_id: str | None, session_id: str) -> str:
        """Generate session key with optional user isolation."""
        if user_id:
            return f"{user_id}:{session_id}"
        return session_id

    async def append(
        self,
        user_id: str | None,
        session_id: str,
        text: str,
    ) -> None:
        """Append a message to the session.

        Args:
            user_id: Optional user identifier for isolation.
            session_id: Session identifier.
            text: Message text.
        """
        key = self._make_session_key(user_id, session_id)
        msg_id = f"msg:{int(time.time() * 1000)}"
        await self._store.set(
            key,
            msg_id,
            {"id": msg_id, "text": text, "ts": time.time()},
            ttl=self._ttl,
        )

    async def take(
        self,
        user_id: str | None,
        session_id: str,
    ) -> List[Dict[str, Any]]:
        """Take all messages for a session (removes them after retrieval).

        Args:
            user_id: Optional user identifier for isolation.
            session_id: Session identifier.

        Returns:
            List of messages.
        """
        key = self._make_session_key(user_id, session_id)
        data = await self._store.get_all(key)
        messages = list(data.values())
        # Sort by timestamp
        messages.sort(key=lambda x: x.get("ts", 0))
        # Clear after reading
        await self._store.clear(key)
        return messages

    async def take_all(
        self,
        user_id: str | None = None,
    ) -> List[Dict[str, Any]]:
        """Take all messages for all sessions (admin/cleanup use).

        Args:
            user_id: Optional user identifier to filter.

        Returns:
            List of all messages.
        """
        # This is a simplified implementation
        # In production, you might want to use Redis SCAN
        logger.warning("take_all() not fully implemented - returns empty list")
        return []

    async def get_recent(
        self,
        user_id: str | None = None,
        max_age_seconds: int = 60,
    ) -> List[Dict[str, Any]]:
        """Get recent messages without removing them.

        Args:
            user_id: Optional user identifier for isolation.
            max_age_seconds: Maximum age of messages.

        Returns:
            List of recent messages.
        """
        # This is a simplified implementation
        # In production, you'd filter by timestamp
        logger.warning(
            "get_recent() not fully implemented - returns empty list",
        )
        return []
