# -*- coding: utf-8 -*-
"""Tests for Monitor cron query API."""

import pytest

from monitor.app.models.cron import (
    CronJobQueryParams,
    ExecutionQueryParams,
    PaginatedResponse,
    CronJobModel,
    ExecutionModel,
)


class TestQueryParams:
    """Tests for query parameter models."""

    def test_cron_job_query_params_defaults(self):
        """Test default values for CronJobQueryParams."""
        params = CronJobQueryParams()
        assert params.page == 1
        assert params.page_size == 10
        assert params.tenant_id is None
        assert params.status is None

    def test_cron_job_query_params_with_filters(self):
        """Test CronJobQueryParams with filters."""
        params = CronJobQueryParams(
            tenant_id="tenant-001",
            status="active",
            enabled=True,
            page=2,
            page_size=50,
        )
        assert params.tenant_id == "tenant-001"
        assert params.status == "active"
        assert params.enabled is True
        assert params.page == 2
        assert params.page_size == 50

    def test_execution_query_params_defaults(self):
        """Test default values for ExecutionQueryParams."""
        params = ExecutionQueryParams()
        assert params.page == 1
        assert params.page_size == 10
        assert params.job_id is None

    def test_execution_query_params_page_size_limit(self):
        """Test ExecutionQueryParams page_size validation."""
        # page_size max is 100
        params = ExecutionQueryParams(page_size=100)
        assert params.page_size == 100
        # Values above 100 should be rejected by pydantic
        with pytest.raises(Exception):
            ExecutionQueryParams(page_size=200)

    def test_execution_query_params_page_minimum(self):
        """Test ExecutionQueryParams page minimum validation."""
        params = ExecutionQueryParams(page=1)
        assert params.page == 1
        # Values below 1 should be rejected
        with pytest.raises(Exception):
            ExecutionQueryParams(page=0)


class TestPaginatedResponse:
    """Tests for PaginatedResponse model."""

    def test_paginated_response_defaults(self):
        """Test default values for PaginatedResponse."""
        response = PaginatedResponse[CronJobModel]()
        assert response.items == []
        assert response.total == 0
        assert response.page == 1
        assert response.page_size == 10

    def test_paginated_response_with_data(self):
        """Test PaginatedResponse with data."""
        response = PaginatedResponse[CronJobModel](
            items=[],
            total=100,
            page=2,
            page_size=20,
        )
        assert response.total == 100
        assert response.page == 2


class TestCronJobModel:
    """Tests for CronJobModel."""

    def test_cron_job_model_from_dict(self):
        """Test CronJobModel creation from dict."""
        job = CronJobModel(
            id="job-001",
            name="Test Job",
            tenant_id="tenant-001",
            enabled=True,
            task_type="agent",
            cron_expr="0 9 * * *",
            timezone="Asia/Shanghai",
            channel="console",
        )
        assert job.id == "job-001"
        assert job.enabled is True
        assert job.status == "active"  # default value

    def test_cron_job_model_get_meta_dict(self):
        """Test CronJobModel.get_meta_dict method."""
        import json

        job = CronJobModel(
            id="job-001",
            name="Test Job",
            tenant_id="tenant-001",
            task_type="agent",
            cron_expr="0 9 * * *",
            channel="console",
            meta=json.dumps({"key": "value"}),
        )
        meta_dict = job.get_meta_dict()
        assert meta_dict == {"key": "value"}

    def test_cron_job_model_empty_meta(self):
        """Test CronJobModel with empty meta."""
        job = CronJobModel(
            id="job-001",
            name="Test Job",
            tenant_id="tenant-001",
            task_type="agent",
            cron_expr="0 9 * * *",
            channel="console",
            meta="",
        )
        meta_dict = job.get_meta_dict()
        assert meta_dict == {}


class TestExecutionModel:
    """Tests for ExecutionModel."""

    def test_execution_model_from_dict(self):
        """Test ExecutionModel creation from dict."""
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        exec = ExecutionModel(
            job_id="job-001",
            job_name="Test Job",
            tenant_id="tenant-001",
            actual_time=now,
            status="success",
            duration_ms=1500,
        )
        assert exec.job_id == "job-001"
        assert exec.status == "success"
        assert exec.duration_ms == 1500
        assert exec.is_manual is False  # default

    def test_execution_model_with_trace_info(self):
        """Test ExecutionModel with trace info."""
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        exec = ExecutionModel(
            job_id="job-001",
            tenant_id="tenant-001",
            actual_time=now,
            status="success",
            trace_id="trace-001",
            session_id="session-001",
        )
        assert exec.trace_id == "trace-001"
        assert exec.session_id == "session-001"
