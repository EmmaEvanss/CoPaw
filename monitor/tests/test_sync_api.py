# -*- coding: utf-8 -*-
"""Tests for Monitor cron sync API."""

import pytest
from datetime import datetime, timezone

from monitor.app.models.cron import CronJobSyncRequest, ExecutionSyncRequest
from monitor.app.services.cron.sync_service import SyncService


class TestSyncService:
    """Tests for SyncService."""

    @pytest.fixture
    def sync_service(self):
        """Create a SyncService instance."""
        return SyncService()

    def test_cron_job_sync_request_model(self):
        """Test CronJobSyncRequest model validation."""
        request = CronJobSyncRequest(
            id="test-job-id",
            name="Test Job",
            tenant_id="tenant-001",
            enabled=True,
            task_type="agent",
            cron_expr="0 9 * * *",
            timezone="Asia/Shanghai",
            channel="console",
            target_user_id="user-001",
            target_session_id="session-001",
        )
        assert request.id == "test-job-id"
        assert request.name == "Test Job"
        assert request.enabled is True
        assert request.task_type == "agent"

    def test_execution_sync_request_model(self):
        """Test ExecutionSyncRequest model validation."""
        now = datetime.now(timezone.utc)
        request = ExecutionSyncRequest(
            job_id="test-job-id",
            job_name="Test Job",
            tenant_id="tenant-001",
            actual_time=now,
            status="success",
            duration_ms=1500,
        )
        assert request.job_id == "test-job-id"
        assert request.status == "success"
        assert request.duration_ms == 1500

    def test_cron_job_sync_request_with_meta(self):
        """Test CronJobSyncRequest with meta field."""
        request = CronJobSyncRequest(
            id="test-job-id",
            name="Test Job",
            tenant_id="tenant-001",
            task_type="agent",
            cron_expr="0 9 * * *",
            channel="console",
            meta='{"key": "value"}',
        )
        assert request.meta == '{"key": "value"}'

    def test_execution_sync_request_with_error(self):
        """Test ExecutionSyncRequest with error message."""
        now = datetime.now(timezone.utc)
        request = ExecutionSyncRequest(
            job_id="test-job-id",
            tenant_id="tenant-001",
            actual_time=now,
            status="error",
            error_message="Task failed: timeout",
        )
        assert request.status == "error"
        assert request.error_message == "Task failed: timeout"
