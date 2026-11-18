"""Data models for Hypervisor Host Network Attachments and iSCSI Discovery."""

from pydantic import BaseModel, ConfigDict, Field


class HostNetworkAttachmentInfo(BaseModel):
    """Information about a logical network attachment on a hypervisor host interface."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(description="UUID of the network attachment")
    network_id: str = Field(description="UUID of the attached logical oVirt network")
    network_name: str = Field(description="Name of the attached logical network (e.g. 'ovirtmgmt')")
    host_nic_id: str = Field(description="UUID of the physical NIC or bond")
    host_nic_name: str = Field(
        description="Name of the physical NIC or bond (e.g. 'eth0', 'bond0')"
    )
    in_sync: bool = Field(
        default=True,
        description="Whether network configuration on the host matches the engine definition",
    )
    boot_protocol: str = Field(
        default="none",
        description="IP assignment protocol: 'static', 'dhcp', or 'none'",
    )
    ip_address: str | None = Field(
        default=None, description="IPv4 address assigned to this attachment"
    )
    netmask: str | None = Field(default=None, description="Subnet mask assigned to this attachment")
    gateway: str | None = Field(
        default=None, description="Default gateway configured on this attachment"
    )


class HostIscsiDiscoverResult(BaseModel):
    """Result of an iSCSI portal discovery operation on a hypervisor host."""

    host_id: str = Field(description="UUID of the hypervisor host performing discovery")
    host_name: str = Field(description="Name of the hypervisor host")
    address: str = Field(description="IP address or hostname of the iSCSI target portal")
    port: int = Field(default=3260, description="iSCSI target portal TCP port")
    targets: list[str] = Field(
        default_factory=list,
        description="List of discovered iSCSI Target IQNs (e.g. 'iqn.2024-01.org.example:storage.target01')",
    )
    count: int = Field(description="Total number of discovered iSCSI targets")


class HostIscsiLoginResult(BaseModel):
    """Result of an iSCSI login operation on a hypervisor host."""

    success: bool = Field(description="Whether login succeeded")
    host_id: str = Field(description="UUID of the hypervisor host")
    host_name: str = Field(description="Name of the hypervisor host")
    target: str = Field(description="iSCSI Target IQN logged into")
    address: str = Field(description="IP address or hostname of the iSCSI portal")
    port: int = Field(default=3260, description="iSCSI portal TCP port")
    message: str = Field(description="Human-readable outcome description")


class HostNetworkSetupResult(BaseModel):
    """Result of host network setup or modification."""

    success: bool = Field(description="Whether network setup succeeded")
    host_id: str = Field(description="UUID of the hypervisor host")
    host_name: str = Field(description="Name of the hypervisor host")
    action: str = Field(description="Action executed: 'attach_network', 'detach_network', etc.")
    message: str = Field(description="Human-readable outcome description")


class HostBondResult(BaseModel):
    """Outcome of a host network bonding operation."""

    success: bool = Field(description="Whether the bonding operation succeeded")
    host_id: str = Field(description="UUID of the hypervisor host")
    host_name: str = Field(description="Name of the hypervisor host")
    bond_name: str = Field(description="Name of the bond interface (e.g. 'bond0')")
    slaves: list[str] = Field(
        default_factory=list, description="Slave physical interfaces in the bond"
    )
    action: str = Field(description="Action executed: 'create' or 'delete'")
    message: str = Field(description="Human-readable outcome description")
