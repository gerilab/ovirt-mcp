#!/usr/bin/env python3
"""Live End-to-End Test for VM Lifecycle, Creation, vtools Shutdown, and Deletion."""

import os
import sys
import time

from ovirt_mcp.client import get_client
from ovirt_mcp.client.exceptions import NotFoundError, OvirtValidationError
from ovirt_mcp.tools.vms import (
    create_vm_tool,
    delete_vm_tool,
    get_vm_tool,
    reboot_vm_tool,
    start_vm_tool,
    stop_vm_tool,
)


def main() -> None:
    print("=" * 70)
    print("oVirt / OLVM MCP Live Lifecycle & vtools Shutdown Tester")
    print("=" * 70)

    test_vm_name = "mcp-lifecycle-testvm"
    cluster_name = os.getenv("OVIRT_TEST_CLUSTER", "DefaultCluster")
    storage_domain = "Data"

    client = get_client()
    conn = client.get_connection()
    system_service = conn.system_service()

    # Pre-cleanup in case a previous aborted run left the VM
    try:
        existing = client.find_resource_by_id_or_name(
            system_service.vms_service(), test_vm_name, "vm"
        )
        if existing:
            print(f"[Cleanup] Found leftover VM '{test_vm_name}', cleaning up...")
            delete_vm_tool(test_vm_name, force=True, confirm=True, wait=True)
            time.sleep(3)
    except Exception:
        pass

    # ──────────────────────────────────────────────────────────────────────────
    # Step 1: Create VM with Bootable Disk
    # ──────────────────────────────────────────────────────────────────────────
    print(
        f"\n[Step 1] Creating VM '{test_vm_name}' with 5GB bootable COW disk on '{storage_domain}'..."
    )
    create_res = create_vm_tool(
        name=test_vm_name,
        cluster=cluster_name,
        template="Blank",
        memory_mb=1024,
        cpu_cores=1,
        disk_size_gb=5,
        storage_domain=storage_domain,
        description="Disposable live test VM for MCP lifecycle testing",
        wait=True,
        timeout_seconds=90,
    )
    print("  -> VM Created successfully:")
    print(f"     ID:       {create_res.vm_id}")
    print(f"     Name:     {create_res.vm_name}")
    print(f"     Status:   {create_res.status.upper()}")
    print(f"     Cluster:  {create_res.cluster_name}")

    # Verify inventory state
    vm_detail = get_vm_tool(test_vm_name, compact=True)
    print(
        f"     Disks:    {', '.join(vm_detail.disks_summary) if vm_detail.disks_summary else 'None'}"
    )

    # ──────────────────────────────────────────────────────────────────────────
    # Step 2: Start VM
    # ──────────────────────────────────────────────────────────────────────────
    print(f"\n[Step 2] Starting VM '{test_vm_name}' (waiting for UP state)...")
    start_res = start_vm_tool(test_vm_name, wait=True, timeout_seconds=90)
    print("  -> Start Initiated successfully:")
    print(f"     Action:          {start_res.action}")
    print(f"     Previous Status: {start_res.previous_status}")
    print(f"     Current Status:  {start_res.current_status.upper()}")
    print(f"     Message:         {start_res.message}")

    # Verify hypervisor host placement
    vm_running = get_vm_tool(test_vm_name, compact=True)
    print(f"  -> VM is actively running on Host: {vm_running.host_name}")

    # ──────────────────────────────────────────────────────────────────────────
    # Step 3: Test Safe Mode Protection on Stop/Shutdown
    # ──────────────────────────────────────────────────────────────────────────
    print("\n[Step 3] Testing Safe-Mode Guard enforcement...")
    try:
        stop_vm_tool(test_vm_name, graceful=True, confirm=False)
        print("  [FAIL] Safe mode failed to block unconfirmed shutdown!")
        sys.exit(1)
    except OvirtValidationError as exc:
        print(
            f"  [PASS] Safe Mode successfully blocked unconfirmed shutdown:\n         {exc.message}"
        )

    # ──────────────────────────────────────────────────────────────────────────
    # Step 4: Test Graceful Stop (vtools / ACPI signal)
    # ──────────────────────────────────────────────────────────────────────────
    print("\n[Step 4] Testing Graceful Shutdown via vtools / ACPI (graceful=True)...")
    stop_graceful = stop_vm_tool(test_vm_name, graceful=True, confirm=True, wait=False)
    print("  -> Graceful Stop response:")
    print(f"     Action:          {stop_graceful.action}")
    print(f"     Graceful:        {stop_graceful.graceful} (via vtools / guest agent & ACPI)")
    print(f"     Current Status:  {stop_graceful.current_status}")
    print(f"     Message:         {stop_graceful.message}")

    # ──────────────────────────────────────────────────────────────────────────
    # Step 5: Test Hard Power-off (graceful=False)
    # (Blank VM without installed OS doesn't run guest OS systemd, so hard stop is used to power off)
    # ──────────────────────────────────────────────────────────────────────────
    print("\n[Step 5] Testing Hard Power-Off (graceful=False) to power off blank disk...")
    stop_hard = stop_vm_tool(
        test_vm_name, graceful=False, force=True, confirm=True, wait=True, timeout_seconds=45
    )
    print("  -> Hard Stop response:")
    print(f"     Action:          {stop_hard.action}")
    print(f"     Graceful:        {stop_hard.graceful}")
    print(f"     Current Status:  {stop_hard.current_status.upper()}")
    print(f"     Message:         {stop_hard.message}")

    # ──────────────────────────────────────────────────────────────────────────
    # Step 6: Test Reboot Validation on DOWN VM
    # ──────────────────────────────────────────────────────────────────────────
    print("\n[Step 6] Testing Reboot Validation on DOWN VM...")
    try:
        reboot_vm_tool(test_vm_name, confirm=True)
        print("  [FAIL] Reboot allowed on DOWN VM!")
        sys.exit(1)
    except OvirtValidationError as exc:
        print(f"  [PASS] Reboot validation rejected DOWN VM as expected:\n         {exc.message}")

    # ──────────────────────────────────────────────────────────────────────────
    # Step 7: Delete Test VM
    # ──────────────────────────────────────────────────────────────────────────
    print(f"\n[Step 7] Deleting VM '{test_vm_name}' and attached disks...")
    del_res = delete_vm_tool(test_vm_name, confirm=True, wait=True, timeout_seconds=60)
    print("  -> Delete Response:")
    print("     Action:          delete")
    print(f"     Disks Detached:  {del_res.disks_detached_only}")
    print(f"     Message:         {del_res.message}")

    # ──────────────────────────────────────────────────────────────────────────
    # Step 8: Confirm VM is completely removed
    # ──────────────────────────────────────────────────────────────────────────
    print("\n[Step 8] Verifying VM is completely removed from engine...")
    try:
        get_vm_tool(test_vm_name)
        print("  [FAIL] VM still found in inventory!")
        sys.exit(1)
    except NotFoundError:
        print("  [PASS] Confirmed: VM no longer exists in oVirt / OLVM inventory.")

    print("\n" + "=" * 70)
    print("ALL LIVE TESTS PASSED COMPLETELY AND CLEANLY!")
    print("=" * 70)


if __name__ == "__main__":
    main()
