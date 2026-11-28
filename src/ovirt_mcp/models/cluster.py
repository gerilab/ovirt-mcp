"""Models for oVirt / OLVM Clusters and hardware capability profiles."""

from pydantic import BaseModel, Field


class ClusterSummary(BaseModel):
    """Summary of a virtualization cluster."""

    id: str = Field(description="Unique ID of the cluster.")
    name: str = Field(description="Display name of the cluster.")
    description: str | None = Field(
        default=None, description="Optional description of the cluster."
    )
    data_center_id: str | None = Field(default=None, description="Parent Data Center UUID.")
    data_center_name: str | None = Field(default=None, description="Parent Data Center name.")
    cpu_type: str | None = Field(
        default=None,
        description="Processor family / CPU model (e.g. 'Intel SandyBridge Family', 'AMD EPYC').",
    )
    cpu_architecture: str | None = Field(
        default=None, description="CPU architecture ('x86_64', 'ppc64le', 's390x')."
    )
    compatibility_version: str | None = Field(
        default=None, description="Cluster compatibility level (e.g. '4.6', '4.7')."
    )
    ballooning_enabled: bool = Field(
        default=False, description="Whether memory ballooning optimization is enabled."
    )
    ha_reservation: bool = Field(
        default=False,
        description="Whether High Availability hardware capacity reservation is active.",
    )


class ClusterMigrationPolicy(BaseModel):
    """VM Live Migration configuration and convergence parameters for a cluster."""

    auto_converge: str | None = Field(
        default=None,
        description="Auto-convergence throttling setting ('true', 'false', 'inherit').",
    )
    compressed: str | None = Field(
        default=None,
        description="Memory page compression during migration ('true', 'false', 'inherit').",
    )
    encrypted: str | None = Field(
        default=None,
        description="Migration TLS encryption policy ('true', 'false', 'inherit').",
    )
    bandwidth_assignment_method: str | None = Field(
        default=None,
        description="Bandwidth limit mode ('auto', 'hypervisor_default', 'custom').",
    )
    bandwidth_custom_value: int | None = Field(
        default=None,
        description="Custom bandwidth limit in Mbps if custom assignment method is configured.",
    )
    parallel_migrations_policy: str | None = Field(
        default=None,
        description="Parallel migrations policy ('auto', 'auto_parallel', 'custom', 'disabled', 'inherit').",
    )
    custom_parallel_migrations: int | None = Field(
        default=None,
        description="Maximum concurrent parallel outgoing/incoming live migrations per host.",
    )
    policy_id: str | None = Field(
        default=None,
        description="UUID of the assigned migration convergence policy.",
    )
    policy_name: str | None = Field(
        default=None,
        description="Display name of migration policy ('Legacy', 'Minimal downtime', 'Post-copy migration', 'Suspend workload if needed').",
    )


class ClusterSchedulingPolicy(BaseModel):
    """Cluster workload scheduling policy details and algorithmic parameters."""

    id: str | None = Field(default=None, description="UUID of the scheduling policy.")
    name: str | None = Field(
        default=None,
        description="Display name of the policy (e.g. 'evenly_distributed', 'power_saving', 'cluster_maintenance', 'vm_to_host_affinity').",
    )
    description: str | None = Field(default=None, description="Scheduling policy description.")
    properties: dict[str, str] = Field(
        default_factory=dict,
        description="Configured scheduling policy properties (e.g. HighUtilization, LowUtilization, CpuOverCommitDurationMinutes).",
    )


class ClusterFencingPolicy(BaseModel):
    """Host power management / fencing safety policy."""

    enabled: bool = Field(default=True, description="Whether host IPMI/power fencing is enabled.")
    skip_if_connectivity_broken: bool | None = Field(
        default=None,
        description="Skip fencing if storage or network connectivity is broken.",
    )
    skip_if_sd_active: bool | None = Field(
        default=None,
        description="Skip fencing if storage domain heartbeats remain active.",
    )
    skip_if_gluster_bricks_up: bool | None = Field(
        default=None,
        description="Skip fencing if Gluster bricks are active and responding.",
    )
    skip_if_gluster_quorum_not_met: bool | None = Field(
        default=None,
        description="Skip fencing if Gluster quorum is not met.",
    )


class ClusterDetail(ClusterSummary):
    """Deep technical configuration and policy profiles of a virtualization cluster."""

    comment: str | None = Field(
        default=None, description="Optional administrator comment for the cluster."
    )
    memory_overcommit_percent: int | None = Field(
        default=None, description="Memory overcommit allowance percentage (e.g. 100, 150, 200)."
    )
    fips_mode: str | None = Field(
        default=None,
        description="FIPS cryptographic compliance mode ('enabled', 'disabled', 'undefined').",
    )
    bios_type: str | None = Field(
        default=None,
        description="Default virtual machine chipset/BIOS type ('i440fx_sea_bios', 'q35_secure_boot', etc.).",
    )
    threads_as_cores: bool = Field(
        default=False,
        description="Whether SMT/HyperThreading logical threads are exposed as discrete CPU cores.",
    )

    # VM Live Migration settings
    migration_encrypted: bool = Field(
        default=False,
        description="Whether VM live migration traffic is TLS encrypted across hypervisors.",
    )
    migration_bandwidth: str | None = Field(
        default=None, description="QEMU/KVM migration bandwidth limit setting or policy."
    )
    migration: ClusterMigrationPolicy | None = Field(
        default=None,
        description="Exhaustive VM Live Migration settings (bandwidth, parallel migrations, auto-converge, policy).",
    )

    # Workload Scheduling and Affinity
    scheduling_policy: ClusterSchedulingPolicy | None = Field(
        default=None,
        description="Cluster scheduling policy details (policy name, algorithm, and threshold properties).",
    )
    custom_scheduling_policy_properties: dict[str, str] = Field(
        default_factory=dict,
        description="Custom scheduling policy key-value properties defined on the cluster.",
    )

    # Fencing & Power Management
    fencing_enabled: bool = Field(
        default=True, description="Whether host IPMI/power fencing is enabled."
    )
    fencing_policy: ClusterFencingPolicy | None = Field(
        default=None,
        description="Granular host power fencing rules and safety bypass conditions.",
    )

    # Kernel & Memory Optimizations
    ksm_enabled: bool = Field(
        default=True,
        description="Whether Kernel Samepage Merging (KSM) RAM de-duplication is active.",
    )
    switch_type: str | None = Field(
        default=None, description="Virtual network switch mechanism ('legacy' or 'ovs')."
    )
    firewall_type: str | None = Field(
        default=None, description="Host firewall management framework ('iptables' or 'nftables')."
    )

    # Networking & Hardware Policies
    mac_pool_id: str | None = Field(
        default=None, description="UUID of the default MAC address pool."
    )
    mac_pool_name: str | None = Field(
        default=None, description="Name of the default MAC address pool."
    )
    management_network_id: str | None = Field(
        default=None, description="UUID of the cluster management logical network."
    )
    management_network_name: str | None = Field(
        default=None,
        description="Name of the cluster management logical network (e.g. 'ovirtmgmt').",
    )
    serial_number_policy: str | None = Field(
        default=None,
        description="VM BIOS serial number generation policy ('host', 'vm', 'custom').",
    )
    serial_number_custom_value: str | None = Field(
        default=None,
        description="Custom serial number string when serial_number_policy is 'custom'.",
    )
    error_handling: str | None = Field(
        default=None,
        description="Cluster error handling strategy upon VM deployment failures ('migrate_check', 'do_not_migrate').",
    )

    # Additional Capabilities
    tunnel_migration: bool | None = Field(
        default=None,
        description="Whether live migration traffic is routed through an encrypted tunnel.",
    )
    vnc_encryption: bool | None = Field(
        default=None,
        description="Whether SPICE/VNC remote graphical display connections require encryption.",
    )
    virt_service: bool = Field(
        default=True, description="Whether Virtualization service is active in this cluster."
    )
    gluster_service: bool = Field(
        default=False, description="Whether GlusterFS storage service is active in this cluster."
    )
    trusted_service: bool = Field(
        default=False, description="Whether Attestation / Trusted execution service is active."
    )
    maintenance_reason_required: bool = Field(
        default=False,
        description="Whether operators must specify a reason when placing hosts into maintenance.",
    )
    log_max_memory_used_threshold: int | None = Field(
        default=None, description="Memory utilization threshold percentage for warning logs."
    )
    log_max_memory_used_threshold_type: str | None = Field(
        default=None, description="Threshold evaluation unit (e.g. 'percentage')."
    )
    upgrade_correlation_id: str | None = Field(
        default=None, description="Tracking ID for rolling cluster hypervisor upgrades."
    )
    upgrade_in_progress: bool | None = Field(
        default=None, description="Whether a rolling cluster upgrade is actively executing."
    )
    upgrade_percent_complete: int | None = Field(
        default=None, description="Progress percentage of active rolling cluster upgrade."
    )


class ClusterOperationResult(BaseModel):
    """Result of an operational action on a virtualization cluster."""

    success: bool = Field(description="Whether the cluster operation succeeded.")
    cluster_id: str = Field(description="UUID of the cluster.")
    cluster_name: str = Field(description="Name of the cluster.")
    action: str = Field(
        description="Action executed ('sync_all_networks', 'reset_emulated_machine')."
    )
    dry_run: bool = Field(default=False, description="Whether this was a dry-run simulation.")
    message: str = Field(description="Human-readable result summary.")
