---
name: ovirt-lifecycle-orchestrator
description: Operational rules, sequential workflow patterns, and state machine safety guidelines for AI agents managing oVirt / OLVM virtualization infrastructure via ovirt-mcp.
---

# oVirt / OLVM Lifecycle Orchestrator Skill

This skill guides AI agents in safely and effectively orchestrating virtualized infrastructure operations on **oVirt** and **Oracle Linux Virtualization Manager (OLVM)** using the `ovirt-mcp` tool suite.

---

## 1. Core Operating Philosophy

1. **State Machine Awareness:**  
   oVirt enforces strict backend state machines. An operation that succeeds on an offline VM will fail on a running VM, and vice-versa. Always check the entity state before requesting mutations.
2. **Respect Pre-flight Status Guards:**  
   If a tool returns an `OvirtValidationError` with `Cannot execute '<action>' on ...: Current status is '...'`, this indicates that the WebAdmin equivalent button is currently disabled. Follow the remediation steps in the error message rather than retrying blindly.
3. **Never Interfere with Transitional States:**  
   If an entity is in `saving_state`, `restoring_state`, `image_locked`, `preparing_for_maintenance`, or `reboot`, all mutations are locked. Wait for the engine to reach a stable state (`up`, `down`, `maintenance`, `active`, `ok`).

---

## 2. Standard Multi-Step Workflow Patterns

### Pattern A: Hypervisor Host Maintenance & Rolling Upgrade
To safely upgrade a hypervisor host without dropping guest VM workloads:
1. **Inventory Workloads:** Call `ovirt_vm_list(host_id="<host_id>")` to verify active VMs.
2. **Cordon Host:** Call `ovirt_host_maintenance(name_or_id="<host_id>", confirm=True)`.
   - The engine automatically migrates running VMs to other healthy cluster hosts.
3. **Verify Maintenance State:** Query `ovirt_host_get` and ensure `status == "maintenance"`.
4. **Check Available Upgrades:** Call `ovirt_host_upgrade_check(name_or_id="<host_id>")`.
5. **Execute Upgrade:** Call `ovirt_host_upgrade(name_or_id="<host_id>", confirm=True)`.
6. **Track Progress:** Use `ovirt_job_list` to monitor package updates and host reboot steps.
7. **Re-activate Host:** Call `ovirt_host_activate(name_or_id="<host_id>", confirm=True)`.

---

### Pattern B: Golden Image Template Creation
To create a reusable VM template from an existing virtual machine:
1. **Graceful Shutdown:** Call `ovirt_vm_shutdown(name_or_id="<vm_id>")` (or `ovirt_vm_stop(name_or_id="<vm_id>", confirm=True)`).
2. **Verify Offline Status:** Poll `ovirt_vm_get` until `status == "down"`.
   - *Status Guard Rule:* `ovirt_template_create_from_vm` strictly requires `down`. Calling it while `up` will be rejected immediately.
3. **Create Template:** Call `ovirt_template_create_from_vm(vm_name_or_id="<vm_id>", template_name="...", confirm=True)`.
4. **Monitor Template Build:** Call `ovirt_template_get` until `status == "ok"` (disks will temporarily be locked during cloning).

---

### Pattern C: Snapshot Management & Disaster Recovery
1. **Memory vs. Disk Snapshot:**
   - If `persist_memory=True`: The VM MUST strictly be `up` or `paused`.
   - If `persist_memory=False`: The VM may be `up` or `down`, but must NOT be in `image_locked` or `saving_state`.
2. **Snapshot Restore / Revert:**
   - **Crucial Rule:** The VM MUST strictly be `down`.
   - Stop the VM first before calling `ovirt_vm_snapshot_restore`.
3. **Snapshot Preview & Commit:**
   - Call `ovirt_vm_snapshot_preview` (VM must be `down`).
   - Test or inspect the previewed volume state.
   - Finalize with `ovirt_vm_snapshot_commit` (or revert with `ovirt_vm_snapshot_undo`).

---

### Pattern D: Infrastructure Teardown & Asynchronous Cleanup
When decommissioning clusters, data centers, or storage domains, account for **engine background task latency**:
1. **Delete / Evacuate Workloads:** Delete or migrate all member VMs first.
2. **Decommission Hosts:**
   - Put host in maintenance (`ovirt_host_maintenance`).
   - Remove host from cluster or delete (`ovirt_host_delete`).
3. **Decommission Storage Domains:**
   - Put domain in maintenance (`ovirt_storage_domain_maintenance`).
   - Detach domain from data center (`ovirt_storage_domain_detach`).
4. **Handle Engine Deregistration Latency:**
   - When all hosts and storage domains are detached, the engine asynchronously unlinks the default `Blank` template reference from the cluster.
   - **Wait 5–15 seconds** before calling `ovirt_cluster_delete` to prevent HTTP 409 Conflict (`One or more Template(s) are still associated`).
5. **Delete Cluster and Data Center:** Call `ovirt_cluster_delete` then `ovirt_datacenter_delete`.

---

## 3. Asynchronous Job Monitoring

For long-running tasks (disk migration, host upgrades, snapshot deletion):
1. Call `ovirt_job_list` to find the active job matching the operation.
2. Call `ovirt_job_get(job_id="...")` to inspect:
   - `status`: e.g. `"started"`, `"finished"`, `"failed"`.
   - `steps`: Step-by-step execution breakdown with progress percentages.
3. Avoid issuing concurrent mutations on the same entity while a job is `"started"`.
