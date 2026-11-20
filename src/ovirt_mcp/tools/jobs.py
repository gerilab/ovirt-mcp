"""Tools for inspecting asynchronous jobs and execution progress in oVirt / OLVM."""

import contextlib
import logging
from typing import Any

from ovirt_mcp.client import get_client
from ovirt_mcp.client.exceptions import NotFoundError
from ovirt_mcp.models.job import JobDetail, JobStepInfo, JobSummary

logger = logging.getLogger(__name__)


def _clean_opt_str(val: Any) -> str | None:
    """Return stripped string or None if unset or not a string."""
    if val is None or not isinstance(val, str):
        return None
    s = val.strip()
    return s if s else None


def _format_datetime(val: Any) -> str | None:
    """Format SDK datetime to ISO string."""
    if val is None:
        return None
    if hasattr(val, "isoformat"):
        return str(val.isoformat())
    s = str(val).strip()
    return s if s else None


def _format_enum(val: Any) -> str:
    """Format SDK enum value to lowercase string."""
    if val is None:
        return "unknown"
    return str(getattr(val, "value", val)).lower()


def extract_step_info(step: Any) -> JobStepInfo:
    """Extract a typed JobStepInfo model from an oVirt SDK Step object."""
    step_id = str(getattr(step, "id", ""))
    description = str(getattr(step, "description", "") or getattr(step, "name", "") or step_id)
    status_str = _format_enum(getattr(step, "status", None))

    type_obj = getattr(step, "type", None)
    type_str = _format_enum(type_obj) if type_obj is not None else None

    progress_raw = getattr(step, "progress", None)
    progress_percent = None
    if progress_raw is not None:
        with contextlib.suppress(ValueError, TypeError):
            progress_percent = int(progress_raw)

    number_raw = getattr(step, "number", None)
    number_val = None
    if number_raw is not None:
        with contextlib.suppress(ValueError, TypeError):
            number_val = int(number_raw)

    start_time = _format_datetime(getattr(step, "start_time", None))
    end_time = _format_datetime(getattr(step, "end_time", None))

    exec_host = getattr(step, "execution_host", None)
    exec_host_id = str(exec_host.id) if exec_host and getattr(exec_host, "id", None) else None
    exec_host_name = _clean_opt_str(getattr(exec_host, "name", None)) if exec_host else None

    parent_step = getattr(step, "parent_step", None)
    parent_step_id = (
        str(parent_step.id) if parent_step and getattr(parent_step, "id", None) else None
    )

    return JobStepInfo(
        id=step_id,
        description=description,
        status=status_str,
        type=type_str,
        progress_percent=progress_percent,
        number=number_val,
        start_time=start_time,
        end_time=end_time,
        execution_host_id=exec_host_id,
        execution_host_name=exec_host_name,
        parent_step_id=parent_step_id,
    )


def extract_job_summary(job: Any) -> JobSummary:
    """Extract a typed JobSummary model from an oVirt SDK Job object."""
    job_id = str(getattr(job, "id", ""))
    description = str(getattr(job, "description", "") or getattr(job, "name", "") or job_id)
    status_str = _format_enum(getattr(job, "status", None))
    start_time = _format_datetime(getattr(job, "start_time", None)) or ""
    end_time = _format_datetime(getattr(job, "end_time", None))
    last_updated = _format_datetime(getattr(job, "last_updated", None))

    auto_cleared = getattr(job, "auto_cleared", None)
    if auto_cleared is not None:
        auto_cleared = bool(auto_cleared)

    external = getattr(job, "external", None)
    if external is not None:
        external = bool(external)

    owner = getattr(job, "owner", None)
    owner_id = str(owner.id) if owner and getattr(owner, "id", None) else None
    owner_name = _clean_opt_str(getattr(owner, "name", None)) if owner else None

    return JobSummary(
        id=job_id,
        description=description,
        status=status_str,
        start_time=start_time,
        end_time=end_time,
        last_updated=last_updated,
        auto_cleared=auto_cleared,
        external=external,
        owner_id=owner_id,
        owner_name=owner_name,
    )


def list_jobs_tool(
    status: str | None = None,
    max_jobs: int = 50,
) -> list[JobSummary]:
    """Retrieve asynchronous engine jobs (tasks, operations, migrations, disk jobs).

    Args:
        status: Optional status filter ('started', 'finished', 'failed', 'aborted').
        max_jobs: Maximum number of jobs to return (default: 50).

    Returns:
        List of JobSummary objects.
    """
    client = get_client()
    connection = client.get_connection()
    jobs_service = connection.system_service().jobs_service()

    sdk_jobs = jobs_service.list(max=max_jobs if not status else max(max_jobs * 2, 100)) or []
    results: list[JobSummary] = []
    clean_status = status.strip().lower() if status else None

    for j in sdk_jobs:
        summary = extract_job_summary(j)
        if clean_status and summary.status.lower() != clean_status:
            continue
        results.append(summary)
        if len(results) >= max_jobs:
            break

    return results


def get_job_tool(job_id: str) -> JobDetail:
    """Retrieve detailed information and execution sub-steps for a specific asynchronous job.

    Args:
        job_id: The UUID of the job to inspect.

    Returns:
        JobDetail with full job metadata and child execution steps.
    """
    client = get_client()
    connection = client.get_connection()
    jobs_service = connection.system_service().jobs_service()

    try:
        job_service = jobs_service.job_service(job_id)
        job = job_service.get()
    except Exception as e:
        raise NotFoundError("job", job_id) from e

    if not job:
        raise NotFoundError("job", job_id)

    summary = extract_job_summary(job)

    steps: list[JobStepInfo] = []
    try:
        sdk_steps = job_service.steps_service().list() or []
        for s in sdk_steps:
            steps.append(extract_step_info(s))
    except Exception as exc:
        logger.debug("Failed to list steps for job %s: %s", job_id, exc)

    return JobDetail(
        id=summary.id,
        description=summary.description,
        status=summary.status,
        start_time=summary.start_time,
        end_time=summary.end_time,
        last_updated=summary.last_updated,
        auto_cleared=summary.auto_cleared,
        external=summary.external,
        owner_id=summary.owner_id,
        owner_name=summary.owner_name,
        steps=steps,
    )
