"""Pydantic data models for oVirt / OLVM Logical Networks."""

from pydantic import BaseModel, Field


class LogicalNetworkSummary(BaseModel):
    """Summary of a logical network."""

    id: str = Field(description="Logical network UUID")
    name: str = Field(description="Logical network name")
    description: str | None = Field(default=None, description="Network description")
    data_center_id: str = Field(description="Parent Data Center UUID")
    data_center_name: str | None = Field(default=None, description="Parent Data Center name")
    vlan_id: int | None = Field(
        default=None, description="VLAN encapsulation tag (None = untagged)"
    )
    mtu: int | None = Field(default=None, description="Configured MTU (e.g. 1500, 9000)")
    status: str = Field(default="operational", description="Network operational status")


class LogicalNetworkResult(BaseModel):
    """Outcome of a logical network creation or deletion operation."""

    success: bool = Field(description="Whether the operation succeeded")
    network_id: str = Field(description="Logical network UUID")
    network_name: str = Field(description="Logical network name")
    data_center_name: str = Field(description="Parent Data Center name")
    action: str = Field(description="Action executed: 'create' or 'delete'")
    message: str = Field(description="Human-readable outcome description")
