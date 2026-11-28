"""Data models for oVirt / OLVM Storage Domains and backend storage."""

from pydantic import BaseModel, ConfigDict, Field


class StorageLogicalUnit(BaseModel):
    """Technical details of a SAN or iSCSI Logical Unit (LUN)."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(description="LUN identifier / device ID.")
    serial: str | None = Field(
        default=None,
        description="Hardware serial number of the storage LUN / volume.",
    )
    vendor_id: str | None = Field(
        default=None,
        description="Storage hardware vendor (e.g. 'NETAPP', 'SYNOLOGY', 'DELL', 'QNAP', 'PURE').",
    )
    product_id: str | None = Field(
        default=None,
        description="Storage product model or array identifier.",
    )
    size_gb: float = Field(default=0.0, description="Capacity of the LUN in gigabytes.")
    target: str | None = Field(default=None, description="iSCSI Target IQN.")
    address: str | None = Field(
        default=None, description="Storage controller IP address or hostname."
    )
    port: int | None = Field(
        default=None, description="Storage target port (default 3260 for iSCSI)."
    )
    portal: str | None = Field(
        default=None, description="iSCSI portal specification (address:port,tag)."
    )
    paths: int | None = Field(default=None, description="Number of active multipath storage paths.")
    volume_group_id: str | None = Field(
        default=None, description="LVM Volume Group ID containing the LUN."
    )
    status: str | None = Field(default=None, description="LUN operational status.")


class StorageConnectionInfo(BaseModel):
    """Storage server connection endpoint (NFS share, iSCSI portal, POSIX)."""

    model_config = ConfigDict(from_attributes=True)

    id: str | None = Field(default=None, description="UUID of the storage connection.")
    address: str | None = Field(
        default=None,
        description="IP address or FQDN of the storage controller / NAS.",
    )
    path: str | None = Field(default=None, description="NFS exported path or local mount path.")
    target: str | None = Field(default=None, description="iSCSI Target IQN.")
    port: int | None = Field(
        default=None, description="Connection port (e.g. 3260 for iSCSI, 2049 for NFS)."
    )
    portal: str | None = Field(default=None, description="Portal string.")
    type: str | None = Field(
        default=None, description="Connection protocol ('nfs', 'iscsi', 'posixfs', etc.)."
    )
    nfs_version: str | None = Field(
        default=None,
        description="NFS protocol version (e.g. 'v3', 'v4', 'v4_1', 'v4_2').",
    )
    nfs_timeo: int | None = Field(default=None, description="NFS timeo parameter.")
    nfs_retrans: int | None = Field(default=None, description="NFS retrans parameter.")
    mount_options: str | None = Field(default=None, description="NFS mount options.")
    vfs_type: str | None = Field(default=None, description="Virtual File System type.")


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
    overcommit_ratio: float = Field(
        default=0.0,
        description="Ratio of committed virtual space to total capacity (committed_gb / total_gb)",
    )
    space_health: str = Field(
        default="ok",
        description="Capacity health status: 'ok', 'warning_low_space', or 'critical_space'",
    )
    storage_format: str | None = Field(
        default=None, description="Metadata format version (e.g. 'v4', 'v5')"
    )
    address: str | None = Field(
        default=None, description="IP address or hostname of storage server / NAS"
    )
    path: str | None = Field(default=None, description="NFS share export path")
    target: str | None = Field(default=None, description="iSCSI Target IQN if block storage")
    port: int | None = Field(default=None, description="Storage service port (e.g. 3260, 2049)")
    portal: str | None = Field(default=None, description="iSCSI portal specification")
    nfs_version: str | None = Field(
        default=None, description="NFS protocol version if file-based domain"
    )
    mount_options: str | None = Field(default=None, description="NFS mount options")
    volume_group_id: str | None = Field(
        default=None, description="LVM Volume Group UUID for block storage"
    )
    lun_serials: list[str] = Field(
        default_factory=list,
        description="Hardware serial numbers of underlying SAN/iSCSI LUNs",
    )
    lun_count: int = Field(
        default=0,
        description="Count of underlying SAN/iSCSI LUNs",
    )
    data_centers: list[str] = Field(
        default_factory=list,
        description="Names of Data Centers this storage domain is attached to",
    )


class StorageDomainIoStats(BaseModel):
    """Aggregate real-time I/O performance and latency metrics for a storage domain."""

    total_read_bytes_sec: float = Field(
        default=0.0, description="Aggregate read throughput in bytes per second"
    )
    total_write_bytes_sec: float = Field(
        default=0.0, description="Aggregate write throughput in bytes per second"
    )
    total_read_mb_sec: float = Field(
        default=0.0, description="Aggregate read throughput in MB/s across stored disks"
    )
    total_write_mb_sec: float = Field(
        default=0.0, description="Aggregate write throughput in MB/s across stored disks"
    )
    total_read_iops: float = Field(
        default=0.0, description="Aggregate read IOPS across all active disks"
    )
    total_write_iops: float = Field(
        default=0.0, description="Aggregate write IOPS across all active disks"
    )
    avg_read_latency_ms: float = Field(
        default=0.0, description="Average read latency across active disks in milliseconds"
    )
    avg_write_latency_ms: float = Field(
        default=0.0, description="Average write latency across active disks in milliseconds"
    )
    active_disks_count: int = Field(
        default=0, description="Number of virtual disks with active I/O telemetry"
    )


class StorageDomainTopDiskIo(BaseModel):
    """Real-time performance profile of an active virtual disk on a storage domain."""

    disk_id: str = Field(description="UUID of the virtual disk")
    disk_name: str = Field(description="Name or alias of the virtual disk")
    read_mb_sec: float = Field(default=0.0, description="Read throughput in MB/s")
    write_mb_sec: float = Field(default=0.0, description="Write throughput in MB/s")
    read_iops: float = Field(default=0.0, description="Read operations per second")
    write_iops: float = Field(default=0.0, description="Write operations per second")
    read_latency_ms: float = Field(default=0.0, description="Read latency in milliseconds")
    write_latency_ms: float = Field(default=0.0, description="Write latency in milliseconds")


class StorageDomainDetail(StorageDomainSummary):
    """Deep configuration, SAN/NAS hardware serials, and telemetry for an oVirt / OLVM Storage Domain."""

    description: str | None = Field(default=None, description="Description of the storage domain")
    comment: str | None = Field(default=None, description="Free-text user comment")
    block_size: int | None = Field(
        default=None, description="Underlying filesystem/block device block size in bytes"
    )
    discard_after_delete: bool | None = Field(
        default=None, description="Whether discard/TRIM is invoked after disk deletion"
    )
    external_status: str | None = Field(
        default=None, description="External health status ('ok', 'warning', 'error')"
    )
    backup: bool | None = Field(
        default=None, description="Whether this domain is configured for backup"
    )
    master: bool | None = Field(
        default=None, description="Whether this is the master storage domain for the data center"
    )
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

    # SAN / NAS Hardware Identification
    logical_units: list[StorageLogicalUnit] = Field(
        default_factory=list,
        description="Detailed SAN/iSCSI LUN properties (serial number, vendor, product, capacity, paths)",
    )
    storage_connections: list[StorageConnectionInfo] = Field(
        default_factory=list,
        description="Underlying NAS / iSCSI storage connection endpoints",
    )

    io_stats: StorageDomainIoStats | None = Field(
        default=None, description="Aggregate real-time I/O telemetry across stored disks"
    )
    top_io_disks: list[StorageDomainTopDiskIo] = Field(
        default_factory=list,
        description="Top active virtual disks ranked by current I/O activity",
    )
    vms_list: list[str] = Field(
        default_factory=list,
        description="Names of virtual machines hosted on this storage domain",
    )


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
    dry_run: bool = Field(
        default=False, description="Whether this was a dry-run simulation without execution"
    )
    message: str = Field(description="Human-readable outcome description")
