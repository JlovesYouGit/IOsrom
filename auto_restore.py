#!/usr/bin/env python3
import subprocess
import time
from pathlib import Path
from utils import PathConfig
from utils import PathConfig

chargfast_dir = Path(str(Path(os.environ.get("IOS_TOOLS_BASE", "N:/ROMLOADDER")) / "chargfast via usb"))
irecovery = cfg.resolve_irecovery()
idevicerestore = chargfast_dir / "idevicerestore.exe"
ipsw = cfg.base_dir / "iPad1,1_4.3.3_8J3_Restore.ipsw"

print("AUTO RESTORE")

# Load iBSS/iBEC
print("[+] Loading iBSS...")
subprocess.run([str(irecovery), "-f", "extracted/Firmware/dfu/iBSS.k48ap.RELEASE.dfu"], cwd=str(chargfast_dir))
subprocess.run([str(irecovery), "-c", "go"], cwd=str(chargfast_dir))
time.sleep(2)

print("[+] Loading iBEC...")
subprocess.run([str(irecovery), "-f", "extracted/Firmware/dfu/iBEC.k48ap.RELEASE.dfu"], cwd=str(chargfast_dir))
subprocess.run([str(irecovery), "-c", "go"], cwd=str(chargfast_dir))
time.sleep(2)

# Restore with custom flag
print("[+] Starting restore...")
subprocess.run([
    str(idevicerestore),
    "--custom",
    "--erase", 
    "--no-input",
    "-R",
    str(ipsw)
], cwd=str(chargfast_dir))

print("[+] Done")
