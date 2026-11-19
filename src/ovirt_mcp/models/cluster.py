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


class ClusterDetail(ClusterSummary):
    """Deep technical configuration of a virtualization cluster."""

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
    migration_encrypted: bool = Field(
        default=False,
        description="Whether VM live migration traffic is TLS encrypted across hypervisors.",
    )
    migration_bandwidth: str | None = Field(
        default=None, description="QEMU/KVM migration bandwidth limit setting or policy."
    )
    fencing_enabled: bool = Field(
        default=True, description="Whether host IPMI/power fencing is enabled."
    )
    ksm_enabled: bool = Field(
        default=True,
        description="Whether Kernel Samepage Merging (KSM) RAM de-duplication is active.",
    )
    switch_type: str | None = Field(
        default=None, description="Virtual network switch mechanism ('legacy' or 'ovs')."
    )
