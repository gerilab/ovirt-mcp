#!/usr/bin/env python3
"""Live End-to-End Test for VM CD-ROM and ISO Media Management."""

import os

from ovirt_mcp.tools.media import (
    eject_vm_iso_tool,
    list_storage_isos_tool,
    list_vm_cdroms_tool,
)


def main() -> None:
    print("=" * 70)
    print("oVirt / OLVM MCP Live Media & CD-ROM Tester")
    print("=" * 70)

    target_vm = os.getenv("OVIRT_TEST_VM", "testvm001")

    print("\n[Step 1] Querying available ISO storage domain files...")
    iso_files = list_storage_isos_tool()
    print(f" -> Discovered {len(iso_files)} ISO files across storage domains.")
    for iso in iso_files:
        print(f"    - File: {iso.name} (Domain: {iso.storage_domain_name})")

    print(f"\n[Step 2] Listing CD-ROM drives on VM '{target_vm}'...")
    cdroms = list_vm_cdroms_tool(target_vm)
    print(f" -> Found {len(cdroms)} CD-ROM drive(s):")
    for cd in cdroms:
        print(f"    - Drive ID: {cd.id} | Attached file: {cd.file_id} | Empty: {cd.is_empty}")
    assert len(cdroms) >= 1, f"Expected at least 1 CD-ROM on VM {target_vm}"

    print(f"\n[Step 3] Executing reversible eject on VM '{target_vm}'...")
    eject_res = eject_vm_iso_tool(name_or_id=target_vm)
    print(f" -> Eject result: {eject_res.message}")
    assert eject_res.success is True
    assert eject_res.iso_file is None

    print("\n[Step 4] Verifying CD-ROM state after eject...")
    cdroms_after = list_vm_cdroms_tool(target_vm)
    assert cdroms_after[0].is_empty is True, "Expected CD-ROM to be empty after eject"
    print(" -> Confirmed CD-ROM is empty.")

    print("\n" + "=" * 70)
    print("ALL MEDIA & CD-ROM LIVE TESTS PASSED SUCCESSFULLY!")
    print("=" * 70)


if __name__ == "__main__":
    main()
