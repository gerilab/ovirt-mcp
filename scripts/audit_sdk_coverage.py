#!/usr/bin/env python3
"""Automated SDK Parity & Coverage Audit Engine for ovirt-mcp.

Compares the official ovirtsdk4 types and services against ovirt-mcp Pydantic models
and registered FastMCP tools, identifying coverage gaps and generating parity metrics.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path

import ovirtsdk4.services as sdk_services
import ovirtsdk4.types as sdk_types

import ovirt_mcp.models as mcp_models
from ovirt_mcp.server import mcp


@dataclass
class TypeCoverageResult:
    """Coverage report for a single oVirt SDK type."""

    resource_name: str
    sdk_type_name: str
    total_sdk_properties: int
    covered_properties_count: int
    coverage_percent: float
    covered_fields: list[str] = field(default_factory=list)
    missing_fields: list[str] = field(default_factory=list)


@dataclass
class ServiceActionCoverageResult:
    """Coverage report for actions/methods on an oVirt SDK service."""

    service_name: str
    total_actions: int
    covered_actions_count: int
    coverage_percent: float
    covered_actions: list[str] = field(default_factory=list)
    unmapped_actions: list[str] = field(default_factory=list)


# Resource types to compare: (Display Name, SDK Type, list of MCP Pydantic model classes)
RESOURCE_COMPARISON_TARGETS: list[tuple[str, type, list[type]]] = [
    (
        "Host",
        sdk_types.Host,
        [
            mcp_models.HostSummary,
            mcp_models.HostDetail,
            mcp_models.HostHardwareInfo,
            mcp_models.HostOSInfo,
            mcp_models.HostPowerManagement,
            mcp_models.HostStats,
        ],
    ),
    (
        "Virtual Machine (Vm)",
        sdk_types.Vm,
        [
            mcp_models.VmSummary,
            mcp_models.VmDetail,
            mcp_models.VmCompactDetail,
            mcp_models.VmCpuDetails,
            mcp_models.VmMemoryPolicy,
            mcp_models.VmIoAndScsi,
            mcp_models.VmPlacementAndAffinity,
            mcp_models.VmGuestOsInfo,
            mcp_models.VmHardwareSecurity,
            mcp_models.VmHighAvailability,
            mcp_models.VmLifecycleInfo,
            mcp_models.VmMigrationOptions,
            mcp_models.VmDiskInfo,
            mcp_models.VmNicInfo,
        ],
    ),
    (
        "Virtual Disk",
        sdk_types.Disk,
        [mcp_models.DiskDetail, mcp_models.VmDiskAttachmentInfo],
    ),
    (
        "Storage Domain",
        sdk_types.StorageDomain,
        [mcp_models.StorageDomainDetail, mcp_models.StorageDomainSummary],
    ),
    (
        "Cluster",
        sdk_types.Cluster,
        [
            mcp_models.ClusterDetail,
            mcp_models.ClusterSummary,
            mcp_models.ClusterFencingPolicy,
            mcp_models.ClusterMigrationPolicy,
            mcp_models.ClusterSchedulingPolicy,
        ],
    ),
    (
        "Logical Network",
        sdk_types.Network,
        [mcp_models.LogicalNetworkDetail],
    ),
    (
        "Template",
        sdk_types.Template,
        [mcp_models.TemplateDetail],
    ),
    (
        "Data Center",
        sdk_types.DataCenter,
        [mcp_models.DataCenterDetail],
    ),
    (
        "Resource Quota",
        sdk_types.Quota,
        [mcp_models.QuotaDetail],
    ),
    (
        "VM Pool",
        sdk_types.VmPool,
        [mcp_models.VmPoolDetail],
    ),
    (
        "User Account",
        sdk_types.User,
        [mcp_models.UserDetail],
    ),
]

# Service method mapping rules (SDK Service -> {method_name: MCP tool name or description})
SERVICE_ACTION_MAPPINGS: dict[type, dict[str, str]] = {
    sdk_services.VmService: {
        "start": "ovirt_vm_start",
        "stop": "ovirt_vm_stop",
        "shutdown": "ovirt_vm_shutdown",
        "reboot": "ovirt_vm_reboot",
        "migrate": "ovirt_vm_migrate",
        "cancel_migration": "ovirt_vm_cancel_migration",
        "suspend": "ovirt_vm_suspend",
        "reset": "ovirt_vm_reset",
        "freeze_filesystems": "ovirt_vm_freeze_filesystems",
        "thaw_filesystems": "ovirt_vm_thaw_filesystems",
        "auto_pin_cpu_and_numa_nodes": "ovirt_vm_auto_pin",
        "preview_snapshot": "ovirt_vm_snapshot_preview",
        "commit_snapshot": "ovirt_vm_snapshot_commit",
        "undo_snapshot": "ovirt_vm_snapshot_undo",
        "ticket": "ovirt_vm_ticket",
        "export": "ovirt_vm_export",
        "remove": "ovirt_vm_delete",
        "update": "ovirt_vm_update",
        "clone": "ovirt_vm_clone",
    },
    sdk_services.HostService: {
        "activate": "ovirt_host_activate",
        "deactivate": "ovirt_host_maintenance",
        "fence": "ovirt_host_restart",
        "upgrade_check": "ovirt_host_upgrade_check",
        "upgrade": "ovirt_host_upgrade",
        "install": "ovirt_host_reinstall",
        "refresh": "ovirt_host_refresh",
        "force_select_spm": "ovirt_host_force_select_spm",
        "enroll_certificate": "ovirt_host_enroll_certificate",
        "sync_all_networks": "ovirt_host_sync_all_networks",
        "commit_net_config": "ovirt_host_commit_net_config",
        "iscsi_discover": "ovirt_host_iscsi_discover",
        "iscsi_login": "ovirt_host_iscsi_login",
        "setup_networks": "ovirt_host_network_sync",
        "remove": "ovirt_host_delete",
        "update": "ovirt_host_update",
    },
    sdk_services.StorageDomainService: {
        "remove": "ovirt_storage_domain_delete",
        "update_ovf_store": "ovirt_storage_domain_update_ovf_store",
        "refresh_luns": "ovirt_storage_domain_refresh_luns",
        "reduce_luns": "ovirt_storage_domain_reduce_luns",
        "update": "ovirt_storage_domain_update",
    },
    sdk_services.ClusterService: {
        "update": "ovirt_cluster_update",
        "sync_all_networks": "ovirt_cluster_sync_all_networks",
        "reset_emulated_machine": "ovirt_cluster_reset_emulated_machine",
        "remove": "ovirt_cluster_delete",
    },
    sdk_services.DiskService: {
        "move": "ovirt_disk_move",
        "copy": "ovirt_disk_copy",
        "sparsify": "ovirt_disk_sparsify",
        "reduce": "ovirt_disk_reduce",
        "export": "ovirt_disk_export",
        "remove": "ovirt_disk_delete",
    },
    sdk_services.TemplateService: {
        "export": "ovirt_template_export",
        "remove": "ovirt_template_delete",
        "update": "ovirt_template_update",
    },
    sdk_services.DataCenterService: {
        "clean_finished_tasks": "ovirt_datacenter_clean_finished_tasks",
        "remove": "ovirt_datacenter_delete",
    },
    sdk_services.NetworkService: {
        "update": "ovirt_network_update",
        "remove": "ovirt_network_delete",
    },
    sdk_services.VmPoolService: {
        "allocate_vm": "ovirt_vm_pool_allocate_vm",
        "update": "ovirt_vm_pool_update",
        "remove": "ovirt_vm_pool_delete",
    },
}


def get_sdk_properties(sdk_cls: type) -> set[str]:
    """Extract public attributes and properties from an ovirtsdk4 Type class."""
    props = set()
    for attr in dir(sdk_cls):
        if not attr.startswith("_") and not attr.startswith("href"):
            val = getattr(sdk_cls, attr, None)
            if not callable(val):
                props.add(attr)
    return props


def get_mcp_model_fields(model_classes: list[type]) -> set[str]:
    """Extract field names from a list of Pydantic model classes."""
    fields = set()
    for m in model_classes:
        if hasattr(m, "model_fields"):
            fields.update(m.model_fields.keys())
    return fields


def audit_types_coverage() -> list[TypeCoverageResult]:
    """Audit SDK property coverage across all target resources."""
    results = []
    for res_name, sdk_cls, mcp_clss in RESOURCE_COMPARISON_TARGETS:
        sdk_props = get_sdk_properties(sdk_cls)
        mcp_fields = get_mcp_model_fields(mcp_clss)

        # Normalize common naming variations (e.g., id -> id, iscsi -> iscsi_initiator_name)
        normalized_mcp = set(mcp_fields)
        if "iscsi_initiator_name" in normalized_mcp:
            normalized_mcp.add("iscsi")

        covered = sorted(sdk_props.intersection(normalized_mcp))
        missing = sorted(sdk_props - normalized_mcp)

        total = len(sdk_props)
        cov_count = len(covered)
        pct = round((cov_count / total * 100), 1) if total > 0 else 0.0

        results.append(
            TypeCoverageResult(
                resource_name=res_name,
                sdk_type_name=sdk_cls.__name__,
                total_sdk_properties=total,
                covered_properties_count=cov_count,
                coverage_percent=pct,
                covered_fields=covered,
                missing_fields=missing,
            )
        )
    return results


def audit_services_coverage() -> list[ServiceActionCoverageResult]:
    """Audit action methods on SDK services vs mapped MCP tools."""
    registered_tools = set(mcp._tool_manager._tools.keys())
    results = []

    for svc_cls, tool_map in SERVICE_ACTION_MAPPINGS.items():
        all_methods = [
            m
            for m in dir(svc_cls)
            if not m.startswith("_")
            and not m.endswith("_service")
            and not m.endswith("_services")
            and m not in ("service", "get", "inspect", "follow")
            and not m.endswith("_using_root_password")
            and not m.endswith("_using_ssh")
        ]

        covered = []
        unmapped = []

        for m_name in all_methods:
            mapped_tool = tool_map.get(m_name)
            if mapped_tool and mapped_tool in registered_tools:
                covered.append(f"{m_name} -> {mapped_tool}")
            else:
                unmapped.append(m_name)

        total = len(all_methods)
        cov_count = len(covered)
        pct = round((cov_count / total * 100), 1) if total > 0 else 0.0

        results.append(
            ServiceActionCoverageResult(
                service_name=svc_cls.__name__,
                total_actions=total,
                covered_actions_count=cov_count,
                coverage_percent=pct,
                covered_actions=covered,
                unmapped_actions=unmapped,
            )
        )
    return results


def format_terminal_report(
    type_results: list[TypeCoverageResult],
    service_results: list[ServiceActionCoverageResult],
) -> str:
    """Format a clean, readable terminal report."""
    total_props = sum(r.total_sdk_properties for r in type_results)
    covered_props = sum(r.covered_properties_count for r in type_results)
    total_pct = round((covered_props / total_props * 100), 1) if total_props > 0 else 0.0

    registered_tools_count = len(mcp._tool_manager._tools)

    lines = [
        "=" * 78,
        "oVirt / OLVM MCP Server - SDK Parity & Coverage Audit Report",
        "=" * 78,
        f"Total Registered MCP Tools:  {registered_tools_count}",
        f"Audited Resource Domains:    {len(type_results)}",
        f"Total SDK Properties:        {total_props}",
        f"Exposed in MCP Models:       {covered_props} ({total_pct}% overall property coverage)",
        "-" * 78,
        f"{'Resource Domain':<26} {'SDK Type':<16} {'SDK Props':<11} {'MCP Fields':<11} {'Coverage %':<10}",
        "-" * 78,
    ]

    for r in type_results:
        lines.append(
            f"{r.resource_name:<26} {r.sdk_type_name:<16} {r.total_sdk_properties:<11} "
            f"{r.covered_properties_count:<11} {r.coverage_percent:>7.1f}%"
        )

    lines.extend(
        [
            "-" * 78,
            "Service Action / Mutation Tool Coverage:",
            "-" * 78,
            f"{'SDK Service':<26} {'Total Methods':<15} {'Covered Tools':<15} {'Coverage %':<10}",
            "-" * 78,
        ]
    )

    for s in service_results:
        lines.append(
            f"{s.service_name:<26} {s.total_actions:<15} {s.covered_actions_count:<15} {s.coverage_percent:>7.1f}%"
        )

    unmapped_lines = []
    for s in service_results:
        if s.unmapped_actions:
            unmapped_lines.append(f"  * {s.service_name}: {', '.join(s.unmapped_actions[:5])}")

    if unmapped_lines:
        lines.extend(
            [
                "=" * 78,
                "Remaining Unmapped Service Actions (Candidates for Future Parity Expansion):",
                *unmapped_lines,
                "=" * 78,
            ]
        )
    else:
        lines.extend(
            [
                "=" * 78,
                "All targeted SDK Service Actions are 100% mapped and covered!",
                "=" * 78,
            ]
        )

    return "\n".join(lines)


def generate_markdown_matrix(
    type_results: list[TypeCoverageResult],
    service_results: list[ServiceActionCoverageResult],
) -> str:
    """Generate the full SDK_COVERAGE.md Markdown document."""
    total_props = sum(r.total_sdk_properties for r in type_results)
    covered_props = sum(r.covered_properties_count for r in type_results)
    total_pct = round((covered_props / total_props * 100), 1) if total_props > 0 else 0.0
    registered_tools_count = len(mcp._tool_manager._tools)

    doc = [
        "# oVirt / OLVM SDK Parity & Coverage Matrix (`SDK_COVERAGE.md`)",
        "",
        "> **Generated by:** `scripts/audit_sdk_coverage.py`  ",
        f"> **Audited Tools Count:** {registered_tools_count}  ",
        f"> **Overall SDK Property Coverage:** {covered_props}/{total_props} ({total_pct}%)  ",
        "",
        "This living document tracks 100% parity between the official `ovirtsdk4` Python SDK and the `ovirt-mcp` tools and Pydantic models. "
        "It acts as the authoritative engineering reference for unmapped data fields and candidate mutation tools.",
        "",
        "---",
        "",
        "## 1. Resource Domain Coverage Summary",
        "",
        "| Resource Domain | SDK Type | Total SDK Properties | Exposed in MCP | Unmapped | Property Coverage |",
        "|---|---|:---:|:---:|:---:|:---:|",
    ]

    for r in type_results:
        doc.append(
            f"| **{r.resource_name}** | `{r.sdk_type_name}` | {r.total_sdk_properties} | "
            f"{r.covered_properties_count} | {len(r.missing_fields)} | **{r.coverage_percent:.1f}%** |"
        )

    doc.extend(
        [
            f"| **Total / Overall** | | **{total_props}** | **{covered_props}** | **{total_props - covered_props}** | **{total_pct:.1f}%** |",
            "",
            "---",
            "",
            "## 2. Service Action & Mutation Tool Coverage",
            "",
            "| SDK Service | Total Action Methods | Mapped MCP Tools | Unmapped Methods | Action Coverage |",
            "|---|:---:|:---:|:---:|:---:|",
        ]
    )

    for s in service_results:
        doc.append(
            f"| `{s.service_name}` | {s.total_actions} | {s.covered_actions_count} | "
            f"{len(s.unmapped_actions)} | **{s.coverage_percent:.1f}%** |"
        )

    doc.extend(
        [
            "",
            "---",
            "",
            "## 3. Detailed Unmapped Fields per Resource Domain",
            "",
        ]
    )

    for r in type_results:
        doc.append(f"### {r.resource_name} (`{r.sdk_type_name}`)")
        doc.append(
            f"- **Covered Fields ({r.covered_properties_count}):** `{', '.join(r.covered_fields)}`"
        )
        doc.append(f"- **Unmapped SDK Properties ({len(r.missing_fields)}):**")
        doc.append(f"  ```text\n  {', '.join(r.missing_fields)}\n  ```")
        doc.append("")

    doc.extend(
        [
            "---",
            "",
            "## 4. Unmapped Service Action Methods (Candidate Tools)",
            "",
        ]
    )

    for s in service_results:
        if s.unmapped_actions:
            doc.append(f"### `{s.service_name}` Unmapped Actions")
            doc.append(
                f"- **Methods awaiting tool implementation:** `{', '.join(s.unmapped_actions)}`"
            )
            doc.append("")

    return "\n".join(doc)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit ovirt-mcp SDK Parity and Coverage")
    parser.add_argument(
        "--write-markdown",
        action="store_true",
        help="Write or update SDK_COVERAGE.md in repository root",
    )
    parser.add_argument(
        "--audit",
        action="store_true",
        help="Run SDK parity and coverage audit",
    )
    parser.add_argument(
        "--coverage",
        action="store_true",
        help="Alias for --audit",
    )
    parser.add_argument(
        "command",
        nargs="?",
        default="audit",
        help="Audit command (default: audit)",
    )
    args, _ = parser.parse_known_args(argv)

    type_results = audit_types_coverage()
    service_results = audit_services_coverage()

    report = format_terminal_report(type_results, service_results)
    print(report)

    if args.write_markdown:
        root_dir = Path(__file__).resolve().parent.parent
        coverage_md_path = root_dir / "SDK_COVERAGE.md"
        md_content = generate_markdown_matrix(type_results, service_results)
        coverage_md_path.write_text(md_content, encoding="utf-8")
        print(f"\n[OK] Successfully wrote: {coverage_md_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
