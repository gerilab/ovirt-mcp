#!/usr/bin/env python3
"""Live End-to-End Test for VM Snapshot Management on OLVM."""

import os
import time

from ovirt_mcp.client import get_client
from ovirt_mcp.client.exceptions import OvirtValidationError
from ovirt_mcp.tools.vms import (
    commit_vm_snapshot_tool,
    create_vm_snapshot_tool,
    create_vm_tool,
    delete_vm_snapshot_tool,
    delete_vm_tool,
    list_vm_snapshots_tool,
    preview_vm_snapshot_tool,
    restore_vm_snapshot_tool,
    undo_vm_snapshot_tool,
)


def main() -> None:
    print("=" * 70)
    print("oVirt / OLVM MCP Live Snapshot Lifecycle & Advanced Preview Tester")
    print("=" * 70)

    test_vm_name = "mcp-snap-testvm"
    cluster_name = os.getenv("OVIRT_TEST_CLUSTER", "DefaultCluster")
    storage_domain = "Data"

    client = get_client()
    conn = client.get_connection()
    system_service = conn.system_service()

    # Pre-cleanup in case a previous run left the VM
    try:
        existing = client.find_resource_by_id_or_name(
            system_service.vms_service(), test_vm_name, "vm"
        )
        if existing:
            print(f"[Cleanup] Found leftover VM '{test_vm_name}', deleting...")
            delete_vm_tool(test_vm_name, force=True, confirm=True, wait=True)
            time.sleep(3)
    except Exception:
        pass

    try:
        # Step 1: Create disposable test VM with 5GB disk
        print(f"\n[Step 1] Creating test VM '{test_vm_name}'...")
        create_res = create_vm_tool(
            name=test_vm_name,
            cluster=cluster_name,
            template="Blank",
            memory_mb=1024,
            cpu_cores=1,
            disk_size_gb=5,
            storage_domain=storage_domain,
            description="Disposable test VM for MCP snapshot lifecycle validation",
            wait=True,
            timeout_seconds=90,
        )
        print(f" -> Created VM ID: {create_res.vm_id}")

        # Step 2: List initial snapshots
        print(f"\n[Step 2] Listing initial snapshots for '{test_vm_name}'...")
        snaps = list_vm_snapshots_tool(test_vm_name)
        print(f" -> Found {len(snaps)} snapshots (includes 'Active VM' container):")
        for s in snaps:
            print(
                f"    - ID: {s.id} | Desc: {s.description} | Status: {s.snapshot_status} | Type: {s.snapshot_type}"
            )

        # Step 3: Create a point-in-time snapshot
        snapshot_desc = "MCP-Test-Snapshot-Point1"
        print(f"\n[Step 3] Creating snapshot '{snapshot_desc}' (wait=True)...")
        snap_res = create_vm_snapshot_tool(
            name_or_id=test_vm_name,
            description=snapshot_desc,
            persist_memory=False,
            wait=True,
            timeout_seconds=180,
        )
        created_snap_id = snap_res.snapshot_id
        print(f" -> Snapshot created: ID={created_snap_id}, message: {snap_res.message}")
        assert created_snap_id is not None, "Snapshot ID should not be None"

        # Step 4: Verify snapshot in list
        print("\n[Step 4] Verifying snapshot exists in list...")
        snaps_after = list_vm_snapshots_tool(test_vm_name)
        regular_snaps = [s for s in snaps_after if s.id == created_snap_id]
        assert len(regular_snaps) == 1, f"Expected snapshot {created_snap_id} to be present"
        target_snap = regular_snaps[0]
        print(
            f" -> Verified snapshot: {target_snap.description} (status: {target_snap.snapshot_status})"
        )
        assert target_snap.snapshot_status == "ok", (
            f"Expected ok status, got {target_snap.snapshot_status}"
        )

        # Step 5: Test pre-flight guard rejection (restore_memory=True on disk-only snapshot)
        print("\n[Step 5] Testing pre-flight memory guard rejection...")
        try:
            restore_vm_snapshot_tool(
                name_or_id=test_vm_name,
                snapshot_id=created_snap_id,
                restore_memory=True,
                confirm=True,
            )
            raise AssertionError(
                "Should have raised OvirtValidationError for snapshot without RAM!"
            )
        except OvirtValidationError as guard_err:
            print(f" -> Guard correctly blocked invalid memory restore: {guard_err.message}")

        # Step 6: Test Snapshot Preview Workflow (Enterprise preview -> undo -> commit)
        print(f"\n[Step 6] Testing Snapshot Preview on '{created_snap_id}' (wait=True)...")
        prev_res = preview_vm_snapshot_tool(
            name_or_id=test_vm_name,
            snapshot_id=created_snap_id,
            restore_memory=False,
            confirm=True,
            wait=True,
            timeout_seconds=180,
        )
        print(f" -> Preview result: {prev_res.message}")
        assert prev_res.success is True

        # Verify snapshot is in_preview
        preview_snaps = list_vm_snapshots_tool(test_vm_name)
        in_preview_list = [s for s in preview_snaps if s.snapshot_status == "in_preview"]
        print(f" -> Snapshots in preview: {len(in_preview_list)}")
        assert len(in_preview_list) == 1, "Expected 1 snapshot to be in_preview"

        # Step 7: Test Undo Snapshot (Reversibility!)
        print("\n[Step 7] Testing Preview Undo (Reversibility, wait=True)...")
        undo_res = undo_vm_snapshot_tool(
            name_or_id=test_vm_name,
            confirm=True,
            wait=True,
            timeout_seconds=180,
        )
        print(f" -> Undo result: {undo_res.message}")
        assert undo_res.success is True

        # Verify no longer in preview
        post_undo_snaps = list_vm_snapshots_tool(test_vm_name)
        in_preview_post_undo = [s for s in post_undo_snaps if s.snapshot_status == "in_preview"]
        assert len(in_preview_post_undo) == 0, "Expected no snapshots in preview after undo"
        print(" -> Confirmed preview successfully undone.")

        # Step 8: Preview again and Commit
        print(f"\n[Step 8] Re-previewing snapshot '{created_snap_id}' for commit...")
        preview_vm_snapshot_tool(
            name_or_id=test_vm_name,
            snapshot_id=created_snap_id,
            restore_memory=False,
            confirm=True,
            wait=True,
            timeout_seconds=180,
        )
        print(" -> Committing snapshot preview...")
        commit_res = commit_vm_snapshot_tool(
            name_or_id=test_vm_name,
            confirm=True,
            wait=True,
            timeout_seconds=180,
        )
        print(f" -> Commit result: {commit_res.message}")
        assert commit_res.success is True

        # Step 9: Restore snapshot (Standard cold restore)
        print(f"\n[Step 9] Restoring snapshot '{created_snap_id}' (confirm=True, wait=True)...")
        restore_res = restore_vm_snapshot_tool(
            name_or_id=test_vm_name,
            snapshot_id=created_snap_id,
            confirm=True,
            wait=True,
            timeout_seconds=120,
        )
        print(f" -> Restore result: {restore_res.message}")
        assert restore_res.success is True

        # Step 10: Delete snapshot (reversibility / consolidation)
        print(f"\n[Step 10] Deleting snapshot '{created_snap_id}' (confirm=True, wait=True)...")
        del_res = delete_vm_snapshot_tool(
            name_or_id=test_vm_name,
            snapshot_id=created_snap_id,
            confirm=True,
            wait=True,
            timeout_seconds=180,
        )
        print(f" -> Delete result: {del_res.message}")
        assert del_res.success is True

        # Step 11: Verify snapshot removed
        print(f"\n[Step 11] Verifying snapshot '{created_snap_id}' is no longer present...")
        final_snaps = list_vm_snapshots_tool(test_vm_name)
        remaining = [s for s in final_snaps if s.id == created_snap_id]
        assert len(remaining) == 0, f"Expected snapshot {created_snap_id} to be deleted!"
        print(f" -> Confirmed snapshot deleted. Remaining snapshots: {len(final_snaps)}")

        print("\n" + "=" * 70)
        print("ALL ADVANCED SNAPSHOT LIFECYCLE LIVE TESTS PASSED SUCCESSFULLY!")
        print("=" * 70)

    finally:
        # Cleanup test VM
        print(f"\n[Teardown] Cleaning up test VM '{test_vm_name}'...")
        try:
            delete_vm_tool(test_vm_name, force=True, confirm=True, wait=True)
            print(" -> Test VM deleted successfully.")
        except Exception as exc:
            print(f" -> Warning during teardown: {exc}")


if __name__ == "__main__":
    main()
