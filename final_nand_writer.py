#!/usr/bin/env python3
"""Final NAND writer - actually write filesystem to NAND"""
import subprocess
import time
from pathlib import Path
from utils import PathConfig

cfg = PathConfig()

def write_to_nand():
    chargfast_dir = cfg.chargfast_dir
    irecovery = cfg.resolve_irecovery()
    
    print("FINAL NAND WRITER")
    
    # Get pwned
    subprocess.run([str(irecovery), "-f", str(chargfast_dir / "extracted/Firmware/dfu/iBSS.k48ap.RELEASE.dfu")], cwd=str(chargfast_dir))
    subprocess.run([str(irecovery), "-c", "go"], cwd=str(chargfast_dir))
    time.sleep(2)
    subprocess.run([str(irecovery), "-f", str(chargfast_dir / "extracted/Firmware/dfu/iBEC.k48ap.RELEASE.dfu")], cwd=str(chargfast_dir))
    subprocess.run([str(irecovery), "-c", "go"], cwd=str(chargfast_dir))
    time.sleep(2)
    
    # Upload restore ramdisk
    print("[+] Loading restore ramdisk...")
    subprocess.run([str(irecovery), "-f", str(chargfast_dir / "extracted/038-1437-004.dmg")], cwd=str(chargfast_dir))
    subprocess.run([str(irecovery), "-c", "ramdisk"], cwd=str(chargfast_dir))
    
    # Upload devicetree
    subprocess.run([str(irecovery), "-f", "extracted/Firmware/all_flash/all_flash.k48ap.production/DeviceTree.k48ap.img3"], cwd=str(chargfast_dir))
    subprocess.run([str(irecovery), "-c", "devicetree"], cwd=str(chargfast_dir))
    
    # Upload kernel
    print("[+] Loading kernel...")
    subprocess.run([str(irecovery), "-f", "extracted/kernelcache.release.k48"], cwd=str(chargfast_dir))
    
    # Boot to ramdisk
    print("[+] Booting to restore ramdisk...")
    subprocess.run([str(irecovery), "-c", "bootx"], cwd=str(chargfast_dir))
    
    print("[+] Waiting for ramdisk boot (60 seconds)...")
    time.sleep(60)
    
    # Now device should be in restore mode with ramdisk
    # Use idevicerestore to finish (it will use ASR from ramdisk)
    print("[+] Using ASR to write filesystem...")
    subprocess.run([
        str(chargfast_dir / "idevicerestore"),
        "--no-input",
        str(cfg.base_dir / "iPad1,1_4.3.3_8J3_Restore.ipsw")
    ], cwd=str(chargfast_dir))
    
    print("[+] DONE")

if __name__ == "__main__":
    write_to_nand()