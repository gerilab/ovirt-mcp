"""Pydantic data models for oVirt / OLVM Quota management."""

from pydantic import BaseModel, Field


class QuotaClusterLimit(BaseModel):
    """Cluster compute limits defined by a quota."""

    id: str = Field(description="Limit UUID")
    cluster_id: str | None = Field(default=None, description="Target cluster UUID if scoped")
    cluster_name: str | None = Field(default=None, description="Target cluster name if scoped")
    vcpu_limit: int | None = Field(default=None, description="vCPU ceiling (-1 = unlimited)")
    memory_limit_gb: float | None = Field(
        default=None, description="Memory ceiling in GB (-1 = unlimited)"
    )


class QuotaStorageLimit(BaseModel):
    """Storage space limits defined by a quota."""

    id: str = Field(description="Limit UUID")
    storage_domain_id: str | None = Field(
        default=None, description="Target Storage Domain UUID if scoped"
    )
    storage_domain_name: str | None = Field(
        default=None, description="Target Storage Domain name if scoped"
    )
    limit_gb: float | None = Field(
        default=None, description="Storage ceiling in GB (-1 = unlimited)"
    )


class QuotaSummary(BaseModel):
    """Summary of a quota in a Data Center."""

    id: str = Field(description="Quota UUID")
    name: str = Field(description="Quota name")
    description: str | None = Field(default=None, description="Quota description")
    data_center_id: str = Field(description="Parent Data Center UUID")
    data_center_name: str | None = Field(default=None, description="Parent Data Center name")


class QuotaDetail(QuotaSummary):
    """Detailed quota configuration with cluster and storage limits."""

    cluster_limits: list[QuotaClusterLimit] = Field(
        default_factory=list, description="Cluster compute limitations"
    )
    storage_limits: list[QuotaStorageLimit] = Field(
        default_factory=list, description="Storage capacity limitations"
    )


class QuotaResult(BaseModel):
    """Outcome of a quota creation or deletion operation."""

    success: bool = Field(description="Whether the operation succeeded")
    quota_id: str = Field(description="Quota UUID")
    quota_name: str = Field(description="Quota name")
    data_center_name: str = Field(description="Parent Data Center name")
    action: str = Field(description="Action executed: 'create' or 'delete'")
    message: str = Field(description="Human-readable outcome description")
