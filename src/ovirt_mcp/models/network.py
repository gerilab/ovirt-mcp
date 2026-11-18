"""Pydantic models for virtual network interfaces (vNICs) and network profiles."""

from pydantic import BaseModel, Field


class VmNicDetail(BaseModel):
    """Details about a network interface card attached to a virtual machine."""

    id: str = Field(description="UUID of the vNIC device")
    name: str = Field(description="Interface name (e.g. 'nic1', 'eth0')")
    mac_address: str | None = Field(default=None, description="Assigned MAC address")
    interface: str = Field(description="Interface model (e.g. 'virtio', 'e1000', 'rtl8139_virtio')")
    vnic_profile_name: str | None = Field(
        default=None, description="Name of the assigned vNIC profile"
    )
    vnic_profile_id: str | None = Field(
        default=None, description="UUID of the assigned vNIC profile"
    )
    network_name: str | None = Field(default=None, description="Underlying logical network name")
    plugged: bool = Field(description="Whether the NIC is plugged (card inserted in slot)")
    linked: bool = Field(description="Whether network link is up (cable connected)")


class VmNicResult(BaseModel):
    """Result of a vNIC add, remove, or modify operation."""

    success: bool = Field(description="Whether the operation succeeded")
    action: str = Field(description="Action executed: 'add', 'remove'")
    vm_id: str = Field(description="UUID of the virtual machine")
    vm_name: str = Field(description="Name of the virtual machine")
    nic_id: str = Field(description="UUID of the vNIC device")
    nic_name: str = Field(description="Name of the vNIC device")
    mac_address: str | None = Field(default=None, description="MAC address of the vNIC")
    message: str = Field(description="Human-readable outcome description")


class VnicProfileInfo(BaseModel):
    """Details about an available vNIC profile."""

    id: str = Field(description="UUID of the vNIC profile")
    name: str = Field(description="Name of the vNIC profile (e.g. 'ovirtmgmt')")
    network_name: str | None = Field(
        default=None, description="Name of the associated logical network"
    )
    network_id: str | None = Field(
        default=None, description="UUID of the associated logical network"
    )
    pass_through: bool = Field(default=False, description="Whether SR-IOV passthrough is enabled")
    port_mirroring: bool = Field(default=False, description="Whether port mirroring is enabled")
