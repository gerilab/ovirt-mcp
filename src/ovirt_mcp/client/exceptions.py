"""Structured exception hierarchy for oVirt / OLVM MCP Server."""

try:
    from mcp.server.mcpserver.exceptions import ToolError
except ImportError:

    class ToolError(Exception):  # type: ignore[no-redef]
        """Fallback ToolError base when mcpserver is not installed."""

        pass


class OvirtMCPError(ToolError):
    """Base exception for all oVirt MCP operations."""

    def __init__(
        self, message: str, code: str = "OVIRT_ERROR", details: dict | None = None
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}

    def to_dict(self) -> dict:
        """Convert exception to structured dictionary."""
        return {
            "error": self.__class__.__name__,
            "code": self.code,
            "message": self.message,
            "details": self.details,
        }


class OvirtConnectionError(OvirtMCPError):
    """Raised when connection to oVirt / OLVM Engine fails or drops."""

    def __init__(self, message: str, details: dict | None = None) -> None:
        super().__init__(message, code="CONNECTION_ERROR", details=details)


class OvirtAuthError(OvirtMCPError):
    """Raised when authentication fails."""

    def __init__(self, message: str, details: dict | None = None) -> None:
        super().__init__(message, code="AUTH_ERROR", details=details)


class OvirtPermissionError(OvirtMCPError):
    """Raised when authorization fails or read-only mode blocks a mutation."""

    def __init__(self, message: str, details: dict | None = None) -> None:
        super().__init__(message, code="PERMISSION_DENIED", details=details)


class NotFoundError(OvirtMCPError):
    """Raised when a requested resource (VM, Host, Cluster, Storage) is not found."""

    def __init__(self, resource_type: str, identifier: str, details: dict | None = None) -> None:
        message = f"{resource_type} '{identifier}' not found"
        super().__init__(
            message,
            code="NOT_FOUND",
            details=details or {"resource_type": resource_type, "identifier": identifier},
        )
        self.resource_type = resource_type
        self.identifier = identifier


class OvirtValidationError(OvirtMCPError):
    """Raised when parameter or precondition validation fails."""

    def __init__(self, message: str, details: dict | None = None) -> None:
        super().__init__(message, code="VALIDATION_ERROR", details=details)


class OvirtTimeoutError(OvirtMCPError):
    """Raised when an operation times out (e.g. waiting for VM up/down status)."""

    def __init__(self, message: str, details: dict | None = None) -> None:
        super().__init__(message, code="TIMEOUT", details=details)


class ResourceLockedError(OvirtMCPError):
    """Raised when a resource is in an image locked or busy state."""

    def __init__(self, message: str, details: dict | None = None) -> None:
        super().__init__(message, code="RESOURCE_LOCKED", details=details)
