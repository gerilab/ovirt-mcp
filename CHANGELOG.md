# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.8.13] - 2026-11-28

### Added
- **Pre-flight Status Guards & Lifecycle State Machine Safety Across All 186 Tools**:
  - Implemented centralized guard module `src/ovirt_mcp/tools/guards.py` providing `require_host_status`, `require_vm_status`, `require_storage_domain_status`, `require_disk_status`, `require_snapshot_status`, and `require_template_status`.
  - Defined explicit transitional state blacklists (`TRANSITIONAL_HOST_STATUSES`, `TRANSITIONAL_VM_STATUSES`, `TRANSITIONAL_STORAGE_STATUSES`, `TRANSITIONAL_DISK_STATUSES`, `TRANSITIONAL_SNAPSHOT_STATUSES`, `TRANSITIONAL_TEMPLATE_STATUSES`) protecting against VDSM disconnects, storage lease corruptions, and engine race conditions during `saving_state`, `image_locked`, `preparing_for_maintenance`, `reboot`, and related in-flight operations.
  - Standardized human- and AI-readable remediation guidance in `OvirtValidationError` specifying current status, required status list, and exact prerequisite remediation steps.
  - Added comprehensive architectural documentation in `docs/STATUS_GUARDS.md` covering the WebAdmin vs REST API safety gap, Mermaid state machine diagrams, and troubleshooting matrix.
- **Asynchronous Job Orchestration Best Practices**:
  - Added documentation and patterns in `README.md` for handling background engine tasks (`ovirt_job_list`, `ovirt_job_get`) and async resource unlinking (e.g. Blank template and disk lock finalization).

### Fixed
- **Storage Domain Root Status Resolution**:
  - Fixed `_extract_status_string` in `guards.py` to handle `status: None` returned by `/api/storagedomains/{id}` (where operational status is scoped to `/api/datacenters/{id}/storagedomains/{id}`), defaulting safely to `"active"`.
- **vNIC Profile UUID Lookup**:
  - Resolved SDK service method mapping mismatch in `connection.py` for `vnic_profile` lookups, delegating properly to `profile_service(id)`.
- **Memory Snapshot & Console Safety**:
  - Enforced strict live VM checks for memory snapshots (`persist_memory=True`) and console tickets/files (`ovirt_vm_ticket`, `ovirt_vm_console_file`), requiring `up` status.
- **Offline Operations Enforcement**:
  - Enforced strict `down` status requirement for `ovirt_template_create_from_vm`, `ovirt_vm_export`, `ovirt_vm_clone`, `ovirt_vm_snapshot_restore`, and `ovirt_vm_snapshot_preview`.

### Changed
- Promoted server safety model from Three-Tier to **Four-Tier Access, Safety & Lifecycle Architecture** (Tier 1: Engine AAA, Tier 2: Read-Only Gate, Tier 3: Safe Mode Confirmation, Tier 4: Pre-flight Status Guards).

## [0.8.12] - 2026-11-27

### Added
- **Cloud-Init & Windows Sysprep Guest OS Customization**:
  - `ovirt_vm_initialization_set`: Set, modify, or clear Cloud-Init (hostname, user, password, SSH authorized keys, custom user-data script, DNS, timezone, static NIC) and Windows Sysprep (domain, OU, admin password, license key, locale, UI language, custom answer script, static NIC) parameters.
  - `ovirt_vm_initialization_get`: Query currently assigned Cloud-Init or Sysprep configuration from any virtual machine.
  - Integrated guest initialization into `ovirt_vm_create` and Run-Once execution in `ovirt_vm_start`.
- **14 New Enterprise Parity Tools (186 Tools Total)**:
  - `ovirt_vm_snapshot_clone`: Clone a new independent virtual machine directly from an existing historical snapshot.
  - `ovirt_disk_convert`: Convert virtual disk format between COW and RAW, with sparse preallocation options.
  - `ovirt_disk_lun_refresh`: Refresh capacity and volume metadata for direct LUN disks.
  - `ovirt_storage_domain_unregistered_vms_list`: List unregistered VMs on a storage domain (disaster recovery / import).
  - `ovirt_storage_domain_unregistered_vm_register`: Register unregistered VMs into target clusters with MAC conflict resolution and partial disk import.
  - `ovirt_host_copy_networks`: Copy logical network bindings and NIC configurations between hypervisor hosts.
  - `ovirt_host_approve`: Approve pre-installed hypervisors with cluster assignment and automatic activation/reboot.
  - `ovirt_cluster_upgrade`: Manage cluster rolling upgrades (`start`, `stop`, `update_progress`).
  - `ovirt_vm_watchdog_list`: Inspect hardware watchdog devices attached to virtual machines.
  - `ovirt_vm_watchdog_add`: Attach virtual hardware watchdogs (`i6300esb`, `diag288`) with customizable timeout actions (`reset`, `poweroff`, `pause`, `dump`, `none`).
  - `ovirt_vm_watchdog_remove`: Detach hardware watchdogs with Safe Mode protection.
  - `ovirt_vm_host_device_list`: Inspect physical host devices (SR-IOV, GPU, PCI passthrough) attached to VMs.
  - `ovirt_vm_host_device_attach`: Attach host PCI/vGPU devices to virtual machines.
  - `ovirt_vm_host_device_detach`: Detach physical host devices with Safe Mode protection.
- **New Data Models**:
  - `VmInitializationInfo`, `VmInitializationResult`, `VmNicConfiguration`, `VmWatchdogInfo`, `VmHostDeviceInfo`, `VmHardwareResult`.

## [0.8.11] - 2026-11-27

### Added
- **11 New Full SDK Parity Tools (170 Tools Total)**:
  - `ovirt_disk_get`: Retrieve comprehensive specifications, capacity metrics, format, storage domain hosting, and real-time I/O telemetry for virtual disks (`DiskDetail`).
  - `ovirt_disk_delete`: Permanently delete virtual disks from storage domains with Safe Mode confirmation and dry_run simulation (`DiskDeleteResult`).
  - `ovirt_vm_clone`: Clone virtual machines to create new independent VMs with target cluster, destination storage domain, snapshot collapsing, and synchronous wait (`VmCloneResult`).
  - `ovirt_cluster_create`: Create virtualization clusters in target Data Centers specifying CPU types, descriptions, and compatibility versions (`ClusterOperationResult`).
  - `ovirt_cluster_delete`: Delete empty virtualization clusters with active host and VM safety guards (`ClusterOperationResult`).
  - `ovirt_datacenter_create`: Create Data Centers with shared or local storage architecture, quota mode, and compatibility levels (`DataCenterOperationResult`).
  - `ovirt_datacenter_delete`: Delete Data Centers with cluster and storage domain safety guards and force removal support (`DataCenterOperationResult`).
  - `ovirt_host_update`: Update hypervisor host comments, display names, and cluster relocation in maintenance mode (`HostDetail`).
  - `ovirt_network_update`: Update logical network properties including names, descriptions, comments, 802.1Q VLAN IDs, and MTU sizes (`LogicalNetworkDetail`).
  - `ovirt_template_update`: Update virtual machine template names, descriptions, and comments (`TemplateDetail`).
  - `ovirt_storage_domain_update`: Update Storage Domain attributes including names, comments, and warning/critical space threshold limits (`StorageDomainDetail`).
- **Updated Result Models**:
  - `DiskDeleteResult` in `ovirt_mcp.models.disk`
  - `VmCloneResult` in `ovirt_mcp.models.vm`
- **Updated Service Action Parity Coverage**:
  - `VmService`: 73.1% (19/26 methods mapped)
  - `HostService`: 80.0% (16/20 methods mapped)
  - `StorageDomainService`: 83.3% (5/6 methods mapped)
  - `ClusterService`: 66.7% (4/6 methods mapped)
  - `DiskService`: 66.7% (6/9 methods mapped)
  - `TemplateService`: 60.0% (3/5 methods mapped)
  - `DataCenterService`: 50.0% (2/4 methods mapped)
  - `NetworkService`: 100.0% (2/2 methods mapped)
  - `VmPoolService`: 100.0% (3/3 methods mapped)

## [0.8.10] - 2026-11-27

### Added
- **15 New Enterprise Operational Parity Tools (159 Tools Total)**:
  - `ovirt_vm_freeze_filesystems`: Freeze (quiesce) guest filesystems via `qemu-guest-agent` for storage-level snapshots/backups.
  - `ovirt_vm_thaw_filesystems`: Thaw (unquiesce) guest filesystems after snapshot/backup completion.
  - `ovirt_vm_auto_pin`: Apply automated CPU and NUMA node pinning topology to virtual machines.
  - `ovirt_host_create`: Add, provision, and enroll a new hypervisor host into a cluster via automated Ansible host deployment (`ovirt-host-deploy`).
  - `ovirt_host_delete`: Permanently remove and decommission a hypervisor host from engine inventory with pre-flight maintenance mode verification, SPM detection, active VM protection, Safe Mode confirmation, and dry_run simulation.
  - `ovirt_host_enroll_certificate`: Enroll / renew host PKI TLS certificates with the internal engine CA.
  - `ovirt_host_sync_all_networks`: Synchronize all out-of-sync networks on a hypervisor host.
  - `ovirt_host_commit_net_config`: Persist running network configuration to permanent host storage.
  - `ovirt_storage_domain_refresh_luns`: Rescan and refresh SAN/iSCSI LUN sizes and visibility on block storage domains.
  - `ovirt_storage_domain_reduce_luns`: Release and reduce unused LUN physical volumes from block storage domains.
  - `ovirt_disk_reduce`: Shrink/reduce underlying physical storage volume allocation for thin-provisioned virtual disks.
  - `ovirt_cluster_sync_all_networks`: Synchronize logical networks across all hypervisor hosts in a cluster.
  - `ovirt_cluster_reset_emulated_machine`: Reset cluster default emulated machine type.
  - `ovirt_datacenter_clean_finished_tasks`: Clean finished asynchronous background tasks in a Data Center.
  - `ovirt_template_export`: Export templates to Export Storage Domains.
- **Service Action Parity Coverage Increases**:
  - `VmService`: 69.2% (18/26 methods mapped)
  - `HostService`: 75.0% (15/20 methods mapped)
  - `StorageDomainService`: 66.7% (4/6 methods mapped)
  - `ClusterService`: 50.0% (3/6 methods mapped)
  - `DiskService`: 66.7% (6/9 methods mapped)
  - `TemplateService`: 40.0% (2/5 methods mapped)
  - `DataCenterService`: 25.0% (1/4 methods mapped)
  - `VmPoolService`: 100.0% (3/3 methods mapped)
- **New Result Models**:
  - `HostCreateResult` in `ovirt_mcp.models.host`
  - `HostDeleteResult` in `ovirt_mcp.models.host`
  - `ClusterOperationResult` in `ovirt_mcp.models.cluster`
  - `DataCenterOperationResult` in `ovirt_mcp.models.datacenter`
  - Added `dry_run` support to `StorageDomainResult`.

## [0.8.9] - 2026-11-27

### Added
- **SDK Parity & Coverage Audit Engine (`ovirt-mcp --audit`)**:
  - Implemented automated introspection engine in `scripts/audit_sdk_coverage.py` comparing official `ovirtsdk4` types and services against `ovirt-mcp` models and tools.
  - Generates comprehensive living parity matrix in `SDK_COVERAGE.md`.
  - Accessible directly via CLI: `ovirt-mcp --audit` or `ovirt-mcp audit`.
  - Increased overall SDK property coverage across core resources from 30.6% to 37.6% (163/434 properties).
- **6 New Enterprise Virtualization Operational Tools (144 Tools Total)**:
  - `ovirt_vm_cancel_migration`: Cancel in-progress live migration of a virtual machine with Safe Mode and `dry_run` support.
  - `ovirt_vm_suspend`: Suspend a running virtual machine to disk (saving RAM/state to hypervisor storage).
  - `ovirt_vm_reset`: Hard hardware reset of VM (simulating physical chassis reset button).
  - `ovirt_host_refresh`: Refresh host capabilities, NUMA topology, network adapters, and devices from VDSM agent.
  - `ovirt_host_force_select_spm`: Force hypervisor host selection as Storage Pool Manager (SPM).
  - `ovirt_storage_domain_update_ovf_store`: Trigger immediate synchronization and generation of the OVF store backup on storage domains.
- **Deep SDK Telemetry & Metadata Field Mapping**:
  - `VmSummary` & `VmDetail`: Exposed `delete_protected`, `has_illegal_images`, `next_run_configuration_exists`, `creation_time`, `start_time`, `stop_time`, `stop_reason`, `comment`, `origin`, `stateless`, `type`, and `status_detail`.
  - `HostSummary` & `HostDetail`: Exposed `comment`, `description`, `kdump_status`, `auto_numa_status`, `se_linux`, `hosted_engine`, `transparent_huge_pages`, `type`, `protocol`, and `numa_supported`.
  - `DiskDetail`: Exposed `backup`, `backup_mode`, `shareable`, `read_only`, `wipe_after_delete`, `sparse`, `qcow_version`, `sgio`, `propagate_errors`, `description`, and `comment`.
  - `StorageDomainDetail`: Exposed `comment`, `block_size`, `discard_after_delete`, `external_status`, `backup`, and `master`.

## [0.8.8] - 2026-11-27

### Added
- **Hypervisor Host Reinstallation Tool (`ovirt_host_reinstall`)**:
  - Added new tool #49 (`ovirt_host_reinstall`) executing the oVirt / OLVM Ansible deployment automation playbook (`ovirt-host-deploy`).
  - Reinstalls and syncs the VDSM node agent, PKI TLS certificates, management network bridges, and firewall rules on hypervisor hosts.
  - Implemented multi-layered safety guards:
    - Pre-flight guard strictly blocks execution on active hosts with running VMs (`status=up`) to protect tenant workloads; host must be in `maintenance`, `non_operational`, `install_failed`, or `down` state.
    - Protected action in Safe Mode: requires `confirm=True` when `MCP_SAFE_MODE=true`.
    - Simulation mode: supports `dry_run=True` to validate pre-conditions, status constraints, and engine reachability without altering host state.
    - Read-only protection: rejects execution when `MCP_READ_ONLY=true`.
    - Configurable post-install actions: `activate: bool = True` (auto-activate to 'up'), `reboot: bool = True` (reboot physical node), `root_password: str | None` (optional SSH credential).
- **Host Reinstallation & Health Status Exposure (`ovirt_host_list`, `ovirt_host_get`)**:
  - Exposed native oVirt SDK `reinstallation_required` boolean flag in `HostSummary` and `HostDetail` data models.
  - Exposed `status_detail` string providing the engine's detailed reason for degraded or non-operational status.
  - Exposed `external_status` health indicator (`ok`, `info`, `warning`, `error`).

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
