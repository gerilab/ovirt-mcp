"""Pydantic models for oVirt / OLVM asynchronous jobs and execution steps."""

from pydantic import BaseModel, Field


class JobStepInfo(BaseModel):
    """Execution step within an asynchronous engine job."""

    id: str = Field(description="Unique step identifier UUID")
    description: str = Field(description="Description of the sub-step execution task")
    status: str = Field(
        description="Execution status of the step (e.g., STARTED, FINISHED, FAILED, ABORTED)"
    )
    type: str | None = Field(
        default=None,
        description="Step phase type (e.g., VALIDATING, EXECUTING, FINALIZING)",
    )
    progress_percent: int | None = Field(
        default=None,
        description="Current step progress percentage (0-100), if tracked",
    )
    number: int | None = Field(
        default=None,
        description="Sequence or order number of this step",
    )
    start_time: str | None = Field(
        default=None,
        description="Timestamp when the step started in ISO format",
    )
    end_time: str | None = Field(
        default=None,
        description="Timestamp when the step completed in ISO format",
    )
    execution_host_id: str | None = Field(
        default=None,
        description="UUID of the hypervisor host executing the step, if bound",
    )
    execution_host_name: str | None = Field(
        default=None,
        description="Name of the hypervisor host executing the step, if bound",
    )
    parent_step_id: str | None = Field(
        default=None,
        description="UUID of the parent step for nested tasks, if applicable",
    )


class JobSummary(BaseModel):
    """Summary overview of an asynchronous engine job."""

    id: str = Field(description="Unique job identifier UUID")
    description: str = Field(description="Human-readable description of the asynchronous task")
    status: str = Field(description="Job status: STARTED, FINISHED, FAILED, ABORTED, or UNKNOWN")
    start_time: str = Field(description="Timestamp when the job was created or started")
    end_time: str | None = Field(
        default=None,
        description="Timestamp when the job concluded, if completed",
    )
    last_updated: str | None = Field(
        default=None,
        description="Timestamp of the most recent status or progress update",
    )
    auto_cleared: bool | None = Field(
        default=None,
        description="Whether the job is automatically purged after completion",
    )
    external: bool | None = Field(
        default=None,
        description="Whether this job was registered by an external integration",
    )
    owner_id: str | None = Field(
        default=None,
        description="UUID of the user account or engine service that owns the job",
    )
    owner_name: str | None = Field(
        default=None,
        description="Name of the user or engine service that owns the job",
    )


class JobDetail(JobSummary):
    """Comprehensive details of an asynchronous job including its execution steps."""

    steps: list[JobStepInfo] = Field(
        default_factory=list,
        description="Ordered sequence of execution sub-steps and their progress",
    )
