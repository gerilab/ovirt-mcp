"""Pydantic data models for oVirt / OLVM Data Centers."""

from pydantic import BaseModel, Field


class DataCenterSummary(BaseModel):
    """Compact summary of a Data Center."""

    id: str = Field(description="Data Center UUID")
    name: str = Field(description="Data Center name")
    description: str | None = Field(default=None, description="Data Center description")
    status: str = Field(default="up", description="Data Center status (e.g. 'up', 'uninitialized')")
    storage_type: str = Field(
        default="shared", description="Storage domain type: 'shared' or 'local'"
    )
    compatibility_version: str | None = Field(
        default=None, description="Cluster compatibility level (e.g. '4.7')"
    )
    quota_mode: str | None = Field(
        default=None, description="Quota enforcement mode: 'audit', 'enabled', or 'disabled'"
    )


class DataCenterDetail(DataCenterSummary):
    """Comprehensive specification of a Data Center including memberships."""

    clusters: list[str] = Field(
        default_factory=list, description="Names or UUIDs of clusters attached to this Data Center"
    )
    storage_domains: list[str] = Field(
        default_factory=list,
        description="Names or UUIDs of Storage Domains attached to this Data Center",
    )
    networks: list[str] = Field(
        default_factory=list,
        description="Names or UUIDs of logical networks defined in this Data Center",
    )


class DataCenterOperationResult(BaseModel):
    """Result of an operational action on a Data Center."""

    success: bool = Field(description="Whether the Data Center operation succeeded.")
    data_center_id: str = Field(description="UUID of the Data Center.")
    data_center_name: str = Field(description="Name of the Data Center.")
    action: str = Field(description="Action executed (e.g. 'clean_finished_tasks').")
    dry_run: bool = Field(default=False, description="Whether this was a dry-run simulation.")
    message: str = Field(description="Human-readable result summary.")
