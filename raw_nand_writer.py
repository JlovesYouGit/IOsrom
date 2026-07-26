#!/usr/bin/env python3
"""
Raw NAND Writer for iPhone9,2
================================

Writes firmware components directly to NAND flash matching iPhone9,2 NAND layout.
Uses irecovery NAND commands for direct hardware access.

NAND Layout for iPhone9,2 (d11ap):
- 0x00000000: LLB (Low Level Bootloader)
- 0x00100000: iBoot (second stage bootloader)
- 0x00200000: DeviceTree
- 0x00300000: Kernelcache
- 0x00500000: Ramdisk
- 0x02500000: Root filesystem
- 0x02250000: SEP (Secure Enclave)
- 0x02270000: Baseband

This bypasses idevicerestore and flashes directly to hardware.
"""

import subprocess
import time
import plistlib
import zipfile
from pathlib import Path
from typing import Optional, Dict, List, Tuple


class RawNANDWriter:
    """Writes firmware directly to NAND flash."""
    
    def __init__(self, irecovery_path: Optional[Path] = None):
        self.irecovery = irecovery_path or Path("/usr/bin/irecovery")
        self.nand_commands = []
        self.device_info = None
    
    def detect_device(self) -> bool:
        """Detect device in Recovery/DFU mode."""
        try:
            result = subprocess.run(
                [str(self.irecovery), "-q"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode != 0:
                print("[-] No device detected")
                return False
            
            # Parse device info
            self.device_info = {}
            for line in result.stdout.splitlines():
                if ":" in line:
                    key, value = line.split(":", 1)
                    self.device_info[key.strip()] = value.strip()
            
            mode = self.device_info.get("MODE", "UNKNOWN")
            product = self.device_info.get("PRODUCT", "unknown")
            
            mode_upper = mode.upper()
            if "DFU" not in mode_upper and "RECOVERY" not in mode_upper:
                print(f"[-] Device not in DFU/Recovery mode: {mode}")
                return False
            
            print(f"[+] Device detected: {product} ({mode})")
            return True
            
        except Exception as e:
            print(f"[-] Device detection failed: {e}")
            return False
    
    def send_command(self, cmd: str, timeout: int = 30) -> Tuple[int, str, str]:
        """Send command to device via irecovery."""
        try:
            result = subprocess.run(
                [str(self.irecovery), "-c", cmd],
                capture_output=True, text=True, timeout=timeout
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            print(f"    [!] Command timed out: {cmd}")
            return -1, "", "timeout"
        except Exception as e:
            print(f"    [!] Command failed: {cmd}: {e}")
            return -1, "", str(e)
    
    def send_file(self, filepath: Path) -> bool:
        """Send file to device via irecovery."""
        try:
            result = subprocess.run(
                [str(self.irecovery), "-f", str(filepath)],
                capture_output=True, text=True, timeout=60
            )
            return result.returncode == 0
        except Exception as e:
            print(f"    [!] Failed to send file: {e}")
            return False
    
    def open_nand(self) -> bool:
        """Open NAND for writing."""
        print("[+] Opening NAND...")
        rc, out, err = self.send_command("nand open")
        if rc != 0:
            print(f"    [!] Failed to open NAND: {err}")
            return False
        print("    NAND opened")
        return True
    
    def close_nand(self) -> bool:
        """Close NAND after writing."""
        print("[+] Closing NAND...")
        rc, out, err = self.send_command("nand close")
        return rc == 0
    
    def erase_nand(self, offset: int, size: int) -> bool:
        """Erase NAND region."""
        print(f"[+] Erasing NAND 0x{offset:x} size 0x{size:x}...")
        rc, out, err = self.send_command(f"nand erase {offset} {size}", timeout=120)
        if rc != 0:
            print(f"    [!] Failed to erase NAND: {err}")
            return False
        print("    NAND erased")
        return True
    
    def write_to_nand(self, data: bytes, nand_address: int) -> bool:
        """Write data to NAND address."""
        print(f"[+] Writing {len(data):,} bytes to NAND 0x{nand_address:x}...")
        
        # Write data in chunks if needed
        chunk_size = 0x100000  # 1MB chunks
        offset = 0
        
        while offset < len(data):
            chunk = data[offset:offset + chunk_size]
            chunk_path = Path(f"/tmp/nand_chunk_{offset:x}.bin")
            chunk_path.write_bytes(chunk)
            
            if not self.send_file(chunk_path):
                print(f"    [!] Failed to send chunk at 0x{offset:x}")
                chunk_path.unlink(missing_ok=True)
                return False
            
            rc, out, err = self.send_command(f"nand write 0x{nand_address + offset:x}")
            if rc != 0:
                print(f"    [!] Failed to write chunk: {err}")
                chunk_path.unlink(missing_ok=True)
                return False
            
            offset += len(chunk)
            print(f"    Written 0x{offset:x} / 0x{len(data):x}")
        
        return True
    
    def read_from_nand(self, nand_address: int, size: int) -> Optional[bytes]:
        """Read data from NAND address."""
        print(f"[+] Reading {size:,} bytes from NAND 0x{nand_address:x}...")
        rc, out, err = self.send_command(f"nand read {nand_address} {size}", timeout=60)
        if rc != 0:
            print(f"    [!] Failed to read NAND: {err}")
            return None
        return out.encode() if isinstance(out, str) else out
    
    def set_boot_environment(self, boot_device: str = "nand0", boot_partition: int = 0) -> bool:
        """Set boot environment variables."""
        print("[+] Setting boot environment...")
        cmds = [
            f"setenv boot-device {boot_device}",
            f"setenv boot-partition {boot_partition}",
            "setenv auto-boot true",
            "saveenv",
        ]
        for cmd in cmds:
            rc, out, err = self.send_command(cmd)
            if rc != 0:
                print(f"    [!] Failed to set boot env: {err}")
                return False
        print("    Boot environment set")
        return True
    
    def reset_device(self) -> bool:
        """Reset device to boot."""
        print("[+] Resetting device...")
        rc, out, err = self.send_command("reset")
        return rc == 0
    
    def flash_ipsw_components(self, ipsw_path: Path) -> bool:
        """
        Extract and flash components from IPSW to NAND.
        
        Args:
            ipsw_path: Path to IPSW file
            
        Returns:
            True if successful, False otherwise
        """
        print(f"[+] Flashing IPSW: {ipsw_path}")
        
        if not ipsw_path.exists():
            print(f"[-] IPSW not found: {ipsw_path}")
            return False
        
        # Extract IPSW
        extract_dir = ipsw_path.parent / f"{ipsw_path.stem}_extracted"
        extract_dir.mkdir(exist_ok=True)
        
        print("[+] Extracting IPSW...")
        with zipfile.ZipFile(ipsw_path, 'r') as zf:
            zf.extractall(extract_dir)
        
        # Find components
        components = self._find_components(extract_dir)
        if not components:
            print("[-] No components found in IPSW")
            return False
        
        print(f"[+] Found {len(components)} components")
        
        # Open NAND
        if not self.open_nand():
            return False
        
        try:
            # Flash each component
            for name, comp_path, nand_addr, nand_size in components:
                print(f"\n[+] Flashing {name}...")
                data = comp_path.read_bytes()
                
                # Erase NAND region first
                self.erase_nand(nand_addr, max(nand_size, len(data)))
                
                # Write to NAND
                if not self.write_to_nand(data, nand_addr):
                    print(f"[-] Failed to flash {name}")
                    return False
                
                print(f"    [+] {name} flashed successfully")
            
            # Set boot environment
            if not self.set_boot_environment():
                return False
            
            return True
            
        finally:
            self.close_nand()
    
    def _find_components(self, extract_dir: Path) -> List[Tuple[str, Path, int, int]]:
        """Find firmware components in extracted IPSW."""
        components = []
        
        # Component mapping: filename_pattern -> (name, nand_address, nand_size)
        component_map = {
            "LLB": ("LLB.d11ap.RELEASE.img3", 0x00000000, 0x100000),
            "iBoot": ("iBoot.d11ap.RELEASE.img3", 0x00100000, 0x200000),
            "DeviceTree": ("DeviceTree.d11ap.img4", 0x00200000, 0x100000),
            "kernelcache": ("kernelcache.release.iphone9,2", 0x00300000, 0x400000),
            "ramdisk": ("ramdisk.dmg", 0x00500000, 0x2000000),
            "rootfs": ("rootfs.dmg", 0x02500000, 0x20000000),
            "SEP": ("sep-firmware.d11ap.RELEASE.im4p", 0x02250000, 0x200000),
            "Baseband": ("baseband.iphone9,2.RELEASE.im4p", 0x02270000, 0x500000),
            "iBSS": ("iBSS.d11ap.RELEASE.dfu", 0x00000000, 0x100000),
            "iBEC": ("iBEC.d11ap.RELEASE.dfu", 0x00000000, 0x200000),
        }
        
        for name, (filename, nand_addr, nand_size) in component_map.items():
            # Search for file in extracted directory
            matches = list(extract_dir.rglob(filename))
            if matches:
                components.append((name, matches[0], nand_addr, nand_size))
        
        return components
    
    def raw_flash_from_pfile(self, pfile_path: Path, output_dir: Path) -> bool:
        """
        Raw flash from PFILE by extracting components and writing to NAND.
        
        This is the ultimate raw metal approach.
        """
        print(f"[+] Raw flashing from PFILE: {pfile_path}")
        
        if not pfile_path.exists():
            print(f"[-] PFILE not found: {pfile_path}")
            return False
        
        # Open NAND
        if not self.open_nand():
            return False
        
        try:
            # Extract components using zero-brain
            from zero_brain_firmware import ZeroBrainFirmwareExtractor
            extractor = ZeroBrainFirmwareExtractor()
            
            print("[+] Analyzing PFILE...")
            data = pfile_path.read_bytes()[:20 * 1024 * 1024]
            context = extractor.ingest(data, max_scan=len(data))
            
            # Extract components
            extract_dir = output_dir / "pfile_extracted"
            extract_dir.mkdir(exist_ok=True)
            extracted = extractor.extract_components(data, extract_dir, min_confidence=0.3)
            
            if not extracted:
                print("[-] No components extracted from PFILE")
                return False
            
            print(f"[+] Extracted {len(extracted)} components")
            
            # Flash each component to NAND
            for comp_info in extracted:
                comp_path = Path(comp_info["path"])
                if not comp_path.exists():
                    continue
                
                comp_type = comp_info.get("type", "unknown")
                data = comp_path.read_bytes()
                
                # Find NAND address for this component type
                nand_addr = self._get_nand_address_for_type(comp_type)
                if nand_addr is None:
                    print(f"    [!] Unknown component type: {comp_type}, skipping")
                    continue
                
                print(f"\n[+] Flashing {comp_type} to NAND 0x{nand_addr:x}...")
                
                # Erase and write
                self.erase_nand(nand_addr, len(data))
                if not self.write_to_nand(data, nand_addr):
                    return False
                
                print(f"    [+] {comp_type} flashed")
            
            return True
            
        finally:
            self.close_nand()
    
    def _get_nand_address_for_type(self, comp_type: str) -> Optional[int]:
        """Get NAND address for component type."""
        mapping = {
            "iOS": 0x02500000,  # rootfs
            "GZIP": 0x02500000,  # compressed rootfs
            "IMG3": 0x00100000,  # iBoot
            "IMG4": 0x00200000,  # DeviceTree/SEP
            "XAR": 0x00300000,   # kernelcache
            "LZ4": 0x00500000,   # ramdisk
            "ZSTD": 0x00500000,  # compressed ramdisk
        }
        return mapping.get(comp_type)


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Raw NAND Writer for iPhone9,2")
    parser.add_argument("--ipsw", type=Path, help="IPSW file to flash")
    parser.add_argument("--pfile", type=Path, help="PFILE to extract and flash")
    parser.add_argument("--output-dir", type=Path, default=Path("/tmp/nand_flash"),
                       help="Output directory for extraction")
    parser.add_argument("--detect-only", action="store_true", help="Only detect device")
    parser.add_argument("--reset", action="store_true", help="Reset device after flash")
    
    args = parser.parse_args()
    
    writer = RawNANDWriter()
    
    # Detect device
    if not writer.detect_device():
        return 1
    
    if args.detect_only:
        print("\n[+] Device info:")
        for key, value in writer.device_info.items():
            print(f"    {key}: {value}")
        return 0
    
    success = False
    
    if args.ipsw:
        # Flash IPSW components
        success = writer.flash_ipsw_components(args.ipsw)
    elif args.pfile:
        # Raw flash from PFILE
        success = writer.raw_flash_from_pfile(args.pfile, args.output_dir)
    else:
        print("[-] Must specify --ipsw or --pfile")
        return 1
    
    if success and args.reset:
        writer.reset_device()
    
    return 0 if success else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
