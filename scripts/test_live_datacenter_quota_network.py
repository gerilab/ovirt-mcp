#!/usr/bin/env python3
"""Live End-to-End Test for Data Centers, Quotas, and Logical Networks on OLVM."""

import os
import sys
import time

from ovirt_mcp.client import get_client
from ovirt_mcp.client.exceptions import OvirtValidationError
from ovirt_mcp.tools.datacenters import (
    get_datacenter_tool,
    list_datacenters_tool,
)
from ovirt_mcp.tools.logical_networks import (
    create_logical_network_tool,
    delete_logical_network_tool,
    list_logical_networks_tool,
)
from ovirt_mcp.tools.quotas import (
    create_quota_tool,
    delete_quota_tool,
    get_quota_tool,
    list_quotas_tool,
)


def main() -> None:
    print("=" * 70)
    print("oVirt / OLVM MCP Live Data Centers, Quotas & Networks Tester")
    print("=" * 70)

    client = get_client()
    conn = client.get_connection()
    sys_svc = conn.system_service()
    dcs_svc = sys_svc.data_centers_service()
    nets_svc = sys_svc.networks_service()

    dc_name = os.getenv("OVIRT_TEST_DC", "DefaultDC")
    test_quota_name = "mcp_live_test_quota"
    test_net_name = "mcp_live_test_vlan888"

    # Pre-cleanup
    try:
        dc_obj = client.find_resource_by_id_or_name(dcs_svc, dc_name, "data center")
        dc_svc = dcs_svc.data_center_service(dc_obj.id)
        for q in dc_svc.quotas_service().list():
            if str(getattr(q, "name", "")).lower() == test_quota_name.lower():
                print(f"[Cleanup] Removing leftover quota '{test_quota_name}'...")
                dc_svc.quotas_service().quota_service(q.id).remove()
                time.sleep(2)
    except Exception:
        pass

    try:
        for net in nets_svc.list():
            if str(getattr(net, "name", "")).lower() == test_net_name.lower():
                print(f"[Cleanup] Removing leftover network '{test_net_name}'...")
                nets_svc.network_service(net.id).remove()
                time.sleep(2)
    except Exception:
        pass

    try:
        # =========================================================================
        # 1. DATA CENTER INSPECTION
        # =========================================================================
        print("\n[Step 1] Listing Data Centers...")
        dcs = list_datacenters_tool()
        print(f" -> Found {len(dcs)} Data Center(s):")
        for dc in dcs:
            print(
                f"    - Name: {dc.name:<18} | ID: {dc.id} | Status: {dc.status} | Storage: {dc.storage_type} | Quota Mode: {dc.quota_mode}"
            )
        assert any(dc.name == dc_name for dc in dcs), f"Data Center '{dc_name}' must exist"

        print(f"\n[Step 2] Deep inspection of Data Center '{dc_name}'...")
        dc_detail = get_datacenter_tool(dc_name)
        print(f" -> Clusters: {dc_detail.clusters}")
        print(f" -> Storage Domains: {dc_detail.storage_domains}")
        print(f" -> Networks: {dc_detail.networks}")
        assert len(dc_detail.clusters) > 0, "Expected at least one cluster in data center"
        assert "Data" in dc_detail.storage_domains
        assert "ovirtmgmt" in dc_detail.networks

        # =========================================================================
        # 2. QUOTA LIFECYCLE & GUARDS
        # =========================================================================
        print(f"\n[Step 3] Listing Quotas in '{dc_name}'...")
        quotas = list_quotas_tool(dc_name)
        print(f" -> Found {len(quotas)} quota(s):")
        for q in quotas:
            print(f"    - Name: {q.name:<15} | ID: {q.id} | DC: {q.data_center_name}")
        default_q = next((q for q in quotas if q.name.lower() == "default"), None)
        assert default_q is not None, "Default quota must exist"

        print("\n[Step 4] Deep inspection of 'Default' Quota...")
        q_detail = get_quota_tool("Default", dc_name)
        print(f" -> Quota: {q_detail.name} (ID: {q_detail.id})")
        print(f" -> Cluster Limits: {len(q_detail.cluster_limits)}")
        print(f" -> Storage Limits: {len(q_detail.storage_limits)}")

        print("\n[Step 5] Testing Guard: Deleting 'Default' system quota...")
        try:
            delete_quota_tool("Default", dc_name, confirm=True)
            print(" -> FAILED: Guard did not catch deletion of Default quota!")
            sys.exit(1)
        except OvirtValidationError as e:
            print(f" -> PASSED: Correctly rejected Default quota removal: {e.message}")

        print(f"\n[Step 6] Creating new Quota '{test_quota_name}'...")
        q_res = create_quota_tool(test_quota_name, dc_name, description="Live MCP test quota")
        assert q_res.success is True
        print(f" -> Created quota ID: {q_res.quota_id}, message: {q_res.message}")

        print("\n[Step 7] Verifying new quota appears in list...")
        qs_after = list_quotas_tool(dc_name)
        assert any(q.name == test_quota_name for q in qs_after)
        print(" -> Verified: New quota listed in Data Center.")

        print(f"\n[Step 8] Deleting quota '{test_quota_name}' (confirm=True)...")
        q_del_res = delete_quota_tool(test_quota_name, dc_name, confirm=True)
        assert q_del_res.success is True
        print(f" -> Delete result: {q_del_res.message}")

        # =========================================================================
        # 3. LOGICAL NETWORK LIFECYCLE & GUARDS
        # =========================================================================
        print(f"\n[Step 9] Listing Logical Networks in '{dc_name}'...")
        nets = list_logical_networks_tool(dc_name)
        print(f" -> Found {len(nets)} logical network(s):")
        for n in nets:
            print(
                f"    - Name: {n.name:<15} | ID: {n.id} | VLAN: {n.vlan_id} | MTU: {n.mtu} | Status: {n.status}"
            )
        assert any(n.name == "ovirtmgmt" for n in nets), "'ovirtmgmt' network must exist"

        print("\n[Step 10] Testing Guard: Deleting protected 'ovirtmgmt' network...")
        try:
            delete_logical_network_tool("ovirtmgmt", dc_name, confirm=True)
            print(" -> FAILED: Guard did not catch deletion of ovirtmgmt network!")
            sys.exit(1)
        except OvirtValidationError as e:
            print(f" -> PASSED: Correctly rejected ovirtmgmt removal: {e.message}")

        print(f"\n[Step 11] Creating new Logical Network '{test_net_name}' (VLAN 888, MTU 9000)...")
        net_res = create_logical_network_tool(
            name=test_net_name,
            data_center=dc_name,
            vlan_id=888,
            mtu=9000,
            description="Live MCP test VLAN network",
        )
        assert net_res.success is True
        print(f" -> Created network ID: {net_res.network_id}, message: {net_res.message}")

        print("\n[Step 12] Verifying new network parameters in inventory...")
        nets_after = list_logical_networks_tool(dc_name)
        matching_net = next((n for n in nets_after if n.name == test_net_name), None)
        assert matching_net is not None
        assert matching_net.vlan_id == 888
        assert matching_net.mtu == 9000
        print(
            f" -> Verified: Network {test_net_name} has VLAN {matching_net.vlan_id} and MTU {matching_net.mtu}."
        )

        print(f"\n[Step 13] Deleting logical network '{test_net_name}' (confirm=True)...")
        net_del_res = delete_logical_network_tool(test_net_name, dc_name, confirm=True)
        assert net_del_res.success is True
        print(f" -> Delete result: {net_del_res.message}")

        print("\n" + "=" * 70)
        print("ALL DATA CENTER, QUOTA & NETWORK OPERATIONS PASSED ON LIVE OLVM!")
        print("=" * 70)

    finally:
        # Cleanup
        print("\n[Teardown] Cleaning up any remaining test entities...")
        try:
            for net in nets_svc.list():
                if str(getattr(net, "name", "")).lower() == test_net_name.lower():
                    nets_svc.network_service(net.id).remove()
                    print(f" -> Teardown: Removed test network '{test_net_name}'")
        except Exception as e:
            print(f" -> Teardown warning (network): {e}")

        try:
            dc_obj = client.find_resource_by_id_or_name(dcs_svc, dc_name, "data center")
            dc_svc = dcs_svc.data_center_service(dc_obj.id)
            for q in dc_svc.quotas_service().list():
                if str(getattr(q, "name", "")).lower() == test_quota_name.lower():
                    dc_svc.quotas_service().quota_service(q.id).remove()
                    print(f" -> Teardown: Removed test quota '{test_quota_name}'")
        except Exception as e:
            print(f" -> Teardown warning (quota): {e}")


if __name__ == "__main__":
    main()
