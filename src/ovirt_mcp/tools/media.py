"""Tools for managing VM CD-ROM drives, ISO media attachment, and ISO storage domains."""

import logging

import ovirtsdk4.types as sdk_types

from ovirt_mcp.client import get_client
from ovirt_mcp.client.exceptions import OvirtMCPError, OvirtValidationError
from ovirt_mcp.models.media import IsoFileInfo, VmCdromInfo, VmCdromResult
from ovirt_mcp.tools.guards import audit_log, require_mutation_allowed

logger = logging.getLogger("ovirt_mcp.tools.media")


def list_vm_cdroms_tool(name_or_id: str) -> list[VmCdromInfo]:
    """List virtual CD-ROM drives and mounted media for a virtual machine.

    Args:
        name_or_id: Display name or UUID of the virtual machine.

    Returns:
        List of VmCdromInfo indicating device IDs and mounted ISO file names.
    """
    client = get_client()
    conn = client.get_connection()
    vms_service = conn.system_service().vms_service()
    vm = client.find_resource_by_id_or_name(vms_service, name_or_id, "vm")
    vm_id = str(vm.id)
    vm_service = vms_service.vm_service(vm_id)

    cdrom_list: list[VmCdromInfo] = []
    try:
        raw_cdroms = vm_service.cdroms_service().list()
        for cd in raw_cdroms:
            cd_id = str(getattr(cd, "id", ""))
            file_obj = getattr(cd, "file", None)
            file_id = getattr(file_obj, "id", None) if file_obj else None
            # In oVirt, an empty drive has file_id as None or empty string
            file_str = str(file_id) if file_id else None
            is_empty = not bool(file_str)

            cdrom_list.append(
                VmCdromInfo(
                    id=cd_id,
                    file_id=file_str,
                    is_empty=is_empty,
                )
            )
    except Exception as exc:
        logger.warning("Failed to list CD-ROM drives for VM '%s': %s", name_or_id, exc)
        raise OvirtMCPError(
            f"Failed to list CD-ROM drives for VM '{name_or_id}': {exc}",
            details={"vm": name_or_id, "error": str(exc)},
        ) from exc

    return cdrom_list


def attach_vm_iso_tool(
    name_or_id: str,
    iso_file: str,
    cdrom_id: str | None = None,
    current: bool | None = None,
) -> VmCdromResult:
    """Attach / mount an ISO image into a virtual machine's CD-ROM drive.

    Args:
        name_or_id: Display name or UUID of the virtual machine.
        iso_file: Name of the ISO file in the active ISO storage domain (e.g. 'boot.iso').
        cdrom_id: Specific CD-ROM device UUID. If omitted, the first available drive is used.
        current: If True, applies media change to currently running VM (hot-swap).
                 If False, applies only to persistent configuration for next boot.
                 If None (default), automatically applies to both live and persistent when VM is up.

    Returns:
        VmCdromResult with operation status and mounted ISO file name.
    """
    require_mutation_allowed("attach_vm_iso")

    if not iso_file or not iso_file.strip():
        raise OvirtValidationError("ISO file name cannot be empty.")

    client = get_client()
    conn = client.get_connection()
    vms_service = conn.system_service().vms_service()
    vm = client.find_resource_by_id_or_name(vms_service, name_or_id, "vm")
    vm_id = str(vm.id)
    vm_name = str(vm.name)
    vm_service = vms_service.vm_service(vm_id)

    raw_cdroms = vm_service.cdroms_service().list()
    if not raw_cdroms:
        raise OvirtValidationError(
            f"Virtual machine '{vm_name}' does not have any CD-ROM drives configured.",
            details={"vm_id": vm_id},
        )

    target_cdrom = raw_cdroms[0]
    if cdrom_id:
        matched = [cd for cd in raw_cdroms if str(getattr(cd, "id", "")) == cdrom_id]
        if not matched:
            raise OvirtValidationError(
                f"CD-ROM device '{cdrom_id}' not found on VM '{vm_name}'.",
                details={"vm_id": vm_id, "cdrom_id": cdrom_id},
            )
        target_cdrom = matched[0]

    target_cd_id = str(getattr(target_cdrom, "id", ""))
    cdrom_svc = vm_service.cdroms_service().cdrom_service(target_cd_id)

    status_obj = getattr(vm, "status", None)
    vm_is_up = getattr(status_obj, "value", str(status_obj or "")).lower() == "up"

    cdrom_spec = sdk_types.Cdrom(
        file=sdk_types.File(id=iso_file.strip()),
    )

    try:
        if current is True:
            cdrom_svc.update(cdrom_spec, current=True)
            hot_swapped = True
        elif current is False:
            cdrom_svc.update(cdrom_spec, current=False)
            hot_swapped = False
        else:
            # Default: update persistent config, and if VM is running also hot-swap
            cdrom_svc.update(cdrom_spec, current=False)
            if vm_is_up:
                try:
                    cdrom_svc.update(cdrom_spec, current=True)
                except Exception as live_exc:
                    logger.warning(
                        "Live CD-ROM update succeeded persistently but live hot-swap failed: %s",
                        live_exc,
                    )
            hot_swapped = vm_is_up
    except Exception as exc:
        audit_log(
            "attach_vm_iso",
            vm_name,
            {"vm_id": vm_id, "iso_file": iso_file, "error": str(exc)},
            "FAILED",
        )
        raise OvirtMCPError(
            f"Failed to attach ISO '{iso_file}' to VM '{vm_name}': {exc}",
            details={"vm_id": vm_id, "iso_file": iso_file, "error": str(exc)},
        ) from exc

    audit_log(
        "attach_vm_iso",
        vm_name,
        {
            "vm_id": vm_id,
            "cdrom_id": target_cd_id,
            "iso_file": iso_file,
            "hot_swapped": hot_swapped,
        },
        "SUCCESS",
    )
    return VmCdromResult(
        success=True,
        action="attach",
        vm_id=vm_id,
        vm_name=vm_name,
        cdrom_id=target_cd_id,
        iso_file=iso_file.strip(),
        current=hot_swapped,
        message=(
            f"ISO '{iso_file.strip()}' attached successfully to CD-ROM '{target_cd_id}' "
            f"on VM '{vm_name}' (hot_swap={hot_swapped})."
        ),
    )


def eject_vm_iso_tool(
    name_or_id: str,
    cdrom_id: str | None = None,
    current: bool | None = None,
) -> VmCdromResult:
    """Eject / unmount any mounted ISO media from a virtual machine's CD-ROM drive.

    Args:
        name_or_id: Display name or UUID of the virtual machine.
        cdrom_id: Specific CD-ROM device UUID. If omitted, the first available drive is used.
        current: If True, applies media eject to currently running VM (hot-eject).
                 If False, applies only to persistent configuration.
                 If None (default), automatically applies to both live and persistent when VM is up.

    Returns:
        VmCdromResult with operation status and empty iso_file.
    """
    require_mutation_allowed("eject_vm_iso")

    client = get_client()
    conn = client.get_connection()
    vms_service = conn.system_service().vms_service()
    vm = client.find_resource_by_id_or_name(vms_service, name_or_id, "vm")
    vm_id = str(vm.id)
    vm_name = str(vm.name)
    vm_service = vms_service.vm_service(vm_id)

    raw_cdroms = vm_service.cdroms_service().list()
    if not raw_cdroms:
        raise OvirtValidationError(
            f"Virtual machine '{vm_name}' does not have any CD-ROM drives configured.",
            details={"vm_id": vm_id},
        )

    target_cdrom = raw_cdroms[0]
    if cdrom_id:
        matched = [cd for cd in raw_cdroms if str(getattr(cd, "id", "")) == cdrom_id]
        if not matched:
            raise OvirtValidationError(
                f"CD-ROM device '{cdrom_id}' not found on VM '{vm_name}'.",
                details={"vm_id": vm_id, "cdrom_id": cdrom_id},
            )
        target_cdrom = matched[0]

    target_cd_id = str(getattr(target_cdrom, "id", ""))
    cdrom_svc = vm_service.cdroms_service().cdrom_service(target_cd_id)

    status_obj = getattr(vm, "status", None)
    vm_is_up = getattr(status_obj, "value", str(status_obj or "")).lower() == "up"

    # In oVirt, an empty File(id="") or empty file ejects the disc
    empty_cdrom_spec = sdk_types.Cdrom(
        file=sdk_types.File(id=""),
    )

    try:
        if current is True:
            cdrom_svc.update(empty_cdrom_spec, current=True)
            hot_swapped = True
        elif current is False:
            cdrom_svc.update(empty_cdrom_spec, current=False)
            hot_swapped = False
        else:
            cdrom_svc.update(empty_cdrom_spec, current=False)
            if vm_is_up:
                try:
                    cdrom_svc.update(empty_cdrom_spec, current=True)
                except Exception as live_exc:
                    logger.warning(
                        "Live CD-ROM eject succeeded persistently but live hot-eject failed: %s",
                        live_exc,
                    )
            hot_swapped = vm_is_up
    except Exception as exc:
        audit_log(
            "eject_vm_iso",
            vm_name,
            {"vm_id": vm_id, "error": str(exc)},
            "FAILED",
        )
        raise OvirtMCPError(
            f"Failed to eject ISO from CD-ROM on VM '{vm_name}': {exc}",
            details={"vm_id": vm_id, "error": str(exc)},
        ) from exc

    audit_log(
        "eject_vm_iso",
        vm_name,
        {"vm_id": vm_id, "cdrom_id": target_cd_id, "hot_swapped": hot_swapped},
        "SUCCESS",
    )
    return VmCdromResult(
        success=True,
        action="eject",
        vm_id=vm_id,
        vm_name=vm_name,
        cdrom_id=target_cd_id,
        iso_file=None,
        current=hot_swapped,
        message=f"ISO media successfully ejected from CD-ROM '{target_cd_id}' on VM '{vm_name}'.",
    )


def list_storage_isos_tool(storage_domain: str | None = None) -> list[IsoFileInfo]:
    """List available ISO image files across ISO storage domains.

    Args:
        storage_domain: Optional name or UUID of a specific storage domain to search.
                        If omitted, queries all active ISO storage domains.

    Returns:
        List of IsoFileInfo with ISO file names and containing storage domain information.
    """
    client = get_client()
    conn = client.get_connection()
    sds_service = conn.system_service().storage_domains_service()

    iso_files: list[IsoFileInfo] = []

    try:
        if storage_domain:
            domains = [
                client.find_resource_by_id_or_name(sds_service, storage_domain, "storage domain")
            ]
        else:
            domains = sds_service.list()
    except Exception as exc:
        logger.warning("Failed to locate storage domain '%s': %s", storage_domain, exc)
        raise OvirtMCPError(
            f"Failed to search ISO storage domains: {exc}",
            details={"storage_domain": storage_domain, "error": str(exc)},
        ) from exc

    for sd in domains:
        sd_id = str(getattr(sd, "id", ""))
        sd_name = str(getattr(sd, "name", ""))
        sd_type_obj = getattr(sd, "type", None)
        sd_type_str = str(getattr(sd_type_obj, "value", sd_type_obj or "")).lower()

        # Only ISO storage domains contain ISO files
        if sd_type_str != "iso":
            continue

        try:
            files_service = sds_service.storage_domain_service(sd_id).files_service()
            raw_files = files_service.list()
            for f in raw_files:
                f_id = str(getattr(f, "id", ""))
                f_name = str(getattr(f, "name", f_id))
                iso_files.append(
                    IsoFileInfo(
                        id=f_id,
                        name=f_name,
                        storage_domain_id=sd_id,
                        storage_domain_name=sd_name,
                    )
                )
        except Exception as sd_exc:
            logger.debug("Storage domain '%s' files query returned error: %s", sd_name, sd_exc)

    return iso_files
