#!/usr/bin/env python3
import subprocess
import time
from pathlib import Path
from utils import PathConfig

cfg = PathConfig()
chargfast = cfg.chargfast_dir
extracted = chargfast / "extracted"
irecovery = cfg.resolve_irecovery()

result = subprocess.run([str(irecovery), "-f", str(extracted / "Firmware/dfu/iBSS.k48ap.RELEASE.dfu")], cwd=str(chargfast))
if result.returncode != 0:
    print(f"[-] iBSS load failed with return code {result.returncode}")
    exit(1)
result = subprocess.run([str(irecovery), "-c", "go"], cwd=str(chargfast))
if result.returncode != 0:
    print(f"[-] iBSS go failed with return code {result.returncode}")
    exit(1)
time.sleep(2)

result = subprocess.run([str(irecovery), "-f", str(extracted / "Firmware/dfu/iBEC.k48ap.RELEASE.dfu")], cwd=str(chargfast))
if result.returncode != 0:
    print(f"[-] iBEC load failed with return code {result.returncode}")
    exit(1)
result = subprocess.run([str(irecovery), "-c", "go"], cwd=str(chargfast))
if result.returncode != 0:
    print(f"[-] iBEC go failed with return code {result.returncode}")
    exit(1)
time.sleep(2)

result = subprocess.run([str(irecovery), "-f", str(extracted / "038-1437-004.dmg")], cwd=str(chargfast))
if result.returncode != 0:
    print(f"[-] ramdisk load failed with return code {result.returncode}")
    exit(1)
result = subprocess.run([str(irecovery), "-c", "ramdisk"], cwd=str(chargfast))
if result.returncode != 0:
    print(f"[-] ramdisk command failed with return code {result.returncode}")
    exit(1)

result = subprocess.run([str(irecovery), "-f", str(extracted / "Firmware/all_flash/all_flash.k48ap.production/DeviceTree.k48ap.img3")], cwd=str(chargfast))
if result.returncode != 0:
    print(f"[-] devicetree load failed with return code {result.returncode}")
    exit(1)
result = subprocess.run([str(irecovery), "-c", "devicetree"], cwd=str(chargfast))
if result.returncode != 0:
    print(f"[-] devicetree command failed with return code {result.returncode}")
    exit(1)

result = subprocess.run([str(irecovery), "-f", str(extracted / "kernelcache.release.k48")], cwd=str(chargfast))
if result.returncode != 0:
    print(f"[-] kernel load failed with return code {result.returncode}")
    exit(1)
result = subprocess.run([str(irecovery), "-c", "fsboot"], cwd=str(chargfast))
if result.returncode != 0:
    print(f"[-] fsboot command failed with return code {result.returncode}")
    exit(1)

print("Wait 60s then check device with: irecovery -q")
