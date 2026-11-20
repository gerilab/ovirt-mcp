"""Audit event and system logging tools for oVirt / OLVM."""

import logging
from typing import Any

from ovirt_mcp.client import get_client
from ovirt_mcp.client.exceptions import OvirtMCPError, OvirtValidationError
from ovirt_mcp.models.event import SystemEvent, VmEvent

logger = logging.getLogger(__name__)


def extract_vm_event(event: Any) -> VmEvent:
    """Extract a typed VmEvent model from an oVirt SDK Event object."""
    event_id = str(getattr(event, "id", ""))
    code = getattr(event, "code", None)

    sev_obj = getattr(event, "severity", None)
    severity_str = getattr(sev_obj, "value", str(sev_obj or "normal")).lower()

    time_str = str(getattr(event, "time", ""))
    description = str(getattr(event, "description", ""))

    vm_obj = getattr(event, "vm", None)
    vm_id = str(vm_obj.id) if vm_obj and getattr(vm_obj, "id", None) else None

    user_name = getattr(event, "user_name", None)
    correlation_id = getattr(event, "correlation_id", None)

    return VmEvent(
        id=event_id,
        code=code,
        severity=severity_str,
        time=time_str,
        description=description,
        vm_id=vm_id,
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


def extract_system_event(event: Any) -> SystemEvent:
    """Extract a typed SystemEvent model from an oVirt SDK Event object."""
    event_id = str(getattr(event, "id", ""))
    code = getattr(event, "code", None)

    sev_obj = getattr(event, "severity", None)
    severity_str = getattr(sev_obj, "value", str(sev_obj or "normal")).lower()

    time_str = str(getattr(event, "time", ""))
    description = str(getattr(event, "description", ""))

    vm_obj = getattr(event, "vm", None)
    vm_id = str(vm_obj.id) if vm_obj and getattr(vm_obj, "id", None) else None
    vm_name = getattr(vm_obj, "name", None) if vm_obj else None

    host_obj = getattr(event, "host", None)
    host_id = str(host_obj.id) if host_obj and getattr(host_obj, "id", None) else None
    host_name = getattr(host_obj, "name", None) if host_obj else None

    cluster_obj = getattr(event, "cluster", None)
    cluster_id = str(cluster_obj.id) if cluster_obj and getattr(cluster_obj, "id", None) else None
    cluster_name = getattr(cluster_obj, "name", None) if cluster_obj else None

    sd_obj = getattr(event, "storage_domain", None)
    sd_id = str(sd_obj.id) if sd_obj and getattr(sd_obj, "id", None) else None
    sd_name = getattr(sd_obj, "name", None) if sd_obj else None

    user_name = getattr(event, "user_name", None)
    correlation_id = getattr(event, "correlation_id", None)

    return SystemEvent(
        id=event_id,
        code=code,
        severity=severity_str,
        time=time_str,
        description=description,
        vm_id=vm_id,
        vm_name=vm_name,
        host_id=host_id,
        host_name=host_name,
        cluster_id=cluster_id,
        cluster_name=cluster_name,
        storage_domain_id=sd_id,
        storage_domain_name=sd_name,
        user_name=user_name,
        correlation_id=correlation_id,
    )


def list_system_events_tool(
    max_events: int = 50,
    severity: str | None = None,
    search: str | None = None,
    from_event_id: int | None = None,
) -> list[SystemEvent]:
    """Retrieve global system audit events, logs, and failure causes across the entire environment.

    Args:
        max_events: Maximum number of events to return (default: 50, max: 500).
        severity: Optional severity filter ('normal', 'warning', 'error', 'alert').
        search: Optional search query string (e.g. 'type = ...', keywords, or entity filters).
        from_event_id: Optional event ID to fetch events starting after this sequence ID.

    Returns:
        List of SystemEvent objects matching the criteria.
    """
    if max_events < 1 or max_events > 500:
        raise OvirtValidationError("max_events must be between 1 and 500.")

    client = get_client()
    connection = client.get_connection()
    events_service = connection.system_service().events_service()

    query_parts: list[str] = []
    if severity:
        clean_sev = severity.strip().lower().replace('"', "")
        query_parts.append(f"severity = {clean_sev}")
    if search:
        query_parts.append(search.strip())

    search_query = " and ".join(query_parts) if query_parts else None

    kwargs: dict[str, Any] = {"max": max_events}
    if search_query:
        kwargs["search"] = search_query
    if from_event_id is not None:
        kwargs["from_"] = from_event_id

    try:
        events = events_service.list(**kwargs)
    except Exception as exc:
        raise OvirtMCPError(
            f"Failed to retrieve system events: {exc}",
            details={"max_events": max_events, "search": search_query, "error": str(exc)},
        ) from exc

    return [extract_system_event(e) for e in events]
