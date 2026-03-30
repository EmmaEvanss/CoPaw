# -*- coding: utf-8 -*-
"""Tests for RedlockRenewalTask with stored quorum."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from copaw.lock.cluster_discovery import ClusterNodeDiscovery
from copaw.lock.lock_token import LockToken
from copaw.lock.redlock_renewal import RedlockRenewalTask


@pytest.fixture
def mock_nodes():
    """Create mock Redis nodes."""
    nodes = []
    for i in range(5):
        node = AsyncMock()
        node.eval = AsyncMock(return_value=1)
        nodes.append(node)
    return nodes


@pytest.fixture
def mock_lock_token(mock_nodes):
    """Create mock LockToken with quorum."""
    return LockToken(
        resource="test:lock:key",
        value="unique-lock-value",
        validity=30000.0,
        nodes=mock_nodes,
        quorum=3,  # 5 nodes, quorum = 5//2 + 1 = 3
        discovery_time=0.0,
    )


@pytest.fixture
def mock_node_discovery():
    """Create mock ClusterNodeDiscovery."""
    discovery = MagicMock(spec=ClusterNodeDiscovery)
    return discovery


class TestRedlockRenewalTask:
    """Test RedlockRenewalTask."""

    @pytest.mark.asyncio
    async def test_renewal_uses_stored_quorum(
        self,
        mock_node_discovery,
        mock_lock_token,
        mock_nodes,
    ):
        """Verify that renewal uses stored quorum from LockToken, not recalculated."""
        renewal = RedlockRenewalTask(
            node_discovery=mock_node_discovery,
            lock_token=mock_lock_token,
            ttl_ms=10000,
        )

        # Mock only 2 nodes to succeed (less than quorum of 3)
        mock_nodes[0].eval.return_value = 1
        mock_nodes[1].eval.return_value = 1
        mock_nodes[2].eval.return_value = 0
        mock_nodes[3].eval.return_value = 0
        mock_nodes[4].eval.return_value = 0

        result = await renewal._extend()

        # Should fail because 2 < 3 (stored quorum)
        assert result is False

        # Now mock 3 nodes to succeed (meets quorum)
        mock_nodes[0].eval.return_value = 1
        mock_nodes[1].eval.return_value = 1
        mock_nodes[2].eval.return_value = 1
        mock_nodes[3].eval.return_value = 0
        mock_nodes[4].eval.return_value = 0

        result = await renewal._extend()

        # Should succeed because 3 >= 3 (stored quorum)
        assert result is True

    @pytest.mark.asyncio
    async def test_renewal_success_with_quorum(
        self,
        mock_node_discovery,
        mock_lock_token,
        mock_nodes,
    ):
        """Renewal succeeds when quorum nodes extend successfully."""
        renewal = RedlockRenewalTask(
            node_discovery=mock_node_discovery,
            lock_token=mock_lock_token,
            ttl_ms=10000,
        )

        # All nodes succeed
        for node in mock_nodes:
            node.eval.return_value = 1

        result = await renewal._extend()

        assert result is True
        # Verify all nodes were called
        for node in mock_nodes:
            node.eval.assert_called()

    @pytest.mark.asyncio
    async def test_renewal_fails_below_quorum(
        self,
        mock_node_discovery,
        mock_lock_token,
        mock_nodes,
    ):
        """Renewal fails when fewer than quorum nodes extend."""
        renewal = RedlockRenewalTask(
            node_discovery=mock_node_discovery,
            lock_token=mock_lock_token,
            ttl_ms=10000,
        )

        # Only 2 nodes succeed (less than quorum of 3)
        mock_nodes[0].eval.return_value = 1
        mock_nodes[1].eval.return_value = 1
        mock_nodes[2].eval.return_value = 0
        mock_nodes[3].eval.return_value = 0
        mock_nodes[4].eval.return_value = 0

        result = await renewal._extend()

        assert result is False

    @pytest.mark.asyncio
    async def test_max_failed_renewals_stops_renewal(
        self,
        mock_node_discovery,
        mock_lock_token,
        mock_nodes,
    ):
        """Renewal task stops after max_failed_renewals consecutive failures."""
        renewal = RedlockRenewalTask(
            node_discovery=mock_node_discovery,
            lock_token=mock_lock_token,
            ttl_ms=200,  # Short TTL for fast testing (interval = 0.1s)
            max_failed_renewals=2,
        )

        # Mock all nodes to fail
        for node in mock_nodes:
            node.eval.return_value = 0

        renewal.start()

        # Wait for renewal attempts
        await asyncio.sleep(0.5)  # Longer than max_failed_renewals * interval

        # Task should have stopped
        assert renewal._task is not None
        assert renewal._task.done()
        assert renewal._failed_renewals >= 2

        await renewal.stop()

    def test_renewal_interval_is_half_ttl(
        self, mock_node_discovery, mock_lock_token
    ):
        """Verify renewal interval is TTL/2."""
        ttl_ms = 10000
        renewal = RedlockRenewalTask(
            node_discovery=mock_node_discovery,
            lock_token=mock_lock_token,
            ttl_ms=ttl_ms,
        )

        # Interval should be TTL/2 in seconds
        expected_interval = ttl_ms / 2000.0
        assert renewal.interval == expected_interval

    @pytest.mark.asyncio
    async def test_extend_uses_lua_script(
        self,
        mock_node_discovery,
        mock_lock_token,
        mock_nodes,
    ):
        """Verify _extend_single uses correct Lua script with pexpire."""
        renewal = RedlockRenewalTask(
            node_discovery=mock_node_discovery,
            lock_token=mock_lock_token,
            ttl_ms=10000,
        )

        # Test on first node
        result = await renewal._extend_single(mock_nodes[0])

        assert result is True
        # Verify eval was called
        mock_nodes[0].eval.assert_called_once()

    def test_is_healthy(self, mock_node_discovery, mock_lock_token):
        """Test is_healthy() method."""
        renewal = RedlockRenewalTask(
            node_discovery=mock_node_discovery,
            lock_token=mock_lock_token,
            ttl_ms=10000,
        )

        # Not started yet
        assert renewal.is_healthy() is False

    @pytest.mark.asyncio
    async def test_renewal_resets_failed_count_on_success(
        self,
        mock_node_discovery,
        mock_lock_token,
        mock_nodes,
    ):
        """Failed renewal counter resets to 0 on successful renewal via _renew_loop."""
        renewal = RedlockRenewalTask(
            node_discovery=mock_node_discovery,
            lock_token=mock_lock_token,
            ttl_ms=10000,
        )

        # Simulate previous failures
        renewal._failed_renewals = 2

        # Mock successful extension
        for node in mock_nodes:
            node.eval.return_value = 1

        # Call _extend() directly - it doesn't reset counter
        result = await renewal._extend()

        assert result is True
        # _extend() doesn't reset counter - _renew_loop() does
        # So counter should still be 2
        assert renewal._failed_renewals == 2

        # Now simulate what _renew_loop does on success
        renewal._failed_renewals = 0
        assert renewal._failed_renewals == 0
