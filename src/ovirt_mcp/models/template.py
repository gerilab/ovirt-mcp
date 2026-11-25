"""Pydantic data models for oVirt / OLVM Templates and Golden Images."""

from pydantic import BaseModel, Field


class TemplateDiskInfo(BaseModel):
    """Information about a virtual disk attachment on a template."""

    id: str = Field(description="Attachment UUID")
    disk_id: str = Field(description="Virtual disk image UUID")
    interface: str | None = Field(
        default=None, description="Bus interface (e.g. virtio, virtio_scsi)"
    )
    bootable: bool = Field(default=False, description="Whether the disk is marked bootable")


class TemplateSummary(BaseModel):
    """Compact summary of a template / golden image."""

    id: str = Field(description="Template UUID")
    name: str = Field(description="Template name")
    description: str | None = Field(default=None, description="Template description")
    cluster_id: str | None = Field(default=None, description="Associated cluster UUID")
    status: str = Field(default="ok", description="Template lifecycle status (e.g. 'ok', 'locked')")
    memory_mb: int | None = Field(default=None, description="Provisioned RAM in MB")
    cpu_cores: int | None = Field(default=None, description="Configured CPU cores")
    cpu_sockets: int | None = Field(default=None, description="Configured CPU sockets")
    version_number: int | None = Field(default=None, description="Template version index")
    version_name: str | None = Field(default=None, description="Human-readable version label")
    base_template_id: str | None = Field(
        default=None, description="Base template UUID if sub-versioned"
    )


class TemplateDetail(TemplateSummary):
    """Comprehensive specification of an oVirt / OLVM template."""

    os_type: str | None = Field(default=None, description="Operating system type (e.g. rhel_8x64)")
    creation_time: str | None = Field(
        default=None, description="ISO timestamp of template creation"
    )
    disks: list[TemplateDiskInfo] = Field(
        default_factory=list, description="Attached virtual disk references"
    )
    nic_count: int = Field(default=0, description="Number of configured virtual network interfaces")


class TemplateResult(BaseModel):
    """Outcome of a template creation, modification, or removal operation."""

    success: bool = Field(description="Whether the operation succeeded")
    template_id: str = Field(description="UUID of the affected template")
    template_name: str = Field(description="Name of the affected template")
    action: str = Field(description="Action executed: 'create' or 'delete'")
    dry_run: bool = Field(
        default=False,
        description="Whether this action was simulated in dry_run mode without execution",
    )
    message: str = Field(description="Human-readable outcome description")
