#!/usr/bin/env python3
"""Direct ctypes bindings to libimobiledevice and libirecovery."""
import ctypes
import ctypes.util
import os
import sys
import time
from pathlib import Path
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass
from enum import Enum

from .exceptions import TransportError, NativeToolkitError


class DeviceMode(Enum):
    """iOS device operational modes."""
    NORMAL = "normal"
    RECOVERY = "recovery"
    DFU = "dfu"
    RESTORE = "restore"
    UNKNOWN = "unknown"


@dataclass
class DeviceInfo:
    """Parsed device information."""
    ecid: str
    cpid: str
    cprv: str
    bdid: str
    srtg: str
    srnm: str
    product: str
    model: str
    name: str
    mode: DeviceMode
    nonce: str
    snon: str
    board_id: str
    firmware_version: str
    raw: str


class LibIMobileDeviceError(NativeToolkitError):
    """Raised when a libimobiledevice call returns an error."""
    def __init__(self, func: str, code: int):
        self.func = func
        self.code = code
        super().__init__(f"{func} failed with error code {code}")


class LibIRecoveryError(NativeToolkitError):
    """Raised when a libirecovery call returns an error."""
    def __init__(self, func: str, code: int):
        self.func = func
        self.code = code
        super().__init__(f"{func} failed with error code {code}")


def _find_library(name: str) -> str:
    """Locate a shared library using ctypes.util."""
    path = ctypes.util.find_library(name)
    if path is None:
        # Fallback paths
        candidates = [
            f"/usr/lib/lib{name}.so",
            f"/usr/lib/x86_64-linux-gnu/lib{name}.so",
            f"/usr/local/lib/lib{name}.so",
        ]
        for c in candidates:
            if os.path.exists(c):
                return c
        raise TransportError(f"Library '{name}' not found")
    return path


class LibIMobileDevice:
    """Thin ctypes wrapper around libimobiledevice."""
    
    def __init__(self):
        self.lib = ctypes.CDLL(_find_library("imobiledevice-1.0"))
        self.glue = ctypes.CDLL(_find_library("libimobiledevice-glue-1.0"))
        self._loaded = False
        
    def _check(self, ret: int, func_name: str) -> int:
        if ret != 0:
            raise LibIMobileDeviceError(func_name, ret)
        return ret
    
    def idevice_new(self, udid: Optional[str]) -> Any:
        device = ctypes.c_void_p()
        udid_b = udid.encode() if udid else None
        ret = self.lib.idevice_new(ctypes.byref(device), udid_b)
        if ret != 0:
            # May fail if no device or usbmuxd not running; that's ok for probing
            raise LibIMobileDeviceError("idevice_new", ret)
        return device
    
    def idevice_free(self, device: Any) -> None:
        self.lib.idevice_free(device)
    
    def idevice_get_value(self, device: Any, domain: str, key: str) -> str:
        value = ctypes.c_char_p()
        ret = self.lib.idevice_get_value(device, domain.encode(), key.encode(), ctypes.byref(value))
        self._check(ret, "idevice_get_value")
        try:
            return value.value.decode() if value.value else ""
        finally:
            self.lib.plist_free(value)
    
    def lockdownd_get_value(self, device: Any, domain: str, key: str) -> Any:
        """Get value via lockdown service. Returns plist pointer."""
        client = ctypes.c_void_p()
        error = self.lib.lockdownd_client_new_with_handshake(device, ctypes.byref(client), b"native-toolkit")
        if error != 0:
            raise LibIMobileDeviceError("lockdownd_client_new_with_handshake", error)
        
        value = ctypes.c_void_p()
        error = self.lib.lockdownd_get_value(client, domain.encode(), key.encode(), ctypes.byref(value))
        self.lib.lockdownd_client_free(client)
        self._check(error, "lockdownd_get_value")
        return value
    
    def lockdownd_get_value_str(self, device: Any, key: str) -> str:
        """Convenience: get string value from lockdown domain 'com.apple.mobile.installation.plist'."""
        plist_ptr = self.lockdownd_get_value(device, "com.apple.mobile.installation.plist", key)
        # Read plist as string - simplified; real impl would serialize plist
        return ""
    
    def plist_to_string(self, plist: Any) -> str:
        """Convert plist_t to XML/binary string."""
        length = ctypes.c_size_t(0)
        buf = self.lib.plist_to_xml(plist, ctypes.byref(length))
        if not buf:
            return ""
        try:
            return ctypes.string_at(buf, length.value).decode("utf-8", errors="replace")
        finally:
            self.lib.plist_free(buf)
    
    def lockdownd_get_device_name(self, device: Any) -> str:
        client = ctypes.c_void_p()
        error = self.lib.lockdownd_client_new_with_handshake(device, ctypes.byref(client), b"native-toolkit")
        if error != 0:
            raise LibIMobileDeviceError("lockdownd_client_new_with_handshake", error)
        
        value = ctypes.c_void_p()
        error = self.lib.lockdownd_get_value(client, None, b"DeviceName", ctypes.byref(value))
        self.lib.lockdownd_client_free(client)
        if error != 0:
            return ""
        xml = self.plist_to_string(value)
        self.lib.plist_free(value)
        # Extract string from plist XML
        import re
        m = re.search(r"<string>([^<]+)</string>", xml)
        return m.group(1) if m else ""
    
    def lockdownd_query_type(self, device: Any) -> str:
        client = ctypes.c_void_p()
        error = self.lib.lockdownd_client_new_with_handshake(device, ctypes.byref(client), b"native-toolkit")
        if error != 0:
            raise LibIMobileDeviceError("lockdownd_client_new_with_handshake", error)
        
        response = ctypes.create_string_buffer(256)
        length = ctypes.c_uint32(ctypes.sizeof(response))
        error = self.lib.lockdownd_query_type(client, response, ctypes.byref(length))
        self.lib.lockdownd_client_free(client)
        if error != 0:
            return ""
        return response.value.decode().rstrip("\x00")


class LibIRecovery:
    """Native ctypes bindings to libirecovery."""
    
    def __init__(self):
        self.lib = ctypes.CDLL(_find_library("irecovery-1.0"))
        self._loaded = True
    
    def recv_error_string(self, code: int) -> str:
        s = self.lib.irecv_strerror(code)
        return ctypes.string_at(s).decode("utf-8", errors="replace") if s else f"Error {code}"
    
    def device_new(self) -> Any:
        client = ctypes.c_void_p()
        ret = self.lib.irecv_open(ctypes.byref(client))
        if ret != 0:
            raise LibIRecoveryError("irecv_open", ret)
        return client
    
    def device_close(self, client: Any) -> None:
        self.lib.irecv_close(client)
    
    def device_reset(self, client: Any) -> None:
        ret = self.lib.irecv_reset(client)
        if ret != 0:
            raise LibIRecoveryError("irecv_reset", ret)
    
    def device_receive(self, client: Any, mode: Optional[str] = None) -> None:
        mode_b = mode.encode() if mode else None
        ret = self.lib.irecv_receive(client, mode_b)
        if ret != 0:
            raise LibIRecoveryError("irecv_receive", ret)
    
    def device_send_file(self, client: Any, path: str) -> None:
        ret = self.lib.irecv_send_file(client, path.encode())
        if ret != 0:
            raise LibIRecoveryError("irecv_send_file", ret)
    
    def device_send_buffer(self, client: Any, data: bytes) -> None:
        buf = ctypes.create_string_buffer(data)
        ret = self.lib.irecv_send_buffer(client, buf, len(data), 0)
        if ret != 0:
            raise LibIRecoveryError("irecv_send_buffer", ret)
    
    def device_execute(self, client: Any, data: bytes, flags: int = 0) -> None:
        buf = ctypes.create_string_buffer(data)
        ret = self.lib.irecv_execute(client, buf, len(data), flags)
        if ret != 0:
            raise LibIRecoveryError("irecv_execute", ret)
    
    def device_setenv(self, client: Any, key: str, value: str) -> None:
        ret = self.lib.irecv_setenv(client, key.encode(), value.encode())
        if ret != 0:
            raise LibIRecoveryError("irecv_setenv", ret)
    
    def device_getenv(self, client: Any, key: str) -> str:
        buf = ctypes.create_string_buffer(256)
        ret = self.lib.irecv_getenv(client, key.encode(), buf, ctypes.sizeof(buf))
        if ret != 0:
            return ""
        return buf.value.decode("utf-8", errors="replace").rstrip("\x00")
    
    def device_saveenv(self, client: Any) -> None:
        ret = self.lib.irecv_saveenv(client)
        if ret != 0:
            raise LibIRecoveryError("irecv_saveenv", ret)
    
    def device_boot(self, client: Any) -> None:
        ret = self.lib.irecv_boot(client)
        if ret != 0:
            raise LibIRecoveryError("irecv_boot", ret)
    
    def device_query(self, client: Any) -> str:
        buf = ctypes.create_string_buffer(4096)
        ret = self.lib.irecv_query_device(client, buf, ctypes.sizeof(buf))
        if ret != 0:
            return ""
        return buf.value.decode("utf-8", errors="replace")
    
    def device_bootx(self, client: Any) -> None:
        ret = self.lib.irecv_bootx(client)
        if ret != 0:
            raise LibIRecoveryError("irecv_bootx", ret)
    
    def device_fsboot(self, client: Any) -> None:
        ret = self.lib.irecv_fsboot(client)
        if ret != 0:
            raise LibIRecoveryError("irecv_fsboot", ret)
    
    def device_nand_open(self, client: Any, operation: str) -> None:
        ret = self.lib.irecv_nand_open(client, operation.encode())
        if ret != 0:
            raise LibIRecoveryError("irecv_nand_open", ret)
    
    def device_nand_close(self, client: Any) -> None:
        ret = self.lib.irecv_nand_close(client)
        if ret != 0:
            raise LibIRecoveryError("irecv_nand_close", ret)
    
    def device_nand_erase(self, client: Any, offset: int, length: int) -> None:
        ret = self.lib.irecv_nand_erase(client, offset, length)
        if ret != 0:
            raise LibIRecoveryError("irecv_nand_erase", ret)
    
    def device_nand_write(self, client: Any, offset: int, data: bytes) -> None:
        buf = ctypes.create_string_buffer(data)
        ret = self.lib.irecv_nand_write(client, offset, buf, len(data))
        if ret != 0:
            raise LibIRecoveryError("irecv_nand_write", ret)
    
    def device_nand_read(self, client: Any, offset: int, length: int) -> bytes:
        buf = ctypes.create_string_buffer(length)
        ret = self.lib.irecv_nand_read(client, offset, buf, length)
        if ret != 0:
            raise LibIRecoveryError("irecv_nand_read", ret)
        return buf.raw
    
    def device_command(self, client: Any, cmd: str) -> str:
        buf = ctypes.create_string_buffer(4096)
        ret = self.lib.irecv_send_command(client, cmd.encode(), buf, ctypes.sizeof(buf))
        if ret != 0:
            # Some commands return errors legitimately; return raw output
            pass
        return buf.value.decode("utf-8", errors="replace")


class NativeTransport:
    """Unified transport layer bridging USB, recovery, and lockdown protocols."""
    
    def __init__(self):
        self.imob = LibIMobileDevice()
        self.irec = LibIRecovery()
        self._usbmuxd_socket = None
        
    def probe(self) -> List[DeviceInfo]:
        """Enumerate all connected iOS devices across all modes."""
        devices = []
        for udid in self._enumerate_usbmux():
            try:
                info = self._probe_single(udid)
                if info:
                    devices.append(info)
            except Exception:
                continue
        return devices
    
    def _enumerate_usbmux(self) -> List[str]:
        """Enumerate UDIDs via usbmuxd (socket interface)."""
        # Use libusbmuxd Python bindings if available, fallback to subprocess
        try:
            import usbmuxd
            conns = usbmuxd.list_devices()
            return [d.get("udid") for d in conns if d.get("udid")]
        except Exception:
            pass
        # Fallback: idevice_id
        import subprocess
        try:
            r = subprocess.run(["idevice_id", "-l"], capture_output=True, text=True, timeout=5)
            if r.returncode == 0:
                return [u.strip() for u in r.stdout.strip().split("\n") if u.strip()]
        except Exception:
            pass
        return []
    
    def _probe_single(self, udid: str) -> Optional[DeviceInfo]:
        """Probe a single UDID to determine its mode and info."""
        # Try lockdown first (normal mode)
        try:
            dev = self.imob.lib.idevice_new(udid.encode())
            if dev:
                query = self.imob.lockdownd_query_type(dev)
                if query and query != "com.apple.mobile.lockdown":
                    # In normal mode, get info from lockdown
                    name = self.imob.lockdownd_get_device_name(dev)
                    self.imob.lib.idevice_free(dev)
                    return DeviceInfo(
                        ecid="", cpid="", cprv="", bdid="", srtg="", srnm="",
                        product="", model="", name=name, mode=DeviceMode.NORMAL,
                        nonce="", snon="", board_id="", firmware_version="", raw=udid
                    )
        except Exception:
            pass
        
        # Try recovery/DFU via libirecovery
        try:
            rc = self.irec.device_new()
            info_str = self.irec.device_query(rc)
            self.irec.device_close(rc)
            if info_str:
                return self._parse_recovery_query(info_str)
        except Exception:
            pass
        
        return None
    
    def _parse_recovery_query(self, raw: str) -> DeviceInfo:
        """Parse irecovery -q output into DeviceInfo."""
        def get(key):
            for line in raw.splitlines():
                if line.startswith(key + ":"):
                    return line.split(":", 1)[1].strip()
            return ""
        
        mode_raw = get("MODE").upper()
        if "DFU" in mode_raw:
            mode = DeviceMode.DFU
        elif "RECOVERY" in mode_raw:
            mode = DeviceMode.RECOVERY
        elif "RESTORE" in mode_raw:
            mode = DeviceMode.RESTORE
        else:
            mode = DeviceMode.UNKNOWN
        
        return DeviceInfo(
            ecid=get("ECID"),
            cpid=get("CPID"),
            cprv=get("CPRV"),
            bdid=get("BDID"),
            srtg=get("SRTG"),
            srnm=get("SRNM"),
            product=get("PRODUCT"),
            model=get("MODEL"),
            name=get("NAME"),
            mode=mode,
            nonce=get("NONC"),
            snon=get("SNON"),
            board_id=get("BDID"),
            firmware_version=get("FirmwareVersion"),
            raw=raw
        )
    
    def open_recovery(self, udid: Optional[str] = None) -> Any:
        """Open connection to device in recovery/DFU mode."""
        client = self.irec.device_new()
        if udid:
            # In real impl, connect to specific UDID via usbmuxd
            pass
        return client
    
    def close(self, client: Any) -> None:
        try:
            self.irec.device_close(client)
        except Exception:
            pass
