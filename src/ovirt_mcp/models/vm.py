"""Pydantic models for Virtual Machine resources."""

from pydantic import BaseModel, Field


class VmSummary(BaseModel):
    """Concise inventory summary of an oVirt / OLVM Virtual Machine."""

    id: str = Field(description="Unique UUID of the virtual machine")
    name: str = Field(description="Display name of the virtual machine")
    status: str = Field(description="Current power state (up, down, paused, migrating, etc.)")
    cluster_name: str | None = Field(default=None, description="Name of the hosting cluster")
    host_name: str | None = Field(default=None, description="Name of running host, if UP")
    memory_mb: int | None = Field(default=None, description="Allocated/desired memory in Megabytes")
    cpu_cores: int | None = Field(
        default=None, description="Total CPU core count (sockets * cores * threads)"
    )
    ip_addresses: list[str] = Field(
        default_factory=list, description="Reported IPv4/IPv6 addresses"
    )
    fqdn: str | None = Field(
        default=None, description="Fully qualified domain name reported by guest agent"
    )
    os_type: str | None = Field(default=None, description="Configured operating system type")
    ha_enabled: bool = Field(
        default=False, description="Whether High Availability is enabled for this VM"
    )
    description: str | None = Field(default=None, description="User description or comment")


class VmCpuDetails(BaseModel):
    """CPU topology, core counts, and scheduling settings."""

    total_cores: int = Field(description="Total vCPU cores (sockets * cores * threads)")
    sockets: int = Field(default=1, description="Number of virtual CPU sockets")
    cores_per_socket: int = Field(default=1, description="Cores per virtual socket")
    threads_per_core: int = Field(default=1, description="Threads per core")
    shares: int | None = Field(default=None, description="CPU shares priority")
    pinning_policy: str | None = Field(
        default=None,
        description="CPU pinning policy (e.g. none, manual, resize_and_pin, dedicated)",
    )
    auto_pinning_policy: str | None = Field(
        default=None, description="Auto pinning policy (e.g. disabled, existing, adjust)"
    )
    custom_cpu_model: str | None = Field(default=None, description="Custom emulated CPU model")
    custom_emulated_machine: str | None = Field(
        default=None, description="Custom emulated machine type (e.g. pc-q35, pc-i440fx)"
    )


class VmMemoryPolicy(BaseModel):
    """Memory allocation, guaranteed physical RAM, and ballooning configuration."""

    allocated_mb: int = Field(
        description="Defined / desired virtual memory size in Megabytes (RAM)"
    )
    guaranteed_mb: int | None = Field(
        default=None,
        description="Physical memory guaranteed to the VM by hypervisor in Megabytes",
    )
    max_memory_mb: int | None = Field(
        default=None,
        description="Maximum memory ceiling in Megabytes for memory ballooning or hotplug",
    )
    ballooning_enabled: bool = Field(
        default=False, description="Whether memory balloon driver is active"
    )
    over_commit_percent: int | None = Field(
        default=None, description="Memory over-commit ratio or percent"
    )


class VmIoAndScsi(BaseModel):
    """I/O threads, VirtIO-SCSI multi-queue, and disk controller architecture."""

    io_threads: int | None = Field(
        default=None, description="Dedicated I/O threads allocated for disk processing"
    )
    virtio_scsi_enabled: bool = Field(
        default=False, description="Whether VirtIO-SCSI controller is enabled"
    )
    virtio_scsi_multi_queues: int | None = Field(
        default=None, description="Configured VirtIO-SCSI multi-queues"
    )
    virtio_scsi_multi_queues_enabled: bool = Field(
        default=False, description="Whether VirtIO-SCSI multi-queue processing is active"
    )
    multi_queues_enabled: bool = Field(
        default=False, description="General multi-queue enabled for networking and storage"
    )


class VmPlacementAndAffinity(BaseModel):
    """Affinity groups, affinity labels, and host placement policy."""

    affinity_groups: list[str] = Field(
        default_factory=list,
        description="Names of cluster affinity groups this VM belongs to (positive/negative/enforcing)",
    )
    affinity_labels: list[str] = Field(default_factory=list, description="Assigned affinity labels")
    tags: list[str] = Field(
        default_factory=list, description="User or system tags attached to this VM"
    )
    placement_affinity: str | None = Field(
        default=None,
        description="Placement affinity (e.g. migratable, user_migratable, pinned)",
    )
    pinned_hosts: list[str] = Field(
        default_factory=list, description="Specific host names the VM is pinned to"
    )


class VmGuestOsInfo(BaseModel):
    """Operating system and guest agent telemetry."""

    configured_os_type: str | None = Field(
        default=None, description="Configured OS type in oVirt (e.g. rhel_8x64)"
    )
    distribution: str | None = Field(
        default=None, description="Guest OS distribution reported by agent"
    )
    kernel_version: str | None = Field(
        default=None, description="Active kernel release reported by guest agent"
    )
    architecture: str | None = Field(
        default=None, description="Operating system architecture (e.g. x86_64)"
    )
    fqdn: str | None = Field(default=None, description="Fully-qualified domain name")
    time_zone: str | None = Field(default=None, description="Guest operating system time zone")


class VmHardwareSecurity(BaseModel):
    """Hardware architecture, BIOS, and protection flags."""

    bios_type: str | None = Field(
        default=None, description="BIOS type (e.g. q35_ovmf, q35_seabios, i440fx_sea_bios)"
    )
    tpm_enabled: bool = Field(default=False, description="Whether virtual TPM chip is enabled")
    delete_protected: bool = Field(
        default=False, description="Whether the VM is protected against accidental deletion"
    )
    stateless: bool = Field(default=False, description="Whether the VM runs in stateless mode")
    soundcard_enabled: bool = Field(default=False, description="Whether soundcard is enabled")
    usb_enabled: bool = Field(
        default=False, description="Whether USB devices/redirection are enabled"
    )
    vm_type: str | None = Field(
        default=None, description="VM optimization type (server, desktop, high_performance)"
    )
    cdrom_iso: str | None = Field(
        default=None, description="Attached CD-ROM / ISO image path or name"
    )
    display_type: str | None = Field(
        default=None, description="Display console protocol (spice, vnc)"
    )


class VmHighAvailability(BaseModel):
    """High availability and failover parameters."""

    enabled: bool = Field(default=False, description="Whether HA is enabled")
    priority: int | None = Field(
        default=None, description="HA priority (higher values get restarted first)"
    )
    watchdog_action: str | None = Field(
        default=None, description="Watchdog action (e.g. reset, poweroff, dump)"
    )
    lease_storage_domain_name: str | None = Field(
        default=None, description="Storage domain holding the SAN lease for split-brain protection"
    )


class VmLifecycleInfo(BaseModel):
    """Runtime lifecycle, timestamps, and pending configuration."""

    creation_time: str | None = Field(default=None, description="Timestamp when VM was created")
    start_time: str | None = Field(default=None, description="Timestamp when VM was last started")
    stop_time: str | None = Field(default=None, description="Timestamp when VM was stopped")
    stop_reason: str | None = Field(
        default=None, description="Reason the VM transitioned to down state"
    )
    next_run_configuration_exists: bool = Field(
        default=False,
        description="Whether configuration changes are pending and require a VM restart to take effect",
    )
    migration_downtime: int | None = Field(
        default=None, description="Maximum permitted migration downtime in milliseconds"
    )


class VmMigrationOptions(BaseModel):
    """Live migration policies, convergence, and compression options."""

    auto_converge: str | None = Field(
        default=None, description="Auto-converge throttling policy (inherit, true, false)"
    )
    compressed: str | None = Field(
        default=None, description="Data stream compression policy (inherit, true, false)"
    )
    encrypted: str | None = Field(
        default=None,
        description="TLS encryption policy during live migration (inherit, true, false)",
    )
    policy: str | None = Field(
        default=None,
        description="Custom migration policy name (e.g. minimal_downtime, suspend, post_copy)",
    )
    parallel_migrations_policy: str | None = Field(
        default=None, description="Parallel migration policy (inherit, auto, custom)"
    )
    custom_parallel_migrations: int | None = Field(
        default=None, description="Configured parallel migration channels count"
    )
    downtime_ms: int | None = Field(
        default=None, description="Maximum permitted migration downtime in milliseconds"
    )


class VmDiskInfo(BaseModel):
    """Virtual machine disk attachment details."""

    id: str = Field(description="Unique UUID of the disk attachment or disk")
    name: str = Field(description="Disk name or alias")
    size_gb: float = Field(description="Disk provisioned size in Gigabytes")
    actual_size_gb: float | None = Field(
        default=None, description="Actual physical disk usage in Gigabytes"
    )
    interface: str = Field(description="Disk interface (e.g. virtio_scsi, virtio, ide)")
    format: str | None = Field(default=None, description="Disk format (cow or raw)")
    sparse: bool | None = Field(
        default=None, description="Whether the disk is thin-provisioned (sparse)"
    )
    bootable: bool = Field(default=False, description="Whether this is a bootable disk")
    read_only: bool = Field(default=False, description="Whether the disk is mounted read-only")
    storage_domain_name: str | None = Field(default=None, description="Target storage domain name")


class VmNicInfo(BaseModel):
    """Virtual machine network interface details."""

    id: str = Field(description="Unique UUID of the network interface")
    name: str = Field(description="NIC device name (e.g. nic1, ens3)")
    network_name: str | None = Field(default=None, description="Logical network name")
    mac_address: str | None = Field(default=None, description="Hardware MAC address")
    interface: str | None = Field(default=None, description="Driver interface (e.g. virtio, e1000)")
    linked: bool = Field(default=True, description="Whether network cable/link is connected")
    ip_addresses: list[str] = Field(default_factory=list, description="Associated IP addresses")


class VmCompactDetail(BaseModel):
    """Token-efficient, lightweight virtual machine details for small context LLMs."""

    id: str = Field(description="Unique UUID of the virtual machine")
    name: str = Field(description="Display name of the virtual machine")
    status: str = Field(description="Current power state (up, down, paused, migrating, etc.)")
    cluster_name: str | None = Field(default=None, description="Hosting cluster name")
    host_name: str | None = Field(default=None, description="Running host name, if UP")
    memory_mb: int | None = Field(default=None, description="Allocated memory in Megabytes")
    cpu_cores: int | None = Field(default=None, description="Total vCPU cores")
    ip_addresses: list[str] = Field(default_factory=list, description="Associated IP addresses")
    fqdn: str | None = Field(default=None, description="Fully qualified domain name")
    os_type: str | None = Field(default=None, description="Configured operating system type")
    ha_enabled: bool = Field(default=False, description="Whether High Availability is enabled")
    disks_summary: list[str] = Field(
        default_factory=list,
        description="Concise disk list in format 'disk_name (size_gb GB)'",
    )
    nics_count: int = Field(default=0, description="Total attached network interfaces")
    snapshots_count: int = Field(default=0, description="Number of existing snapshots")
    description: str | None = Field(default=None, description="User description or comment")


class VmDetail(BaseModel):
    """Comprehensive details of an oVirt / OLVM Virtual Machine."""

    id: str = Field(description="Unique UUID of the virtual machine")
    name: str = Field(description="Display name of the virtual machine")
    status: str = Field(
        description="Current power state (up, down, paused, migrating, unknown, etc.)"
    )
    status_detail: str | None = Field(
        default=None, description="Detailed status message if available"
    )
    cluster_name: str | None = Field(default=None, description="Hosting cluster name")
    host_name: str | None = Field(default=None, description="Running host name, if UP")
    template_name: str | None = Field(default=None, description="Base template name")
    description: str | None = Field(default=None, description="User description or comment")

    cpu: VmCpuDetails = Field(description="CPU topology, cores, pinning, and scheduling")
    memory: VmMemoryPolicy = Field(
        description="Allocated RAM, guaranteed memory, max ceiling, and ballooning"
    )
    io_scsi: VmIoAndScsi = Field(
        description="I/O threads, VirtIO-SCSI multi-queue, and disk queues"
    )
    affinity_and_placement: VmPlacementAndAffinity = Field(
        description="Affinity groups, affinity labels, tags, and pinned hosts"
    )
    guest_os: VmGuestOsInfo = Field(
        description="Operating system, kernel, and guest agent information"
    )
    hardware: VmHardwareSecurity = Field(
        description="Hardware architecture, BIOS, display, and protection flags"
    )
    high_availability: VmHighAvailability = Field(
        description="High availability, watchdog, and storage lease settings"
    )
    migration: VmMigrationOptions = Field(
        description="Live migration policies, compression, convergence, and parallel options"
    )
    lifecycle: VmLifecycleInfo = Field(
        description="Runtime lifecycle, timestamps, stop reasons, and pending restart flags"
    )

    disks: list[VmDiskInfo] = Field(default_factory=list, description="Attached virtual disks")
    nics: list[VmNicInfo] = Field(default_factory=list, description="Attached network interfaces")
    snapshots_count: int = Field(default=0, description="Number of existing snapshots")


class VmLifecycleResult(BaseModel):
    """Result of a virtual machine lifecycle operation (start, stop, reboot)."""

    success: bool = Field(
        description="Whether the lifecycle operation was accepted or reached target state"
    )
    action: str = Field(description="Executed action name (e.g. start, stop, shutdown, reboot)")
    vm_id: str = Field(description="UUID of the virtual machine")
    vm_name: str = Field(description="Name of the virtual machine")
    previous_status: str = Field(
        description="Power status of the VM prior to initiating the action"
    )
    current_status: str = Field(
        description="Current power status of the VM after action initiation or completion"
    )
    graceful: bool | None = Field(
        default=None,
        description=(
            "For stop/shutdown: True if clean shutdown was initiated via guest agent (vtools) / ACPI; "
            "False if hard power-off was executed"
        ),
    )
    message: str = Field(description="Human-readable summary of the operation and outcome")


class VmCreateResult(BaseModel):
    """Result of creating a new virtual machine."""

    success: bool = Field(description="Whether VM creation was successful")
    vm_id: str = Field(description="UUID of the newly created virtual machine")
    vm_name: str = Field(description="Name of the virtual machine")
    cluster_name: str = Field(description="Cluster hosting the virtual machine")
    template_name: str = Field(description="Template used as base for the virtual machine")
    status: str = Field(description="Initial power state (usually 'down' or 'image_locked')")
    memory_mb: int = Field(description="Allocated memory in megabytes")
    cpu_cores: int = Field(description="Total vCPU count")
    message: str = Field(description="Human-readable outcome description")


class VmDeleteResult(BaseModel):
    """Result of deleting a virtual machine."""

    success: bool = Field(description="Whether VM deletion succeeded")
    vm_id: str = Field(description="UUID of the deleted virtual machine")
    vm_name: str = Field(description="Name of the deleted virtual machine")
    disks_detached_only: bool = Field(
        description="Whether disks were preserved (detached) rather than wiped"
    )
    message: str = Field(description="Human-readable outcome description")


class VmMigrateResult(BaseModel):
    """Result of virtual machine live migration."""

    success: bool = Field(description="Whether migration initiation or completion succeeded")
    vm_id: str = Field(description="UUID of the virtual machine")
    vm_name: str = Field(description="Name of the virtual machine")
    source_host: str | None = Field(
        default=None, description="Host where VM was running before migration"
    )
    target_host: str | None = Field(
        default=None, description="Target host where VM migrated, or None if auto-scheduled"
    )
    status: str = Field(
        description="VM power/migration status after action (e.g. 'migrating', 'up')"
    )
    message: str = Field(description="Human-readable outcome description")


class VmPinResult(BaseModel):
    """Result of pinning or unpinning a virtual machine to/from a hypervisor host."""

    success: bool = Field(description="Whether pinning/unpinning succeeded")
    vm_id: str = Field(description="UUID of the virtual machine")
    vm_name: str = Field(description="Name of the virtual machine")
    affinity: str = Field(description="Placement affinity: 'pinned' or 'migratable'")
    pinned_hosts: list[str] = Field(
        default_factory=list, description="List of host names the VM is pinned to"
    )
    message: str = Field(description="Human-readable outcome description")


class VmSnapshotInfo(BaseModel):
    """Information about a virtual machine snapshot."""

    id: str = Field(description="UUID of the snapshot")
    description: str = Field(description="Snapshot description or title")
    snapshot_status: str = Field(description="Snapshot state (e.g. 'ok', 'locked', 'in_preview')")
    snapshot_type: str = Field(
        description="Snapshot type ('regular' for restore points, 'active' for live state)"
    )
    date: str | None = Field(default=None, description="Creation timestamp")
    persist_memorystate: bool = Field(
        default=False, description="Whether guest RAM state is preserved in the snapshot"
    )


class VmSnapshotResult(BaseModel):
    """Result of a snapshot operation (create, restore, delete, preview, commit, undo)."""

    success: bool = Field(description="Whether the snapshot operation succeeded")
    action: str = Field(
        description="Executed action: 'create', 'restore', 'delete', 'preview', 'commit', 'undo'"
    )
    vm_id: str = Field(description="UUID of the virtual machine")
    vm_name: str = Field(description="Name of the virtual machine")
    snapshot_id: str | None = Field(default=None, description="UUID of the affected snapshot")
    description: str | None = Field(
        default=None, description="Description of the affected snapshot"
    )
    restore_memory: bool = Field(
        default=False,
        description="Whether guest RAM state was restored / previewed online",
    )
    message: str = Field(description="Human-readable outcome description")
