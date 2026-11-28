"""Unit tests for OvirtClient and exception classes."""

from unittest.mock import MagicMock, patch

import pytest

from ovirt_mcp.client import (
    NotFoundError,
    OvirtClient,
)
from ovirt_mcp.config import OvirtConfig


def test_exception_serialization() -> None:
    """Test exception dictionary serialization."""
    err = NotFoundError("vm", "prod-web-01")
    data = err.to_dict()
    assert data["code"] == "NOT_FOUND"
    assert "prod-web-01" in data["message"]
    assert data["details"]["resource_type"] == "vm"


def test_client_init(mock_config: OvirtConfig) -> None:
    """Test client initialization without active connection."""
    client = OvirtClient(config=mock_config)
    assert not client.is_connected
    assert client.config.ovirt_insecure is True


def test_client_test_connection_success(mock_config: OvirtConfig) -> None:
    """Test successful connection test."""
    client = OvirtClient(config=mock_config)

    mock_conn = MagicMock()
    mock_system = MagicMock()
    mock_api = MagicMock()
    mock_prod = MagicMock()
    mock_version = MagicMock()

    mock_version.full_version = "4.5.4"
    mock_prod.version = mock_version
    mock_prod.name = "Oracle Linux Virtualization Manager"
    mock_api.product_info = mock_prod

    mock_system.get.return_value = mock_api
    mock_conn.system_service.return_value = mock_system

    with patch.object(client, "get_connection", return_value=mock_conn):
        result = client.test_connection()
        assert result["status"] == "connected"
        assert result["product_name"] == "Oracle Linux Virtualization Manager"
        assert result["version"] == "4.5.4"


def test_find_resource_not_found(mock_config: OvirtConfig) -> None:
    """Test find_resource_by_id_or_name raises NotFoundError when not present."""
    client = OvirtClient(config=mock_config)

    mock_service = MagicMock()
    mock_sub_service = MagicMock()
    mock_sub_service.get.side_effect = Exception("Not found")
    mock_service.vm_service.return_value = mock_sub_service
    mock_service.list.return_value = []

    with pytest.raises(NotFoundError):
        client.find_resource_by_id_or_name(mock_service, "non-existent-vm", "vm")


def test_find_resource_ambiguous_name(mock_config: OvirtConfig) -> None:
    """Test find_resource_by_id_or_name raises OvirtValidationError when multiple resources share a name."""
    from ovirt_mcp.client.exceptions import OvirtValidationError

    client = OvirtClient(config=mock_config)

    mock_service = MagicMock()
    mock_sub_service = MagicMock()
    mock_sub_service.get.side_effect = Exception("Not a UUID")
    mock_service.disk_service.return_value = mock_sub_service

    disk1 = MagicMock(id="uuid-1", name="duplicate-disk")
    disk1.name = "duplicate-disk"
    disk2 = MagicMock(id="uuid-2", name="duplicate-disk")
    disk2.name = "duplicate-disk"
    mock_service.list.return_value = [disk1, disk2]

    with pytest.raises(OvirtValidationError) as exc_info:
        client.find_resource_by_id_or_name(mock_service, "duplicate-disk", "disk")

    assert "Ambiguous disk identifier" in str(exc_info.value)
    assert "uuid-1" in str(exc_info.value)
    assert "uuid-2" in str(exc_info.value)
