#!/usr/bin/env python3
"""Raw metal flash attempt for iPhone9,2 in Recovery mode."""
import os
import subprocess
import sys
import time
from pathlib import Path

BASE_DIR = Path("/home/j/Downloads/ios romm")
IRECOVERY = Path("/usr/bin/irecovery")
PART_IPSW = BASE_DIR / "iPhone18,5_26.5.2_23F84_Restore.ipsw.part"
RADISK_DMG = Path("/tmp/partial_ipsw/098-68700-067.dmg")
PFILE_SLICE = BASE_DIR / "firmware/iPhone18,5_26.5.2_23F84_Restore.ipsw.PFILE"


def run(cmd, timeout=60):
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.returncode, result.stdout, result.stderr
    except Exception as e:
        return -1, "", str(e)


def device_info():
    rc, out, err = run([str(IRECOVERY), "-q"])
    if rc != 0:
        print("[-] Device not detected")
        return None
    info = {}
    for line in out.strip().splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            info[k.strip()] = v.strip()
    return info


def attempt_raw_flash():
    print("=" * 60)
    print("RAW METAL FLASH - iPhone9,2 Recovery Mode")
    print("=" * 60)

    info = device_info()
    if not info:
        return
    print(f"[+] Device: {info.get('NAME', 'Unknown')}")
    print(f"    Mode: {info.get('MODE', 'Unknown')}")
    print(f"    Product: {info.get('PRODUCT', 'Unknown')}")
    print()

    # Strategy 1: Try loading the ramdisk from partial IPSW
    print("[1] Attempting ramdisk load from partial IPSW...")
    if RADISK_DMG.exists():
        rc, out, err = run([str(IRECOVERY), "-f", str(RADISK_DMG)], timeout=120)
        print(f"    Load ramdisk: rc={rc}")
        if rc == 0:
            rc, out, err = run([str(IRECOVERY), "-c", "ramdisk"], timeout=30)
            print(f"    Execute ramdisk: rc={rc}")
            time.sleep(2)
    else:
        print(f"    [-] Ramdisk not found: {RADISK_DMG}")

    # Strategy 2: Try to load PFILE slice directly
    print("\n[2] Attempting direct PFILE slice load...")
    if PFILE_SLICE.exists():
        # Try loading first 1MB to see if device accepts it
        test_file = PFILE_SLICE.parent / "test_1mb.bin"
        with open(PFILE_SLICE, 'rb') as fin:
            data = fin.read(1024 * 1024)
        with open(test_file, 'wb') as fout:
            fout.write(data)
        
        rc, out, err = run([str(IRECOVERY), "-f", str(test_file)], timeout=60)
        print(f"    Load 1MB test: rc={rc}")
        
        # Try go command
        rc, out, err = run([str(IRECOVERY), "-c", "go"], timeout=30)
        print(f"    Execute go: rc={rc}")
        time.sleep(2)
    else:
        print(f"    [-] PFILE slice not found: {PFILE_SLICE}")

    # Strategy 3: Try NAND write commands
    print("\n[3] Attempting NAND write commands...")
    nand_commands = [
        "nand read.i 0x09000000 0x0 0x100",
        "nand read.i 0x09000000 0x100000 0x100",
        "md 0x09000000",
    ]
    for cmd in nand_commands:
        rc, out, err = run([str(IRECOVERY), "-c", cmd], timeout=15)
        print(f"    {cmd}: rc={rc}, out={out.strip()[:100] if out else ''}")

    # Strategy 4: Try boot commands
    print("\n[4] Attempting boot commands...")
    boot_cmds = ["fsboot", "bootx", "go"]
    for cmd in boot_cmds:
        rc, out, err = run([str(IRECOVERY), "-c", cmd], timeout=30)
        print(f"    {cmd}: rc={rc}")
        time.sleep(1)

    # Check final state
    print("\n[5] Final device state:")
    info = device_info()
    if info:
        print(f"    Mode: {info.get('MODE', 'Unknown')}")
        print(f"    Product: {info.get('PRODUCT', 'Unknown')}")


if __name__ == "__main__":
    attempt_raw_flash()
