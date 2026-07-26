#!/usr/bin/env python3
"""Consolidated flash script with method arguments"""
import subprocess
import os
import sys
from pathlib import Path
from utils import PathConfig

cfg = PathConfig()

def flash_direct():
    """Flash using Windows-compatible tools from Legacy Kit"""
    
    # Use Windows-compatible idevicerestore directly
    idevicerestore_path = "git-hash_2025-09-30-2a7836e/Legacy-iOS-Kit-latest/Legacy-iOS-Kit-latest/bin/linux/x86_64/idevicerestore"
    
    if not os.path.exists(idevicerestore_path):
        print("[!] idevicerestore not found in Legacy iOS Kit")
        return False
    
    print("[+] Direct IPSW Flash")
    print("[+] Put device in DFU mode (black screen)")
    input("Press Enter when ready...")
    
    # Copy to local path for easier execution
    if not os.path.exists("idevice"):
        os.makedirs("idevice")
    
    import shutil
    local_idevicerestore = "idevice/idevicerestore"
    shutil.copy2(idevicerestore_path, local_idevicerestore)
    
    # Run idevicerestore with no signature checks
    cmd = [local_idevicerestore, "-e", "-w", "iPad1,1_iOS9_A4_Final.ipsw"]
    print(f"[+] Running: {' '.join(cmd)}")
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    print(f"[+] Return code: {result.returncode}")
    if result.stdout:
        print(f"[+] Output: {result.stdout}")
    if result.stderr:
        print(f"[!] Errors: {result.stderr}")
    
    return result.returncode == 0

def flash_checkm8():
    """Raw IPSW flash using checkm8 exploit"""
    ipsw_dir = "iPad1,1_iOS9_A4_Final"
    
    print("[+] checkm8 Raw Flash - No Apple Permission Required")
    print("[+] Put device in DFU mode (black screen)")
    input("Press Enter when ready...")
    
    steps = [
        ("Pwn DFU (checkm8)", ["python", "ipwndfu-win32/ipwndfu", "-p"]),
        ("Send patched iBoot", ["python", "secureboot_tools/send_iboot.py", f"{ipsw_dir}/iBoot.patched"]),
        ("Send kernel", ["python", "secureboot_tools/send_kernel.py", f"{ipsw_dir}/kernelcache.release.n90ap"]),
        ("Write rootfs", ["python", "secureboot_tools/nand_write.py", f"{ipsw_dir}/rootfs9.dmg", "/dev/disk0s1s1"]),
        ("Reboot", ["python", "secureboot_tools/reset.py"])
    ]
    
    for desc, cmd in steps:
        print(f"[+] {desc}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"[!] Failed: {result.stderr}")
            return False
        print(f"[✅] {desc} complete")
    
    print("[✅] Raw flash complete - device should boot iOS 9")
    return True

def flash_manual():
    """Print manual flash instructions"""
    print("""
[!] Linux binaries from Legacy iOS Kit are incompatible with Windows

[+] Manual Flash Options:

1. Use WSL (Windows Subsystem for Linux):
   - Install WSL: wsl --install
   - Copy Legacy iOS Kit to WSL
   - Run from WSL terminal

2. Use 3uTools:
   - Download 3uTools
   - Put device in DFU mode
   - Flash iPad1,1_iOS9_A4_Final.ipsw

3. Use iTunes + DFU mode:
   - Put device in DFU mode
   - Hold Shift + Restore in iTunes
   - Select iPad1,1_iOS9_A4_Final.ipsw

4. Build Windows idevicerestore:
   - Install MSYS2
   - Build from source in: 1.0.0 source code/libimobiledevice-idevicerestore-a88351d

[+] Target IPSW: iPad1,1_iOS9_A4_Final.ipsw
[+] Device must be in DFU mode (black screen)
""")

def main():
    if len(sys.argv) < 2:
        print("Usage: python flash.py <method>")
        print("Methods:")
        print("  direct   - Flash using idevicerestore from Legacy Kit")
        print("  checkm8  - Flash using checkm8 exploit chain")
        print("  manual   - Print manual flash instructions")
        sys.exit(1)
    
    method = sys.argv[1].lower()
    
    if method == "direct":
        flash_direct()
    elif method == "checkm8":
        flash_checkm8()
    elif method == "manual":
        flash_manual()
    else:
        print(f"Unknown method: {method}")
        print("Available methods: direct, checkm8, manual")
        sys.exit(1)

if __name__ == "__main__":
    main()
