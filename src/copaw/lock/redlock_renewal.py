# -*- coding: utf-8 -*-
"""Redlock lock renewal task with stored quorum support."""
from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from redis.asyncio import Redis

from .cluster_discovery import ClusterNodeDiscovery
from .lock_token import LockToken

logger = logging.getLogger(__name__)

# Lua script for atomic check-and-extend
EXTEND_LOCK_SCRIPT = """
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('pexpire', KEYS[1], ARGV[2])
end
return 0
"""


class RedlockRenewalTask:
    """Background task for automatic Redlock renewal.

    Renewal uses the stored quorum from LockToken, not recalculated quorum,
    ensuring correct behavior during cluster scaling.
    """

    def __init__(
        self,
        node_discovery: ClusterNodeDiscovery,
        lock_token: LockToken,
        ttl_ms: int,
        max_failed_renewals: int = 3,
    ):
        """Initialize Redlock renewal task.

        Args:
            node_discovery: ClusterNodeDiscovery instance.
            lock_token: LockToken from successful acquire().
            ttl_ms: Lock TTL in milliseconds.
            max_failed_renewals: Maximum consecutive failures before stopping.
        """
        self.node_discovery = node_discovery
        self.lock_token = lock_token
        self.ttl_ms = ttl_ms
        self.max_failed_renewals = max_failed_renewals

        # Renewal interval is TTL/2 in seconds
        self.interval = ttl_ms / 2000.0
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task | None = None
        self._failed_renewals = 0

    def start(self) -> None:
        """Start the background renewal task."""
        if self._task is not None and not self._task.done():
            logger.warning(
                f"Redlock renewal task already running for {self.lock_token.resource}",
            )
            return

        self._stop_event.clear()
        self._failed_renewals = 0
        self._task = asyncio.create_task(self._renew_loop())
        logger.debug(
            f"Started Redlock renewal task for {self.lock_token.resource} "
            f"(quorum: {self.lock_token.quorum}, interval: {self.interval}s)",
        )

    async def stop(self) -> None:
        """Stop the renewal task with 5s timeout, then cancel."""
        if self._task is None or self._task.done():
            return

        self._stop_event.set()

        try:
            await asyncio.wait_for(self._task, timeout=5.0)
        except asyncio.TimeoutError:
            logger.warning(
                f"Redlock renewal task did not stop gracefully for "
                f"{self.lock_token.resource}, cancelling",
            )
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        logger.debug(
            f"Stopped Redlock renewal task for {self.lock_token.resource} "
            f"(failed renewals: {self._failed_renewals})",
        )

    async def _renew_loop(self) -> None:
        """Main renewal loop."""
        while not self._stop_event.is_set():
            try:
                # Wait for interval or stop signal
                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(),
                        timeout=self.interval,
                    )
                    # Stop was signaled
                    break
                except asyncio.TimeoutError:
                    # Normal timeout, proceed with renewal
                    pass

                if self._stop_event.is_set():
                    break

                # Attempt renewal
                success = await self._extend()

                if success:
                    self._failed_renewals = 0
                    logger.debug(
                        f"Renewed Redlock {self.lock_token.resource} "
                        f"(quorum: {self.lock_token.quorum})",
                    )
                else:
                    self._failed_renewals += 1
                    logger.warning(
                        f"Failed to renew Redlock {self.lock_token.resource} "
                        f"(failure #{self._failed_renewals}, "
                        f"quorum: {self.lock_token.quorum})",
                    )

                    if self._failed_renewals >= self.max_failed_renewals:
                        logger.error(
                            f"Redlock renewal failed {self._failed_renewals} times, "
                            f"stopping renewal for {self.lock_token.resource}",
                        )
                        break

            except asyncio.CancelledError:
                logger.debug(
                    f"Redlock renewal task cancelled for {self.lock_token.resource}",
                )
                break
            except Exception as e:
                logger.error(
                    f"Unexpected error in Redlock renewal for "
                    f"{self.lock_token.resource}: {e}",
                    exc_info=True,
                )
                self._failed_renewals += 1

                if self._failed_renewals >= self.max_failed_renewals:
                    logger.error(
                        f"Too many failures, stopping Redlock renewal for "
                        f"{self.lock_token.resource}",
                    )
                    break

    async def _extend(self) -> bool:
        """Extend lock TTL on acquired nodes using stored quorum.

        CRITICAL: Uses stored quorum from LockToken, not recalculated quorum.
        This ensures renewal works correctly during cluster scaling.

        Returns:
            True if extension succeeded on >= quorum nodes, False otherwise.
        """
        try:
            # Extend lock on all acquired nodes in parallel
            tasks = [
                self._extend_single(node) for node in self.lock_token.nodes
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Count successful extensions
            success_count = sum(
                1 for result in results if isinstance(result, bool) and result
            )

            # Use STORED QUORUM from lock token, not recalculated
            if success_count >= self.lock_token.quorum:
                logger.debug(
                    f"Extended lock on {success_count}/{len(self.lock_token.nodes)} "
                    f"nodes (quorum: {self.lock_token.quorum})",
                )
                return True
            else:
                logger.warning(
                    f"Failed to extend lock: only {success_count}/"
                    f"{len(self.lock_token.nodes)} nodes succeeded "
                    f"(need quorum: {self.lock_token.quorum})",
                )
                return False

        except Exception as e:
            logger.error(
                f"Exception during lock extension for "
                f"{self.lock_token.resource}: {e}",
                exc_info=True,
            )
            return False

    async def _extend_single(self, node: Redis) -> bool:
        """Extend lock on a single node using Lua script.

        Args:
            node: Redis client for the node.

        Returns:
            True if extension succeeded, False otherwise.
        """
        try:
            result = await node.eval(
                EXTEND_LOCK_SCRIPT,
                1,
                self.lock_token.resource,
                self.lock_token.value,
                self.ttl_ms,
            )
            return bool(result)
        except Exception as e:
            logger.debug(f"Failed to extend lock on node: {e}")
            return False

    def is_healthy(self) -> bool:
        """Check if the renewal task is healthy.

        Returns:
            True if renewal is running and healthy, False otherwise.
        """
        return (
            self._task is not None
            and not self._task.done()
            and self._failed_renewals < self.max_failed_renewals
        )
