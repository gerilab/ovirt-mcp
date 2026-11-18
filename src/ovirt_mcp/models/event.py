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
