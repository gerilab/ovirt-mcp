#!/usr/bin/env python3
"""Live End-to-End Test for Inventory Tags and Entity Tagging on OLVM."""

import contextlib
import os
import sys
import time

from ovirt_mcp.client import get_client
from ovirt_mcp.client.exceptions import OvirtValidationError
from ovirt_mcp.tools.tags import (
    assign_host_tag_tool,
    assign_vm_tag_tool,
    create_tag_tool,
    delete_tag_tool,
    list_tags_tool,
    unassign_host_tag_tool,
    unassign_vm_tag_tool,
)
from ovirt_mcp.tools.vms import (
    create_vm_tool,
    delete_vm_tool,
)


def main() -> None:
    print("=" * 70)
    print("oVirt / OLVM MCP Live Inventory Tags & Assignment Tester")
    print("=" * 70)

    client = get_client()
    conn = client.get_connection()
    sys_svc = conn.system_service()
    tags_svc = sys_svc.tags_service()
    hosts_svc = sys_svc.hosts_service()

    target_host = os.getenv("OVIRT_TEST_HOST", "olvmhost002.example.com")
    test_vm_name = "mcp-tag-testvm"
    cluster_name = os.getenv("OVIRT_TEST_CLUSTER", "DefaultCluster")
    tag_parent_name = "mcp_live_parent_tag"
    tag_child_name = "mcp_live_child_tag"

    # Pre-cleanup
    for t_name in [tag_child_name, tag_parent_name]:
        try:
            for t in tags_svc.list():
                if str(getattr(t, "name", "")).lower() == t_name.lower():
                    print(f"[Cleanup] Removing leftover tag '{t_name}'...")
                    tags_svc.tag_service(t.id).remove()
                    time.sleep(1)
        except Exception:
            pass

    try:
        existing_vm = client.find_resource_by_id_or_name(sys_svc.vms_service(), test_vm_name, "vm")
        if existing_vm:
            print(f"[Cleanup] Removing leftover VM '{test_vm_name}'...")
            delete_vm_tool(test_vm_name, force=True, confirm=True, wait=True)
            time.sleep(2)
    except Exception:
        pass

    test_vm_id = None
    parent_tag_id = None
    child_tag_id = None

    try:
        # Step 1: List existing tags
        print("\n[Step 1] Listing existing inventory tags...")
        tags = list_tags_tool()
        print(f" -> Found {len(tags)} tag(s):")
        for t in tags:
            print(f"    - Name: {t.name:<15} | ID: {t.id} | Parent: {t.parent_id}")
        root_tag = next((t for t in tags if t.name.lower() == "root"), None)
        assert root_tag is not None, "Root system tag must exist"

        # Step 2: Guard Test: Attempting to delete root tag
        print("\n[Step 2] Testing Guard: Deleting protected root tag...")
        try:
            delete_tag_tool("root", confirm=True)
            print(" -> FAILED: Guard did not catch root tag deletion!")
            sys.exit(1)
        except OvirtValidationError as e:
            print(f" -> PASSED: Correctly rejected root tag deletion: {e.message}")

        # Step 3: Create parent tag
        print(f"\n[Step 3] Creating parent tag '{tag_parent_name}'...")
        p_res = create_tag_tool(tag_parent_name, description="MCP live test parent tag")
        assert p_res.success is True
        parent_tag_id = p_res.tag_id
        print(f" -> Created parent tag ID: {parent_tag_id}")

        # Step 4: Create child nested tag
        print(f"\n[Step 4] Creating nested child tag '{tag_child_name}' under parent...")
        c_res = create_tag_tool(
            tag_child_name,
            description="MCP live test child tag",
            parent=tag_parent_name,
        )
        assert c_res.success is True
        child_tag_id = c_res.tag_id
        print(f" -> Created child tag ID: {child_tag_id}")

        # Step 5: Assign child tag to host
        print(f"\n[Step 5] Assigning tag '{tag_child_name}' to host '{target_host}'...")
        h_assign_res = assign_host_tag_tool(target_host, tag_child_name)
        assert h_assign_res.success is True
        print(f" -> Host assign result: {h_assign_res.message}")

        # Verify host has tag
        h_obj = client.find_resource_by_id_or_name(hosts_svc, target_host, "host")
        h_tags = hosts_svc.host_service(h_obj.id).tags_service().list()
        assert any(str(t.id) == child_tag_id for t in h_tags), "Host must have child tag assigned"
        print(f" -> Verified: Host '{target_host}' has tag '{tag_child_name}'.")

        # Step 6: Unassign child tag from host
        print(f"\n[Step 6] Unassigning tag '{tag_child_name}' from host '{target_host}'...")
        h_unassign_res = unassign_host_tag_tool(target_host, tag_child_name)
        assert h_unassign_res.success is True
        print(f" -> Host unassign result: {h_unassign_res.message}")

        # Verify host tag removed
        h_tags_after = hosts_svc.host_service(h_obj.id).tags_service().list()
        assert not any(str(t.id) == child_tag_id for t in h_tags_after), (
            "Host must not have child tag"
        )
        print(f" -> Verified: Host '{target_host}' no longer has tag '{tag_child_name}'.")

        # Step 7: Create disposable test VM
        print(f"\n[Step 7] Creating test VM '{test_vm_name}'...")
        vm_res = create_vm_tool(
            name=test_vm_name,
            cluster=cluster_name,
            template="Blank",
            memory_mb=1024,
            cpu_cores=1,
            description="Disposable VM for live tag testing",
            wait=True,
            timeout_seconds=90,
        )
        test_vm_id = vm_res.vm_id
        print(f" -> Created test VM ID: {test_vm_id}")

        # Step 8: Assign parent tag to VM
        print(f"\n[Step 8] Assigning parent tag '{tag_parent_name}' to VM '{test_vm_name}'...")
        vm_assign_res = assign_vm_tag_tool(test_vm_name, tag_parent_name)
        assert vm_assign_res.success is True
        print(f" -> VM assign result: {vm_assign_res.message}")

        # Verify VM has tag
        vm_tags = sys_svc.vms_service().vm_service(test_vm_id).tags_service().list()
        assert any(str(t.id) == parent_tag_id for t in vm_tags), "VM must have parent tag assigned"
        print(f" -> Verified: VM '{test_vm_name}' has tag '{tag_parent_name}'.")

        # Step 9: Unassign parent tag from VM
        print(f"\n[Step 9] Unassigning tag '{tag_parent_name}' from VM '{test_vm_name}'...")
        vm_unassign_res = unassign_vm_tag_tool(test_vm_name, tag_parent_name)
        assert vm_unassign_res.success is True
        print(f" -> VM unassign result: {vm_unassign_res.message}")

        # Step 10: Delete both tags
        print("\n[Step 10] Deleting test tags...")
        c_del = delete_tag_tool(tag_child_name, confirm=True)
        assert c_del.success is True
        print(f" -> Deleted child tag: {c_del.message}")
        child_tag_id = None

        p_del = delete_tag_tool(tag_parent_name, confirm=True)
        assert p_del.success is True
        print(f" -> Deleted parent tag: {p_del.message}")
        parent_tag_id = None

        print("\n" + "=" * 70)
        print("ALL INVENTORY TAG OPERATIONS PASSED SUCCESSFULLY ON LIVE OLVM!")
        print("=" * 70)

    finally:
        # Cleanup
        print("\n[Teardown] Cleaning up test resources...")
        if child_tag_id:
            with contextlib.suppress(Exception):
                delete_tag_tool(child_tag_id, confirm=True)
        if parent_tag_id:
            with contextlib.suppress(Exception):
                delete_tag_tool(parent_tag_id, confirm=True)
        if test_vm_id:
            try:
                delete_vm_tool(test_vm_id, force=True, confirm=True, wait=True)
                print(f" -> Teardown: Removed test VM '{test_vm_name}'")
            except Exception as e:
                print(f" -> Teardown warning (vm): {e}")


if __name__ == "__main__":
    main()
