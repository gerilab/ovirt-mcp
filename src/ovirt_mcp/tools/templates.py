"""Tools for managing oVirt / OLVM templates, golden images, and template lifecycle."""

import logging
import time

import ovirtsdk4.types as sdk_types

from ovirt_mcp.client import get_client
from ovirt_mcp.client.exceptions import OvirtMCPError, OvirtValidationError
from ovirt_mcp.models.template import (
    TemplateDetail,
    TemplateDiskInfo,
    TemplateResult,
    TemplateSummary,
)
from ovirt_mcp.tools.guards import (
    audit_log,
    require_destructive_confirmation,
    require_mutation_allowed,
)

logger = logging.getLogger("ovirt_mcp.tools.templates")

BLANK_TEMPLATE_ID = "00000000-0000-0000-0000-000000000000"


def list_templates_tool(search: str | None = None) -> list[TemplateSummary]:
    """List all templates and golden images in the virtualization environment.

    Args:
        search: Optional search query (e.g. 'name=gold*', 'status=ok').

    Returns:
        List of TemplateSummary objects with hardware specs and version indices.
    """
    client = get_client()
    conn = client.get_connection()
    t_svc = conn.system_service().templates_service()

    try:
        raw_templates = t_svc.list(search=search)
    except Exception as exc:
        raise OvirtMCPError(
            f"Failed to list templates: {exc}",
            details={"search": search, "error": str(exc)},
        ) from exc

    results: list[TemplateSummary] = []
    for t in raw_templates:
        t_id = str(t.id)
        t_name = str(getattr(t, "name", t_id))
        desc = getattr(t, "description", None)

        cl_id = None
        if hasattr(t, "cluster") and t.cluster and getattr(t.cluster, "id", None):
            cl_id = str(t.cluster.id)

        st_obj = getattr(t, "status", None)
        status_str = str(getattr(st_obj, "value", st_obj or "ok")).lower()

        mem_bytes = getattr(t, "memory", None)
        mem_mb = (mem_bytes // (1024 * 1024)) if mem_bytes else None

        cpu_cores = None
        cpu_sockets = None
        if hasattr(t, "cpu") and t.cpu and getattr(t.cpu, "topology", None):
            topo = t.cpu.topology
            cpu_cores = getattr(topo, "cores", None)
            cpu_sockets = getattr(topo, "sockets", None)

        ver_num = None
        ver_name = None
        base_id = None
        if hasattr(t, "version") and t.version:
            ver_num = getattr(t.version, "version_number", None)
            ver_name = getattr(t.version, "version_name", None)
            if hasattr(t.version, "base_template") and t.version.base_template:
                base_id = getattr(t.version.base_template, "id", None)

        results.append(
            TemplateSummary(
                id=t_id,
                name=t_name,
                description=desc,
                cluster_id=cl_id,
                status=status_str,
                memory_mb=mem_mb,
                cpu_cores=cpu_cores,
                cpu_sockets=cpu_sockets,
                version_number=ver_num,
                version_name=ver_name,
                base_template_id=base_id,
            )
        )

    return results


def get_template_tool(name_or_id: str) -> TemplateDetail:
    """Retrieve deep hardware, disk, and configuration details of a template.

    Args:
        name_or_id: Template name or UUID.

    Returns:
        TemplateDetail with hardware profile, attached disks, and NIC count.
    """
    client = get_client()
    conn = client.get_connection()
    t_svc = conn.system_service().templates_service()

    template = client.find_resource_by_id_or_name(t_svc, name_or_id, "template")
    t_inst = t_svc.template_service(template.id)

    # Basic fields
    t_id = str(template.id)
    t_name = str(getattr(template, "name", t_id))
    desc = getattr(template, "description", None)

    cl_id = None
    if hasattr(template, "cluster") and template.cluster and getattr(template.cluster, "id", None):
        cl_id = str(template.cluster.id)

    st_obj = getattr(template, "status", None)
    status_str = str(getattr(st_obj, "value", st_obj or "ok")).lower()

    mem_bytes = getattr(template, "memory", None)
    mem_mb = (mem_bytes // (1024 * 1024)) if mem_bytes else None

    cpu_cores = None
    cpu_sockets = None
    if hasattr(template, "cpu") and template.cpu and getattr(template.cpu, "topology", None):
        topo = template.cpu.topology
        cpu_cores = getattr(topo, "cores", None)
        cpu_sockets = getattr(topo, "sockets", None)

    ver_num = None
    ver_name = None
    base_id = None
    if hasattr(template, "version") and template.version:
        ver_num = getattr(template.version, "version_number", None)
        ver_name = getattr(template.version, "version_name", None)
        if hasattr(template.version, "base_template") and template.version.base_template:
            base_id = getattr(template.version.base_template, "id", None)

    os_type = None
    if hasattr(template, "os") and template.os and getattr(template.os, "type", None):
        os_type = str(template.os.type)

    created_at = (
        template.creation_time.isoformat()
        if hasattr(template, "creation_time") and template.creation_time
        else None
    )

    # Disks attached to template
    disk_infos: list[TemplateDiskInfo] = []
    try:
        attachments = t_inst.disk_attachments_service().list()
        for att in attachments:
            att_id = str(att.id)
            d_id = str(att.disk.id) if hasattr(att, "disk") and att.disk else att_id
            iface = str(getattr(att, "interface", "virtio"))
            boot = bool(getattr(att, "bootable", False))
            disk_infos.append(
                TemplateDiskInfo(
                    id=att_id,
                    disk_id=d_id,
                    interface=iface,
                    bootable=boot,
                )
            )
    except Exception as exc:
        logger.warning("Could not fetch disk attachments for template %s: %s", t_name, exc)

    # NIC count
    nic_cnt = 0
    try:
        nics = t_inst.nics_service().list()
        nic_cnt = len(nics)
    except Exception as exc:
        logger.warning("Could not fetch NICs for template %s: %s", t_name, exc)

    return TemplateDetail(
        id=t_id,
        name=t_name,
        description=desc,
        cluster_id=cl_id,
        status=status_str,
        memory_mb=mem_mb,
        cpu_cores=cpu_cores,
        cpu_sockets=cpu_sockets,
        version_number=ver_num,
        version_name=ver_name,
        base_template_id=base_id,
        os_type=os_type,
        creation_time=created_at,
        disks=disk_infos,
        nic_count=nic_cnt,
    )


def create_template_from_vm_tool(
    vm_name_or_id: str,
    template_name: str,
    description: str | None = None,
    wait: bool = True,
    timeout: int = 300,
) -> TemplateResult:
    """Create a new reusable template / golden image from an existing virtual machine.

    Args:
        vm_name_or_id: Name or UUID of the source virtual machine.
        template_name: Name for the new template.
        description: Optional descriptive text.
        wait: Whether to synchronously wait until template provisioning completes.
        timeout: Maximum wait time in seconds.

    Returns:
        TemplateResult with creation outcome.
    """
    require_mutation_allowed("ovirt_template_create_from_vm")

    template_name = template_name.strip()
    if not template_name:
        raise OvirtValidationError("template_name cannot be empty.")

    client = get_client()
    conn = client.get_connection()
    sys_svc = conn.system_service()
    vms_svc = sys_svc.vms_service()
    t_svc = sys_svc.templates_service()

    vm = client.find_resource_by_id_or_name(vms_svc, vm_name_or_id, "vm")

    # Guard: VM must be powered down (down) before template creation
    vm_status = str(getattr(vm, "status", "unknown")).lower()
    if vm_status != "down":
        raise OvirtValidationError(
            f"Cannot create template from VM '{vm.name}': VM is currently '{vm_status}'. "
            "oVirt requires the virtual machine to be completely stopped ('down') to snapshot disk images.",
            details={"vm_id": str(vm.id), "vm_name": str(vm.name), "status": vm_status},
        )

    # Check for name collision
    existing = t_svc.list(search=f"name={template_name}")
    if existing:
        raise OvirtValidationError(
            f"A template named '{template_name}' already exists in the environment.",
            details={"template_name": template_name, "existing_id": str(existing[0].id)},
        )

    template_spec = sdk_types.Template(
        name=template_name,
        description=description,
        vm=sdk_types.Vm(id=vm.id),
    )

    try:
        created = t_svc.add(template_spec)
        t_id = str(created.id)
    except Exception as exc:
        audit_log(
            "ovirt_template_create_from_vm",
            template_name,
            {"vm_name": str(vm.name), "vm_id": str(vm.id), "error": str(exc)},
            "FAILED",
        )
        raise OvirtMCPError(
            f"Failed to create template '{template_name}' from VM '{vm.name}': {exc}",
            details={"template_name": template_name, "vm_id": str(vm.id), "error": str(exc)},
        ) from exc

    t_inst = t_svc.template_service(t_id)

    if wait:
        start_time = time.time()
        time.sleep(2)
        while time.time() - start_time < timeout:
            updated = t_inst.get()
            status = str(getattr(updated, "status", "ok")).lower()
            if status == "ok":
                break
            if status == "illegal":
                raise OvirtMCPError(
                    f"Template creation failed for '{template_name}'. Status became 'illegal'.",
                    details={"template_id": t_id, "status": status},
                )
            time.sleep(3)

    audit_log(
        "ovirt_template_create_from_vm",
        template_name,
        {"template_id": t_id, "vm_name": str(vm.name), "vm_id": str(vm.id)},
        "SUCCESS",
    )

    return TemplateResult(
        success=True,
        template_id=t_id,
        template_name=template_name,
        action="create",
        message=f"Template '{template_name}' created successfully from VM '{vm.name}'.",
    )


def delete_template_tool(
    name_or_id: str,
    confirm: bool = False,
    wait: bool = True,
    timeout: int = 180,
) -> TemplateResult:
    """Delete an oVirt / OLVM template from the environment.

    Protected by safe-mode confirmation. Protected system templates (such as 'Blank')
    cannot be deleted.

    Args:
        name_or_id: Template name or UUID.
        confirm: Confirmation flag required in safe-mode.
        wait: Whether to synchronously wait for removal to complete.
        timeout: Maximum wait time in seconds.

    Returns:
        TemplateResult with removal outcome.
    """
    require_destructive_confirmation("ovirt_template_delete", confirm)
    require_mutation_allowed("ovirt_template_delete")

    client = get_client()
    conn = client.get_connection()
    t_svc = conn.system_service().templates_service()

    template = client.find_resource_by_id_or_name(t_svc, name_or_id, "template")
    t_id = str(template.id)
    t_name = str(getattr(template, "name", t_id))

    # Guard: Protected system Blank template cannot be deleted
    if t_id == BLANK_TEMPLATE_ID or t_name.lower() == "blank":
        raise OvirtValidationError(
            f"Cannot delete system template '{t_name}' ({t_id}). "
            "The Blank template is permanently reserved and protected by oVirt / OLVM.",
            details={"template_id": t_id, "template_name": t_name},
        )

    t_inst = t_svc.template_service(t_id)

    try:
        t_inst.remove()
    except Exception as exc:
        audit_log(
            "ovirt_template_delete",
            t_name,
            {"template_id": t_id, "error": str(exc)},
            "FAILED",
        )
        raise OvirtMCPError(
            f"Failed to delete template '{t_name}' ({t_id}): {exc}",
            details={"template_id": t_id, "error": str(exc)},
        ) from exc

    if wait:
        start_time = time.time()
        time.sleep(2)
        while time.time() - start_time < timeout:
            try:
                t_inst.get()
                time.sleep(2)
            except Exception:
                # 404 / NotFound means removal finished
                break

    audit_log(
        "ovirt_template_delete",
        t_name,
        {"template_id": t_id},
        "SUCCESS",
    )

    return TemplateResult(
        success=True,
        template_id=t_id,
        template_name=t_name,
        action="delete",
        message=f"Template '{t_name}' ({t_id}) successfully deleted.",
    )
