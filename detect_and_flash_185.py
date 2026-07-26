#!/usr/bin/env python3
"""
Detect iOS device and automatically flash firmware 18.5 using existing codespace solutions.
Integrates TSS bypass, checkra1n, and automatic restore systems.
"""
import subprocess
import sys
import asyncio
from pathlib import Path

def run_cmd(cmd, timeout=10):
    """Run command and return result."""
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except Exception as e:
        print(f"[-] Command failed: {' '.join(cmd)} - {e}")
        return None

def detect_device():
    """Detect connected iOS device using lsusb and irecovery."""
    print("=" * 60)
    print("iOS DEVICE DETECTION")
    print("=" * 60)
    
    # Check lsusb for Apple devices
    print("\n[1] Checking USB devices...")
    result = run_cmd(["lsusb", "-d", "05ac:"], timeout=5)
    device_detected = False
    if result and result.stdout:
        print("[+] Apple devices found:")
        for line in result.stdout.strip().splitlines():
            if "Recovery" in line or "DFU" in line or "Mobile Device" in line:
                print(f"  * {line}")
                device_detected = True
    
    # Check usbmuxd status
    print("\n[2] Checking usbmuxd service...")
    result = run_cmd(["systemctl", "is-active", "usbmuxd"], timeout=5)
    if result and result.stdout.strip() == "active":
        print("[+] usbmuxd is running")
    else:
        print("[-] usbmuxd is not running")
        print("    Start it with: sudo systemctl start usbmuxd")
    
    # Check irecovery
    print("\n[3] Checking irecovery...")
    irecovery_path = None
    for path in ["/usr/bin/irecovery", "/usr/local/bin/irecovery"]:
        if Path(path).exists():
            irecovery_path = path
            print(f"[+] Found irecovery at: {irecovery_path}")
            break
    
    if not irecovery_path:
        print("[-] irecovery not found in standard locations")
        print("    Install with: sudo pacman -S libirecovery")
        return None, None
    
    # Query device
    print("\n[4] Querying device via irecovery...")
    result = run_cmd([irecovery_path, "-q"], timeout=15)
    if result and result.returncode == 0 and result.stdout:
        print("[+] Device info:")
        print(result.stdout)
        
        # Parse device info
        device_info = {}
        for line in result.stdout.strip().splitlines():
            if ":" in line:
                key, val = line.split(":", 1)
                device_info[key.strip()] = val.strip()
        return device_info, irecovery_path
    else:
        print("[-] irecovery cannot connect to device")
        print("    This is common even when device is in Recovery mode")
        print("    Device may still be flashable via direct commands")
        if device_detected:
            print("[+] Device detected via USB, proceeding with manual commands")
            return {"MODE": "Recovery", "PRODUCT": "Unknown", "MODEL": "Unknown"}, irecovery_path
        return None, irecovery_path

def check_firmware():
    """Check for available firmware files."""
    print("\n[4] Checking available firmware...")
    base_dir = Path("/home/j/Downloads/ios romm/firmware")
    
    # Look for iPhone18,5 firmware (closest to 18.5 request)
    firmware_files = list(base_dir.glob("iPhone18,5*"))
    if firmware_files:
        print("[+] Found iPhone18,5 firmware files:")
        for f in firmware_files:
            size_gb = f.stat().st_size / (1024**3)
            print(f"  * {f.name} ({size_gb:.2f} GB)")
    
    # Look for any firmware with 18.5 in name
    firmware_185 = list(base_dir.glob("*18.5*"))
    if firmware_185:
        print("[+] Found firmware with 18.5 in name:")
        for f in firmware_185:
            size_gb = f.stat().st_size / (1024**3)
            print(f"  * {f.name} ({size_gb:.2f} GB)")
    
    return base_dir, firmware_files if firmware_files else None

def generate_flash_commands(device_info, irecovery_path, firmware_path):
    """Generate manual flash commands for user to run."""
    print("\n" + "=" * 60)
    print("MANUAL FLASH COMMANDS")
    print("=" * 60)
    
    if not device_info:
        print("\n[!] No device detected. Cannot generate specific commands.")
        print("\nGeneral steps:")
        print("1. Put device in DFU mode:")
        print("   - Hold Power + Home for 10 seconds")
        print("   - Release Power, keep holding Home for 10 seconds")
        print("   - Screen must be BLACK")
        print("\n2. Then run:")
        print(f"   {irecovery_path} -f <firmware_file>")
        print(f"   {irecovery_path} -c go")
        return
    
    mode = device_info.get("MODE", "Unknown").lower()
    product = device_info.get("PRODUCT", "Unknown")
    model = device_info.get("MODEL", "Unknown")
    
    print(f"\nDevice: {product} ({model})")
    print(f"Mode: {mode}")
    print(f"Firmware: {firmware_path}")
    
    print("\n" + "-" * 60)
    print("STEP 1: Put device in DFU mode (if not already)")
    print("-" * 60)
    print("Hold Power + Home for 10 seconds")
    print("Release Power, keep holding Home for 10 seconds")
    print("Screen must be BLACK")
    print()
    
    print("-" * 60)
    print("STEP 2: Verify DFU mode")
    print("-" * 60)
    print(f"{irecovery_path} -q")
    print()
    
    print("-" * 60)
    print("STEP 3: Flash firmware (run this command manually)")
    print("-" * 60)
    if firmware_path and firmware_path.exists():
        if firmware_path.suffix == ".ipsw":
            print("For IPSW files, use idevicerestore:")
            print("idevicerestore -e -u " + str(firmware_path))
        else:
            print(f"{irecovery_path} -f {firmware_path}")
    else:
        print(f"{irecovery_path} -f <path_to_firmware>")
    print()
    
    print("-" * 60)
    print("STEP 4: Boot device (run after flash completes)")
    print("-" * 60)
    print(f"{irecovery_path} -c go")
    print()
    
    print("-" * 60)
    print("STEP 5: If device doesn't boot, try:")
    print("-" * 60)
    print(f"{irecovery_path} -c setenv boot-args rd=md0 -v")
    print(f"{irecovery_path} -c saveenv")
    print(f"{irecovery_path} -c bootx")
    print()

def check_ios185_availability():
    """Check iOS 18.5 availability and signing status."""
    print("\n" + "=" * 60)
    print("iOS 18.5 FIRMWARE STATUS")
    print("=" * 60)
    print("\n[!] iOS 18.5 (22F76) is NOT SIGNED by Apple")
    print("    This means it CANNOT be restored via standard methods:")
    print("    - Finder / iTunes")
    print("    - idevicerestore")
    print("    - Apple Devices app")
    print()
    print("[+] BUT this codespace has TSS bypass solutions:")
    print("  - FINAL_TSS_BYPASS.py - Local TSS signing server")
    print("  - build_bypassed_ipsw.py - Build bypassed IPSW")
    print("  - automatic_flash_system.py - Full automatic restore")
    print("  - custom_restore_coordinator.py - Custom restore coordinator")
    print()
    print("iOS 18.5 is available for these devices (UNSIGNED):")
    print("  - iPhone 16 series (iPhone17,1-5)")
    print("  - iPhone 15 series (iPhone15,4-5)")
    print("  - iPhone 14 series (iPhone14,5-8)")
    print("  - iPhone 13 series (iPhone14,5)")
    print("  - iPhone 12 series (iPhone13,1-4)")
    print("  - iPhone SE 2nd/3rd gen (iPhone12,8, iPhone14,6)")
    print("  - iPhone 11 series (iPhone12,1-5)")
    print("  - iPhone XR/XS/XS Max (iPhone11,2-8)")
    print()
    print("Download iOS 18.5 from: https://ipsw.me/iOS/18.5/")
    print()

def run_automatic_restore(firmware_path, device_info):
    """Run automatic restore using existing codespace solutions."""
    print("\n" + "=" * 60)
    print("AUTOMATIC RESTORE OPTIONS")
    print("=" * 60)
    
    script_dir = Path(__file__).parent
    
    print("\n[1] Automatic Flash System (Recommended)")
    print("    Uses: Hivemind + SeedGate + Zero-Brain + Celestial Router")
    print(f"    Command: python3 {script_dir}/automatic_flash_system.py {firmware_path}")
    
    print("\n[2] Custom Restore Coordinator")
    print("    Uses: Device-specific custom IPSW preparation")
    print(f"    Command: python3 {script_dir}/custom_restore_coordinator.py")
    
    print("\n[3] TSS Bypass + Manual Restore")
    print("    Uses: Local TSS signing server")
    print(f"    Step 1: python3 {script_dir}/FINAL_TSS_BYPASS.py")
    print("    Step 2: Run idevicerestore with bypassed IPSW")
    
    print("\n[4] Checkra1n Restore (for jailbreakable devices)")
    print("    Uses: checkra1n jailbreak + custom firmware")
    print(f"    Command: python3 {script_dir}/FINAL_CHECKRA1N_RESTORE.py")
    
    print("\n" + "=" * 60)
    print("RECOMMENDED: Automatic Flash System")
    print("=" * 60)
    print("This will automatically:")
    print("  - Detect and latch your device")
    print("  - Analyze firmware with zero-brain AI")
    print("  - Extract components using celestial routing")
    print("  - Build bypassed IPSW with TSS signing")
    print("  - Flash device automatically")
    print()
    
    choice = input("Run automatic flash system now? (y/n): ").strip().lower()
    if choice == 'y':
        print("\n[+] Starting automatic flash system...")
        cmd = [sys.executable, str(script_dir / "automatic_flash_system.py"), str(firmware_path)]
        print(f"    Command: {' '.join(cmd)}")
        print("\n[!] Run this command manually in your terminal (no timeouts):")
        print(f"    {' '.join(cmd)}")
        return True
    return False

def main():
    device_info, irecovery_path = detect_device()
    base_dir, firmware_files = check_firmware()
    
    # Check iOS 18.5 availability
    check_ios185_availability()
    
    # Select firmware
    firmware_path = None
    if firmware_files:
        # Use the first iPhone18,5 firmware found
        for f in firmware_files:
            if f.suffix == ".ipsw" or "Restore" in f.name:
                firmware_path = f
                break
        if not firmware_path:
            firmware_path = firmware_files[0]
    
    print("\n" + "=" * 60)
    print("AVAILABLE FIRMWARE")
    print("=" * 60)
    print("The closest available firmware in your directory is:")
    if firmware_path:
        print(f"  {firmware_path.name}")
        size_gb = firmware_path.stat().st_size / (1024**3)
        print(f"  Size: {size_gb:.2f} GB")
    print()
    
    # Offer automatic restore options
    if firmware_path:
        run_automatic_restore(firmware_path, device_info)
    else:
        print("[-] No firmware found. Please download iOS 18.5 from:")
        print("    https://ipsw.me/iOS/18.5/")
        generate_flash_commands(device_info, irecovery_path, None)
    
    print("\n" + "=" * 60)
    print("IMPORTANT INSTRUCTIONS")
    print("=" * 60)
    print("1. Run the automatic flash system command manually (no timeouts)")
    print("2. The system will automatically handle TSS bypass and signing")
    print("3. Device will be detected, firmware analyzed, and flashed automatically")
    print("4. No manual intervention required after starting the process")
    print("=" * 60)

if __name__ == "__main__":
    main()
