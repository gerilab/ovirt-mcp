"""Configuration management for oVirt/OLVM MCP server using Pydantic Settings."""

from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class OvirtConfig(BaseSettings):
    """Configuration settings for connecting to oVirt or OLVM Engine."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ovirt_url: str = Field(
        default="https://localhost/ovirt-engine/api",
        description="Base URL of the oVirt / OLVM Engine REST API",
    )
    ovirt_username: str = Field(
        default="admin@internal",
        description="Username for authentication (e.g., admin@internal)",
    )
    ovirt_password: SecretStr = Field(
        default=SecretStr(""),
        description="Password for the user",
    )
    ovirt_ca_file: Path | None = Field(
        default=None,
        description="Path to PEM-encoded CA certificate for TLS verification",
    )
    ovirt_insecure: bool = Field(
        default=False,
        description="Disable TLS certificate verification (not recommended for production)",
    )
    ovirt_auto_download_ca: bool = Field(
        default=True,
        description="Automatically download and cache CA certificate from engine PKI endpoint",
    )
    ovirt_timeout: int = Field(
        default=30,
        ge=1,
        le=300,
        description="API request timeout in seconds",
    )
    ovirt_max_retries: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Maximum number of connection retries",
    )
    mcp_log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
    )
    mcp_compact_mode: bool = Field(
        default=False,
        description="Default to compact responses to conserve tokens for small context-window models",
    )
    mcp_read_only: bool = Field(
        default=False,
        description="Enforce read-only mode, blocking all mutating and destructive operations",
    )
    mcp_safe_mode: bool = Field(
        default=True,
        description="Enable safe mode (requires explicit confirmation flags for destructive operations)",
    )
    mcp_transport: str = Field(
        default="stdio",
        description="Transport protocol for MCP communications: 'stdio', 'sse', or 'streamable-http'",
    )
    mcp_host: str = Field(
        default="0.0.0.0",
        description="Bind IP address when running with network transport ('sse' or 'streamable-http')",
    )
    mcp_port: int = Field(
        default=8000,
        ge=1,
        le=65535,
        description="Listening TCP port when running with network transport ('sse' or 'streamable-http')",
    )

    def sanitized_url(self) -> str:
        """Return the URL stripped of trailing slash."""
        return self.ovirt_url.rstrip("/")


_config: OvirtConfig | None = None


def get_config() -> OvirtConfig:
    """Get or initialize the global configuration instance."""
    global _config
    if _config is None:
        _config = OvirtConfig()
    return _config
