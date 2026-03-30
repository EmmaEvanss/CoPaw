# -*- coding: utf-8 -*-
"""Tests for LockToken dataclass."""
import time

import pytest

from src.copaw.lock.lock_token import LockToken


class TestLockToken:
    """Test LockToken dataclass."""

    def test_lock_token_creation(self):
        """Test basic LockToken creation."""
        token = LockToken(
            resource="copaw:cron:user:{alice}",
            value="abc-123",
            validity=590000.0,
            nodes=[],
            quorum=2,
            discovery_time=1234567890.0,
        )
        assert token.resource == "copaw:cron:user:{alice}"
        assert token.value == "abc-123"
        assert token.validity == 590000.0
        assert token.quorum == 2
        assert token.discovery_time == 1234567890.0

    def test_lock_token_is_expired(self):
        """Test validity expiration check."""
        # Token created with 100ms validity, should expire after that
        current_time = time.time()
        token = LockToken(
            resource="test",
            value="v",
            validity=100.0,  # 100ms remaining
            nodes=[],
            quorum=1,
            discovery_time=current_time,
        )
        # Token should not be expired immediately
        assert not token.is_expired()
        # Wait for validity to pass
        time.sleep(0.15)  # 150ms
        # Now it should be expired
        assert token.is_expired()

    def test_lock_token_is_discovery_stale(self):
        """Test discovery staleness check."""
        current_time = time.time()
        token = LockToken(
            resource="test",
            value="v",
            validity=10000.0,
            nodes=[],
            quorum=1,
            discovery_time=current_time - 10,  # Discovery was 10 seconds ago
        )
        # Should be stale after 5 seconds (default)
        assert token.is_discovery_stale(max_age=5.0)
        # Should not be stale with 15 second threshold
        assert not token.is_discovery_stale(max_age=15.0)
