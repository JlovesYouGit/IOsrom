#!/usr/bin/env python3
import subprocess
from pathlib import Path
from utils import PathConfig
from utils import PathConfig

chargfast = cfg.chargfast_dir
irecovery = cfg.resolve_irecovery()

print("[+] Current device state:")
result = subprocess.run([str(irecovery), "-q"], capture_output=True, text=True, cwd=str(chargfast))
print(result.stdout)

if "Recovery" in result.stdout:
    print("\n[+] Device in Recovery mode - entering DFU mode...")
    subprocess.run([str(irecovery), "-c", "setenv auto-boot false"], cwd=str(chargfast))
    subprocess.run([str(irecovery), "-c", "saveenv"], cwd=str(chargfast))
    subprocess.run([str(irecovery), "-c", "reset"], cwd=str(chargfast))
    
    print("\n[!] Device will reboot to DFU mode")
    print("[!] Wait 10 seconds then run: python DFU_LOAD_DIRECT.py")
else:
    print("\n[-] Device not in Recovery mode")
