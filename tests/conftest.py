"""Pytest fixtures and configuration."""

import pytest

from ovirt_mcp.config import OvirtConfig


@pytest.fixture
def mock_config() -> OvirtConfig:
    """Fixture providing a mock OvirtConfig instance."""
    return OvirtConfig(
        ovirt_url="https://olvm.example.com/ovirt-engine/api",
        ovirt_username="admin@internal",
        ovirt_password="mock_password",  # type: ignore[arg-type]
        ovirt_insecure=True,
        ovirt_timeout=15,
        ovirt_max_retries=2,
    )
