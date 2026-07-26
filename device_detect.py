import hashlib
import json
import os
import re
import subprocess
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class iOSDevice:
    udid: str = ""
    ecid: str = ""
    device_type: str = ""
    product_type: str = ""
    mode: str = "unknown"
    recovery_mode: bool = False
    dfu_mode: bool = False
    normal_mode: bool = False
    restore_mode: bool = False
    connected: bool = False
    detected_at: float = field(default_factory=time.time)
    ipsw_match: str | None = None
    hardware_model: str = ""
    os_version: str = ""
    build_version: str = ""
    serial_number: str = ""


@dataclass
class DeviceDetectResult:
    success: bool = False
    devices: list[dict[str, Any]] = field(default_factory=list)
    total_detected: int = 0
    recovery_devices: list[str] = field(default_factory=list)
    available_ipsws: list[str] = field(default_factory=list)
    matched_ipsw: dict[str, str] = field(default_factory=dict)
    firmware_manifest: dict[str, Any] = field(default_factory=dict)
    recommended_firmware: dict[str, str] = field(default_factory=dict)
    error: str | None = None
    timestamp: float = field(default_factory=time.time)


IPSWS = [
    "/home/j/Downloads/ios romm/firmware",
    "/home/j/Downloads/ios romm",
    "/home/j/Downloads/ios romm/firmware/auto_flash_output",
]

FIRMWARE_MANIFEST_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "firmware_manifest.json"
)

IPSW_EXTENSIONS = {".ipsw", ".PFILE"}

DEVICE_MODEL_MAP = {
    "iPhone8,2": "iPhone 8 Plus",
    "iPhone8,1": "iPhone 8",
    "iPhone9,1": "iPhone 7",
    "iPhone9,2": "iPhone 7 Plus",
    "iPhone9,3": "iPhone 7",
    "iPhone9,4": "iPhone 7 Plus",
    "iPhone10,1": "iPhone 8",
    "iPhone10,2": "iPhone 8 Plus",
    "iPhone10,3": "iPhone X",
    "iPhone10,4": "iPhone 8",
    "iPhone10,5": "iPhone 8 Plus",
    "iPhone10,6": "iPhone X",
    "iPhone11,2": "iPhone XS",
    "iPhone11,4": "iPhone XS Max",
    "iPhone11,6": "iPhone XS Max",
    "iPhone11,8": "iPhone XR",
    "iPhone12,1": "iPhone 11",
    "iPhone12,3": "iPhone 11 Pro",
    "iPhone12,5": "iPhone 11 Pro Max",
    "iPhone12,8": "iPhone SE (2nd gen)",
    "iPhone13,1": "iPhone 12 mini",
    "iPhone13,2": "iPhone 12",
    "iPhone13,3": "iPhone 12 Pro",
    "iPhone13,4": "iPhone 12 Pro Max",
    "iPhone14,2": "iPhone 13 Pro",
    "iPhone14,3": "iPhone 13 Pro Max",
    "iPhone14,4": "iPhone 13 mini",
    "iPhone14,5": "iPhone 13",
    "iPhone14,6": "iPhone SE (3rd gen)",
    "iPhone14,7": "iPhone 14",
    "iPhone14,8": "iPhone 14 Plus",
    "iPhone15,2": "iPhone 14 Pro",
    "iPhone15,3": "iPhone 14 Pro Max",
    "iPhone15,4": "iPhone 15",
    "iPhone15,5": "iPhone 15 Plus",
    "iPhone15,6": "iPhone 15 Pro",
    "iPhone15,7": "iPhone 15 Pro Max",
    "iPhone16,1": "iPhone 16e",
    "iPhone16,2": "iPhone 16",
    "iPhone16,3": "iPhone 16 Pro",
    "iPhone16,4": "iPhone 16 Pro Max",
}


def _run_idevice_id() -> list[str]:
    try:
        result = subprocess.run(
            ["idevice_id", "-l"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            return [u.strip() for u in result.stdout.strip().splitlines() if u.strip()]
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    return []


def _run_ideviceinfo(udid: str) -> dict[str, str]:
    info: dict[str, str] = {}
    try:
        result = subprocess.run(
            ["ideviceinfo", "-u", udid],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                if ":" in line:
                    key, _, val = line.partition(":")
                    info[key.strip()] = val.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    return info


def _run_idevicerestore_mode(udid: str) -> str:
    try:
        result = subprocess.run(
            ["idevicerestore", "-i", udid],
            capture_output=True, text=True, timeout=10,
        )
        output = (result.stdout + result.stderr).lower()
        if "recovery" in output or "recovery mode" in output:
            return "recovery"
        if "dfu" in output:
            return "dfu"
        if "normal" in output:
            return "normal"
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    return "unknown"


def _detect_device_mode(udid: str) -> str:
    try:
        result = subprocess.run(
            ["ideviceenterrecovery", "-u", udid],
            capture_output=True, text=True, timeout=5,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass

    try:
        result = subprocess.run(
            ["ideviceinfo", "-u", udid],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            return "normal"
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass

    return "recovery"


def _find_ipsw_files() -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for directory in IPSWS:
        if not os.path.isdir(directory):
            continue
        for root, _dirs, files in os.walk(directory):
            for fname in files:
                ext = os.path.splitext(fname)[1].lower()
                if ext in IPSW_EXTENSIONS:
                    full_path = os.path.join(root, fname)
                    if full_path not in seen:
                        seen.add(full_path)
                        found.append(full_path)
    return found


def _load_firmware_manifest() -> dict:
    if os.path.exists(FIRMWARE_MANIFEST_PATH):
        try:
            with open(FIRMWARE_MANIFEST_PATH, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {}


def _parse_ipsw_version(filename: str) -> tuple[str, str]:
    base = os.path.splitext(filename)[0]
    m = re.search(r"(\d+\.\d+(?:\.\d+)?)[_\-](\d+[A-Z]\d+)", base)
    if m:
        return m.group(1), m.group(2)
    return "", ""


def _validate_ipsw(path: str) -> bool:
    if not os.path.isfile(path):
        return False
    try:
        import zipfile
        with zipfile.ZipFile(path, "r") as zf:
            names = zf.namelist()
            if not names:
                return False
            has_manifest = any(
                n.lower().endswith("manifest.plist") or n.lower().endswith("buildmanifest.plist")
                for n in names
            )
            return has_manifest
    except (zipfile.BadZipFile, OSError):
        return False


def _match_ipsw_to_device(device: iOSDevice) -> str | None:
    if not device.product_type:
        return None

    ipsws = _find_ipsw_files()
    valid_ipsws = [ip for ip in ipsws if _validate_ipsw(ip)]

    if not valid_ipsws:
        return None

    manifest = _load_firmware_manifest()
    manifest_fws = manifest.get("firmwares", [])

    matched_manifest = None
    for mfw in manifest_fws:
        if mfw.get("product_type") == device.product_type and mfw.get("signed"):
            matched_manifest = mfw
            break

    pt_normalized = device.product_type.lower().replace(",", "_")

    best_local = None
    best_version = (0, 0)

    for ipsw in valid_ipsws:
        basename = os.path.basename(ipsw).lower()
        if pt_normalized in basename or device.product_type in basename:
            ver, build = _parse_ipsw_version(basename)
            if ver:
                try:
                    parts = [int(p) for p in ver.split(".")]
                    while len(parts) < 3:
                        parts.append(0)
                    if parts > best_version:
                        best_version = parts
                        best_local = ipsw
                except ValueError:
                    if best_local is None:
                        best_local = ipsw

    if matched_manifest:
        expected_name = matched_manifest.get("filename", "")
        if expected_name:
            for ipsw in valid_ipsws:
                if os.path.basename(ipsw).lower() == expected_name.lower():
                    return ipsw

        for ipsw in valid_ipsws:
            basename = os.path.basename(ipsw).lower()
            expected_lower = expected_name.lower()
            expected_base = os.path.splitext(expected_lower)[0] if expected_lower else ""
            if expected_base and expected_base in basename:
                return ipsw

    if best_local:
        return best_local

    for ipsw in valid_ipsws:
        basename = os.path.basename(ipsw).lower()
        if "restore" in basename or "15.8.8" in basename:
            return ipsw

    return valid_ipsws[0] if valid_ipsws else None


def detect_devices() -> DeviceDetectResult:
    result = DeviceDetectResult()

    try:
        manifest = _load_firmware_manifest()
        result.firmware_manifest = manifest

        udids = _run_idevice_id()
        result.total_detected = len(udids)

        if not udids:
            result.error = "No iOS devices detected via idevice_id"
            result.success = False
            return result

        for udid in udids:
            device = iOSDevice(udid=udid, connected=True)

            info = _run_ideviceinfo(udid)
            device.product_type = info.get("ProductType", "")
            device.os_version = info.get("ProductVersion", "")
            device.build_version = info.get("BuildVersion", "")
            device.serial_number = info.get("SerialNumber", "")
            device.hardware_model = info.get("HardwareModel", "")

            if device.product_type in DEVICE_MODEL_MAP:
                device.device_type = DEVICE_MODEL_MAP[device.product_type]

            device.mode = _detect_device_mode(udid)
            device.recovery_mode = device.mode == "recovery"
            device.normal_mode = device.mode == "normal"
            device.restore_mode = "restore" in device.mode.lower()

            matched_ipsw = _match_ipsw_to_device(device)
            if matched_ipsw:
                device.ipsw_match = matched_ipsw

            result.devices.append(asdict(device))
            if device.recovery_mode:
                result.recovery_devices.append(udid)

            for mfw in manifest.get("firmwares", []):
                if mfw.get("product_type") == device.product_type:
                    result.recommended_firmware[udid] = mfw
                    break

        result.available_ipsws = _find_ipsw_files()
        result.matched_ipsw = {
            d["udid"]: d.get("ipsw_match", "")
            for d in result.devices
            if d.get("ipsw_match")
        }
        result.success = True

    except Exception as e:
        result.error = str(e)
        result.success = False

    return result


def get_device_details(udid: str) -> dict[str, Any] | None:
    result = detect_devices()
    for device in result.devices:
        if device.get("udid") == udid:
            return device
    return None


def save_detect_result(result: DeviceDetectResult, output_path: str | None = None) -> str:
    if output_path is None:
        output_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "device_detect.json"
        )

    doc = asdict(result)
    doc["timestamp_iso"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(result.timestamp))

    with open(output_path, "w") as f:
        json.dump(doc, f, indent=2, default=str)

    return output_path


def flash_device(udid: str, ipsw_path: str | None = None) -> dict[str, Any]:
    device = get_device_details(udid)
    if device is None:
        return {"success": False, "error": f"Device {udid} not found"}

    if ipsw_path is None:
        ipsw_path = device.get("ipsw_match")

    if ipsw_path is None or not os.path.isfile(ipsw_path):
        manifest = _load_firmware_manifest()
        product_type = device.get("product_type", "")
        for mfw in manifest.get("firmwares", []):
            if mfw.get("product_type") == product_type and mfw.get("signed"):
                expected_name = mfw.get("filename", "")
                available = _find_ipsw_files()
                for avail in available:
                    if os.path.basename(avail).lower() == expected_name.lower():
                        ipsw_path = avail
                        break
                if ipsw_path:
                    break

    if ipsw_path is None or not os.path.isfile(ipsw_path):
        return {"success": False, "error": "No valid IPSW path available"}

    try:
        cmd = ["idevicerestore", "-i", udid, ipsw_path]
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=300,
        )
        return {
            "success": result.returncode == 0,
            "command": " ".join(cmd),
            "returncode": result.returncode,
            "stdout": result.stdout[-500:] if result.stdout else "",
            "stderr": result.stderr[-500:] if result.stderr else "",
        }
    except FileNotFoundError:
        return {"success": False, "error": "idevicerestore not found"}
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Restore timed out after 300s"}
    except OSError as e:
        return {"success": False, "error": str(e)}