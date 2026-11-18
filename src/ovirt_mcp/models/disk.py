"""Pydantic models for virtual disk operations and management."""

from pydantic import BaseModel, Field


class VmDiskAttachmentInfo(BaseModel):
    """Details about a disk attached to a virtual machine."""

    attachment_id: str = Field(description="UUID of the disk attachment")
    disk_id: str = Field(description="UUID of the underlying virtual disk")
    disk_name: str = Field(description="Display name or alias of the disk")
    interface: str = Field(
        description="Interface type (e.g. 'virtio', 'virtio_scsi', 'sata', 'ide')"
    )
    bootable: bool = Field(description="Whether this disk is marked bootable")
    active: bool = Field(description="Whether the disk attachment is currently active / plugged")
    read_only: bool = Field(default=False, description="Whether the disk is attached as read-only")
    provisioned_size_gb: float = Field(description="Allocated logical capacity in gigabytes")
    actual_size_gb: float | None = Field(
        default=None, description="Actual physical storage consumed in gigabytes"
    )
    disk_format: str = Field(default="cow", description="Storage format ('cow' or 'raw')")
    storage_domain_name: str | None = Field(
        default=None, description="Storage domain where disk image resides"
    )
    status: str = Field(default="ok", description="Disk status ('ok', 'locked', etc.)")


class VmDiskAttachmentResult(BaseModel):
    """Result of a disk attach, detach, or create operation."""

    success: bool = Field(description="Whether the operation succeeded")
    action: str = Field(description="Action executed: 'attach', 'detach', 'create'")
    vm_id: str = Field(description="UUID of the virtual machine")
    vm_name: str = Field(description="Name of the virtual machine")
    disk_id: str = Field(description="UUID of the disk")
    disk_name: str | None = Field(default=None, description="Name of the disk")
    interface: str | None = Field(default=None, description="Interface type used")
    message: str = Field(description="Human-readable outcome description")


class DiskCreateResult(BaseModel):
    """Result of creating a floating or attached virtual disk."""

    success: bool = Field(description="Whether the operation succeeded")
    action: str = Field(default="create", description="Action executed: 'create'")
    disk_id: str = Field(description="UUID of the created disk")
    disk_name: str = Field(description="Name/alias of the created disk")
    provisioned_size_gb: float = Field(description="Provisioned capacity in gigabytes")
    storage_domain: str = Field(description="Hosting storage domain name")
    disk_format: str = Field(description="Disk format ('cow' or 'raw')")
    vm_id: str | None = Field(default=None, description="UUID of virtual machine if attached")
    vm_name: str | None = Field(default=None, description="Name of virtual machine if attached")
    interface: str | None = Field(default=None, description="Interface type if attached")
    bootable: bool | None = Field(default=None, description="Whether marked bootable")
    active: bool | None = Field(default=None, description="Whether marked active/plugged")
    message: str = Field(description="Human-readable outcome description")


class DiskDetail(BaseModel):
    """Information about a virtual disk in the oVirt / OLVM engine."""

    id: str = Field(description="UUID of the virtual disk")
    name: str = Field(description="Name or alias of the disk")
    status: str = Field(description="Current status (e.g. 'ok', 'locked', 'illegal')")
    provisioned_size_gb: float = Field(description="Provisioned capacity in gigabytes")
    actual_size_gb: float | None = Field(
        default=None, description="Actual physical storage consumed in gigabytes"
    )
    disk_format: str = Field(description="Disk format: 'cow' or 'raw'")
    content_type: str = Field(
        default="data", description="Disk content type (e.g. 'data', 'iso', 'ovf_store')"
    )
    storage_domain_name: str | None = Field(
        default=None, description="Name of the hosting storage domain"
    )
    storage_domain_id: str | None = Field(
        default=None, description="UUID of the hosting storage domain"
    )


class DiskResizeResult(BaseModel):
    """Result of a disk resize / extension operation."""

    success: bool = Field(description="Whether the disk resize succeeded")
    disk_id: str = Field(description="UUID of the resized disk")
    disk_name: str = Field(description="Name of the resized disk")
    old_size_gb: float = Field(description="Previous provisioned size in GB")
    new_size_gb: float = Field(description="New provisioned size in GB")
    message: str = Field(description="Human-readable outcome description")


class DiskOperationResult(BaseModel):
    """Result of a disk move, copy, or sparsify operation."""

    success: bool = Field(description="Whether the operation succeeded")
    disk_id: str = Field(description="UUID of the virtual disk")
    disk_name: str = Field(description="Name/alias of the virtual disk")
    action: str = Field(description="Action executed: 'move', 'copy', or 'sparsify'")
    source_storage_domain: str | None = Field(
        default=None, description="Original hosting storage domain"
    )
    target_storage_domain: str | None = Field(
        default=None, description="Target storage domain for move or copy"
    )
    message: str = Field(description="Human-readable outcome description")
