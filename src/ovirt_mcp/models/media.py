"""Pydantic models for media and CD-ROM / ISO management."""

from pydantic import BaseModel, Field


class VmCdromInfo(BaseModel):
    """Details about a virtual machine CD-ROM drive."""

    id: str = Field(description="UUID of the CD-ROM drive device")
    file_id: str | None = Field(
        default=None, description="ISO image file name attached, or None if empty"
    )
    is_empty: bool = Field(
        default=True, description="Whether the CD-ROM drive has no media inserted"
    )


class VmCdromResult(BaseModel):
    """Result of a CD-ROM attach or eject operation."""

    success: bool = Field(description="Whether the operation succeeded")
    action: str = Field(description="Action executed: 'attach' or 'eject'")
    vm_id: str = Field(description="UUID of the virtual machine")
    vm_name: str = Field(description="Name of the virtual machine")
    cdrom_id: str = Field(description="UUID of the CD-ROM drive device")
    iso_file: str | None = Field(
        default=None, description="ISO file name attached, or None if ejected"
    )
    current: bool = Field(
        default=False,
        description="Whether media was updated on running VM (hot-plugged / hot-swapped)",
    )
    message: str = Field(description="Human-readable outcome description")


class IsoFileInfo(BaseModel):
    """Information about an ISO file available in an ISO storage domain."""

    id: str = Field(description="File identifier or filename")
    name: str = Field(description="ISO image filename")
    storage_domain_id: str = Field(description="UUID of the ISO storage domain containing the file")
    storage_domain_name: str = Field(
        description="Name of the ISO storage domain containing the file"
    )
