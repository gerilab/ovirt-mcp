---
name: ovirt-mcp-developer
description: Guidelines and core architectural rules for developing, maintaining, and testing enterprise MCP tools in ovirt-mcp, including Pre-flight Status Guards, transitional state protection, quality gates, and zero-leakage policies.
---

# oVirt / OLVM MCP Developer Skill

When working on this repository, you act as a **Senior Virtualization Infrastructure & Systems Architect**.

---

## 1. Core Architecture & Design Principles

- **FastMCP Framework:** Build robust, self-describing MCP tools with strict Pydantic V2 input and output models.
- **Engine SDK Integration:** Leverage `ovirtsdk4` services cleanly with connection pooling, automatic PKI certificate caching, and proactive exception translation.
- **Hierarchical Naming Scheme (Mandatory):** Every tool MUST strictly follow:
  ```text
  ovirt_<domain>_[<subresource>_]<action>
  ```
  - `ovirt_vm_*`: Virtual machine compute, lifecycle, migration, and guest agents.
  - `ovirt_host_*`: Hypervisor hosts, hardware devices, NUMA, power management, and maintenance.
  - `ovirt_cluster_*`: Virtualization clusters, CPU profiles, and policy rules.
  - `ovirt_storage_*`: Storage domains, capacity health, and LUN management.
  - `ovirt_disk_*`: Floating disks, volume operations, format conversion, and lease locks.
  - `ovirt_network_*`: Logical networks, vNIC profiles, and cluster network bindings.
  - `ovirt_tag_*`: Tag lifecycle and assignments across VMs, hosts, and users.
  - `ovirt_job_*`: Asynchronous background task tracking and execution progress.

---

## 2. Four-Tier Safety Model & Mandatory Pre-flight Status Guards

Every tool modifying hypervisor state must adhere to the four-tier security architecture:
1. **Tier 1 (Engine Floor):** oVirt AAA role boundaries (e.g. `ReadOnlyAdmin` blocks all engine writes).
2. **Tier 2 (Read-Only Gate):** When `MCP_READ_ONLY=true`, locally abort all mutating operations.
3. **Tier 3 (Safe Mode Gate):** When `MCP_SAFE_MODE=true` (default), require explicit `confirm=True` for destructive actions. Support `dry_run=True` simulation where applicable.
4. **Tier 4 (Pre-flight Status Guards):** **MANDATORY for all state-dependent mutations.**

### Implementing Pre-flight Guards (`src/ovirt_mcp/tools/guards.py`)
Never dispatch a mutation call to the oVirt Engine without validating the live entity state first:
- Virtual Machines: Call `require_vm_status(vm_name, vm.status, allowed_statuses, action_name)`.
- Hypervisor Hosts: Call `require_host_status(host_name, host.status, allowed_statuses, action_name)`.
- Storage Domains: Call `require_storage_domain_status(domain_name, domain.status, allowed_statuses, action_name)`.
- Disks: Call `require_disk_status(disk_id, disk.status, allowed_statuses, action_name)`.
- Snapshots: Call `require_snapshot_status(snapshot_id, snapshot.status, allowed_statuses, action_name)`.
- Templates: Call `require_template_status(template_name, template.status, allowed_statuses, action_name)`.

### Strict Transitional State Blacklist
Operations MUST be blocked while entities are in flux:
- **VMs:** Block on `saving_state`, `restoring_state`, `image_locked`, `powering_up`, `powering_down`, `migrating`.
- **Hosts:** Block on `reboot`, `installing`, `preparing_for_maintenance`, `kdumping`, `connecting`.
- **Disks & Snapshots:** Block on `locked`, `illegal`.
- **Storage Domains:** Block on `locked`, `unknown`.

---

## 3. Known Engine & SDK Quirks to Handle

1. **Storage Domain Root `status: None`:**
   - In oVirt REST API, `/api/storagedomains/{id}` does not expose operational status; it is scoped to the Data Center context (`/api/datacenters/{id}/storagedomains/{id}`).
   - Ensure `_extract_status_string` safely treats `status is None` as `"active"` for root storage domain lookups.
2. **SDK Method Naming Quirks:**
   - For vNIC Profiles, `vnic_profiles_service` uses `profile_service(id)`, not `vnic_profile_service(id)`. Maintain resolution fallbacks in `find_resource_by_id_or_name`.
3. **Asynchronous Deregistration Latency:**
   - Certain engine operations (e.g., detaching storage domains, deleting clusters after host removal) require 5–15 seconds for background cleanup of default template links (Blank template). Workflows must account for this latency.

---

## 4. Quality Gates & Policies

1. **Zero-Commit Policy:**
   - **CRITICAL:** NEVER execute `git commit`, `git tag`, or `git push` without explicit user review and approval in the chat.
2. **Data Sanitization & Privacy (RFC 2606 / RFC 5737):**
   - Strictly adhere to `data-sanitization-and-privacy` policy.
   - NEVER commit real private infrastructure identifiers (internal hostnames, physical hypervisor names, private homelab domains, or local subnet IP addresses).
   - Use RFC 2606 (`example.com`, `example.org`) and RFC 5737 (`192.0.2.0/24`, `198.51.100.0/24`) for documentation, tests, and mock fixtures.
3. **English-Only Submission Standard:**
   - All code, docstrings, comments, documentation, and commit messages MUST be in English.
4. **Mandatory Pre-Completion Verification:**
   ```bash
   .venv/bin/ruff check .
   .venv/bin/ruff format .
   .venv/bin/mypy src
   .venv/bin/pytest tests/unit/ -v
   ```
