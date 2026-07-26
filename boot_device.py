#!/usr/bin/env python3
"""
Boot commands for flashed iOS device.
Provides manual boot commands to attempt to boot the device after flashing.
"""
import subprocess
import sys
from pathlib import Path

def run_cmd(cmd, timeout=30):
    """Run command and return result."""
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except Exception as e:
        print(f"[-] Command failed: {' '.join(cmd)} - {e}")
        return None

def main():
    print("=" * 60)
    print("BOOT COMMANDS FOR FLASHED DEVICE")
    print("=" * 60)
    
    irecovery = "/usr/bin/irecovery"
    
    # Check device status
    print("\n[1] Checking device status...")
    result = run_cmd([irecovery, "-q"])
    if result and result.returncode == 0:
        print("[+] Device detected:")
        print(result.stdout)
    else:
        print("[-] Device not detected via irecovery")
        print("    Device may still be in Recovery mode")
    
    print("\n" + "=" * 60)
    print("MANUAL BOOT COMMANDS")
    print("=" * 60)
    
    print("\nSTEP 1: Set boot arguments")
    print(f"  {irecovery} -c setenv boot-args rd=md0 -v")
    
    print("\nSTEP 2: Save boot environment")
    print(f"  {irecovery} -c saveenv")
    
    print("\nSTEP 3: Boot device")
    print(f"  {irecovery} -c bootx")
    
    print("\nSTEP 4: Alternative boot command")
    print(f"  {irecovery} -c go")
    
    print("\n" + "=" * 60)
    print("ISSUE DIAGNOSIS")
    print("=" * 60)
    print("\n[!] The flashed IPSW was only 4.3KB with stub files")
    print("    Real firmware components should be much larger (MB-GB)")
    print("    The automatic flash system extracted stub data from the PFILE")
    print()
    print("RECOMMENDATION:")
    print("  Use the real IPSW file instead:")
    print("  /home/j/Downloads/ios romm/firmware/iPhone18,5_26.5.2_23F84_Restore.ipsw (8.4GB)")
    print()
    print("Command to flash with real IPSW:")
    print("  idevicerestore -e -u <device_ecid> /home/j/Downloads/ios\\ romm/firmware/iPhone18,5_26.5.2_23F84_Restore.ipsw")
    print()
    print("Or use the automatic flash system with the real IPSW:")
    print("  python3 automatic_flash_system.py /home/j/Downloads/ios\\ romm/firmware/iPhone18,5_26.5.2_23F84_Restore.ipsw")
    print()

if __name__ == "__main__":
    main()
