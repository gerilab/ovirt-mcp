# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.8.7] - 2026-11-25

### Added
- **Pre-flight Diagnostic Check (`ovirt-mcp check` / `ovirt-mcp --check`)**:
  - Implemented an interactive CLI pre-flight diagnostic utility directly in `ovirt-mcp`.
  - Verifies `.env` and environment variables, REST API reachability, TLS handshake, engine authentication, API version, and confirms registration of all 137 MCP tools.
- **Extended `dry_run` Support to Disks, Snapshots, and Templates**:
  - Added `dry_run: bool = False` simulation support across 7 additional operations:
    - Virtual disks: `ovirt_disk_resize`, `ovirt_disk_move`, `ovirt_disk_sparsify`.
    - VM snapshots: `ovirt_vm_snapshot_restore`, `ovirt_vm_snapshot_delete`.
    - Templates: `ovirt_template_create_from_vm`, `ovirt_template_delete`.
  - Updated `TemplateResult`, `DiskResizeResult`, and `DiskOperationResult` schemas with `dry_run: bool = False`.
- **GitHub Actions Release Workflow**:
  - Added `.github/workflows/release.yml` to automatically generate GitHub Releases and changelog notes upon pushing `v*` tags.

### Fixed
- **Pytest Asyncio Configuration**:
  - Configured `asyncio_default_fixture_loop_scope = "function"` in `pyproject.toml` to eliminate `PytestDeprecationWarning`.
- **RFC 2606 Compliance & Privacy in Test Fixtures**:
  - Replaced non-RFC test domain references (`olvm.local`, `*.corp`) with standard `example.com` domains.
  - Sanitized fixture MAC addresses (`00:50:56:00:11:22`).
- **Repository Cleanliness (`.gitignore`)**:
  - Expanded `.gitignore` with comprehensive patterns for logs, test cache files, coverage reports, and OS artifacts.

## [0.8.6] - 2026-11-25

### Added
- **`dry_run` Simulation Flag for Lifecycle & Operational Tools**:
  - Added `dry_run: bool = False` parameter across 10 vital operational and lifecycle tools:
    - Virtual machines: `ovirt_vm_start`, `ovirt_vm_stop`, `ovirt_vm_shutdown`, `ovirt_vm_reboot`, `ovirt_vm_delete`, `ovirt_vm_migrate`, `ovirt_vm_snapshot_create`.
    - Hypervisor hosts: `ovirt_host_maintenance`, `ovirt_host_activate`, `ovirt_host_restart`.
  - In simulation mode (`dry_run=True`), the server executes all authentication, entity resolution, validation checks, enterprise safety gates (e.g., zero VMs running, IPMI fencing verification, pinned VMs detection), and records the audit entry, but completely bypasses destructive Safe Mode confirmation requirements and makes zero state alterations on the oVirt / OLVM cluster.
  - Returns structured results with `dry_run: bool = True` and clear human-readable preview messages detailing what changes would occur upon actual execution.
- **Append-only Audit Log File (`OVIRT_AUDIT_LOG_FILE`)**:
  - Added `OVIRT_AUDIT_LOG_FILE` environment variable / `config.ovirt_audit_log_file` setting.
  - Automatically appends structured JSON Lines (`.jsonl`) audit records for every mutation and dry-run simulation across all 17 resource domains.
  - Records include UTC timestamp (`timestamp`), operation name (`action`), acting credentials (`user`), target entity (`target`), execution outcome (`status`: `SUCCESS`, `FAILED`, `TIMEOUT`), and structured payload details (`details`).
  - Ensures compliance with enterprise SOC2, ISO 27001, and change management auditing without external log shipping overhead.

## [0.8.5] - 2026-11-25

### Added
- **Cluster Settings & Policy Management (`ovirt_cluster_update`)**:
  - Added new tool #89 (`ovirt_cluster_update`) to modify cluster configuration, VM live migration convergence policies, scheduling placement algorithms, and fencing rules.
  - Operational settings (live migration auto-converge, data encryption, compression, custom bandwidth limits, parallel migrations, workload scheduling policies, threshold parameters, fencing safety bypass, and administrator comments) are applied dynamically online without requiring cluster or hypervisor maintenance mode.
- **Host iSCSI Initiator Name / IQN (`ovirt_host_get`, `ovirt_host_list`)**:
  - Exposed `iscsi_initiator_name` (Host IQN, e.g. `iqn.1994-05.com.redhat:...`) in `HostDetail` and `HostSummary` for SAN/iSCSI storage discovery and mapping.
  - Exposed `vdsm_port` in `HostDetail` (VDSM management daemon port, default 54321).
- **Physical Interface LLDP Neighbor & Switch Port Discovery (`ovirt_host_nic_list`)**:
  - Added `include_lldp` parameter to `ovirt_host_nic_list` (enabled by default) querying Link Layer Discovery Protocol (LLDP) elements received on host network interfaces.
  - Decoded structured LLDP neighbor telemetry in `HostNicInfo` (`lldp` field):
    - `port_id`: Identifies the exact physical switch port connected to the hypervisor NIC (e.g. `GigabitEthernet1/0/24`, `1/1/2`).
    - `chassis_id`: Connected switch chassis MAC address / identifier.
    - `port_description`: Configured port description on switch.
    - `system_name`: Connected switch system / hostname.
    - `system_description`: Switch hardware vendor, model, and OS firmware version.
    - `management_address`: Switch management IP address.
    - `elements`: Exhaustive list of raw/decoded TLVs (`HostNicLldpElement`).

### Documentation & Tool Reference
- **Expanded Catalog to 137 Tools**: Updated `TOOLS.md` and `README.md` reflecting the new `ovirt_cluster_update` tool, updated host IQN and LLDP port parameters, and revised resource domain tool counts.

## [0.8.4] - 2026-11-25

### Added
- **Detailed Cluster Live Migration & Scheduling Policies**: Extended `ovirt_cluster_get` with exhaustive technical policies:
  - `migration`: Full VM live migration and convergence settings (`auto_converge`, `compressed`, `encrypted`, `bandwidth_assignment_method`, `bandwidth_custom_value`, `parallel_migrations_policy`, `custom_parallel_migrations`, `policy_id`, `policy_name`).
  - `scheduling_policy`: Granular workload placement and scheduling algorithm details (`id`, `name`, `description`, and algorithm threshold parameters in `properties`).
  - `fencing_policy`: Safety fencing bypass rules (`skip_if_connectivity_broken`, `skip_if_sd_active`, `skip_if_gluster_bricks_up`, `skip_if_gluster_quorum_not_met`).
  - Additional cluster attributes: `management_network_name`, `firewall_type`, `serial_number_policy`, `error_handling`, and administrator `comment`.
- **Storage Domain Hardware LUN Serials & NAS Connection Endpoints**: Extended `ovirt_storage_domain_get` and `ovirt_storage_domain_list` with deep hardware identifiers:
  - `lun_serials`: List of hardware serial numbers for underlying iSCSI / SAN LUNs for immediate discovery and inventory correlation.
  - `logical_units`: Full SAN/iSCSI LUN records (`id`, `serial`, `vendor_id`, `product_id`, `size_gb`, `target`, `address`, `port`, `portal`, `paths`, `volume_group_id`, `status`).
  - `storage_connections`: Active storage connection endpoints (`address`, `path`, `target`, `port`, `portal`, `type`, `nfs_version`, `mount_options`, `vfs_type`).
  - Top-level storage connection metadata: `port`, `portal`, `nfs_version`, `mount_options`, and `volume_group_id`.

### Documentation & Developer Experience
- **Windows Deployment & Astral `uv` / `uvx` Guide**: Expanded `README.md` (Method 4) with clear, step-by-step guidance on running `ovirt-mcp` on Windows:
  - Option A: Zero-build execution via WSL2 with `uvx` (recommended for Windows clients to avoid C++ build requirements).
  - Option B: Zero-build execution via Docker Desktop.
  - Option C: Native Windows PowerShell setup with Astral `uv` and path rules.
- **Updated Catalog Specifications**: Documented new cluster and storage domain fields in `TOOLS.md`.

## [0.8.3] - 2026-11-20

### Added
- **Async Job & Progress Monitoring Tools**: Added `ovirt_job_list` and `ovirt_job_get` tools to monitor asynchronous engine operations (live migrations, disk operations, snapshot consolidations) with execution sub-steps, real-time progress percentages (0-100%), and execution host mapping.

### Fixed
- **Guest OS Kernel Version Coercion**: Fixed Pydantic validation failure in `ovirt_vm_get` when guest agent returns an `ovirtsdk4.types.Version` object instead of a string for `kernel_version`. Added `_format_version` extraction logic and Pydantic before-validator on `VmGuestOsInfo` to format `full_version` or `major.minor.build-revision`.
- **MCP Tool Error Transparency**: Subclassed `MCPServer` into `OvirtMCPServer` and mapped `OvirtMCPError` to `ToolError` across all 136 tools so that tool errors surface detailed, actionable diagnostic messages rather than generic opaque errors.

### Documentation & Architecture
- **Documentation Architecture Split**: Decoupled the monolithic 3,600-line `README.md` by moving the exhaustive 136-tool reference catalog into a dedicated `TOOLS.md` reference manual.
- **Structured Domain Summary**: Added an executive resource domain overview table in `README.md` categorizing all 136 tools across 17 functional domains.
- **Updated Telemetry References**: Expanded tool documentation in `TOOLS.md` with detailed schemas and examples for real-time per-disk I/O, VM runtime telemetry, storage domain overcommitment health, and event UUID correlations.
- **Sanitized Documentation Examples**: Anonymized all internal hostnames, domains, and IP ranges across documentation and unit test fixtures to RFC 2606 (`example.com`) and RFC 5737 (`10.0.0.0/24`, `192.0.2.0/24`) compliant placeholders.

## [0.8.2] - 2026-11-20

### Added
- **Real-Time Per-Disk I/O Telemetry**: Each virtual disk in `ovirt_vm_get` (`disks` list) and `ovirt_disk_list` now returns `io_stats` containing `read_mb_sec`, `write_mb_sec`, `read_iops`, `write_iops`, and granular latency metrics (`read_latency_ms`, `write_latency_ms`, `flush_latency_ms`).
- **VM Runtime Telemetry & Network Error Counters**: `ovirt_vm_get` now includes an aggregate `telemetry` block (CPU guest/hypervisor/total %, RAM allocation and utilization, aggregate disk throughput and IOPS) along with per-NIC packet error and lifetime throughput metrics (`rx_errors`, `tx_errors`, `total_rx_bytes`, `total_tx_bytes`).
- **Storage Domain Real-Time Performance & Health**: `ovirt_storage_domain_get` and `ovirt_storage_domain_list` now calculate `overcommit_ratio` (thin-provisioning over-allocation), `space_health` indicator (`ok`, `warning_low_space`, `critical_space`), aggregate storage domain I/O, top active disks ranked by load (`top_io_disks`), and hosted VMs list (`vms_list`).
- **Hypervisor Host Telemetry**: `ovirt_host_get` now includes host performance metrics (`stats`: CPU usage %, 5-minute load average, memory consumed/free in GB).
- **Audit Event Entity Correlation**: `ovirt_system_events` and `ovirt_vm_events` now return entity UUIDs (`vm_id`, `host_id`, `cluster_id`, `storage_domain_id`) enabling direct cross-referencing and immediate inspection from log entries.

### Fixed
- **Guest Agent IP Address Retrieval**: Fixed empty `ip_addresses` in `ovirt_vm_list`, `ovirt_vm_get`, and `ovirt_vm_nic_list` by populating the `reported_devices` subcollection and adding hardware MAC address matching.
- **Storage Domain Name Resolution on Disks**: Fixed raw UUID strings or `'None'` in `ovirt_disk_list` and `ovirt_vm_get` by pre-fetching and mapping storage domain IDs to human-readable names.

### Documentation & Developer Experience
- Added comprehensive step-by-step setup guides for Windows PowerShell and Remote Linux jumpboxes via SSH (VS Code Remote - SSH and Kiro IDE).
- Clarified that coding agents maintain a strict English policy for repository submissions while preserving full freedom for developers to communicate in Hungarian or their native language in chat.

## [0.8.0] - 2026-11-19
- Initial enterprise feature release with 113 MCP tools covering VM lifecycle, storage management, networking, quotas, users, backups, and multi-arch GHCR publishing.
