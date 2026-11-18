#!/usr/bin/env python3
"""Live End-to-End Test for VM Compute Resource Reconfiguration and Console Access."""

import os
import time

from ovirt_mcp.client import get_client
from ovirt_mcp.tools.compute import (
    get_vm_console_ticket_tool,
    list_vm_graphics_consoles_tool,
    update_vm_tool,
)
from ovirt_mcp.tools.vms import (
    create_vm_tool,
    delete_vm_tool,
    start_vm_tool,
)


def main() -> None:
    print("=" * 70)
    print("oVirt / OLVM MCP Live Compute & Console Tester")
    print("=" * 70)

    test_vm_name = "mcp-compute-testvm"
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

    try:
        # Step 1: Create disposable test VM with 5GB boot disk
        print(f"\n[Step 1] Creating test VM '{test_vm_name}' (1 vCPU, 1024MB)...")
        create_res = create_vm_tool(
            name=test_vm_name,
            cluster=cluster_name,
            template="Blank",
            memory_mb=1024,
            cpu_cores=1,
            disk_size_gb=5,
            storage_domain=storage_domain,
            description="Disposable test VM for MCP compute testing",
            wait=True,
            timeout_seconds=90,
        )
        print(f" -> Created VM ID: {create_res.vm_id}")

        # Step 2: List graphics consoles
        print(f"\n[Step 2] Listing graphics consoles for '{test_vm_name}'...")
        consoles = list_vm_graphics_consoles_tool(test_vm_name)
        print(f" -> Discovered {len(consoles)} console(s):")
        for c in consoles:
            print(
                f"    - ID: {c.id} | Protocol: {c.protocol} | Port: {c.port} | TLS Port: {c.tls_port}"
            )
        assert len(consoles) >= 1, "Expected at least 1 graphics console"

        # Step 3: Update compute resources (RAM to 2048MB, 2 vCPUs, HA enabled)
        print("\n[Step 3] Updating VM resources: 2048MB RAM, 2 vCPUs, HA=True (confirm=True)...")
        up_res = update_vm_tool(
            name_or_id=test_vm_name,
            memory_mb=2048,
            cpu_cores=2,
            ha_enabled=True,
            description="Updated by MCP compute tester",
            confirm=True,
        )
        print(f" -> Update result: {up_res.message}")
        assert up_res.success is True
        assert up_res.memory_mb == 2048
        assert up_res.cpu_cores == 2
        assert up_res.ha_enabled is True

        # Step 4: Start VM to test live console ticket generation
        print(f"\n[Step 4] Starting VM '{test_vm_name}' (wait=True)...")
        start_res = start_vm_tool(test_vm_name, wait=True, timeout_seconds=90)
        print(f" -> Start result: {start_res.message}")
        assert start_res.current_status == "up"

        # Step 5: Generate console ticket on running VM
        print(f"\n[Step 5] Generating console ticket for running VM '{test_vm_name}'...")
        ticket = get_vm_console_ticket_tool(test_vm_name, expiry_seconds=180)
        print(
            f" -> Ticket generated! Value: {ticket.ticket_value} (Expiry: {ticket.expiry_seconds}s)"
        )
        assert bool(ticket.ticket_value), "Ticket value should not be empty"

        print("\n" + "=" * 70)
        print("ALL COMPUTE & CONSOLE LIVE TESTS PASSED SUCCESSFULLY!")
        print("=" * 70)

    finally:
        # Cleanup
        print(f"\n[Teardown] Cleaning up test VM '{test_vm_name}'...")
        try:
            delete_vm_tool(test_vm_name, force=True, confirm=True, wait=True)
            print(" -> Test VM deleted successfully.")
        except Exception as exc:
            print(f" -> Warning during teardown: {exc}")


if __name__ == "__main__":
    main()
