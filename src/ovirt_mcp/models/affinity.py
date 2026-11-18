"""Pydantic models for Affinity Labels and Affinity Groups."""

from pydantic import BaseModel, ConfigDict, Field


class AffinityLabelInfo(BaseModel):
    """Detailed information about an Affinity Label."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(description="UUID of the affinity label")
    name: str = Field(description="Name of the affinity label")
    hosts: list[str] = Field(
        default_factory=list,
        description="List of hypervisor host names or IDs assigned to this label",
    )
    vms: list[str] = Field(
        default_factory=list,
        description="List of virtual machine names or IDs assigned to this label",
    )


class AffinityLabelResult(BaseModel):
    """Result of an Affinity Label lifecycle operation (create/delete)."""

    success: bool = Field(description="Whether the operation succeeded")
    label_id: str | None = Field(default=None, description="UUID of the affinity label")
    label_name: str = Field(description="Name of the affinity label")
    action: str = Field(description="Action executed: 'create' or 'delete'")
    message: str = Field(description="Human-readable outcome description")


class EntityLabelResult(BaseModel):
    """Result of assigning or unassigning a label to/from a Host or VM."""

    success: bool = Field(description="Whether assignment or unassignment succeeded")
    entity_type: str = Field(description="Target entity type: 'host' or 'vm'")
    entity_id: str = Field(description="UUID of the host or VM")
    entity_name: str = Field(description="Name of the host or VM")
    label_id: str = Field(description="UUID of the affinity label")
    label_name: str = Field(description="Name of the affinity label")
    action: str = Field(description="Action executed: 'assign' or 'unassign'")
    current_labels: list[str] = Field(
        default_factory=list,
        description="List of all label names currently attached to this entity",
    )
    message: str = Field(description="Human-readable outcome description")


class AffinityRuleConfig(BaseModel):
    """Rule settings for VM-to-VM or VM-to-Host affinity."""

    enabled: bool = Field(default=True, description="Whether this affinity rule is active")
    positive: bool = Field(
        default=True,
        description="True for positive affinity (run together / on targets), False for negative (anti-affinity)",
    )
    enforcing: bool = Field(
        default=False,
        description="True for hard/mandatory enforcement, False for soft preference",
    )


class AffinityGroupInfo(BaseModel):
    """Detailed configuration of a Cluster Affinity Group."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(description="UUID of the affinity group")
    name: str = Field(description="Name of the affinity group")
    cluster_id: str = Field(description="UUID of the cluster containing this group")
    cluster_name: str = Field(description="Name of the cluster containing this group")
    description: str | None = Field(default=None, description="Description or purpose of the group")
    priority: float | None = Field(default=None, description="Scheduling priority (1-5 or float)")
    vms_rule: AffinityRuleConfig | None = Field(
        default=None, description="Rule governing VM-to-VM affinity/anti-affinity"
    )
    hosts_rule: AffinityRuleConfig | None = Field(
        default=None, description="Rule governing VM-to-Host affinity/anti-affinity"
    )
    vms: list[str] = Field(
        default_factory=list, description="List of VM names or IDs in this affinity group"
    )
    hosts: list[str] = Field(
        default_factory=list, description="List of Host names or IDs in this affinity group"
    )
    vm_labels: list[str] = Field(
        default_factory=list, description="List of VM Affinity Label names or IDs"
    )
    host_labels: list[str] = Field(
        default_factory=list, description="List of Host Affinity Label names or IDs"
    )


class AffinityGroupResult(BaseModel):
    """Result of an Affinity Group lifecycle operation (create/update/delete)."""

    success: bool = Field(description="Whether the operation succeeded")
    group_id: str | None = Field(default=None, description="UUID of the affinity group")
    group_name: str = Field(description="Name of the affinity group")
    cluster_id: str = Field(description="UUID of the cluster")
    cluster_name: str = Field(description="Name of the cluster")
    action: str = Field(description="Action executed: 'create', 'update', or 'delete'")
    message: str = Field(description="Human-readable outcome description")
