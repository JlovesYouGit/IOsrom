#!/usr/bin/env python3
"""Fix bootloop - kernel/filesystem issue"""
import subprocess
import time
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

def fix_bootloop():
    """Fix the fucking bootloop"""
    from utils import PathConfig
    cfg = PathConfig()
    irecovery = cfg.chargfast_dir / 'irecovery'
    if not irecovery.exists() and (cfg.chargfast_dir / cfg.resolve_irecovery()).exists():
        irecovery = cfg.resolve_irecovery()
    
    print("🔧 BOOTLOOP FIXER")
    print("Apple logo loop = bootloader works, kernel/fs fucked")
    print()
    
    # Force device back to recovery
    print("[+] Forcing back to recovery mode...")
    time.sleep(5)  # Wait for bootloop
    
    # Try to catch it
    for i in range(10):
        try:
            result = subprocess.run([str(irecovery), "-q"], capture_output=True, text=True, timeout=2)
            if result.returncode == 0:
                logger.info("Caught device in recovery")
                break
        except Exception as e:
            logger.debug(f"Recovery check attempt {i} failed: {e}")
        time.sleep(1)
    
    # Get pwned again
    subprocess.run([str(irecovery), "-f", str(cfg.extracted_dir / "Firmware/dfu/iBSS.k48ap.RELEASE.dfu")], cwd=str(cfg.chargfast_dir))
    subprocess.run([str(irecovery), "-c", "go"], cwd=str(cfg.chargfast_dir))
    time.sleep(2)
    subprocess.run([str(irecovery), "-f", str(cfg.extracted_dir / "Firmware/dfu/iBEC.k48ap.RELEASE.dfu")], cwd=str(cfg.chargfast_dir))
    subprocess.run([str(irecovery), "-c", "go"], cwd=str(cfg.chargfast_dir))
    time.sleep(2)
    
    # Fix the kernel issue
    logger.info("Fixing kernel boot arguments")
    kernel_fixes = [
        "setenv boot-args -v debug=0x14e",  # Verbose + debug
        "setenv boot-device nand0s1",       # Correct boot device
        "setenv boot-path /",               # Root path
        "saveenv"
    ]
    
    for fix in kernel_fixes:
        subprocess.run([str(irecovery), "-c", fix], cwd=str(cfg.chargfast_dir))
    
    # Try different kernel
    logger.info("Trying different kernels")
    kernels = [
        cfg.extracted_dir / "kernelcache.release.k48",
        cfg.base_dir / "iPad1,1_iOS9_A4_Final/kernelcache.release.k48",
        cfg.base_dir / "workspace/kernelcache.patched"
    ]
    
    for kernel in kernels:
        if Path(kernel).exists():
            logger.info(f"Testing kernel: {Path(kernel).name}")
            subprocess.run([str(irecovery), "-f", str(kernel)], cwd=str(cfg.chargfast_dir))
            subprocess.run([str(irecovery), "-c", "bootx"], cwd=str(cfg.chargfast_dir))
            time.sleep(10)
            
            # Check if it worked
            try:
                result = subprocess.run([str(irecovery), "-q"], capture_output=True, timeout=2)
                if result.returncode != 0:
                    logger.info("SUCCESS! Device booted")
                    return True
            except Exception:
                logger.info("SUCCESS! Device booted")
                return True
            
            logger.warning("Still in bootloop, trying next kernel")
    
    logger.error("All kernels failed. Filesystem issue.")
    return False

if __name__ == "__main__":
    fix_bootloop()