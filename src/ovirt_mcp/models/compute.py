"""Pydantic models for VM compute resource reconfiguration and graphics console tickets."""

from pydantic import BaseModel, Field


class VmUpdateResult(BaseModel):
    """Result of updating virtual machine resources or configuration."""

    success: bool = Field(description="Whether the update succeeded")
    vm_id: str = Field(description="UUID of the virtual machine")
    vm_name: str = Field(description="Name of the virtual machine")
    memory_mb: int | None = Field(default=None, description="Updated RAM allocation in MB")
    cpu_cores: int | None = Field(default=None, description="Updated CPU cores count")
    cpu_sockets: int | None = Field(default=None, description="Updated CPU sockets count")
    ha_enabled: bool | None = Field(default=None, description="Updated HA status")
    description: str | None = Field(default=None, description="Updated description")
    message: str = Field(description="Human-readable outcome description")


class VmGraphicsConsoleInfo(BaseModel):
    """Details about a VM graphical display console."""

    id: str = Field(description="Console device identifier")
    protocol: str = Field(description="Graphics protocol ('vnc' or 'spice')")
    port: int | None = Field(default=None, description="Unencrypted display port")
    tls_port: int | None = Field(default=None, description="TLS-secured display port")


class VmConsoleTicket(BaseModel):
    """Console access ticket for SPICE or VNC remote viewer."""

    vm_id: str = Field(description="UUID of the virtual machine")
    vm_name: str = Field(description="Name of the virtual machine")
    ticket_value: str = Field(description="Single-use or time-limited access password")
    expiry_seconds: int = Field(description="Ticket validity duration in seconds")
    message: str = Field(description="Instructions for connecting")


class VmConsoleFileInfo(BaseModel):
    """Virt-Viewer .vv configuration file payload for direct graphical console connection."""

    vm_id: str = Field(description="UUID of the virtual machine")
    vm_name: str = Field(description="Name of the virtual machine")
    protocol: str = Field(description="Display protocol ('vnc' or 'spice')")
    host: str = Field(description="Hypervisor host IP address or FQDN")
    port: int = Field(description="Display port")
    ticket_value: str = Field(description="One-time password for this session")
    expiry_seconds: int = Field(description="Ticket lifetime in seconds")
    vv_content: str = Field(description="Complete .vv file text content ready for remote-viewer")
    instructions: str = Field(description="Command-line or GUI instructions to launch")


class VmExportResult(BaseModel):
    """Result of exporting a virtual machine to an export domain or as an OVA."""

    success: bool = Field(description="Whether the export completed or initiated successfully")
    vm_id: str = Field(description="UUID of the exported virtual machine")
    vm_name: str = Field(description="Name of the exported virtual machine")
    export_target: str = Field(description="Export storage domain name or target path")
    format: str = Field(description="Export format ('export_domain' or 'ova')")
    message: str = Field(description="Human-readable outcome description")


class VmImportResult(BaseModel):
    """Result of importing a virtual machine into oVirt / OLVM."""

    success: bool = Field(description="Whether the import succeeded")
    vm_id: str = Field(description="UUID of the imported virtual machine")
    vm_name: str = Field(description="Name of the imported virtual machine")
    cluster_name: str = Field(description="Target cluster")
    storage_domain_name: str = Field(description="Target storage domain")
    message: str = Field(description="Human-readable outcome description")
