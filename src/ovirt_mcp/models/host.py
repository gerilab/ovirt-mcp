"""Pydantic data models for oVirt / OLVM Hypervisor Host infrastructure."""

from pydantic import BaseModel, Field


class HostSummary(BaseModel):
    """Compact summary of a hypervisor host for inventory listings."""

    id: str = Field(description="UUID of the hypervisor host")
    name: str = Field(description="Display name / FQDN of the host")
    status: str = Field(
        description="Host operational status: 'up', 'maintenance', 'down', 'non_operational', etc."
    )
    cluster_name: str = Field(description="Parent cluster name")
    cluster_id: str | None = Field(default=None, description="Parent cluster UUID")
    address: str = Field(description="IP address or resolvable hostname of the host")
    active_vms_count: int = Field(
        default=0, description="Number of virtual machines currently running on this host"
    )
    spm_status: str = Field(
        default="none",
        description="Storage Pool Manager role: 'spm', 'contending', or 'none'",
    )
    is_nested: bool = Field(
        default=False,
        description="True if the hypervisor is virtualized (nested inside VMware, KVM, etc.)",
    )
    cpu_model: str | None = Field(default=None, description="CPU model name detected by engine")
    cpu_cores: int = Field(default=1, description="Total physical CPU cores")
    cpu_sockets: int = Field(default=1, description="Physical CPU sockets count")
    total_memory_gb: float = Field(default=0.0, description="Total physical RAM in GB")
    update_available: bool | None = Field(
        default=None, description="Whether OS or package updates are available for this host"
    )


class HostHardwareInfo(BaseModel):
    """Host physical or virtual hardware manufacturing details."""

    manufacturer: str | None = Field(
        default=None, description="Hardware vendor (e.g. 'VMware, Inc.', 'Dell Inc.')"
    )
    product_name: str | None = Field(default=None, description="Server product name / model")
    version: str | None = Field(default=None, description="Hardware / chassis version")
    serial_number: str | None = Field(default=None, description="Chassis serial number")
    uuid: str | None = Field(default=None, description="System hardware UUID")


class HostOSInfo(BaseModel):
    """Host operating system and virtualization stack versions."""

    os_type: str | None = Field(default=None, description="Operating system distribution")
    os_version: str | None = Field(default=None, description="OS release version")
    kernel_version: str | None = Field(default=None, description="Linux kernel release")
    kvm_version: str | None = Field(default=None, description="KVM hypervisor version")
    libvirt_version: str | None = Field(
        default=None, description="libvirt management daemon version"
    )
    vdsm_version: str | None = Field(default=None, description="oVirt / VDSM node agent version")


class HostPowerManagement(BaseModel):
    """Out-of-band power management and fencing configuration."""

    enabled: bool = Field(
        default=False, description="Whether IPMI / fencing power management is enabled"
    )
    pm_type: str | None = Field(
        default=None, description="Fence agent type (e.g. 'ipmilan', 'drac7', 'ilo4')"
    )
    address: str | None = Field(default=None, description="Management controller IP / FQDN")
    username: str | None = Field(default=None, description="Management controller user")
    automatic_pm_enabled: bool = Field(
        default=False, description="Whether engine automatically controls fencing"
    )


class HostStats(BaseModel):
    """Real-time performance and telemetry statistics for a hypervisor host."""

    host_id: str = Field(description="UUID of the hypervisor host")
    host_name: str = Field(description="Display name of the host")
    status: str = Field(description="Host operational status")
    active_vms_count: int = Field(default=0, description="Running virtual machines count")
    cpu_usage_percent: float = Field(
        default=0.0, description="Total active CPU utilization percentage (0-100%)"
    )
    cpu_user_percent: float = Field(
        default=0.0, description="CPU user space utilization percentage"
    )
    cpu_system_percent: float = Field(
        default=0.0, description="CPU kernel space utilization percentage"
    )
    cpu_idle_percent: float = Field(default=100.0, description="CPU idle percentage")
    cpu_load_avg_5m: float = Field(default=0.0, description="5-minute system load average")
    memory_total_gb: float = Field(default=0.0, description="Total physical RAM in GB")
    memory_used_gb: float = Field(default=0.0, description="Physically consumed RAM in GB")
    memory_free_gb: float = Field(default=0.0, description="Unallocated RAM in GB")
    memory_used_percent: float = Field(default=0.0, description="Memory consumption percentage")
    swap_total_mb: float = Field(default=0.0, description="Total swap space in MB")
    swap_used_mb: float = Field(default=0.0, description="Active swap consumed in MB")
    boot_time: str | None = Field(default=None, description="Host system boot timestamp")


class HostDetail(BaseModel):
    """Full detailed configuration and state of a hypervisor host."""

    id: str = Field(description="UUID of the hypervisor host")
    name: str = Field(description="Display name / FQDN of the host")
    status: str = Field(description="Current operational status")
    cluster_name: str = Field(description="Parent cluster name")
    cluster_id: str = Field(description="Parent cluster UUID")
    address: str = Field(description="Management IP / hostname")
    ssh_port: int = Field(default=22, description="SSH daemon port")
    active_vms_count: int = Field(default=0, description="Running virtual machines count")
    spm_status: str = Field(default="none", description="SPM role status")
    is_nested: bool = Field(default=False, description="Whether host is nested virtualized")
    cpu_model: str | None = Field(default=None, description="CPU model name")
    cpu_sockets: int = Field(default=1, description="CPU sockets")
    cpu_cores: int = Field(default=1, description="CPU cores")
    cpu_threads: int = Field(default=1, description="CPU threads")
    total_memory_gb: float = Field(default=0.0, description="Total physical RAM in GB")
    max_scheduling_memory_gb: float = Field(
        default=0.0, description="Available scheduling RAM in GB"
    )
    hardware: HostHardwareInfo = Field(
        default_factory=HostHardwareInfo, description="Hardware manufacturing info"
    )
    os: HostOSInfo = Field(
        default_factory=HostOSInfo, description="Operating system and virtualization stack"
    )
    power_management: HostPowerManagement = Field(
        default_factory=HostPowerManagement, description="Out-of-band power management / fencing"
    )
    nics_count: int = Field(default=0, description="Physical network interfaces count")
    numa_nodes_count: int = Field(default=0, description="NUMA architecture nodes count")
    update_available: bool | None = Field(
        default=None, description="Whether OS or package updates are available for this host"
    )
    stats: HostStats | None = Field(
        default=None, description="Real-time performance and telemetry statistics"
    )


class HostNicInfo(BaseModel):
    """Physical network interface card (pNIC) on a hypervisor host."""

    id: str = Field(description="UUID of the network interface device")
    name: str = Field(description="Interface name (e.g. 'eth0', 'ens192', 'bond0')")
    mac_address: str | None = Field(default=None, description="Physical MAC hardware address")
    speed_mbps: int | None = Field(
        default=None, description="Link speed in megabits per second (e.g. 10000)"
    )
    status: str = Field(default="unknown", description="Link operational status ('up', 'down')")
    ip_addresses: list[str] = Field(
        default_factory=list, description="Configured IPv4/IPv6 addresses"
    )
    network_name: str | None = Field(default=None, description="Attached logical network name")
    bridged: bool = Field(
        default=False, description="Whether this interface participates in a bridged network"
    )
    bonding_slaves: list[str] = Field(
        default_factory=list, description="Slave interfaces if this is a bond"
    )


class HostNumaNodeInfo(BaseModel):
    """Host Non-Uniform Memory Access (NUMA) node topology."""

    index: int = Field(description="NUMA node index (0, 1, ...)")
    memory_mb: int = Field(default=0, description="RAM memory allocated to this NUMA node in MB")
    cpu_cores: list[int] = Field(
        default_factory=list, description="CPU core indices belonging to this NUMA node"
    )


class HostDeviceInfo(BaseModel):
    """Host hardware or PCI bus device (SR-IOV, GPU, HBA)."""

    id: str = Field(description="Device identifier / PCI address (e.g. 'pci_0000_00_16_3')")
    name: str = Field(description="Device system name")
    product: str | None = Field(default=None, description="Product description")
    vendor: str | None = Field(default=None, description="Hardware vendor name")
    driver: str | None = Field(default=None, description="Active Linux kernel driver module")
    iommu_group: int | None = Field(default=None, description="IOMMU group for PCI passthrough")


class HostEvent(BaseModel):
    """Operational audit log event concerning a hypervisor host."""

    id: str = Field(description="Event identifier")
    code: int = Field(description="oVirt internal event code")
    severity: str = Field(description="Event severity: 'normal', 'warning', 'error', 'alert'")
    description: str = Field(description="Event audit message")
    timestamp: str | None = Field(default=None, description="ISO timestamp of event occurrence")


class HostLifecycleResult(BaseModel):
    """Result of a hypervisor host lifecycle mutation (maintenance, activate, restart)."""

    success: bool = Field(description="Whether the host operation succeeded")
    action: str = Field(description="Executed action: 'maintenance', 'activate', 'restart'")
    host_id: str = Field(description="UUID of the hypervisor host")
    host_name: str = Field(description="Display name / FQDN of the host")
    previous_status: str = Field(description="Status of the host prior to the action")
    current_status: str = Field(description="Status of the host after initiation or completion")
    active_vms_count: int = Field(default=0, description="Virtual machines remaining on the host")
    message: str = Field(description="Human-readable summary of outcome and safety checks")


class HostUpgradeCheckResult(BaseModel):
    """Result of checking for host software and OS upgrades."""

    success: bool = Field(description="Whether the upgrade check was initiated or completed")
    host_id: str = Field(description="UUID of the hypervisor host")
    host_name: str = Field(description="Display name / FQDN of the host")
    status: str = Field(description="Current operational status of the host")
    update_available: bool = Field(
        description="Whether OS/package updates are available for this host"
    )
    message: str = Field(description="Human-readable outcome description")


class HostUpgradeResult(BaseModel):
    """Result of initiating an OS and package upgrade on a hypervisor host."""

    success: bool = Field(description="Whether the host upgrade was initiated")
    action: str = Field(default="upgrade", description="Executed action ('upgrade')")
    host_id: str = Field(description="UUID of the hypervisor host")
    host_name: str = Field(description="Display name / FQDN of the host")
    status: str = Field(description="Status of the host ('maintenance', etc.)")
    reboot_requested: bool = Field(
        default=True, description="Whether host reboot was requested after upgrade"
    )
    message: str = Field(description="Human-readable outcome and upgrade instructions")
