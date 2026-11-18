#!/usr/bin/env python3
"""Live End-to-End Test for VM vNIC and Network Profile Management."""

import os
import time

from ovirt_mcp.client import get_client
from ovirt_mcp.tools.networks import (
    add_vm_nic_tool,
    list_vm_nics_tool,
    list_vnic_profiles_tool,
    remove_vm_nic_tool,
)
from ovirt_mcp.tools.vms import (
    create_vm_tool,
    delete_vm_tool,
)


def main() -> None:
    print("=" * 70)
    print("oVirt / OLVM MCP Live vNIC & Network Profile Tester")
    print("=" * 70)

    test_vm_name = "mcp-nic-testvm"
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
        # Step 1: List available vNIC profiles
        print("\n[Step 1] Querying available vNIC profiles...")
        profiles = list_vnic_profiles_tool()
        print(f" -> Discovered {len(profiles)} vNIC profile(s):")
        for p in profiles:
            print(f"    - ID: {p.id} | Name: {p.name} | Network: {p.network_name}")
        assert len(profiles) >= 1, "Expected at least 1 vNIC profile"
        chosen_profile = profiles[0].name

        # Step 2: Create disposable test VM with initial nic
        print(f"\n[Step 2] Creating test VM '{test_vm_name}' with profile '{chosen_profile}'...")
        vm_res = create_vm_tool(
            name=test_vm_name,
            cluster=cluster_name,
            template="Blank",
            memory_mb=1024,
            cpu_cores=1,
            disk_size_gb=5,
            storage_domain=storage_domain,
            network_profile=chosen_profile,
            description="Disposable test VM for MCP network testing",
            wait=True,
            timeout_seconds=90,
        )
        print(f" -> Created VM ID: {vm_res.vm_id}")

        # Step 3: List initial vNICs on VM
        print(f"\n[Step 3] Listing initial vNICs for '{test_vm_name}'...")
        initial_nics = list_vm_nics_tool(test_vm_name)
        print(f" -> VM has {len(initial_nics)} vNIC(s):")
        for n in initial_nics:
            print(
                f"    - ID: {n.id} | Name: {n.name} | MAC: {n.mac_address} | Profile: {n.vnic_profile_name}"
            )
        assert len(initial_nics) == 1

        # Step 4: Add secondary vNIC 'nic2'
        print(f"\n[Step 4] Adding secondary vNIC 'nic2' to '{test_vm_name}'...")
        add_res = add_vm_nic_tool(
            name_or_id=test_vm_name,
            name="nic2",
            profile=chosen_profile,
            interface="virtio",
            plugged=True,
            linked=True,
        )
        print(
            f" -> Add result: ID={add_res.nic_id}, MAC={add_res.mac_address}, message: {add_res.message}"
        )
        assert add_res.success is True

        # Step 5: Verify 2 vNICs present
        print("\n[Step 5] Verifying 2 vNICs attached...")
        nics_after = list_vm_nics_tool(test_vm_name)
        assert len(nics_after) == 2, f"Expected 2 vNICs, found {len(nics_after)}"
        matching = [n for n in nics_after if n.name == "nic2"]
        assert len(matching) == 1
        print(f" -> Confirmed 'nic2' present with MAC: {matching[0].mac_address}")

        # Step 6: Remove vNIC 'nic2' (reversibility / symmetry)
        print(f"\n[Step 6] Removing vNIC 'nic2' from '{test_vm_name}' (confirm=True)...")
        remove_res = remove_vm_nic_tool(
            name_or_id=test_vm_name,
            nic_name_or_id="nic2",
            confirm=True,
        )
        print(f" -> Remove result: {remove_res.message}")
        assert remove_res.success is True

        # Step 7: Verify only 1 vNIC remains
        print("\n[Step 7] Verifying 'nic2' was cleanly removed...")
        final_nics = list_vm_nics_tool(test_vm_name)
        assert len(final_nics) == 1
        assert final_nics[0].name != "nic2"
        print(f" -> Confirmed 'nic2' removed. Remaining vNICs: {len(final_nics)}")

        print("\n" + "=" * 70)
        print("ALL vNIC LIFECYCLE & REVERSIBILITY LIVE TESTS PASSED!")
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
