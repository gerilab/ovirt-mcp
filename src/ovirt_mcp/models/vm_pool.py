"""Pydantic models for oVirt / OLVM Virtual Machine Pools."""

from pydantic import BaseModel, Field


class VmPoolSummary(BaseModel):
    """Summary of a Virtual Machine Pool."""

    id: str = Field(description="Unique UUID of the VM pool")
    name: str = Field(description="Name of the VM pool")
    description: str | None = Field(default=None, description="Description of the VM pool")
    cluster_id: str = Field(description="Parent Cluster UUID")
    cluster_name: str | None = Field(default=None, description="Parent Cluster name")
    template_id: str = Field(description="Base template UUID from which pool VMs are created")
    template_name: str | None = Field(default=None, description="Base template name")
    size: int = Field(default=1, description="Total number of virtual machines in the pool")
    prestarted_vms: int = Field(
        default=0, description="Number of pre-started, standby VMs kept ready in the pool"
    )
    max_user_vms: int = Field(
        default=1, description="Maximum number of pool VMs a single user is permitted to hold"
    )
    type: str = Field(
        default="automatic",
        description="Pool allocation type: 'automatic' (stateless refresh) or 'manual'",
    )
    stateful: bool = Field(
        default=False, description="Whether VM modifications persist across allocations"
    )


class VmPoolDetail(VmPoolSummary):
    """Detailed representation of a Virtual Machine Pool including member VMs."""

    allocated_vms_count: int = Field(
        default=0, description="Number of pool VMs currently assigned or running"
    )
    vms: list[str] = Field(
        default_factory=list, description="Names of virtual machines belonging to this pool"
    )


class VmPoolResult(BaseModel):
    """Result of a VM pool mutation operation (create, update, delete, allocate)."""

    success: bool = Field(description="Whether the VM pool operation succeeded")
    action: str = Field(
        description="Action executed: 'create', 'update', 'delete', or 'allocate_vm'"
    )
    pool_id: str | None = Field(default=None, description="UUID of the affected VM pool")
    pool_name: str = Field(description="Name of the affected VM pool")
    allocated_vm_id: str | None = Field(
        default=None, description="UUID of the assigned VM if an allocation occurred"
    )
    allocated_vm_name: str | None = Field(
        default=None, description="Name of the assigned VM if an allocation occurred"
    )
    message: str = Field(description="Human-readable outcome description")
