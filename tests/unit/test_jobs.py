"""Unit tests for asynchronous jobs and execution progress tools."""

from unittest.mock import MagicMock, patch

import pytest

from ovirt_mcp.client.exceptions import NotFoundError
from ovirt_mcp.tools.jobs import (
    extract_job_summary,
    extract_step_info,
    get_job_tool,
    list_jobs_tool,
)


def test_extract_step_info() -> None:
    """Test extracting JobStepInfo from mock SDK Step object."""
    mock_step = MagicMock()
    mock_step.id = "step-101"
    mock_step.description = "Migrating memory state"
    mock_step.name = "Migrating memory state"
    mock_step.status.value = "executing"
    mock_step.type.value = "executing"
    mock_step.progress = 65
    mock_step.number = 2
    mock_step.start_time = "2026-11-20T12:00:00Z"
    mock_step.end_time = None
    mock_step.execution_host.id = "host-002"
    mock_step.execution_host.name = "node01.example.com"
    mock_step.parent_step.id = "step-100"

    info = extract_step_info(mock_step)

    assert info.id == "step-101"
    assert info.description == "Migrating memory state"
    assert info.status == "executing"
    assert info.type == "executing"
    assert info.progress_percent == 65
    assert info.number == 2
    assert info.start_time == "2026-11-20T12:00:00Z"
    assert info.end_time is None
    assert info.execution_host_id == "host-002"
    assert info.execution_host_name == "node01.example.com"
    assert info.parent_step_id == "step-100"


def test_extract_job_summary() -> None:
    """Test extracting JobSummary from mock SDK Job object."""
    mock_job = MagicMock()
    mock_job.id = "job-uuid-1"
    mock_job.description = "Live VM migration"
    mock_job.name = "Live VM migration"
    mock_job.status.value = "started"
    mock_job.start_time = "2026-11-20T11:58:00Z"
    mock_job.end_time = None
    mock_job.last_updated = "2026-11-20T12:01:00Z"
    mock_job.auto_cleared = True
    mock_job.external = False
    mock_job.owner.id = "user-uuid-9"
    mock_job.owner.name = "admin@internal"

    summary = extract_job_summary(mock_job)

    assert summary.id == "job-uuid-1"
    assert summary.description == "Live VM migration"
    assert summary.status == "started"
    assert summary.start_time == "2026-11-20T11:58:00Z"
    assert summary.end_time is None
    assert summary.last_updated == "2026-11-20T12:01:00Z"
    assert summary.auto_cleared is True
    assert summary.external is False
    assert summary.owner_id == "user-uuid-9"
    assert summary.owner_name == "admin@internal"


def test_list_jobs_tool_all() -> None:
    """Test listing all jobs without filter."""
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_sys = MagicMock()
    mock_jobs_service = MagicMock()

    mock_j1 = MagicMock()
    mock_j1.id = "j1"
    mock_j1.description = "Snapshot creation"
    mock_j1.status.value = "finished"
    mock_j1.start_time = "2026-11-20T10:00:00Z"
    mock_j1.end_time = "2026-11-20T10:05:00Z"
    mock_j1.last_updated = "2026-11-20T10:05:00Z"
    mock_j1.auto_cleared = True
    mock_j1.external = False
    mock_j1.owner = None

    mock_j2 = MagicMock()
    mock_j2.id = "j2"
    mock_j2.description = "Disk resize"
    mock_j2.status.value = "started"
    mock_j2.start_time = "2026-11-20T10:10:00Z"
    mock_j2.end_time = None
    mock_j2.last_updated = "2026-11-20T10:12:00Z"
    mock_j2.auto_cleared = False
    mock_j2.external = False
    mock_j2.owner = None

    mock_jobs_service.list.return_value = [mock_j1, mock_j2]
    mock_sys.jobs_service.return_value = mock_jobs_service
    mock_conn.system_service.return_value = mock_sys
    mock_client.get_connection.return_value = mock_conn

    with patch("ovirt_mcp.tools.jobs.get_client", return_value=mock_client):
        results = list_jobs_tool(max_jobs=10)

    assert len(results) == 2
    assert results[0].id == "j1"
    assert results[0].status == "finished"
    assert results[1].id == "j2"
    assert results[1].status == "started"


def test_list_jobs_tool_filtered() -> None:
    """Test listing jobs filtered by status."""
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_sys = MagicMock()
    mock_jobs_service = MagicMock()

    mock_j1 = MagicMock()
    mock_j1.id = "j1"
    mock_j1.description = "Snapshot creation"
    mock_j1.status.value = "finished"
    mock_j1.start_time = "2026-11-20T10:00:00Z"
    mock_j1.end_time = "2026-11-20T10:05:00Z"
    mock_j1.last_updated = "2026-11-20T10:05:00Z"
    mock_j1.auto_cleared = True
    mock_j1.external = False
    mock_j1.owner = None

    mock_j2 = MagicMock()
    mock_j2.id = "j2"
    mock_j2.description = "Disk resize"
    mock_j2.status.value = "started"
    mock_j2.start_time = "2026-11-20T10:10:00Z"
    mock_j2.end_time = None
    mock_j2.last_updated = "2026-11-20T10:12:00Z"
    mock_j2.auto_cleared = False
    mock_j2.external = False
    mock_j2.owner = None

    mock_jobs_service.list.return_value = [mock_j1, mock_j2]
    mock_sys.jobs_service.return_value = mock_jobs_service
    mock_conn.system_service.return_value = mock_sys
    mock_client.get_connection.return_value = mock_conn

    with patch("ovirt_mcp.tools.jobs.get_client", return_value=mock_client):
        results = list_jobs_tool(status="STARTED")

    assert len(results) == 1
    assert results[0].id == "j2"
    assert results[0].status == "started"


def test_get_job_tool_success() -> None:
    """Test retrieving job details with child execution steps."""
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_sys = MagicMock()
    mock_jobs_service = MagicMock()
    mock_job_service = MagicMock()
    mock_steps_service = MagicMock()

    mock_job = MagicMock()
    mock_job.id = "j100"
    mock_job.description = "Migrating VM db-srv01"
    mock_job.name = "Migrating VM db-srv01"
    mock_job.status.value = "started"
    mock_job.start_time = "2026-11-20T11:00:00Z"
    mock_job.end_time = None
    mock_job.last_updated = "2026-11-20T11:02:00Z"
    mock_job.auto_cleared = True
    mock_job.external = False
    mock_job.owner.id = "u1"
    mock_job.owner.name = "admin@internal"

    mock_step1 = MagicMock()
    mock_step1.id = "s1"
    mock_step1.description = "Validating target host"
    mock_step1.name = "Validating target host"
    mock_step1.status.value = "finished"
    mock_step1.type.value = "validating"
    mock_step1.progress = 100
    mock_step1.number = 1
    mock_step1.start_time = "2026-11-20T11:00:01Z"
    mock_step1.end_time = "2026-11-20T11:00:03Z"
    mock_step1.execution_host = None
    mock_step1.parent_step = None

    mock_step2 = MagicMock()
    mock_step2.id = "s2"
    mock_step2.description = "Transferring RAM blocks"
    mock_step2.name = "Transferring RAM blocks"
    mock_step2.status.value = "started"
    mock_step2.type.value = "executing"
    mock_step2.progress = 42
    mock_step2.number = 2
    mock_step2.start_time = "2026-11-20T11:00:03Z"
    mock_step2.end_time = None
    mock_step2.execution_host.id = "h1"
    mock_step2.execution_host.name = "node01.example.com"
    mock_step2.parent_step = None

    mock_job_service.get.return_value = mock_job
    mock_steps_service.list.return_value = [mock_step1, mock_step2]
    mock_job_service.steps_service.return_value = mock_steps_service
    mock_jobs_service.job_service.return_value = mock_job_service

    mock_sys.jobs_service.return_value = mock_jobs_service
    mock_conn.system_service.return_value = mock_sys
    mock_client.get_connection.return_value = mock_conn

    with patch("ovirt_mcp.tools.jobs.get_client", return_value=mock_client):
        detail = get_job_tool(job_id="j100")

    assert detail.id == "j100"
    assert detail.description == "Migrating VM db-srv01"
    assert detail.status == "started"
    assert detail.owner_name == "admin@internal"
    assert len(detail.steps) == 2
    assert detail.steps[0].id == "s1"
    assert detail.steps[0].status == "finished"
    assert detail.steps[0].progress_percent == 100
    assert detail.steps[1].id == "s2"
    assert detail.steps[1].status == "started"
    assert detail.steps[1].progress_percent == 42
    assert detail.steps[1].execution_host_name == "node01.example.com"


def test_get_job_tool_not_found() -> None:
    """Test get_job_tool raises NotFoundError when job does not exist."""
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_sys = MagicMock()
    mock_jobs_service = MagicMock()
    mock_job_service = MagicMock()

    mock_job_service.get.side_effect = Exception("Job not found")
    mock_jobs_service.job_service.return_value = mock_job_service
    mock_sys.jobs_service.return_value = mock_jobs_service
    mock_conn.system_service.return_value = mock_sys
    mock_client.get_connection.return_value = mock_conn

    with (
        patch("ovirt_mcp.tools.jobs.get_client", return_value=mock_client),
        pytest.raises(NotFoundError),
    ):
        get_job_tool(job_id="nonexistent-id")
