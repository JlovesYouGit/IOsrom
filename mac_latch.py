#!/usr/bin/env python3
"""
MAC Device Latch System
=======================

Provides MAC-address-based device identification and latching for iOS devices.

A "latch" is a persistent device identity that survives mode transitions
(recovery -> DFU -> normal). On iOS devices, the MAC address serves as
a stable hardware identifier that can be used to:
1. Latch a device across mode changes
2. Route SeedGate connections to the correct physical device
3. Maintain hivemind agent state across reboots

Architecture:
- MacLatch: Maps device UDID <-> MAC address
- DeviceLatchStore: Persistent latch store (JSON)
- MacDeviceLatch: High-level interface for device latching
"""

import json
import subprocess
import time
from pathlib import Path
from typing import Optional, Dict, List
from dataclasses import dataclass, field, asdict
from enum import Enum


class DeviceMode(Enum):
    NORMAL = "normal"
    RECOVERY = "recovery"
    DFU = "dfu"
    RESTORE = "restore"
    UNKNOWN = "unknown"


@dataclass
class DeviceLatch:
    """Persistent device identity latch."""
    udid: str
    mac_address: Optional[str]
    product: str
    model: str
    name: str
    last_mode: str
    last_seen: float
    latch_count: int = 0
    history: List[Dict] = field(default_factory=list)


class MacLatch:
    """
    MAC-address-based device latching.
    
    Maps device UDIDs to MAC addresses and maintains persistent identity
    across mode transitions and USB reconnections.
    """
    
    def __init__(self, store_path: Optional[Path] = None):
        if store_path is None:
            store_path = Path(__file__).parent.parent.parent / "firmware" / "device_latches.json"
        self.store_path = store_path
        self.latches: Dict[str, DeviceLatch] = {}
        self._load()
    
    def _load(self):
        """Load latch store from disk."""
        if self.store_path.exists():
            try:
                data = json.loads(self.store_path.read_text())
                for udid, latch_data in data.items():
                    self.latches[udid] = DeviceLatch(**latch_data)
            except Exception:
                pass
    
    def _save(self):
        """Save latch store to disk."""
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        data = {udid: asdict(latch) for udid, latch in self.latches.items()}
        self.store_path.write_text(json.dumps(data, indent=2, default=str))
    
    def get_mac_from_normal(self, udid: str) -> Optional[str]:
        """
        Get MAC address from a device in normal mode via lockdown.
        
        Uses ideviceinfo or similar to read Wi-Fi MAC address.
        """
        try:
            # Try ideviceinfo first
            result = subprocess.run(
                ["ideviceinfo", "-u", udid, "-k", "WiFiAddress"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                mac = result.stdout.strip()
                if mac and ":" in mac:
                    return mac.lower()
        except Exception:
            pass
        
        try:
            # Try getting from network interfaces via usbmux
            result = subprocess.run(
                ["ideviceinfo", "-u", udid, "-k", "MACAddress"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                mac = result.stdout.strip()
                if mac and ":" in mac:
                    return mac.lower()
        except Exception:
            pass
        
        return None
    
    def get_mac_from_recovery(self, udid: str) -> Optional[str]:
        """
        Attempt to get MAC address from recovery mode.
        
        In recovery mode, we can't directly query the MAC address,
        but we can try to read it from the device's NVRAM or use
        the UDID as a proxy for latching.
        """
        # In recovery mode, MAC isn't directly accessible
        # Return None to indicate unknown
        return None
    
    def latch_device(self, udid: str, product: str, model: str, name: str, mode: str) -> DeviceLatch:
        """
        Latch a device by UDID, updating or creating the latch record.
        
        If the device was previously seen in normal mode, try to retrieve
        its MAC address and use it as the persistent identifier.
        """
        now = time.time()
        
        # Check if we already have this device latched
        if udid in self.latches:
            latch = self.latches[udid]
            latch.last_mode = mode
            latch.last_seen = now
            latch.latch_count += 1
            latch.history.append({
                "mode": mode,
                "timestamp": now,
                "action": "mode_change" if len(latch.history) > 0 else "initial"
            })
            self._save()
            return latch
        
        # New device - try to get MAC address if in normal mode
        mac = None
        if mode == DeviceMode.NORMAL.value:
            mac = self.get_mac_from_normal(udid)
        
        # Create new latch
        latch = DeviceLatch(
            udid=udid,
            mac_address=mac,
            product=product,
            model=model,
            name=name,
            last_mode=mode,
            last_seen=now,
            latch_count=1,
            history=[{"mode": mode, "timestamp": now, "action": "initial"}]
        )
        
        self.latches[udid] = latch
        self._save()
        
        return latch
    
    def get_latch(self, udid: str) -> Optional[DeviceLatch]:
        """Get existing latch for a device."""
        return self.latches.get(udid)
    
    def find_by_mac(self, mac: str) -> Optional[DeviceLatch]:
        """Find device latch by MAC address."""
        mac = mac.lower()
        for latch in self.latches.values():
            if latch.mac_address and latch.mac_address.lower() == mac:
                return latch
        return None
    
    def find_by_udid(self, udid: str) -> Optional[DeviceLatch]:
        """Find device latch by UDID."""
        return self.latches.get(udid)
    
    def update_mac(self, udid: str, mac: str) -> Optional[DeviceLatch]:
        """Update MAC address for a latched device."""
        if udid not in self.latches:
            return None
        
        latch = self.latches[udid]
        old_mac = latch.mac_address
        latch.mac_address = mac.lower()
        latch.history.append({
            "mode": latch.last_mode,
            "timestamp": time.time(),
            "action": "mac_update",
            "old_mac": old_mac,
            "new_mac": mac.lower()
        })
        self._save()
        return latch
    
    def get_all_latches(self) -> List[DeviceLatch]:
        """Get all device latches."""
        return list(self.latches.values())
    
    def get_active_latches(self, max_age: float = 3600) -> List[DeviceLatch]:
        """Get latches seen within max_age seconds."""
        now = time.time()
        return [l for l in self.latches.values() if now - l.last_seen < max_age]


class MacDeviceLatch:
    """
    High-level MAC device latching interface.
    
    Combines MAC latching with device detection and mode tracking.
    """
    
    def __init__(self, native_transport=None):
        self.transport = native_transport
        self.mac_latch = MacLatch()
    
    def detect_and_latch(self) -> Optional[DeviceLatch]:
        """
        Detect connected device and create/update latch.
        
        Returns:
            DeviceLatch if device detected, None otherwise
        """
        devices = self.transport.probe()
        if not devices:
            return None
        
        dev = devices[0]
        udid = dev.raw.strip() if hasattr(dev, 'raw') else str(dev)
        
        # Extract UDID properly
        if hasattr(dev, 'udid') and dev.udid:
            udid = dev.udid
        else:
            # Try to extract from raw output
            for line in (dev.raw if hasattr(dev, 'raw') else '').splitlines():
                if 'UniqueDeviceID' in line:
                    udid = line.split(':', 1)[1].strip()
                    break
        
        if not udid:
            return None
        
        # Determine mode
        mode = DeviceMode.UNKNOWN.value
        if hasattr(dev, 'mode'):
            mode = dev.mode.value if isinstance(dev.mode, DeviceMode) else str(dev.mode)
        
        # Extract product/model/name
        product = getattr(dev, 'product', '')
        model = getattr(dev, 'model', '')
        name = getattr(dev, 'name', '')
        
        # Latch the device
        latch = self.mac_latch.latch_device(udid, product, model, name, mode)
        
        # Try to update MAC if in normal mode
        if mode == DeviceMode.NORMAL.value and not latch.mac_address:
            mac = self.mac_latch.get_mac_from_normal(udid)
            if mac:
                self.mac_latch.update_mac(udid, mac)
        
        return latch
    
    def get_latched_device(self) -> Optional[DeviceLatch]:
        """Get the most recently latched device."""
        active = self.mac_latch.get_active_latches(max_age=7200)
        if not active:
            return None
        return max(active, key=lambda l: l.last_seen)
    
    def wait_for_device(self, timeout: float = 60) -> Optional[DeviceLatch]:
        """
        Wait for a device to be connected and latched.
        
        Args:
            timeout: Maximum time to wait in seconds
            
        Returns:
            DeviceLatch if device detected, None on timeout
        """
        start = time.time()
        while time.time() - start < timeout:
            latch = self.detect_and_latch()
            if latch:
                return latch
            time.sleep(2)
        return None
    
    def get_device_by_mac(self, mac: str) -> Optional[DeviceLatch]:
        """Find device by MAC address."""
        return self.mac_latch.find_by_mac(mac)
    
    def get_device_by_udid(self, udid: str) -> Optional[DeviceLatch]:
        """Find device by UDID."""
        return self.mac_latch.find_by_udid(udid)


def main():
    """CLI for MAC device latching."""
    import argparse
    
    parser = argparse.ArgumentParser(description="MAC Device Latch System")
    parser.add_argument("--detect", action="store_true", help="Detect and latch connected device")
    parser.add_argument("--wait", type=float, default=0, help="Wait for device (seconds)")
    parser.add_argument("--list", action="store_true", help="List all latched devices")
    parser.add_argument("--mac", type=str, help="Find device by MAC address")
    parser.add_argument("--udid", type=str, help="Find device by UDID")
    
    args = parser.parse_args()
    
    latch_system = MacDeviceLatch()
    
    if args.detect or args.wait > 0:
        print(f"[+] Waiting for device..." if args.wait > 0 else "[+] Detecting device...")
        latch = latch_system.wait_for_device(timeout=args.wait if args.wait > 0 else 5)
        if latch:
            print(f"[+] Device latched:")
            print(f"    UDID: {latch.udid}")
            print(f"    MAC: {latch.mac_address or 'unknown'}")
            print(f"    Product: {latch.product} {latch.model}")
            print(f"    Name: {latch.name}")
            print(f"    Mode: {latch.last_mode}")
            print(f"    Latches: {latch.latch_count}")
        else:
            print("[-] No device detected")
    
    elif args.list:
        latches = latch_system.mac_latch.get_all_latches()
        print(f"[+] Latched devices: {len(latches)}")
        for latch in latches:
            print(f"    {latch.udid[:16]}... | {latch.mac_address or 'no-MAC'} | {latch.product} | {latch.last_mode}")
    
    elif args.mac:
        latch = latch_system.get_device_by_mac(args.mac)
        if latch:
            print(f"[+] Found device: {latch.udid}")
        else:
            print("[-] Device not found")
    
    elif args.udid:
        latch = latch_system.get_device_by_udid(args.udid)
        if latch:
            print(f"[+] Found device: {latch.mac_address or 'no-MAC'}")
        else:
            print("[-] Device not found")
    
    else:
        parser.print_help()


if __name__ == "__main__":
    import sys
    sys.exit(main() or 0)
