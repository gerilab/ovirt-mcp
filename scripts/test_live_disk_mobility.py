#!/usr/bin/env python3
"""Live End-to-End Test for Disk Mobility (Move, Copy, Sparsify) on OLVM."""

import sys
import time

import ovirtsdk4.types as sdk_types

from ovirt_mcp.client import get_client
from ovirt_mcp.client.exceptions import OvirtValidationError
from ovirt_mcp.tools.disks import (
    copy_disk_tool,
    list_disks_tool,
    move_disk_tool,
    sparsify_disk_tool,
)


def _wait_disk_ok(disks_svc, disk_id: str, timeout: int = 90) -> None:
    start = time.time()
    while time.time() - start < timeout:
        d = disks_svc.disk_service(disk_id).get()
        if str(getattr(d, "status", "")).lower() == "ok":
            return
        time.sleep(2)
    raise RuntimeError(f"Disk {disk_id} did not reach 'ok' status in {timeout}s.")


def main() -> None:
    print("=" * 70)
    print("oVirt / OLVM MCP Live Disk Mobility Tester (Move, Copy, Sparsify)")
    print("=" * 70)

    client = get_client()
    conn = client.get_connection()
    sys_svc = conn.system_service()
    disks_svc = sys_svc.disks_service()
    sds_svc = sys_svc.storage_domains_service()

    # Verify Data and Data3 storage domains exist and are active
    sd_data = client.find_resource_by_id_or_name(sds_svc, "Data", "storage domain")
    sd_data3 = client.find_resource_by_id_or_name(sds_svc, "Data3", "storage domain")
    print(f"[Init] Found active Storage Domains: Data ({sd_data.id}), Data3 ({sd_data3.id})")

    test_disk_alias = "mcp_live_test_mobility_disk"
    cloned_disk_alias = "mcp_live_test_cloned_disk"
    raw_disk_alias = "mcp_live_test_raw_sparsify_disk"

    # Pre-cleanup in case of leftover from previous runs
    for alias in (test_disk_alias, cloned_disk_alias, raw_disk_alias):
        try:
            existing = client.find_resource_by_id_or_name(disks_svc, alias, "disk")
            if existing:
                print(f"[Cleanup] Removing leftover disk '{alias}' ({existing.id})...")
                disks_svc.disk_service(existing.id).remove()
                time.sleep(3)
        except Exception:
            pass

    test_disk_id = None
    cloned_disk_id = None
    raw_disk_id = None

    try:
        # Step 1: Create a 1GB floating thin COW disk on 'Data'
        print(f"\n[Step 1] Creating floating 1GB COW disk '{test_disk_alias}' on 'Data'...")
        new_disk = disks_svc.add(
            sdk_types.Disk(
                alias=test_disk_alias,
                description="Live mobility test disk for MCP",
                format=sdk_types.DiskFormat.COW,
                provisioned_size=1 * (1024**3),
                storage_domains=[sdk_types.StorageDomain(id=sd_data.id)],
            )
        )
        test_disk_id = str(new_disk.id)
        print(f" -> Created disk ID: {test_disk_id}")
        _wait_disk_ok(disks_svc, test_disk_id)
        print(f" -> Disk '{test_disk_alias}' is OK and ready.")

        # Step 2: Guard Test: Move disk to current domain ('Data') should raise OvirtValidationError
        print("\n[Step 2] Testing Guard: Moving disk to same domain ('Data')...")
        try:
            move_disk_tool(test_disk_id, "Data", wait=False)
            print(" -> FAILED: Guard did not catch same-domain move!")
            sys.exit(1)
        except OvirtValidationError as e:
            print(f" -> PASSED: Correctly rejected same-domain move: {e.message}")

        # Step 3: Move disk from 'Data' to 'Data3' (Storage vMotion)
        print("\n[Step 3] Moving disk from 'Data' to 'Data3' (Storage vMotion)...")
        move_res = move_disk_tool(test_disk_id, "Data3", wait=True, timeout=180)
        assert move_res.success is True
        print(f" -> Move result: {move_res.message}")

        # Verify disk is now on Data3
        d_moved = disks_svc.disk_service(test_disk_id).get()
        cur_sd_ids = [str(sd.id) for sd in getattr(d_moved, "storage_domains", [])]
        assert str(sd_data3.id) in cur_sd_ids, (
            f"Disk should now be on Data3 ({sd_data3.id}), got {cur_sd_ids}"
        )
        print(" -> Verified: Disk is now on Data3.")

        # Step 4: Clone / Copy disk to 'Data' with new alias
        print(f"\n[Step 4] Copying disk from 'Data3' to 'Data' as '{cloned_disk_alias}'...")
        copy_res = copy_disk_tool(
            test_disk_id,
            "Data",
            new_alias=cloned_disk_alias,
            wait=True,
            timeout=180,
        )
        assert copy_res.success is True
        print(f" -> Copy result: {copy_res.message}")

        # Locate copied disk
        cloned_disk = client.find_resource_by_id_or_name(disks_svc, cloned_disk_alias, "disk")
        cloned_disk_id = str(cloned_disk.id)
        print(f" -> Verified cloned disk ID: {cloned_disk_id}")

        # Step 5: Guard Test: Sparsifying a COW disk must be rejected by pre-flight guard
        print("\n[Step 5] Testing Guard: Sparsify on COW formatted disk...")
        try:
            sparsify_disk_tool(test_disk_id, wait=False)
            print(" -> FAILED: Guard did not catch COW format sparsify!")
            sys.exit(1)
        except OvirtValidationError as e:
            print(f" -> PASSED: Correctly rejected COW sparsify: {e.message}")

        # Step 6: Create a 1GB RAW disk on Data for sparsification test
        print(
            f"\n[Step 6] Creating 1GB RAW disk '{raw_disk_alias}' on 'Data' for sparsification..."
        )
        raw_disk = disks_svc.add(
            sdk_types.Disk(
                alias=raw_disk_alias,
                description="Live raw disk for MCP sparsify test",
                format=sdk_types.DiskFormat.RAW,
                provisioned_size=1 * (1024**3),
                storage_domains=[sdk_types.StorageDomain(id=sd_data.id)],
            )
        )
        raw_disk_id = str(raw_disk.id)
        print(f" -> Created RAW disk ID: {raw_disk_id}")
        _wait_disk_ok(disks_svc, raw_disk_id)
        print(f" -> RAW disk '{raw_disk_alias}' is OK and ready.")

        # Step 7: Sparsify the RAW disk
        print(f"\n[Step 7] Sparsifying RAW disk '{raw_disk_alias}' on 'Data'...")
        sparsify_res = sparsify_disk_tool(raw_disk_id, wait=True, timeout=180)
        assert sparsify_res.success is True
        print(f" -> Sparsify result: {sparsify_res.message}")

        # Step 8: Verify via list_disks_tool
        print("\n[Step 8] Listing disks with storage domain filter 'Data3'...")
        disks_on_data3 = list_disks_tool(storage_domain="Data3")
        found = any(d.id == test_disk_id for d in disks_on_data3)
        assert found, f"Disk {test_disk_id} must appear in Data3 disk listing"
        print(" -> Verified: Disk found in list_disks_tool(storage_domain='Data3').")

        print("\n" + "=" * 70)
        print("ALL DISK MOBILITY OPERATIONS PASSED SUCCESSFULLY ON LIVE OLVM!")
        print("=" * 70)

    finally:
        # Cleanup
        print("\n[Teardown] Cleaning up test disks...")
        for did, name in [
            (cloned_disk_id, cloned_disk_alias),
            (test_disk_id, test_disk_alias),
            (raw_disk_id, raw_disk_alias),
        ]:
            if did:
                try:
                    for _ in range(15):
                        d = disks_svc.disk_service(did).get()
                        if str(getattr(d, "status", "")).lower() == "ok":
                            break
                        time.sleep(2)
                    disks_svc.disk_service(did).remove()
                    print(f" -> Removed disk '{name}' ({did})")
                except Exception as err:
                    print(f" -> Warning: Cleanup of disk '{name}' failed: {err}")


if __name__ == "__main__":
    main()
