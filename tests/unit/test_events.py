"""Unit tests for VM and global system audit events tools."""

from unittest.mock import MagicMock, patch

import pytest

from ovirt_mcp.client.exceptions import OvirtValidationError
from ovirt_mcp.models.event import SystemEvent
from ovirt_mcp.tools.events import (
    extract_system_event,
    extract_vm_event,
    list_system_events_tool,
    list_vm_events_tool,
)


def test_extract_vm_event() -> None:
    """Test extracting VmEvent from mock oVirt SDK Event."""
    mock_event = MagicMock()
    mock_event.id = "4321"
    mock_event.code = 12
    mock_event.severity.value = "error"
    mock_event.time = "2026-11-18T10:00:00Z"
    mock_event.description = "VM failed to power on due to missing storage domain"
    mock_event.vm.id = "vm-uuid-4321"
    mock_event.user_name = "admin@internal"
    mock_event.correlation_id = "flow-999"

    event_model = extract_vm_event(mock_event)

    assert event_model.id == "4321"
    assert event_model.code == 12
    assert event_model.severity == "error"
    assert event_model.time == "2026-11-18T10:00:00Z"
    assert "missing storage domain" in event_model.description
    assert event_model.vm_id == "vm-uuid-4321"
    assert event_model.user_name == "admin@internal"
    assert event_model.correlation_id == "flow-999"


def test_list_vm_events_tool() -> None:
    """Test list_vm_events_tool fetches events with proper search query."""
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_system = MagicMock()
    mock_vms_service = MagicMock()
    mock_events_service = MagicMock()

    mock_vm = MagicMock()
    mock_vm.name = "web-prod-01"

    mock_client.find_resource_by_id_or_name.return_value = mock_vm
    mock_system.vms_service.return_value = mock_vms_service
    mock_system.events_service.return_value = mock_events_service
    mock_conn.system_service.return_value = mock_system
    mock_client.get_connection.return_value = mock_conn

    mock_events_service.list.return_value = []

    with patch("ovirt_mcp.tools.events.get_client", return_value=mock_client):
        res = list_vm_events_tool("web-prod-01", max_events=15, severity="error")
        assert res == []
        mock_events_service.list.assert_called_once_with(
            search='vm.name="web-prod-01" and severity=error',
            max=15,
        )


def test_extract_system_event() -> None:
    """Test extracting SystemEvent with all correlated entity fields."""
    mock_event = MagicMock()
    mock_event.id = "9901"
    mock_event.code = 104
    mock_event.severity.value = "alert"
    mock_event.time = "2026-11-19T10:00:00Z"
    mock_event.description = "Low disk space on storage domain Data01"
    mock_event.vm.id = "vm-uuid-111"
    mock_event.vm.name = "testvm001"
    mock_event.host.id = "host-uuid-222"
    mock_event.host.name = "olvmhost001"
    mock_event.cluster.id = "cluster-uuid-333"
    mock_event.cluster.name = "DefaultCluster"
    mock_event.storage_domain.id = "sd-uuid-444"
    mock_event.storage_domain.name = "Data01"
    mock_event.user_name = "admin@internal"
    mock_event.correlation_id = "corr-1234"

    event_model = extract_system_event(mock_event)

    assert isinstance(event_model, SystemEvent)
    assert event_model.id == "9901"
    assert event_model.code == 104
    assert event_model.severity == "alert"
    assert event_model.time == "2026-11-19T10:00:00Z"
    assert "Low disk space" in event_model.description
    assert event_model.vm_id == "vm-uuid-111"
    assert event_model.vm_name == "testvm001"
    assert event_model.host_id == "host-uuid-222"
    assert event_model.host_name == "olvmhost001"
    assert event_model.cluster_id == "cluster-uuid-333"
    assert event_model.cluster_name == "DefaultCluster"
    assert event_model.storage_domain_id == "sd-uuid-444"
    assert event_model.storage_domain_name == "Data01"
    assert event_model.user_name == "admin@internal"
    assert event_model.correlation_id == "corr-1234"


def test_list_system_events_tool_success() -> None:
    """Test list_system_events_tool with severity and query filtering."""
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_system = MagicMock()
    mock_events_service = MagicMock()

    mock_event = MagicMock()
    mock_event.id = "1"
    mock_event.code = 10
    mock_event.severity.value = "warning"
    mock_event.time = "2026-11-19T11:00:00Z"
    mock_event.description = "Host CPU threshold exceeded"
    mock_event.vm = None
    mock_event.host.name = "olvmhost002"
    mock_event.cluster = None
    mock_event.storage_domain = None
    mock_event.user_name = None
    mock_event.correlation_id = None

    mock_events_service.list.return_value = [mock_event]
    mock_system.events_service.return_value = mock_events_service
    mock_conn.system_service.return_value = mock_system
    mock_client.get_connection.return_value = mock_conn

    with patch("ovirt_mcp.tools.events.get_client", return_value=mock_client):
        res = list_system_events_tool(
            max_events=20,
            severity="warning",
            search="host = olvmhost002",
            from_event_id=500,
        )

    assert len(res) == 1
    assert res[0].id == "1"
    assert res[0].severity == "warning"
    assert res[0].host_name == "olvmhost002"
    mock_events_service.list.assert_called_once_with(
        max=20,
        search="severity = warning and host = olvmhost002",
        from_=500,
    )


def test_list_system_events_tool_invalid_max() -> None:
    """Test validation error when max_events is out of range."""
    with pytest.raises(OvirtValidationError):
        list_system_events_tool(max_events=0)

    with pytest.raises(OvirtValidationError):
        list_system_events_tool(max_events=501)
