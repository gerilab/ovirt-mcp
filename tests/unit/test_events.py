"""Unit tests for VM audit events tool."""

from unittest.mock import MagicMock, patch

from ovirt_mcp.tools.events import extract_vm_event, list_vm_events_tool


def test_extract_vm_event() -> None:
    """Test extracting VmEvent from mock oVirt SDK Event."""
    mock_event = MagicMock()
    mock_event.id = "4321"
    mock_event.code = 12
    mock_event.severity.value = "error"
    mock_event.time = "2026-11-18T10:00:00Z"
    mock_event.description = "VM failed to power on due to missing storage domain"
    mock_event.user_name = "admin@internal"
    mock_event.correlation_id = "flow-999"

    event_model = extract_vm_event(mock_event)

    assert event_model.id == "4321"
    assert event_model.code == 12
    assert event_model.severity == "error"
    assert event_model.time == "2026-11-18T10:00:00Z"
    assert "missing storage domain" in event_model.description
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
