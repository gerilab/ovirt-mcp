# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Async Job & Progress Monitoring Tools**: Added `ovirt_job_list` and `ovirt_job_get` tools to monitor asynchronous engine operations (live migrations, disk operations, snapshot consolidations) with execution sub-steps, real-time progress percentages (0-100%), and execution host mapping.

### Fixed
- **Guest OS Kernel Version Coercion**: Fixed Pydantic validation failure in `ovirt_vm_get` when guest agent returns an `ovirtsdk4.types.Version` object instead of a string for `kernel_version`. Added `_format_version` extraction logic and Pydantic before-validator on `VmGuestOsInfo` to format `full_version` or `major.minor.build-revision`.
- **MCP Tool Error Transparency**: Subclassed `MCPServer` into `OvirtMCPServer` and mapped `OvirtMCPError` to `ToolError` across all 136 tools so that tool errors surface detailed, actionable diagnostic messages rather than generic opaque errors.

### Documentation & Architecture
- **Documentation Architecture Split**: Decoupled the monolithic 3,600-line `README.md` by moving the exhaustive 136-tool reference catalog into a dedicated `TOOLS.md` reference manual.
- **Structured Domain Summary**: Added an executive resource domain overview table in `README.md` categorizing all 136 tools across 17 functional domains.
- **Updated Telemetry References**: Expanded tool documentation in `TOOLS.md` with detailed schemas and examples for real-time per-disk I/O, VM runtime telemetry, storage domain overcommitment health, and event UUID correlations.

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
