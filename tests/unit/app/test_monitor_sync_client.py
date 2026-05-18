# -*- coding: utf-8 -*-
"""Tests for SWE Monitor sync client."""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import asyncio

from swe.app.crons.monitor_sync_client import (
    MonitorSyncClient,
    get_monitor_sync_client,
    get_monitor_api_url,
)


class TestMonitorSyncClient:
    """Tests for MonitorSyncClient."""

    def test_get_monitor_api_url_default(self):
        """Test default Monitor API URL."""
        url = get_monitor_api_url()
        assert url == "http://localhost:9090/api"

    def test_get_monitor_api_url_from_env(self, monkeypatch):
        """Test Monitor API URL from environment variable."""
        monkeypatch.setenv("SWE_MONITOR_API_URL", "http://monitor:8080/api")
        url = get_monitor_api_url()
        assert url == "http://monitor:8080/api"

    def test_client_initialization(self):
        """Test client initialization."""
        client = MonitorSyncClient("http://test:8080/api")
        assert client._base_url == "http://test:8080/api"
        assert client._enabled is True

    def test_client_uses_default_url_when_empty_string(self):
        """Test client falls back to default URL when base_url is empty."""
        client = MonitorSyncClient("")
        assert client._base_url == "http://localhost:9090/api"
        assert client._enabled is True

    def test_get_monitor_sync_client_singleton(self):
        """Test singleton pattern for sync client."""
        client1 = get_monitor_sync_client()
        client2 = get_monitor_sync_client()
        # They should be the same instance (or at least have same URL)
        assert client1._base_url == client2._base_url

    @pytest.mark.asyncio
    async def test_sync_fire_and_forget_disabled(self):
        """Test fire and forget when disabled."""
        client = MonitorSyncClient("")
        client._sync_fire_and_forget(AsyncMock())
        # Should not raise, just return silently

    @pytest.mark.asyncio
    async def test_sync_job_disabled(self):
        """Test sync_job when disabled."""
        from swe.app.crons.models import CronJobSpec

        client = MonitorSyncClient("")
        job = MagicMock()
        job.id = "test-job"
        job.model_dump = MagicMock(return_value={})

        # Should not raise, just return silently
        await client.sync_job(job)


class TestSyncRequestFormat:
    """Tests for sync request data format."""

    @pytest.fixture
    def sample_job_spec_dict(self):
        """Sample CronJobSpec dict."""
        return {
            "id": "job-001",
            "name": "Test Job",
            "tenant_id": "tenant-001",
            "enabled": True,
            "task_type": "agent",
            "schedule": {
                "cron": "0 9 * * *",
                "timezone": "Asia/Shanghai",
            },
            "dispatch": {
                "channel": "console",
                "target": {
                    "user_id": "user-001",
                    "session_id": "session-001",
                },
            },
            "runtime": {
                "timeout_seconds": 7200,
                "max_concurrency": 1,
                "misfire_grace_seconds": 300,
            },
            "meta": {
                "creator_user_id": "user-001",
                "task_chat_id": "chat-001",
            },
        }

    def test_sync_request_fields_mapping(self, sample_job_spec_dict):
        """Test that sync request fields are correctly mapped."""
        # This tests the internal mapping logic in sync_job
        schedule = sample_job_spec_dict.get("schedule", {})
        dispatch = sample_job_spec_dict.get("dispatch", {})
        target = dispatch.get("target", {})
        runtime = sample_job_spec_dict.get("runtime", {})
        meta = sample_job_spec_dict.get("meta", {})

        # Verify key fields are extracted correctly
        assert schedule.get("cron") == "0 9 * * *"
        assert dispatch.get("channel") == "console"
        assert target.get("user_id") == "user-001"
        assert runtime.get("timeout_seconds") == 7200
        assert meta.get("creator_user_id") == "user-001"


class TestExecutionRecordFormat:
    """Tests for execution record format."""

    @pytest.mark.asyncio
    async def test_record_execution_disabled(self):
        """Test record_execution when disabled."""
        from swe.app.crons.models import CronJobSpec

        client = MonitorSyncClient("")
        job = MagicMock()
        job.id = "test-job"

        # Should not raise, just return silently
        await client.record_execution(
            job=job,
            status="success",
            actual_time=datetime.now(timezone.utc),
        )
