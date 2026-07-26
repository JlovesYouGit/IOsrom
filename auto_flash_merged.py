#!/usr/bin/env python3
"""
Auto-detect connected iOS device and flash firmware from merged_firmware.PFILE.

Pipeline:
  1. Detect device via irecovery -q
  2. Map to firmware family (iPhone9,2 -> iPhone8,2)
  3. Extract matching slice from merged_firmware.PFILE
  4. Convert PFILE slice to flashable IPSW if possible
  5. Flash using idevicerestore or irecovery kit
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

# PFILE converter is in the same directory
sys.path.insert(0, str(Path(__file__).resolve().parent))

CONVERTER_AVAILABLE = False
try:
    from pfile2ipsw import convert_pfile_to_ipsw
    CONVERTER_AVAILABLE = True
except ImportError:
    pass

FIRMWARE_MAP = {
    "iPhone8,2":  (0, 5555860816, "iPhone8,2_iOS15.8.8_19H422"),
    "N56AP":      (0, 5555860816, "iPhone8,2_iOS15.8.8_19H422"),
    "iPhone18,5": (5555860816, 10954737840, "iPhone18,5_iOS26.5.2_23F84"),
}

FAMILY_MAP = {
    "iPhone8,1": "iPhone8,2",
    "iPhone8,2": "iPhone8,2",
    "iPhone9,1": "iPhone18,5",
    "iPhone9,2": "iPhone18,5",
    "iPhone9,3": "iPhone18,5",
    "iPhone9,4": "iPhone18,5",
    "iPhone10,1": "iPhone8,2",
    "iPhone10,2": "iPhone8,2",
    "iPhone10,3": "iPhone8,2",
    "iPhone10,4": "iPhone8,2",
    "iPhone10,5": "iPhone8,2",
    "iPhone18,1": "iPhone18,5",
    "iPhone18,2": "iPhone18,5",
    "iPhone18,3": "iPhone18,5",
    "iPhone18,4": "iPhone18,5",
    "iPhone18,5": "iPhone18,5",
}

BASE_DIR = Path("/home/j/Downloads/ios romm/firmware")
MERGED_BLOB = BASE_DIR / "merged_firmware.PFILE"
OUTPUT_DIR = BASE_DIR / "auto_flash_output"
CHUNK_SIZE = 4 * 1024 * 1024


def run_cmd(cmd: list[str], timeout: int = 30) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError:
        print(f"[-] Command not found: {cmd[0]}")
        raise
    except subprocess.TimeoutExpired:
        print(f"[-] Command timed out: {' '.join(cmd)}")
        raise


def resolve_irecovery() -> Path:
    candidates = [
        Path("/usr/bin/irecovery"),
        Path("/usr/local/bin/irecovery"),
        Path("/home/j/Downloads/ios romm/IOsrom/chargfast via usb/irecovery"),
        Path("/home/j/Downloads/ios romm/IOsrom/chargfast via usb/irecovery.exe"),
        Path("/home/j/Downloads/ios romm/chargfast via usb/irecovery"),
        Path("/home/j/Downloads/ios romm/chargfast via usb/irecovery.exe"),
    ]
    for c in candidates:
        if c.exists():
            return c
    return Path("irecovery")


def detect_device() -> dict[str, str] | None:
    irecovery = resolve_irecovery()
    print(f"[1] Querying device via: {irecovery}")
    try:
        result = run_cmd([str(irecovery), "-q"], timeout=15)
    except Exception:
        return None

    if result.returncode != 0 or not result.stdout.strip():
        print("[-] irecovery query failed or no output")
        return None

    info: dict[str, str] = {}
    for line in result.stdout.strip().splitlines():
        if ":" in line:
            key, val = line.split(":", 1)
            info[key.strip()] = val.strip()

    mode = info.get("MODE", "Unknown")
    product = info.get("PRODUCT", "Unknown")
    model = info.get("MODEL", "Unknown")
    name = info.get("NAME", "Unknown")
    print(f"[+] Device detected: {name}")
    print(f"    Product: {product}")
    print(f"    Model: {model}")
    print(f"    Mode: {mode}")
    return info


def match_firmware_family(device_info: dict[str, str]) -> str | None:
    product = device_info.get("PRODUCT", "")
    model = device_info.get("MODEL", "")

    if product in FIRMWARE_MAP:
        return product
    if model in FIRMWARE_MAP:
        return model
    if product in FAMILY_MAP:
        return FAMILY_MAP[product]
    if model in FAMILY_MAP:
        return FAMILY_MAP[model]

    print(f"[-] No firmware mapping for PRODUCT={product}, MODEL={model}")
    return None


def extract_slice(family: str, output_path: Path) -> bool:
    offset, size, _ = FIRMWARE_MAP[family]
    if not MERGED_BLOB.exists():
        print(f"[-] Merged blob not found: {MERGED_BLOB}")
        return False

    print(f"[2] Extracting {family} firmware from merged blob:")
    print(f"    Offset: {offset:,} bytes")
    print(f"    Size: {size:,} bytes")
    print(f"    Output: {output_path}")

    if output_path.exists():
        output_path.unlink()

    try:
        with MERGED_BLOB.open("rb") as fin, output_path.open("wb") as fout:
            fin.seek(offset)
            remaining = size
            while remaining > 0:
                chunk = fin.read(min(CHUNK_SIZE, remaining))
                if not chunk:
                    break
                fout.write(chunk)
                remaining -= len(chunk)
    except Exception as e:
        print(f"[-] Extraction failed: {e}")
        return False

    actual = output_path.stat().st_size
    if actual == size:
        print(f"[+] Extracted successfully: {actual:,} bytes")
        return True
    print(f"[-] Size mismatch: expected {size}, got {actual}")
    return False


def convert_extracted_slice(pfile_path: Path, family: str) -> Path | None:
    """Convert extracted PFILE slice to a usable flashable format."""
    output_dir = OUTPUT_DIR / f"{family}_converted"
    output_dir.mkdir(parents=True, exist_ok=True)

    if not CONVERTER_AVAILABLE:
        print("[-] PFILE converter module not available")
        return None

    print(f"[3] Converting PFILE slice to flashable format...")
    converted = convert_pfile_to_ipsw(pfile_path, output_dir)
    if converted:
        print(f"[+] Converted to: {converted}")
        return converted
    print("[-] Conversion did not produce valid IPSW")
    return None


def find_idevicerestore() -> Path | None:
    candidates = [
        Path("/usr/local/bin/idevicerestore"),
        Path("/usr/bin/idevicerestore"),
        Path("/home/j/Downloads/ios romm/IOsrom/chargfast via usb/idevicerestore"),
        Path("/home/j/Downloads/ios romm/IOsrom/chargfast via usb/idevicerestore.exe"),
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def flash_with_idevicerestore(idevicerestore: Path, firmware_path: Path, pwn: bool = False, extra_args: list[str] | None = None) -> bool:
    print("[4] Flashing via idevicerestore...")
    cmd = [str(idevicerestore)]
    if pwn:
        cmd.append("--pwn")
    if extra_args:
        cmd.extend(extra_args)
    cmd.append(str(firmware_path))
    print(f"    Command: {' '.join(cmd)}")
    try:
        result = run_cmd(cmd, timeout=1800)
        print(f"    Return code: {result.returncode}")
        if result.stdout:
            print(f"    Output: {result.stdout.strip()}")
        if result.stderr:
            print(f"    Errors: {result.stderr.strip()}")
        return result.returncode == 0
    except Exception as e:
        print(f"[-] idevicerestore flash failed: {e}")
        return False


def flash_with_irecovery(irecovery: Path, firmware_path: Path, device_info: dict[str, str]) -> bool:
    print("[4] Attempting flash via irecovery (project kit)...")
    model = device_info.get("MODEL", "")
    name = device_info.get("NAME", "Unknown")

    print(f"    Device: {name} ({model})")
    print(f"    Firmware: {firmware_path.name}")

    # Direct flash assumes the file is a single bootable payload
    # This works for iBSS/iBEC/kernel when loaded individually
    cmd = [str(irecovery), "-f", str(firmware_path)]
    print(f"    Command: {' '.join(cmd)}")
    try:
        result = run_cmd(cmd, timeout=120)
        print(f"    Return code: {result.returncode}")
        if result.stdout:
            print(f"    Output: {result.stdout.strip()}")
        if result.stderr:
            print(f"    Errors: {result.stderr.strip()}")
        return result.returncode == 0
    except Exception as e:
        print(f"[-] irecovery flash failed: {e}")
        return False


def print_fallback_instructions(firmware_path: Path, device_info: dict[str, str]) -> None:
    name = device_info.get("NAME", "Unknown")
    product = device_info.get("PRODUCT", "Unknown")
    model = device_info.get("MODEL", "Unknown")

    print("\n[!] Automated flash failed. Manual steps required.")
    print("=" * 60)
    print(f"Device: {name} ({product} / {model})")
    print(f"Firmware: {firmware_path}")
    print()
    print("Option A: Manually with project kit (irecovery)")
    print("  1. Put device in DFU mode:")
    print("     - Hold Power + Home 10s")
    print("     - Release Power, keep holding Home 10s")
    print("     - Screen must be BLACK")
    print(f"  2. Load firmware:")
    print(f"     irecovery -f {firmware_path}")
    print("  3. If needed, load accompanying components:")
    print(f"     irecovery -f <iBSS path>")
    print("     irecovery -c go")
    print("     irecovery -c setenv boot-args rd=md0 -v")
    print("     irecovery -c bootx")
    print()
    print("Option B: Use converted IPSW if available")
    print("  1. Install idevicerestore if missing")
    print("  2. Run: idevicerestore -e -u <converted.ipsw>")
    print("=" * 60)


def main() -> int:
    print("=" * 60)
    print("AUTO FLASH - Merged Firmware Blob (Project Kit)")
    print("=" * 60)

    if not MERGED_BLOB.exists():
        print(f"[-] Merged blob not found: {MERGED_BLOB}")
        print("[!] Run merge_firmware.py first")
        return 1

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    device_info = detect_device()
    if not device_info:
        print("[-] No device detected. Ensure device is connected and in Recovery/DFU mode.")
        return 1

    family = match_firmware_family(device_info)
    if not family:
        return 1

    _, _, output_name = FIRMWARE_MAP[family]
    output_path = OUTPUT_DIR / f"{output_name}.PFILE"

    if not extract_slice(family, output_path):
        return 1

    # Try conversion
    flashable = convert_extracted_slice(output_path, family)

    # Determine flash path
    irecovery = resolve_irecovery()
    idevicerestore = find_idevicerestore()
    target = flashable if flashable and flashable.exists() else output_path

    flashed = False
    if idevicerestore and flashable and flashable.suffix == ".ipsw":
        pwn = device_info.get("MODE", "").lower() == "dfu"
        flashed = flash_with_idevicerestore(idevicerestore, flashable, pwn=pwn)
    elif device_info.get("MODE", "").lower() in ("recovery", "dfu"):
        flashed = flash_with_irecovery(irecovery, target, device_info)
    else:
        # Try irecovery anyway
        flashed = flash_with_irecovery(irecovery, target, device_info)

    if not flashed:
        print_fallback_instructions(target, device_info)
        return 1

    print("\n[+] Flash command completed")
    print(f"[+] Firmware source: {output_path}")
    if flashable and flashable != output_path:
        print(f"[+] Converted IPSW: {flashable}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
