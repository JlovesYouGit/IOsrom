#!/usr/bin/env python3
"""
Detect iOS/iPad/iPod devices connected to USB ports.
Uses Windows WMI/PowerShell and common iOS tooling when available.
"""
import os
import sys
import subprocess
import platform
from pathlib import Path
from utils import PathConfig

APPLE_VENDOR_ID = "0x05AC"
IOS_MODEL_HINTS = [
    "iPhone",
    "iPad",
    "iPod",
    "Apple Mobile Device",
    "Apple Device",
]


cfg = PathConfig()

def run_cmd(cmd, **kwargs):
    try:
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=kwargs.get("timeout", 15),
            **{k: v for k, v in kwargs.items() if k != "timeout"},
        )
    except Exception as exc:
        print(f"[!] Command failed: {' '.join(cmd)}\n    {exc}")
        return None


def detect_by_wmi():
    print("[+] Detecting devices via WMI...")
    result = run_cmd([
        "wmic", "path", "Win32_USBHub", "get", "DeviceID,Description,PNPDeviceID"
    ])
    if not result or not result.stdout.strip():
        print("[!] WMI returned no USB info")
        return []

    devices = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line or line.startswith("DeviceID") or line.startswith("Description"):
            continue
        joined = " | ".join(
            part.strip()
            for part in line.split()
            if part.strip()
        )
        if any(hint.lower() in joined.lower() for hint in IOS_MODEL_HINTS):
            devices.append(joined)
    return devices


def detect_by_powershell():
    print("[+] Detecting devices via PowerShell CIM...")
    ps_script = (
        "Get-CimInstance Win32_USBHub | "
        "Select-Object DeviceID,Description,PNPDeviceID | "
        "Format-List"
    )
    result = run_cmd(["powershell", "-Command", ps_script])
    if not result or not result.stdout.strip():
        print("[!] PowerShell returned no USB info")
        return []

    devices = []
    current = {}
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            if current and any(
                hint.lower() in current.get("Description", "").lower()
                for hint in IOS_MODEL_HINTS
            ):
                devices.append(current)
            current = {}
            continue
        if ":" in line:
            key, val = line.split(":", 1)
            current[key.strip()] = val.strip()

    if current and any(
        hint.lower() in current.get("Description", "").lower()
        for hint in IOS_MODEL_HINTS
    ):
        devices.append(current)
    return devices


def detect_by_pnputil():
    print("[+] Detecting Apple devices via pnputil...")
    result = run_cmd(["pnputil", "/enum-devices", "/class", "USB"])
    if not result or not result.stdout.strip():
        print("[!] pnputil returned no USB info")
        return []

    devices = []
    for line in result.stdout.splitlines():
        if any(hint.lower() in line.lower() for hint in IOS_MODEL_HINTS):
            devices.append(line.strip())
    return devices


def detect_by_libimobiledevice():
    print("[+] Trying idevice_id / idevicerestore detection...")
    tool_candidates = ["idevice_id", "idevicerestore", "irecovery"]
    found = []

    for tool in tool_candidates:
        path = shutil_which(tool)
        if not path:
            continue
        if tool == "idevice_id":
            result = run_cmd([path, "-l"])
            if result and result.stdout.strip():
                found.append(f"idevice_id:\n{result.stdout.strip()}")
        elif tool == "irecovery":
            result = run_cmd([path, "-q"])
            if result and result.stdout.strip():
                found.append(f"irecovery:\n{result.stdout.strip()}")
    return found


def shutil_which(name):
    path = os.environ.get("PATH", "")
    for folder in path.split(os.pathsep):
        candidate = Path(folder) / f"{name}.exe"
        if candidate.exists():
            return str(candidate)
    return None


def detect_apple_mobile_service():
    print("[+] Checking Apple Mobile Device Service...")
    result = run_cmd(["sc", "query", "Apple Mobile Device Service"])
    if result and "RUNNING" in result.stdout:
        print("[+] Apple Mobile Device Service is running")
        return True
    print("[!] Apple Mobile Device Service is not running")
    return False


def detect_dfu_recovery_mode():
    print("[+] Checking for DFU / Recovery mode devices...")
    result = run_cmd(["powershell", "-Command", "Get-PnpDevice -Class WPD | Format-List"])
    if not result or not result.stdout.strip():
        print("[!] No WPD devices detected")
        return []

    devices = []
    for line in result.stdout.splitlines():
        if "Apple" in line or "iPhone" in line or "iPad" in line or "iPod" in line:
            devices.append(line.strip())
    return devices


def main():
    if platform.system() != "Windows":
        print("[!] This detector is intended for Windows hosts.")
        return 1

    print("=" * 60)
    print("USB iOS DEVICE DETECTOR")
    print("=" * 60)
    print()

    apple_mobile_running = detect_apple_mobile_service()
    print()

    wmi_devices = detect_by_wmi()
    ps_devices = detect_by_powershell()
    pnp_devices = detect_by_pnputil()
    tools_info = detect_by_libimobiledevice()
    dfu_devices = detect_dfu_recovery_mode()

    print()
    print("=" * 60)
    print("DETECTION RESULTS")
    print("=" * 60)

    found = False

    if wmi_devices:
        found = True
        print("\n[WMI] Apple USB devices:")
        for device in wmi_devices:
            print(f"  * {device}")

    if ps_devices:
        found = True
        print("\n[PowerShell] Apple USB devices:")
        for device in ps_devices:
            print(f"  * {device}")

    if pnp_devices:
        found = True
        print("\n[pnputil] Apple USB devices:")
        for device in pnp_devices:
            print(f"  * {device}")

    if tools_info:
        found = True
        print("\n[iOS tools] Device info:")
        for info in tools_info:
            print(info)

    if dfu_devices:
        found = True
        print("\n[WPD] Apple devices:")
        for device in dfu_devices:
            print(f"  * {device}")

    if not found:
        print("\n[!] No iOS/iPad/iPod device detected on USB.")
        print("\nTroubleshooting:")
        print("1. Connect device via USB cable")
        print("2. Trust this computer if prompted on device")
        print("3. Install Apple Mobile Device Service / iTunes")
        print("4. Try a different USB port")
        return 1

    if not apple_mobile_running:
        print("\n[!] Warning: Apple Mobile Device Service is not running.")
        print("    Install iTunes or Apple Mobile Device Support.")
    return 0


if __name__ == "__main__":
    sys.exit(main())