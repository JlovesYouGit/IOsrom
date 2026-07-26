#!/usr/bin/env python3
import subprocess
import time
from pathlib import Path
from utils import PathConfig

cfg = PathConfig()
chargfast = cfg.chargfast_dir
extracted = chargfast / "extracted"
irecovery = cfg.resolve_irecovery()

print("[+] Loading iBSS...")
result = subprocess.run([str(irecovery), "-f", str(extracted / "Firmware/dfu/iBSS.k48ap.RELEASE.dfu")], cwd=str(chargfast))
if result.returncode != 0:
    print(f"[-] iBSS load failed with return code {result.returncode}")
    exit(1)
result = subprocess.run([str(irecovery), "-c", "go"], cwd=str(chargfast))
if result.returncode != 0:
    print(f"[-] iBSS go failed with return code {result.returncode}")
    exit(1)
time.sleep(2)

print("[+] Loading iBEC...")
result = subprocess.run([str(irecovery), "-f", str(extracted / "Firmware/dfu/iBEC.k48ap.RELEASE.dfu")], cwd=str(chargfast))
if result.returncode != 0:
    print(f"[-] iBEC load failed with return code {result.returncode}")
    exit(1)
result = subprocess.run([str(irecovery), "-c", "go"], cwd=str(chargfast))
if result.returncode != 0:
    print(f"[-] iBEC go failed with return code {result.returncode}")
    exit(1)
time.sleep(2)

print("[+] Loading ramdisk...")
result = subprocess.run([str(irecovery), "-f", str(extracted / "038-1437-004.dmg")], cwd=str(chargfast))
if result.returncode != 0:
    print(f"[-] ramdisk load failed with return code {result.returncode}")
    exit(1)
result = subprocess.run([str(irecovery), "-c", "ramdisk"], cwd=str(chargfast))
if result.returncode != 0:
    print(f"[-] ramdisk command failed with return code {result.returncode}")
    exit(1)

print("[+] Loading devicetree...")
result = subprocess.run([str(irecovery), "-f", str(extracted / "Firmware/all_flash/all_flash.k48ap.production/DeviceTree.k48ap.img3")], cwd=str(chargfast))
if result.returncode != 0:
    print(f"[-] devicetree load failed with return code {result.returncode}")
    exit(1)
result = subprocess.run([str(irecovery), "-c", "devicetree"], cwd=str(chargfast))
if result.returncode != 0:
    print(f"[-] devicetree command failed with return code {result.returncode}")
    exit(1)

print("[+] Loading kernel...")
result = subprocess.run([str(irecovery), "-f", str(extracted / "kernelcache.release.k48")], cwd=str(chargfast))
if result.returncode != 0:
    print(f"[-] kernel load failed with return code {result.returncode}")
    exit(1)

print("[+] Booting...")
result = subprocess.run([str(irecovery), "-c", "bootx"], cwd=str(chargfast))
if result.returncode != 0:
    print(f"[-] boot command failed with return code {result.returncode}")
    exit(1)

print("[+] Waiting 60s...")
time.sleep(60)

print("[+] Checking device mode...")
result = subprocess.run([str(irecovery), "-q"], capture_output=True, text=True, cwd=str(chargfast))
if result.returncode != 0:
    print(f"[-] Query failed with return code {result.returncode}")
else:
    print(result.stdout)
