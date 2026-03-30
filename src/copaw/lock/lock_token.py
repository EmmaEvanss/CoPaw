# -*- coding: utf-8 -*-
"""LockToken dataclass for Redlock distributed locking."""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import List, TYPE_CHECKING

if TYPE_CHECKING:
    from redis.asyncio import Redis


@dataclass
class LockToken:
    """Redlock lock token with metadata for renewal and validation.

    Attributes:
        resource: The lock key (e.g., "copaw:cron:user:{alice}").
        value: Unique lock value for ownership verification.
        validity: Lock validity time in milliseconds (TTL - elapsed - drift).
        nodes: List of Redis nodes where lock was acquired.
        quorum: Original quorum value from acquisition (N/2 + 1).
        discovery_time: Timestamp when cluster topology was discovered.
    """

    resource: str
    value: str
    validity: float
    nodes: List[Redis]
    quorum: int
    discovery_time: float

    def is_expired(self) -> bool:
        """Check if lock validity has expired.

        Checks elapsed time since discovery against remaining validity.

        Returns:
            True if lock has expired.
        """
        elapsed_ms = (time.time() - self.discovery_time) * 1000
        remaining_validity = self.validity - elapsed_ms
        return remaining_validity <= 0

    def is_discovery_stale(self, max_age: float = 5.0) -> bool:
        """Check if node discovery is stale (may cause split-brain).

        Args:
            max_age: Maximum acceptable age in seconds.

        Returns:
            True if discovery is older than max_age.
        """
        return (time.time() - self.discovery_time) > max_age
