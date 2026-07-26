#!/usr/bin/env python3
import subprocess
from pathlib import Path
from utils import PathConfig

cfg = PathConfig()
chargfast = cfg.chargfast_dir
irecovery = cfg.resolve_irecovery()

print("[+] Testing device connection...")
result = subprocess.run([str(irecovery), "-q"], capture_output=True, text=True, cwd=str(chargfast))
print(result.stdout)
print(result.stderr)

if result.returncode != 0:
    print(f"[-] irecovery failed with code {result.returncode}")
else:
    print("[+] Device connected")

print("\n[+] Testing file upload...")
extracted = chargfast / "extracted"
result = subprocess.run([str(irecovery), "-f", str(extracted / "Firmware/dfu/iBSS.k48ap.RELEASE.dfu")], 
                       capture_output=True, text=True, cwd=str(chargfast))
print("STDOUT:", result.stdout)
print("STDERR:", result.stderr)
print("Return code:", result.returncode)
