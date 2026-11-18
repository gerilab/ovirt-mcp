#!/usr/bin/env python3
"""Live End-to-End Test for Virtual Disks, Creation, Resize, Detach, and Re-attach on OLVM."""

import os
import time

from ovirt_mcp.client import get_client
from ovirt_mcp.tools.disks import (
    attach_vm_disk_tool,
    create_vm_disk_tool,
    detach_vm_disk_tool,
    list_disks_tool,
    list_vm_disks_tool,
    resize_disk_tool,
)
from ovirt_mcp.tools.vms import (
    create_vm_tool,
    delete_vm_tool,
)


def main() -> None:
    print("=" * 70)
    print("oVirt / OLVM MCP Live Disk Operations & Lifecycle Tester")
    print("=" * 70)

    test_vm_name = "mcp-disk-testvm"
    cluster_name = os.getenv("OVIRT_TEST_CLUSTER", "DefaultCluster")
    storage_domain = "Data"

    client = get_client()
    conn = client.get_connection()
    system_service = conn.system_service()

    # Pre-cleanup in case of leftover from interrupted run
    try:
        existing = client.find_resource_by_id_or_name(
            system_service.vms_service(), test_vm_name, "vm"
        )
        if existing:
            print(f"[Cleanup] Deleting leftover VM '{test_vm_name}'...")
            delete_vm_tool(test_vm_name, force=True, confirm=True, wait=True)
            time.sleep(3)
    except Exception:
        pass

    created_disk_id = None

    try:
        # Step 1: Create disposable test VM with 5GB primary boot disk
        print(f"\n[Step 1] Creating test VM '{test_vm_name}'...")
        vm_res = create_vm_tool(
            name=test_vm_name,
            cluster=cluster_name,
            template="Blank",
            memory_mb=1024,
            cpu_cores=1,
            disk_size_gb=5,
            storage_domain=storage_domain,
            description="Disposable test VM for MCP disk operations",
            wait=True,
            timeout_seconds=90,
        )
        print(f" -> Created VM ID: {vm_res.vm_id}")

        # Step 2: List initial disks on VM
        print(f"\n[Step 2] Listing initial disks for '{test_vm_name}'...")
        initial_disks = list_vm_disks_tool(test_vm_name)
        print(f" -> VM has {len(initial_disks)} disk(s):")
        for d in initial_disks:
            print(
                f"    - ID: {d.disk_id} | Name: {d.disk_name} | Size: {d.provisioned_size_gb}GB | Bootable: {d.bootable}"
            )

        # Step 3: Create and attach secondary 2GB data disk
        print(f"\n[Step 3] Creating and attaching new 2GB disk to '{test_vm_name}'...")
        new_disk_res = create_vm_disk_tool(
            name_or_id=test_vm_name,
            size_gb=2,
            storage_domain=storage_domain,
            disk_name=f"{test_vm_name}_data2gb",
            disk_format="cow",
            interface="virtio",
            wait=True,
            timeout_seconds=120,
        )
        created_disk_id = new_disk_res.disk_id
        print(f" -> Created disk ID: {created_disk_id}, message: {new_disk_res.message}")
        assert created_disk_id is not None

        # Step 4: Verify 2GB disk attached
        print("\n[Step 4] Verifying disk attachment on VM...")
        disks_after = list_vm_disks_tool(test_vm_name)
        matching = [d for d in disks_after if d.disk_id == created_disk_id]
        assert len(matching) == 1, f"Disk {created_disk_id} should be attached to VM"
        print(
            f" -> Verified attached disk: {matching[0].disk_name} ({matching[0].provisioned_size_gb}GB)"
        )

        # Step 5: Expand disk to 3GB
        print("\n[Step 5] Expanding disk from 2GB to 3GB (confirm=True)...")
        resize_res = resize_disk_tool(
            disk_id=created_disk_id,
            size_gb=3,
            confirm=True,
        )
        print(f" -> Resize result: {resize_res.message}")
        assert resize_res.success is True
        assert resize_res.new_size_gb == 3.0

        # Step 6: Detach disk (detach_only=True, reversible!)
        print(f"\n[Step 6] Detaching disk '{created_disk_id}' from VM (confirm=True, wait=True)...")
        detach_res = detach_vm_disk_tool(
            name_or_id=test_vm_name,
            disk_id=created_disk_id,
            confirm=True,
            wait=True,
            timeout_seconds=60,
        )
        print(f" -> Detach result: {detach_res.message}")
        assert detach_res.success is True

        disks_detached = list_vm_disks_tool(test_vm_name)
        remaining = [d for d in disks_detached if d.disk_id == created_disk_id]
        assert len(remaining) == 0, "Detached disk should no longer be attached to VM"
        print(" -> Verified disk is no longer attached to VM.")

        # Step 7: Re-attach disk back (symmetry / reversibility)
        print(f"\n[Step 7] Re-attaching floating disk back to '{test_vm_name}' (virtio_scsi)...")
        reattach_res = attach_vm_disk_tool(
            name_or_id=test_vm_name,
            disk_id=created_disk_id,
            interface="virtio_scsi",
            bootable=False,
            active=True,
        )
        print(f" -> Re-attach result: {reattach_res.message}")
        assert reattach_res.success is True

        disks_reattached = list_vm_disks_tool(test_vm_name)
        reattached = [d for d in disks_reattached if d.disk_id == created_disk_id]
        assert len(reattached) == 1, "Disk should be re-attached"
        print(
            f" -> Confirmed re-attached disk: {reattached[0].disk_name} (interface={reattached[0].interface})"
        )

        # Step 8: Search disk in global inventory
        print("\n[Step 8] Checking disk in global inventory (ovirt_disk_list)...")
        all_disks = list_disks_tool(storage_domain=storage_domain)
        found_in_inv = [d for d in all_disks if d.id == created_disk_id]
        assert len(found_in_inv) == 1
        print(
            f" -> Verified disk in global inventory: {found_in_inv[0].name} ({found_in_inv[0].provisioned_size_gb}GB, status={found_in_inv[0].status})"
        )

        print("\n" + "=" * 70)
        print("ALL DISK LIFECYCLE & REVERSIBILITY LIVE TESTS PASSED!")
        print("=" * 70)

    finally:
        # Cleanup
        print(f"\n[Teardown] Cleaning up test VM '{test_vm_name}' and disks...")
        try:
            delete_vm_tool(test_vm_name, force=True, confirm=True, wait=True)
            print(" -> Test VM deleted successfully.")
        except Exception as exc:
            print(f" -> Warning during VM teardown: {exc}")

        # Also remove the created floating disk if it was left detached
        if created_disk_id:
            try:
                system_service.disks_service().disk_service(created_disk_id).remove()
                print(f" -> Cleaned up disk {created_disk_id}.")
            except Exception:
                pass


if __name__ == "__main__":
    main()
