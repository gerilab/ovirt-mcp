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
