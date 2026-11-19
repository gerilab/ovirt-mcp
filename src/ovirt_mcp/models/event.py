"""Pydantic models for oVirt / OLVM audit events and log messages."""

from pydantic import BaseModel, Field


class VmEvent(BaseModel):
    """Audit event or system log entry associated with a virtual machine."""

    id: str = Field(description="Unique event ID")
    code: int | None = Field(default=None, description="Internal numeric event code")
    severity: str = Field(
        description="Severity level (normal, warning, error, alert)",
    )
    time: str = Field(description="Timestamp when the event occurred in ISO format")
    description: str = Field(description="Human-readable event message or audit description")
    user_name: str | None = Field(
        default=None, description="Username who initiated or triggered the action, if applicable"
    )
    correlation_id: str | None = Field(
        default=None, description="Flow correlation ID for tracking complex operations"
    )


class SystemEvent(BaseModel):
    """Global system audit log event or diagnostic message across the virtualization environment."""

    id: str = Field(description="Unique event ID")
    code: int | None = Field(default=None, description="oVirt internal numeric event code")
    severity: str = Field(description="Severity level: 'normal', 'warning', 'error', 'alert'")
    time: str = Field(description="Timestamp when event occurred in ISO format")
    description: str = Field(description="Audit event message or diagnostic detail")
    vm_name: str | None = Field(
        default=None, description="Affected virtual machine name, if applicable"
    )
    host_name: str | None = Field(
        default=None, description="Affected hypervisor host name, if applicable"
    )
    cluster_name: str | None = Field(
        default=None, description="Affected cluster name, if applicable"
    )
    storage_domain_name: str | None = Field(
        default=None, description="Affected storage domain name, if applicable"
    )
    user_name: str | None = Field(
        default=None, description="Username who initiated or triggered the action, if applicable"
    )
    correlation_id: str | None = Field(
        default=None, description="Correlation ID for tracking complex operations"
    )
