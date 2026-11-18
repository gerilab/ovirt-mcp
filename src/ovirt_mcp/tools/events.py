"""Audit event and system logging tools for oVirt / OLVM."""

import logging
from typing import Any

from ovirt_mcp.client import get_client
from ovirt_mcp.models.event import VmEvent

logger = logging.getLogger(__name__)


def extract_vm_event(event: Any) -> VmEvent:
    """Extract a typed VmEvent model from an oVirt SDK Event object."""
    event_id = str(getattr(event, "id", ""))
    code = getattr(event, "code", None)

    sev_obj = getattr(event, "severity", None)
    severity_str = getattr(sev_obj, "value", str(sev_obj or "normal")).lower()

    time_str = str(getattr(event, "time", ""))
    description = str(getattr(event, "description", ""))
    user_name = getattr(event, "user_name", None)
    correlation_id = getattr(event, "correlation_id", None)

    return VmEvent(
        id=event_id,
        code=code,
        severity=severity_str,
        time=time_str,
        description=description,
        user_name=user_name,
        correlation_id=correlation_id,
    )


def list_vm_events_tool(
    name_or_id: str,
    max_events: int = 25,
    severity: str | None = None,
) -> list[VmEvent]:
    """Retrieve audit history, shutdown causes, and operational events for a virtual machine.

    Args:
        name_or_id: Virtual machine name or UUID.
        max_events: Maximum number of events to return (default: 25).
        severity: Optional severity filter (e.g. 'normal', 'warning', 'error', 'alert').
    """
    client = get_client()
    connection = client.get_connection()
    system_service = connection.system_service()
    vms_service = system_service.vms_service()

    # Find VM to ensure it exists and get canonical name
    vm = client.find_resource_by_id_or_name(vms_service, name_or_id, "vm")

    clean_name = str(vm.name).replace('"', "")
    search_query = f'vm.name="{clean_name}"'
    if severity:
        clean_sev = severity.strip().lower().replace('"', "")
        search_query += f" and severity={clean_sev}"

    logger.debug("Fetching events with search query: %s (max=%d)", search_query, max_events)
    events_service = system_service.events_service()
    sdk_events = events_service.list(search=search_query, max=max_events)

    return [extract_vm_event(e) for e in sdk_events]
