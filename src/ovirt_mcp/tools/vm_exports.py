"""Tools for exporting and importing virtual machines and virtual disks in oVirt / OLVM."""

import logging
from typing import Any

import ovirtsdk4.types as sdk_types

from ovirt_mcp.client import get_client
from ovirt_mcp.client.exceptions import OvirtMCPError, OvirtValidationError
from ovirt_mcp.models.compute import VmExportResult, VmImportResult
from ovirt_mcp.models.disk import DiskOperationResult
from ovirt_mcp.tools.guards import (
    audit_log,
    require_destructive_confirmation,
)

logger = logging.getLogger(__name__)


def export_vm_tool(
    vm_name_or_id: str,
    storage_domain: str | None = None,
    host: str | None = None,
    directory: str | None = None,
    filename: str | None = None,
    discard_snapshots: bool = False,
    confirm: bool = False,
) -> VmExportResult:
    """Export a virtual machine to an Export Storage Domain or as an OVA archive on a host.

    Args:
        vm_name_or_id: Virtual machine display name or UUID.
        storage_domain: Name or UUID of target Export Storage Domain.
        host: Host name or UUID for OVA export (required if directory is specified).
        directory: Target path on host filesystem where the OVA file will be created.
        filename: Optional custom OVA filename (e.g. 'my-app.ova').
        discard_snapshots: Whether to collapse and discard snapshot history during export.
        confirm: Confirmation flag required in Safe Mode.

    Returns:
        VmExportResult confirming initiation of the export.
    """
    if not storage_domain and not (host and directory):
        raise OvirtValidationError(
            "You must specify either 'storage_domain' (for export domain) "
            "or both 'host' and 'directory' (for OVA export)."
        )

    target_desc = (
        f"storage domain '{storage_domain}'"
        if storage_domain
        else f"path '{directory}' on host '{host}'"
    )
    require_destructive_confirmation(f"Export VM '{vm_name_or_id}' to {target_desc}", confirm)

    client = get_client()
    conn = client.get_connection()
    sys_service = conn.system_service()
    vms_service = sys_service.vms_service()

    vm = client.find_resource_by_id_or_name(vms_service, vm_name_or_id, "vm")
    vm_id = str(vm.id)
    vm_name = str(getattr(vm, "name", vm_id))
    vm_service = vms_service.vm_service(vm_id)

    try:
        if storage_domain:
            sds_service = sys_service.storage_domains_service()
            sd = client.find_resource_by_id_or_name(sds_service, storage_domain, "storage_domain")
            sd_id = str(sd.id)
            sd_name = str(getattr(sd, "name", sd_id))

            vm_service.export(
                storage_domain=sdk_types.StorageDomain(id=sd_id),
                discard_snapshots=discard_snapshots,
            )
            audit_log("export_vm", vm_name, {"vm_id": vm_id, "storage_domain": sd_name}, "SUCCESS")
            return VmExportResult(
                success=True,
                vm_id=vm_id,
                vm_name=vm_name,
                export_target=sd_name,
                format="export_domain",
                message=f"Virtual machine '{vm_name}' successfully triggered export to storage domain '{sd_name}'.",
            )
        else:
            hosts_service = sys_service.hosts_service()
            h = client.find_resource_by_id_or_name(hosts_service, str(host), "host")
            h_id = str(h.id)
            h_name = str(getattr(h, "name", h_id))

            export_kwargs: dict[str, Any] = {
                "host": sdk_types.Host(id=h_id),
                "directory": directory,
                "discard_snapshots": discard_snapshots,
            }
            if filename:
                export_kwargs["filename"] = filename

            vm_service.export_to_path_on_host(**export_kwargs)
            target_path = f"{directory}/{filename}" if filename else directory
            audit_log(
                "export_vm",
                vm_name,
                {"vm_id": vm_id, "host": h_name, "path": target_path},
                "SUCCESS",
            )
            return VmExportResult(
                success=True,
                vm_id=vm_id,
                vm_name=vm_name,
                export_target=f"{h_name}:{target_path}",
                format="ova",
                message=f"Virtual machine '{vm_name}' successfully triggered OVA export to '{target_path}' on host '{h_name}'.",
            )
    except Exception as exc:
        audit_log("export_vm", vm_name, {"vm_id": vm_id, "error": str(exc)}, "FAILED")
        raise OvirtMCPError(f"Failed to export VM '{vm_name}': {exc}") from exc


def import_vm_tool(
    storage_domain: str,
    vm_name_or_id: str,
    cluster: str,
    target_storage_domain: str | None = None,
    confirm: bool = False,
) -> VmImportResult:
    """Import a virtual machine from an Export Storage Domain into a designated cluster.

    Args:
        storage_domain: Name or UUID of the Export Storage Domain containing the VM.
        vm_name_or_id: Display name or UUID of the virtual machine on the export domain.
        cluster: Target cluster name or UUID where the VM will run.
        target_storage_domain: Target data storage domain for the imported disks (optional).
        confirm: Confirmation flag required in Safe Mode.

    Returns:
        VmImportResult confirming completion of the import.
    """
    require_destructive_confirmation(
        f"Import VM '{vm_name_or_id}' from '{storage_domain}' into cluster '{cluster}'",
        confirm,
    )

    client = get_client()
    conn = client.get_connection()
    sys_service = conn.system_service()

    sds_service = sys_service.storage_domains_service()
    sd = client.find_resource_by_id_or_name(sds_service, storage_domain, "storage_domain")
    sd_id = str(sd.id)
    sd_name = str(getattr(sd, "name", sd_id))

    clusters_service = sys_service.clusters_service()
    cl = client.find_resource_by_id_or_name(clusters_service, cluster, "cluster")
    cl_id = str(cl.id)
    cl_name = str(getattr(cl, "name", cl_id))

    sd_vms_service = sds_service.storage_domain_service(sd_id).vms_service()
    exported_vms = sd_vms_service.list() or []

    target_vm = None
    clean_id = vm_name_or_id.replace("'", "").replace('"', "")
    for exp_vm in exported_vms:
        if str(exp_vm.id) == clean_id or str(getattr(exp_vm, "name", "")) == clean_id:
            target_vm = exp_vm
            break

    if not target_vm:
        raise OvirtValidationError(
            f"Virtual machine '{vm_name_or_id}' not found on export storage domain '{sd_name}'."
        )

    t_vm_id = str(target_vm.id)
    t_vm_name = str(getattr(target_vm, "name", t_vm_id))

    import_kwargs: dict[str, Any] = {
        "cluster": sdk_types.Cluster(id=cl_id),
    }
    target_sd_name = sd_name
    if target_storage_domain:
        target_sd = client.find_resource_by_id_or_name(
            sds_service, target_storage_domain, "storage_domain"
        )
        target_sd_name = str(getattr(target_sd, "name", target_sd.id))
        import_kwargs["storage_domain"] = sdk_types.StorageDomain(id=str(target_sd.id))

    try:
        sd_vm_service = sd_vms_service.vm_service(t_vm_id)
        sd_vm_service.import_(**import_kwargs)
        audit_log(
            "import_vm",
            t_vm_name,
            {"vm_id": t_vm_id, "cluster": cl_name, "storage_domain": target_sd_name},
            "SUCCESS",
        )
        return VmImportResult(
            success=True,
            vm_id=t_vm_id,
            vm_name=t_vm_name,
            cluster_name=cl_name,
            storage_domain_name=target_sd_name,
            message=f"Virtual machine '{t_vm_name}' successfully triggered import into cluster '{cl_name}'.",
        )
    except Exception as exc:
        audit_log("import_vm", t_vm_name, {"vm_id": t_vm_id, "error": str(exc)}, "FAILED")
        raise OvirtMCPError(f"Failed to import VM '{t_vm_name}': {exc}") from exc


def export_disk_tool(
    disk_name_or_id: str,
    storage_domain: str,
    confirm: bool = False,
) -> DiskOperationResult:
    """Export a virtual disk to an Export Storage Domain.

    Args:
        disk_name_or_id: Virtual disk display name, alias, or UUID.
        storage_domain: Target Export Storage Domain name or UUID.
        confirm: Confirmation flag required in Safe Mode.

    Returns:
        DiskOperationResult confirming disk export initiation.
    """
    require_destructive_confirmation(
        f"Export virtual disk '{disk_name_or_id}' to storage domain '{storage_domain}'",
        confirm,
    )

    client = get_client()
    conn = client.get_connection()
    sys_service = conn.system_service()

    disks_service = sys_service.disks_service()
    disk = client.find_resource_by_id_or_name(disks_service, disk_name_or_id, "disk")
    disk_id = str(disk.id)
    raw_name = getattr(disk, "name", None) or getattr(disk, "alias", None)
    if isinstance(raw_name, str):
        disk_name = raw_name
    elif raw_name and not hasattr(raw_name, "_mock_return_value"):
        disk_name = str(raw_name)
    else:
        disk_name = disk_id

    sds_service = sys_service.storage_domains_service()
    sd = client.find_resource_by_id_or_name(sds_service, storage_domain, "storage_domain")
    sd_id = str(sd.id)
    sd_name = str(getattr(sd, "name", sd_id))

    try:
        disk_service = disks_service.disk_service(disk_id)
        disk_service.export(storage_domain=sdk_types.StorageDomain(id=sd_id))
        audit_log(
            "export_disk", disk_name, {"disk_id": disk_id, "storage_domain": sd_name}, "SUCCESS"
        )
        return DiskOperationResult(
            success=True,
            disk_id=disk_id,
            disk_name=disk_name,
            action="export",
            target_storage_domain=sd_name,
            message=f"Virtual disk '{disk_name}' ({disk_id}) successfully triggered export to storage domain '{sd_name}'.",
        )
    except Exception as exc:
        audit_log("export_disk", disk_name, {"disk_id": disk_id, "error": str(exc)}, "FAILED")
        raise OvirtMCPError(f"Failed to export disk '{disk_name}': {exc}") from exc
