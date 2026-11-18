"""Data models for oVirt / OLVM Storage Domains and backend storage."""

from pydantic import BaseModel, ConfigDict, Field


class StorageDomainSummary(BaseModel):
    """Summary of an oVirt / OLVM Storage Domain."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(description="UUID of the storage domain")
    name: str = Field(description="Display name of the storage domain")
    type: str = Field(description="Domain purpose: 'data', 'iso', 'export', or 'image'")
    storage_type: str = Field(
        description="Underlying storage protocol: 'nfs', 'iscsi', 'fcp', 'glance', 'local'"
    )
    status: str = Field(
        default="unknown",
        description="Operational status: 'active', 'maintenance', 'unattached', or 'inactive'",
    )
    available_gb: float = Field(description="Free space in gigabytes")
    used_gb: float = Field(description="Used space in gigabytes")
    committed_gb: float = Field(description="Committed / over-allocated space in gigabytes")
    total_gb: float = Field(description="Total storage capacity in gigabytes")
    usage_percent: float = Field(description="Storage utilization percentage (0-100%)")
    storage_format: str | None = Field(
        default=None, description="Metadata format version (e.g. 'v4', 'v5')"
    )
    address: str | None = Field(
        default=None, description="IP address or hostname of storage server"
    )
    path: str | None = Field(default=None, description="NFS share export path")
    target: str | None = Field(default=None, description="iSCSI Target IQN if block storage")
    data_centers: list[str] = Field(
        default_factory=list,
        description="Names of Data Centers this storage domain is attached to",
    )


class StorageDomainDetail(StorageDomainSummary):
    """Deep configuration and telemetry for an oVirt / OLVM Storage Domain."""

    description: str | None = Field(default=None, description="Description of the storage domain")
    warning_low_space_indicator: int | None = Field(
        default=None, description="Threshold percentage for low space warning"
    )
    critical_space_action_blocker: int | None = Field(
        default=None, description="Threshold GB for blocking VM operations due to critical space"
    )
    supports_discard: bool = Field(
        default=False, description="Whether storage backend supports TRIM / discard"
    )
    supports_discard_zeroes_data: bool = Field(
        default=False, description="Whether discard zeroes underlying data blocks"
    )
    wipe_after_delete: bool = Field(
        default=False, description="Whether deleted virtual disks are scrubbed"
    )
    disks_count: int = Field(default=0, description="Number of virtual disks stored in domain")
    templates_count: int = Field(default=0, description="Number of VM templates stored in domain")
    vms_count: int = Field(default=0, description="Number of VMs with lease or OVF store in domain")


class StorageDomainResult(BaseModel):
    """Result of a storage domain lifecycle action."""

    success: bool = Field(description="Whether the operation succeeded")
    storage_domain_id: str | None = Field(default=None, description="UUID of the storage domain")
    storage_domain_name: str = Field(description="Name of the storage domain")
    action: str = Field(
        description="Action executed: 'create_nfs', 'create_iscsi', 'attach', 'detach', 'activate', 'maintenance', 'delete'"
    )
    data_center_name: str | None = Field(
        default=None, description="Name of the affected Data Center if applicable"
    )
    status: str | None = Field(default=None, description="New status of the storage domain")
    message: str = Field(description="Human-readable outcome description")
