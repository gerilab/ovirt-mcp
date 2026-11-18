#!/usr/bin/env python3
"""Live End-to-End Test for Template Lifecycle and Golden Images on OLVM."""

import os
import sys
import time

from ovirt_mcp.client import get_client
from ovirt_mcp.client.exceptions import OvirtValidationError
from ovirt_mcp.tools.templates import (
    create_template_from_vm_tool,
    delete_template_tool,
    get_template_tool,
    list_templates_tool,
)
from ovirt_mcp.tools.vms import (
    create_vm_tool,
    delete_vm_tool,
)


def main() -> None:
    print("=" * 70)
    print("oVirt / OLVM MCP Live Template Lifecycle & Golden Image Tester")
    print("=" * 70)

    client = get_client()
    conn = client.get_connection()
    sys_svc = conn.system_service()
    t_svc = sys_svc.templates_service()
    vms_svc = sys_svc.vms_service()

    test_vm_name = "mcp-tpl-srcvm"
    test_tpl_name = "mcp_test_golden_template"
    cluster_name = os.getenv("OVIRT_TEST_CLUSTER", "DefaultCluster")

    # Pre-cleanup in case of interrupted runs
    for name, is_vm in [(test_tpl_name, False), (test_vm_name, True)]:
        try:
            svc = vms_svc if is_vm else t_svc
            res_type = "vm" if is_vm else "template"
            existing = client.find_resource_by_id_or_name(svc, name, res_type)
            if existing:
                print(f"[Cleanup] Removing leftover {res_type} '{name}' ({existing.id})...")
                if is_vm:
                    delete_vm_tool(name, force=True, confirm=True, wait=True)
                else:
                    delete_template_tool(name, confirm=True, wait=True)
                time.sleep(3)
        except Exception:
            pass

    test_vm_id = None
    created_tpl_id = None

    try:
        # Step 1: List templates and inspect existing ones
        print("\n[Step 1] Listing templates in OLVM environment...")
        templates = list_templates_tool()
        print(f" -> Found {len(templates)} template(s):")
        for t in templates:
            print(
                f"    - Name: {t.name:<20} | ID: {t.id} | Status: {t.status} | "
                f"RAM: {t.memory_mb or 0:>5}MB | CPU: {t.cpu_cores or 0}c/{t.cpu_sockets or 0}s"
            )
        blank_tpl = next((t for t in templates if t.name.lower() == "blank"), None)
        assert blank_tpl is not None, "System 'Blank' template must exist in environment"

        # Step 2: Deep inspection of a template
        print("\n[Step 2] Deep inspection of 'Blank' template...")
        blank_detail = get_template_tool("Blank")
        print(f" -> Blank template detail: ID={blank_detail.id}, Status={blank_detail.status}")
        assert blank_detail.id == "00000000-0000-0000-0000-000000000000"

        # Step 3: Guard Test: Attempting to delete Blank template must be rejected
        print("\n[Step 3] Testing Guard: Deleting protected 'Blank' template...")
        try:
            delete_template_tool("Blank", confirm=True)
            print(" -> FAILED: Guard did not catch deletion of Blank template!")
            sys.exit(1)
        except OvirtValidationError as e:
            print(f" -> PASSED: Correctly rejected Blank template deletion: {e.message}")

        # Step 4: Create a lightweight stopped VM as template source
        print(f"\n[Step 4] Creating stopped test VM '{test_vm_name}'...")
        vm_res = create_vm_tool(
            name=test_vm_name,
            cluster=cluster_name,
            template="Blank",
            memory_mb=1024,
            cpu_cores=1,
            description="Source VM for live template creation test",
            wait=True,
            timeout_seconds=90,
        )
        test_vm_id = vm_res.vm_id
        print(f" -> Source VM created: ID={test_vm_id}, Status={vm_res.status}")

        # Step 5: Create template from stopped VM
        print(f"\n[Step 5] Creating new golden template '{test_tpl_name}' from VM...")
        tpl_res = create_template_from_vm_tool(
            vm_name_or_id=test_vm_name,
            template_name=test_tpl_name,
            description="Automated golden image test created by ovirt-mcp",
            wait=True,
            timeout=180,
        )
        created_tpl_id = tpl_res.template_id
        assert tpl_res.success is True
        print(f" -> Template creation succeeded: ID={created_tpl_id}, message: {tpl_res.message}")

        # Step 6: Verify and deep inspect newly created template
        print(f"\n[Step 6] Inspecting newly created template '{test_tpl_name}'...")
        new_detail = get_template_tool(created_tpl_id)
        assert new_detail.name == test_tpl_name
        assert new_detail.status == "ok"
        print(
            f" -> Verified template: Name={new_detail.name}, RAM={new_detail.memory_mb}MB, "
            f"CPU={new_detail.cpu_cores}c/{new_detail.cpu_sockets}s, Disks={len(new_detail.disks)}"
        )

        # Step 7: Delete the created template (safe-mode confirm=True)
        print(f"\n[Step 7] Deleting template '{test_tpl_name}' (confirm=True)...")
        del_res = delete_template_tool(created_tpl_id, confirm=True, wait=True)
        assert del_res.success is True
        print(f" -> Delete result: {del_res.message}")
        created_tpl_id = None  # Successfully deleted

        # Step 8: Verify template is no longer listed
        print("\n[Step 8] Verifying template removal from inventory...")
        remaining = list_templates_tool(search=f"name={test_tpl_name}")
        assert len(remaining) == 0, f"Template {test_tpl_name} should no longer exist"
        print(" -> Verified: Template completely removed from oVirt inventory.")

        print("\n" + "=" * 70)
        print("ALL TEMPLATE LIFECYCLE OPERATIONS PASSED SUCCESSFULLY ON LIVE OLVM!")
        print("=" * 70)

    finally:
        # Cleanup
        print("\n[Teardown] Cleaning up test resources...")
        if created_tpl_id:
            try:
                delete_template_tool(created_tpl_id, confirm=True, wait=True)
                print(f" -> Teardown: Removed template '{test_tpl_name}'")
            except Exception as e:
                print(f" -> Teardown warning (template): {e}")
        if test_vm_id:
            try:
                delete_vm_tool(test_vm_id, force=True, confirm=True, wait=True)
                print(f" -> Teardown: Removed source VM '{test_vm_name}'")
            except Exception as e:
                print(f" -> Teardown warning (vm): {e}")


if __name__ == "__main__":
    main()
