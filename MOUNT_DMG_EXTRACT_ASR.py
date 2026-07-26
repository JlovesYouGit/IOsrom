#!/usr/bin/env python3
import subprocess
import gzip
import shutil
from pathlib import Path
from utils import PathConfig
from utils import PathConfig

chargfast = cfg.chargfast_dir
extracted = chargfast / "extracted"

# Extract ASR binary from restore ramdisk
ramdisk = extracted / "038-1437-004.dmg"
output_dir = cfg.base_dir / "asr_extracted"
output_dir.mkdir(exist_ok=True)

print("[+] Extracting restore ramdisk...")
# Use 7z to extract DMG
subprocess.run(["7z", "x", str(ramdisk), f"-o{output_dir}"], check=True)

print("[+] Looking for ASR binary...")
asr_path = output_dir / "usr" / "sbin" / "asr"
if asr_path.exists():
    print(f"[+] Found ASR at: {asr_path}")
    print(f"[+] Size: {asr_path.stat().st_size} bytes")
else:
    print("[-] ASR not found, searching...")
    for f in output_dir.rglob("*asr*"):
        print(f"    {f}")
