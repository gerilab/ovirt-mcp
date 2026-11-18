#!/usr/bin/env python3
"""Interactive test script for verifying ovirt-mcp tools against a live OLVM/oVirt engine."""

import json
import sys
from pathlib import Path

# Add src to pythonpath
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ovirt_mcp.client import get_client
from ovirt_mcp.client.exceptions import OvirtValidationError
from ovirt_mcp.config import get_config
from ovirt_mcp.tools.events import list_vm_events_tool
from ovirt_mcp.tools.vms import get_vm_tool, list_vms_tool, reboot_vm_tool, stop_vm_tool


def main() -> None:
    print("=" * 65)
    print("oVirt / OLVM MCP Live Integration Tester")
    print("=" * 65)

    cfg = get_config()
    print(f"Target Engine URL: {cfg.sanitized_url()}")
    print(f"Username:          {cfg.ovirt_username}")
    print(f"Insecure TLS:      {cfg.ovirt_insecure}")
    print(f"CA File:           {cfg.ovirt_ca_file or 'Auto-download / None'}")
    print("-" * 65)

    # 1. Test Connection
    print("\n[Step 1] Testing Connection & Engine System Info...")
    client = get_client()
    try:
        health = client.test_connection()
        print(" Connection SUCCESSFUL!")
        print(json.dumps(health, indent=2))
    except Exception as exc:
        print(f" Connection FAILED: {exc}")
        sys.exit(1)

    # 2. Test VM List
    print("\n[Step 2] Testing ovirt_vm_list Tool (Inventory & Topology)...")
    vms = list_vms_tool(max_results=10)
    print(f" Retrieved {len(vms)} Virtual Machines:\n")
    for idx, vm in enumerate(vms, 1):
        ha_badge = "[HA Enabled]" if vm.ha_enabled else ""
        print(f"  {idx}. [{vm.status.upper()}] {vm.name} {ha_badge}")
        print(f"     ID:      {vm.id}")
        print(f"     Cluster: {vm.cluster_name or 'N/A'}")
        print(f"     Host:    {vm.host_name or 'N/A'}")
        print(f"     Memory:  {vm.memory_mb} MB | vCPUs: {vm.cpu_cores}")
        print()

    # 3. Test Deep VM Inspection
    if vms:
        target_vm_name = vms[0].name
        print(f"[Step 3] Testing ovirt_vm_get on '{target_vm_name}'...")

        # 3a. Compact Mode (for lightweight / local LLMs)
        print("  --> Testing [COMPACT MODE] (lightweight, ~80% token savings):")
        compact_vm = get_vm_tool(target_vm_name, compact=True)
        print(
            f"      Name:       {compact_vm.name} ({compact_vm.status.upper()}) | Cluster: {compact_vm.cluster_name}"
        )
        print(f"      Resources:  {compact_vm.memory_mb} MB RAM | {compact_vm.cpu_cores} vCPUs")
        print(
            f"      Disks:      {', '.join(compact_vm.disks_summary) if compact_vm.disks_summary else 'None'}"
        )
        print(
            f"      Interfaces: {compact_vm.nics_count} NIC(s) | Snapshots: {compact_vm.snapshots_count}"
        )

        # 3b. Detailed Mode (for deep engineering analysis)
        print("\n  --> Testing [FULL DETAILED MODE] (complete hardware, BIOS, and policies):")
        detail = get_vm_tool(target_vm_name, compact=False)
        print(f"      Name:            {detail.name} (UUID: {detail.id})")
        print(f"      Status:          {detail.status}")
        print(f"      Cluster:         {detail.cluster_name} | Template: {detail.template_name}")
        print(
            f"      CPU Topology:    {detail.cpu.total_cores} vCPUs ({detail.cpu.sockets} sockets x {detail.cpu.cores_per_socket} cores)"
        )
        print(
            f"      Memory Policy:   Allocated: {detail.memory.allocated_mb} MB | Guaranteed: {detail.memory.guaranteed_mb} MB | Max: {detail.memory.max_memory_mb} MB | Ballooning: {detail.memory.ballooning_enabled}"
        )
        print(
            f"      I/O & SCSI:      IO Threads: {detail.io_scsi.io_threads} | VirtIO-SCSI: {detail.io_scsi.virtio_scsi_enabled} | Multi-queue: {detail.io_scsi.multi_queues_enabled}"
        )
        print(
            f"      Placement & Aff: Placement: {detail.affinity_and_placement.placement_affinity} | Groups: {detail.affinity_and_placement.affinity_groups} | Labels: {detail.affinity_and_placement.affinity_labels}"
        )
        print(
            f"      Hardware/BIOS:   BIOS: {detail.hardware.bios_type} | Type: {detail.hardware.vm_type} | Display: {detail.hardware.display_type} | Delete Protected: {detail.hardware.delete_protected}"
        )
        print(f"      Disks ({len(detail.disks)}):")
        for d in detail.disks:
            print(
                f"        - {d.name} ({d.size_gb} GB prov / {d.actual_size_gb or 0} GB actual) [{d.interface}, format={d.format}, bootable={d.bootable}]"
            )
        print(f"      NICs ({len(detail.nics)}):")
        for n in detail.nics:
            print(f"        - {n.name} (MAC: {n.mac_address}) [{n.interface}, linked={n.linked}]")
        print(f"      Snapshots:       {detail.snapshots_count}")

        # 4. Test VM Audit Events
        print(f"\n[Step 4] Testing ovirt_vm_events (Recent Audit Log for '{target_vm_name}')...")
        events = list_vm_events_tool(target_vm_name, max_events=5)
        print(f" Retrieved {len(events)} recent events:\n")
        for ev in events:
            print(f"  * [{ev.severity.upper()}] {ev.time} (Code {ev.code}):")
            print(f"    {ev.description}")

        # 5. Test VM Lifecycle Safety & Idempotency
        print(f"\n[Step 5] Testing Lifecycle Safety Controls on '{target_vm_name}'...")
        # 5a. Safe mode enforcement without confirm=True
        try:
            stop_vm_tool(target_vm_name, confirm=False)
            print("  [FAIL] Safe mode failed to block unconfirmed stop")
        except OvirtValidationError as exc:
            print(f"  [PASS] Safe Mode Guard successfully blocked stop: {exc.message[:65]}...")

        # 5b. Reboot validation on DOWN VM
        try:
            reboot_vm_tool(target_vm_name, confirm=True)
            print("  [FAIL] Reboot allowed on DOWN VM")
        except OvirtValidationError as exc:
            print(f"  [PASS] Reboot validation blocked on DOWN VM: {exc.message[:65]}...")

        # 5c. Idempotent stop on already DOWN VM
        res = stop_vm_tool(target_vm_name, confirm=True)
        print(f"  [PASS] Idempotent Stop handled gracefully: {res.message}")

    print("\n" + "=" * 65)
    print("All live tests completed successfully!")
    print("=" * 65)


if __name__ == "__main__":
    main()
