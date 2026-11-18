#!/usr/bin/env python3
"""Live End-to-End Verification for Affinity Labels & Cluster Affinity Groups on OLVM."""

import os

from ovirt_mcp.client.exceptions import OvirtValidationError
from ovirt_mcp.tools.affinity import (
    ovirt_affinity_label_create,
    ovirt_affinity_label_delete,
    ovirt_affinity_label_list,
    ovirt_cluster_affinity_group_create,
    ovirt_cluster_affinity_group_delete,
    ovirt_cluster_affinity_group_get,
    ovirt_cluster_affinity_group_list,
    ovirt_cluster_affinity_group_update,
    ovirt_host_label_assign,
    ovirt_host_label_list,
    ovirt_host_label_unassign,
    ovirt_vm_label_assign,
    ovirt_vm_label_list,
    ovirt_vm_label_unassign,
)


def main() -> None:
    print("=" * 75)
    print("oVirt / OLVM MCP Live Affinity Labels & Affinity Groups E2E Tester")
    print("=" * 75)

    test_cluster = os.getenv("OVIRT_TEST_CLUSTER", "DefaultCluster")
    test_host = os.getenv("OVIRT_TEST_HOST", "olvmhost002.example.com")
    test_vm = os.getenv("OVIRT_TEST_VM", "testvm001")
    test_label_name = "e2e_test_db_tier"
    test_ag_name = "e2e_test_db_anti_affinity"

    # ── Step 1: Query global affinity labels ─────────────────────────────────────
    print("\n[Step 1] Listing initial global affinity labels (ovirt_affinity_label_list)...")
    initial_labels = ovirt_affinity_label_list()
    print(f" -> Found {len(initial_labels)} existing affinity label(s)")
    for lbl in initial_labels:
        print(f"    * Label: {lbl.name} (UUID: {lbl.id}) | Hosts: {lbl.hosts} | VMs: {lbl.vms}")

    # ── Step 2: Create a new global affinity label ───────────────────────────────
    print(
        f"\n[Step 2] Creating global affinity label '{test_label_name}' (ovirt_affinity_label_create)..."
    )
    create_lbl_res = ovirt_affinity_label_create(name=test_label_name)
    print(f" -> Result: {create_lbl_res.message} (ID: {create_lbl_res.label_id})")
    assert create_lbl_res.success is True
    assert create_lbl_res.label_id is not None
    label_id = create_lbl_res.label_id

    # ── Step 3: Assign label to hypervisor host ─────────────────────────────────
    print(f"\n[Step 3] Assigning label to host '{test_host}' (ovirt_host_label_assign)...")
    assign_h_res = ovirt_host_label_assign(
        host_name_or_id=test_host, label_name_or_id=test_label_name
    )
    print(f" -> Result: {assign_h_res.message}")
    assert assign_h_res.success is True
    assert test_label_name in assign_h_res.current_labels

    print(" -> Verifying host labels directly (ovirt_host_label_list)...")
    h_labels = ovirt_host_label_list(host_name_or_id=test_host)
    print(f"    Host '{test_host}' current labels: {h_labels}")
    assert test_label_name in h_labels

    # ── Step 4: Assign label to virtual machine ─────────────────────────────────
    print(f"\n[Step 4] Assigning label to VM '{test_vm}' (ovirt_vm_label_assign)...")
    assign_v_res = ovirt_vm_label_assign(vm_name_or_id=test_vm, label_name_or_id=test_label_name)
    print(f" -> Result: {assign_v_res.message}")
    assert assign_v_res.success is True
    assert test_label_name in assign_v_res.current_labels

    print(" -> Verifying VM labels directly (ovirt_vm_label_list)...")
    v_labels = ovirt_vm_label_list(vm_name_or_id=test_vm)
    print(f"    VM '{test_vm}' current labels: {v_labels}")
    assert test_label_name in v_labels

    # ── Step 5: Check global label memberships ──────────────────────────────────
    print("\n[Step 5] Checking global labels again to verify bidirectional membership...")
    updated_labels = ovirt_affinity_label_list()
    matching_lbl = next((lbl for lbl in updated_labels if lbl.id == label_id), None)
    assert matching_lbl is not None
    print(
        f" -> Label '{matching_lbl.name}' members: Hosts={matching_lbl.hosts}, VMs={matching_lbl.vms}"
    )
    assert test_host in matching_lbl.hosts or any(
        test_host.split(".")[0] in h for h in matching_lbl.hosts
    )
    assert test_vm in matching_lbl.vms

    # ── Step 6: Test pre-flight delete guard (must block if entities attached) ──
    print(
        "\n[Step 6] Testing pre-flight delete guard (ovirt_affinity_label_delete without detach_first)..."
    )
    try:
        ovirt_affinity_label_delete(name_or_id=test_label_name, confirm=True, detach_first=False)
        raise AssertionError(
            "Expected OvirtValidationError was not raised for assigned label deletion!"
        )
    except OvirtValidationError as e:
        print(f" -> [GUARD WORKING] Successfully blocked deletion of assigned label:\n    {e}")

    # ── Step 7: Unassign from VM and Host (Reversibility check) ──────────────────
    print("\n[Step 7] Testing reversible unassign operations...")
    unassign_v_res = ovirt_vm_label_unassign(
        vm_name_or_id=test_vm, label_name_or_id=test_label_name
    )
    print(f" -> VM unassign: {unassign_v_res.message}")
    assert unassign_v_res.success is True
    assert test_label_name not in unassign_v_res.current_labels

    unassign_h_res = ovirt_host_label_unassign(
        host_name_or_id=test_host, label_name_or_id=test_label_name
    )
    print(f" -> Host unassign: {unassign_h_res.message}")
    assert unassign_h_res.success is True
    assert test_label_name not in unassign_h_res.current_labels

    # ── Step 8: Delete global label ─────────────────────────────────────────────
    print(f"\n[Step 8] Deleting global label '{test_label_name}' (ovirt_affinity_label_delete)...")
    del_lbl_res = ovirt_affinity_label_delete(name_or_id=test_label_name, confirm=True)
    print(f" -> Result: {del_lbl_res.message}")
    assert del_lbl_res.success is True
    remaining_labels = ovirt_affinity_label_list()
    assert not any(lbl.id == label_id for lbl in remaining_labels)
    print(" -> Global label deleted cleanly.")

    # ── Step 9: Cluster Affinity Groups lifecycle ───────────────────────────────
    print(f"\n[Step 9] Listing initial Affinity Groups in cluster '{test_cluster}'...")
    initial_ags = ovirt_cluster_affinity_group_list(cluster_name_or_id=test_cluster)
    print(f" -> Found {len(initial_ags)} existing Affinity Group(s)")

    print(f"\n[Step 10] Creating Affinity Group '{test_ag_name}' with anti-affinity rule...")
    create_ag_res = ovirt_cluster_affinity_group_create(
        cluster_name_or_id=test_cluster,
        name=test_ag_name,
        description="E2E test anti-affinity group for database workload",
        priority=2.0,
        vm_positive=False,  # Anti-affinity (run apart)
        vm_enforcing=True,  # Mandatory
        vms=[test_vm],
        hosts=[test_host],
    )
    print(f" -> Result: {create_ag_res.message} (UUID: {create_ag_res.group_id})")
    assert create_ag_res.success is True
    ag_id = create_ag_res.group_id
    assert ag_id is not None

    print("\n[Step 11] Getting Affinity Group details (ovirt_cluster_affinity_group_get)...")
    ag_info = ovirt_cluster_affinity_group_get(
        cluster_name_or_id=test_cluster, group_name_or_id=test_ag_name
    )
    print(f" -> Group: {ag_info.name} (UUID: {ag_info.id})")
    print(f"    Description: {ag_info.description}")
    print(
        f"    VM Rule: positive={ag_info.vms_rule.positive if ag_info.vms_rule else 'None'}, "
        f"enforcing={ag_info.vms_rule.enforcing if ag_info.vms_rule else 'None'}"
    )
    print(f"    Member VMs: {ag_info.vms}")
    print(f"    Member Hosts: {ag_info.hosts}")
    assert ag_info.vms_rule is not None
    assert ag_info.vms_rule.positive is False
    assert ag_info.vms_rule.enforcing is True
    assert test_vm in ag_info.vms

    print("\n[Step 12] Updating Affinity Group (ovirt_cluster_affinity_group_update)...")
    update_ag_res = ovirt_cluster_affinity_group_update(
        cluster_name_or_id=test_cluster,
        group_name_or_id=test_ag_name,
        description="Updated E2E description for database workload",
        vm_enforcing=False,  # Relax enforcement to soft preference
    )
    print(f" -> Result: {update_ag_res.message}")
    assert update_ag_res.success is True

    updated_ag_info = ovirt_cluster_affinity_group_get(
        cluster_name_or_id=test_cluster, group_name_or_id=test_ag_name
    )
    assert updated_ag_info.vms_rule is not None
    assert updated_ag_info.vms_rule.enforcing is False
    print(f" -> Verified relaxed enforcement: enforcing={updated_ag_info.vms_rule.enforcing}")

    print("\n[Step 13] Deleting Affinity Group (ovirt_cluster_affinity_group_delete)...")
    del_ag_res = ovirt_cluster_affinity_group_delete(
        cluster_name_or_id=test_cluster,
        group_name_or_id=test_ag_name,
        confirm=True,
    )
    print(f" -> Result: {del_ag_res.message}")
    assert del_ag_res.success is True

    final_ags = ovirt_cluster_affinity_group_list(cluster_name_or_id=test_cluster)
    assert not any(g.id == ag_id for g in final_ags)
    print(" -> Verified Affinity Group cleanly removed from cluster.")

    print("\n" + "=" * 75)
    print("ALL LIVE AFFINITY LABELS & AFFINITY GROUPS TESTS PASSED ON OLVM!")
    print("=" * 75)


if __name__ == "__main__":
    main()
