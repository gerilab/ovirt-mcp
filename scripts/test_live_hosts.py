#!/usr/bin/env python3
"""Live End-to-End Test for Hypervisor Host Management & Safety Guards on OLVM."""

import os

from ovirt_mcp.client.exceptions import OvirtValidationError
from ovirt_mcp.tools.hosts import (
    activate_host_tool,
    get_host_stats_tool,
    get_host_tool,
    list_host_devices_tool,
    list_host_events_tool,
    list_host_nics_tool,
    list_host_numa_tool,
    list_hosts_tool,
    maintenance_host_tool,
    restart_host_tool,
)


def main() -> None:
    print("=" * 75)
    print("oVirt / OLVM MCP Live Hypervisor Host Management & Safety Guards Tester")
    print("=" * 75)

    test_target_host = os.getenv("OVIRT_TEST_HOST", "olvmhost002.example.com")

    # ── Step 1: List all hosts ──────────────────────────────────────────────────
    print("\n[Step 1] Listing all hypervisor hosts (ovirt_host_list)...")
    hosts = list_hosts_tool()
    print(f" -> Discovered {len(hosts)} hypervisor hosts:")
    for h in hosts:
        print(
            f"    * {h.name} [{h.status}] | Cluster: {h.cluster_name} | IP: {h.address} | "
            f"RAM: {h.total_memory_gb}GB | SPM: {h.spm_status} | Nested: {h.is_nested} | CPU: {h.cpu_model}"
        )
    assert len(hosts) >= 2, "Expected at least 2 hosts in test cluster"

    # Verify nested virtualization detection
    target_summary = next((h for h in hosts if h.name == test_target_host), None)
    assert target_summary is not None, f"Target host {test_target_host} not found"
    assert target_summary.is_nested is True, (
        f"Expected nested=True for {test_target_host} on VMware nested hypervisor"
    )

    # ── Step 2: Get detailed host hardware and OS profile ───────────────────────
    print(f"\n[Step 2] Retrieving deep host profile for '{test_target_host}' (ovirt_host_get)...")
    detail = get_host_tool(test_target_host)
    print(f" -> Host Name: {detail.name} (UUID: {detail.id})")
    print(f"    Hardware: {detail.hardware.manufacturer} | Model: {detail.hardware.product_name}")
    print(
        f"    CPU Topology: {detail.cpu_sockets} sockets x {detail.cpu_cores} cores x {detail.cpu_threads} threads"
    )
    print(
        f"    RAM: {detail.total_memory_gb} GB total, {detail.max_scheduling_memory_gb} GB scheduling"
    )
    print(
        f"    OS & Stack: {detail.os.os_type} {detail.os.os_version} | Kernel: {detail.os.kernel_version}"
    )
    print(
        f"    KVM: {detail.os.kvm_version} | Libvirt: {detail.os.libvirt_version} | VDSM: {detail.os.vdsm_version}"
    )
    print(f"    Power Management Enabled: {detail.power_management.enabled}")
    print(f"    Physical NICs: {detail.nics_count} | NUMA Nodes: {detail.numa_nodes_count}")
    assert detail.hardware.manufacturer == "VMware, Inc."
    assert detail.power_management.enabled is False

    # ── Step 3: Retrieve real-time telemetry statistics ────────────────────────
    print(
        f"\n[Step 3] Retrieving real-time telemetry for '{test_target_host}' (ovirt_host_stats)..."
    )
    stats = get_host_stats_tool(test_target_host)
    print(
        f" -> CPU Usage: {stats.cpu_usage_percent}% (user: {stats.cpu_user_percent}%, sys: {stats.cpu_system_percent}%, idle: {stats.cpu_idle_percent}%)"
    )
    print(f"    Load Avg (5m): {stats.cpu_load_avg_5m}")
    print(
        f"    RAM: {stats.memory_used_gb} GB used / {stats.memory_total_gb} GB total ({stats.memory_used_percent}%)"
    )
    print(f"    Active VMs Hosted: {stats.active_vms_count}")
    print(f"    Boot Time: {stats.boot_time}")
    assert stats.memory_total_gb > 0

    # ── Step 4: List physical network interfaces (pNICs) ───────────────────────
    print(
        f"\n[Step 4] Listing physical network interfaces for '{test_target_host}' (ovirt_host_nic_list)..."
    )
    nics = list_host_nics_tool(test_target_host)
    print(f" -> Found {len(nics)} physical network interfaces:")
    for nic in nics:
        print(
            f"    * {nic.name}: MAC={nic.mac_address}, Speed={nic.speed_mbps} Mbps, Status={nic.status}"
        )
    assert len(nics) >= 1

    # ── Step 5: List NUMA node topology ────────────────────────────────────────
    print(f"\n[Step 5] Listing NUMA topology for '{test_target_host}' (ovirt_host_numa_list)...")
    numa = list_host_numa_tool(test_target_host)
    print(f" -> Found {len(numa)} NUMA nodes:")
    for node in numa:
        print(f"    * Node {node.index}: Memory={node.memory_mb} MB, Cores={node.cpu_cores}")
    assert len(numa) >= 1

    # ── Step 6: List hardware / PCI bus devices ────────────────────────────────
    print(
        f"\n[Step 6] Listing hardware devices for '{test_target_host}' (ovirt_host_device_list)..."
    )
    devices = list_host_devices_tool(test_target_host, max_devices=5)
    print(f" -> Sampled {len(devices)} hardware devices:")
    for dev in devices:
        print(f"    * {dev.name}: Product={dev.product}, Vendor={dev.vendor}, Driver={dev.driver}")
    assert len(devices) >= 1

    # ── Step 7: List host audit events ─────────────────────────────────────────
    print(
        f"\n[Step 7] Listing recent operational events for '{test_target_host}' (ovirt_host_events)..."
    )
    events = list_host_events_tool(test_target_host, max_events=5)
    print(f" -> Found {len(events)} events:")
    for ev in events:
        print(f"    * [{ev.timestamp}] ({ev.severity}) Code {ev.code}: {ev.description[:75]}...")

    # ── Step 8: Enterprise Safety Guard - Restart while active ('up') blocked ───
    print(
        "\n[Step 8] Testing Enterprise Safety Guard: Rebooting an active ('up') host must be REJECTED..."
    )
    try:
        restart_host_tool(test_target_host, confirm=True)
        raise AssertionError("Expected OvirtValidationError when rebooting an active ('up') host!")
    except OvirtValidationError as guard_err:
        print(
            f" -> Safety Guard 1 correctly blocked restart of active host:\n    {guard_err.message}"
        )
        assert "currently active ('up')" in guard_err.message

    # ── Step 9: Maintenance Transition (Safe live migration) ───────────────────
    print(
        f"\n[Step 9] Transitioning '{test_target_host}' to MAINTENANCE mode (confirm=True, wait=True)..."
    )
    maint_res = maintenance_host_tool(
        test_target_host, confirm=True, wait=True, timeout_seconds=180
    )
    print(f" -> Maintenance outcome: {maint_res.message} (status: {maint_res.current_status})")
    assert maint_res.success is True
    assert maint_res.current_status == "maintenance"

    # Verify status on host
    h_maint = get_host_tool(test_target_host)
    assert h_maint.status == "maintenance", f"Expected maintenance, got {h_maint.status}"

    # ── Step 10: Enterprise Safety Guard - Power Management check while in maintenance ─
    print("\n[Step 10] Testing Enterprise Safety Guard 3: Power Management (Fencing) Check...")
    try:
        restart_host_tool(test_target_host, confirm=True)
        raise AssertionError("Expected OvirtValidationError for unconfigured power management!")
    except OvirtValidationError as pm_err:
        print(
            f" -> Safety Guard 3 correctly diagnosed missing power management in nested virtualization:\n    {pm_err.message}"
        )
        assert "Power management (fencing / IPMI) is not enabled" in pm_err.message
        assert "nested virtualized: True" in pm_err.message

    # ── Step 11: Reversibility Principle - Activate host back to 'up' ──────────
    print(
        f"\n[Step 11] Activating '{test_target_host}' back to UP mode (Reversibility, wait=True)..."
    )
    act_res = activate_host_tool(test_target_host, wait=True, timeout_seconds=180)
    print(f" -> Activation outcome: {act_res.message} (status: {act_res.current_status})")
    assert act_res.success is True
    assert act_res.current_status == "up"

    # Verify host status is up
    h_final = get_host_tool(test_target_host)
    assert h_final.status == "up", f"Expected up, got {h_final.status}"
    print(f" -> Confirmed '{test_target_host}' is fully active ('up') in cluster.")

    print("\n" + "=" * 75)
    print("ALL HYPERVISOR HOST MANAGEMENT & ENTERPRISE SAFETY TESTS PASSED!")
    print("=" * 75)


if __name__ == "__main__":
    main()
