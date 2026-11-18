"""oVirt client and exception modules."""

from .connection import OvirtClient, get_client
from .exceptions import (
    NotFoundError,
    OvirtAuthError,
    OvirtConnectionError,
    OvirtMCPError,
    OvirtTimeoutError,
    OvirtValidationError,
    ResourceLockedError,
)

__all__ = [
    "NotFoundError",
    "OvirtAuthError",
    "OvirtClient",
    "OvirtConnectionError",
    "OvirtMCPError",
    "OvirtTimeoutError",
    "OvirtValidationError",
    "ResourceLockedError",
    "get_client",
]
