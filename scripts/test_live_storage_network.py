#!/usr/bin/env python3
"""Live End-to-End Verification for Host Network, iSCSI Discovery, and Storage Domains on OLVM."""

import os

from ovirt_mcp.client.exceptions import OvirtValidationError
from ovirt_mcp.tools.hosts_network import (
    ovirt_host_iscsi_discover,
    ovirt_host_iscsi_login,
    ovirt_host_network_attachment_list,
    ovirt_host_network_sync,
)
from ovirt_mcp.tools.storage import (
    ovirt_storage_domain_delete,
    ovirt_storage_domain_get,
    ovirt_storage_domain_list,
)


def main() -> None:
    print("=" * 75)
    print("oVirt / OLVM MCP Live Host Network, iSCSI & Storage Domains E2E Tester")
    print("=" * 75)

    test_host = os.getenv("OVIRT_TEST_HOST", "olvmhost002.example.com")
    test_portal = os.getenv("OVIRT_TEST_ISCSI_PORTAL", "192.0.2.10")
    test_target_iqn = os.getenv("OVIRT_TEST_TARGET_IQN", "iqn.2024-01.org.example:storage.target01")

    # ── Step 1: List logical network attachments on host ────────────────────────
    print(
        f"\n[Step 1] Listing network attachments on host '{test_host}' (ovirt_host_network_attachment_list)..."
    )
    attachments = ovirt_host_network_attachment_list(host_name_or_id=test_host)
    print(f" -> Found {len(attachments)} network attachment(s) on host:")
    for att in attachments:
        print(
            f"    * Network: {att.network_name} ({att.network_id[:8]}...) -> NIC: {att.host_nic_name} "
            f"| Proto: {att.boot_protocol} | IP: {att.ip_address} | In-Sync: {att.in_sync}"
        )
    assert len(attachments) >= 1, "Expected at least 1 network attachment (ovirtmgmt) on host"
    ovirtmgmt_att = next((a for a in attachments if a.network_name == "ovirtmgmt"), None)
    assert ovirtmgmt_att is not None, "ovirtmgmt network attachment not found on host"
    assert ovirtmgmt_att.in_sync is True, "ovirtmgmt should be in-sync"

    # ── Step 2: Check network synchronization ───────────────────────────────────
    print("\n[Step 2] Testing host network sync (ovirt_host_network_sync)...")
    sync_res = ovirt_host_network_sync(host_name_or_id=test_host)
    print(f" -> Sync Result: {sync_res.message}")
    assert sync_res.success is True

    # ── Step 3: Discover iSCSI targets from hypervisor host ──────────────────────
    print(
        f"\n[Step 3] Discovering iSCSI targets from '{test_host}' on '{test_portal}:3260' (ovirt_host_iscsi_discover)..."
    )
    disc_res = ovirt_host_iscsi_discover(
        host_name_or_id=test_host,
        address=test_portal,
        port=3260,
    )
    print(f" -> Discovered {disc_res.count} targets on portal {disc_res.address}:{disc_res.port}:")
    for t in disc_res.targets:
        print(f"    * {t}")
    assert disc_res.count >= 1, "Expected at least 1 iSCSI target on portal"
    assert test_target_iqn in disc_res.targets, f"Expected {test_target_iqn} in discovered targets"

    # ── Step 4: Login to iSCSI target from hypervisor host ───────────────────────
    print(
        f"\n[Step 4] Logging in to iSCSI target '{test_target_iqn}' from '{test_host}' (ovirt_host_iscsi_login)..."
    )
    login_res = ovirt_host_iscsi_login(
        host_name_or_id=test_host,
        address=test_portal,
        target=test_target_iqn,
        port=3260,
    )
    print(f" -> Login Result: {login_res.message}")
    assert login_res.success is True

    # ── Step 5: List all storage domains ─────────────────────────────────────────
    print("\n[Step 5] Listing all Storage Domains (ovirt_storage_domain_list)...")
    sds = ovirt_storage_domain_list()
    print(f" -> Discovered {len(sds)} storage domain(s):")
    for sd in sds:
        print(
            f"    * {sd.name} [{sd.type}/{sd.storage_type}] | Status: {sd.status} | "
            f"Avail: {sd.available_gb} GB / Total: {sd.total_gb} GB ({sd.usage_percent}%) | "
            f"DCs: {sd.data_centers} | Format: {sd.storage_format}"
        )
    assert len(sds) >= 3, "Expected at least 3 storage domains in lab"
    data_domain = next((s for s in sds if s.name == "Data"), None)
    assert data_domain is not None, "Storage domain 'Data' not found"
    assert data_domain.storage_type == "nfs"
    assert len(data_domain.data_centers) > 0, "Expected data domain to be attached to a data center"

    # ── Step 6: Deep inspection of storage domain ────────────────────────────────
    print("\n[Step 6] Deep inspection of Storage Domain 'Data' (ovirt_storage_domain_get)...")
    detail = ovirt_storage_domain_get(name_or_id="Data")
    print(f" -> Domain: {detail.name} (UUID: {detail.id})")
    print(f"    Type: {detail.type} | Protocol: {detail.storage_type} | Status: {detail.status}")
    print(f"    Backend: {detail.address}:{detail.path}")
    print(
        f"    Capacity: {detail.available_gb} GB free / {detail.total_gb} GB total ({detail.usage_percent}% used)"
    )
    print(
        f"    Virtual Disks: {detail.disks_count} | Templates: {detail.templates_count} | VMs: {detail.vms_count}"
    )
    print(
        f"    Thresholds: Warning={detail.warning_low_space_indicator}%, CriticalBlocker={detail.critical_space_action_blocker} GB"
    )
    assert detail.disks_count > 0, "Expected at least 1 virtual disk in Data domain"

    # ── Step 7: Safety Guard Test: Deleting an attached domain must be BLOCKED ──
    print(
        "\n[Step 7] Testing pre-flight delete guard on attached domain 'Data' (ovirt_storage_domain_delete)..."
    )
    try:
        ovirt_storage_domain_delete(name_or_id="Data", confirm=True)
        raise AssertionError(
            "Expected OvirtValidationError was not raised for attached storage domain!"
        )
    except OvirtValidationError as e:
        print(
            f" -> [GUARD WORKING] Successfully blocked deletion of attached storage domain:\n    {e}"
        )

    print("\n" + "=" * 75)
    print("ALL LIVE HOST NETWORK, iSCSI & STORAGE DOMAINS TESTS PASSED ON OLVM!")
    print("=" * 75)


if __name__ == "__main__":
    main()
