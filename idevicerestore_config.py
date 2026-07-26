#!/usr/bin/env python3
"""
Modified idevicerestore configuration for codespace integration.
Integrates TSS bypass, SeedGate transport, and custom restore paths.
"""
import os
import sys
import subprocess
from pathlib import Path

class CodespaceConfig:
    """Configuration for idevicerestore with codespace integration."""
    
    def __init__(self):
        self.base_dir = Path("/home/j/Downloads/ios romm")
        self.firmware_dir = self.base_dir / "firmware"
        self.iosrom_dir = self.base_dir / "IOsrom"
        self.output_dir = self.firmware_dir / "auto_flash_output"
        
        # Transport layer configuration
        self.transport_config = {
            'use_seedgate': True,
            'use_mac_latch': True,
            'usbmuxd_socket': '/var/run/usbmuxd',
            'fallback_to_native': True,
        }
        
        # TSS bypass configuration
        self.tss_config = {
            'local_tss_server': True,
            'tss_host': '127.0.0.1',
            'tss_port': 80,
            'bypass_signing': True,
            'use_firmware_shsh': True,
        }
        
        # Restore configuration
        self.restore_config = {
            'allow_unsigned': True,
            'custom_ipsw_build': True,
            'use_idevicerestore': True,
            'idevicerestore_path': self._find_idevicerestore(),
            'extra_args': ['-c'],  # Custom firmware flag
        }
        
    def _find_idevicerestore(self):
        """Find idevicerestore binary."""
        candidates = [
            Path("/usr/local/bin/idevicerestore"),
            Path("/usr/bin/idevicerestore"),
            self.iosrom_dir / "chargfast via usb" / "idevicerestore",
        ]
        for c in candidates:
            if c.exists():
                return str(c)
        return None
    
    def setup_tss_bypass(self):
        """Setup local TSS bypass server."""
        print("[+] Setting up TSS bypass...")
        
        # Start TSS bypass server
        tss_script = self.iosrom_dir / "FINAL_TSS_BYPASS.py"
        if tss_script.exists():
            print(f"[+] TSS bypass script: {tss_script}")
            print("[!] Run this in a separate terminal:")
            print(f"    python3 {tss_script}")
            print()
            print("[!] Then add to /etc/hosts:")
            print("    127.0.0.1 gs.apple.com")
            return True
        return False
    
    def setup_transport_layer(self):
        """Setup SeedGate transport layer."""
        print("[+] Setting up SeedGate transport...")
        
        # Ensure usbmuxd is running
        try:
            subprocess.run(["sudo", "systemctl", "start", "usbmuxd"], check=True)
            print("[+] usbmuxd started")
        except:
            print("[-] Could not start usbmuxd")
        
        # Check for native toolkit
        native_toolkit = self.iosrom_dir.parent / "native_toolkit"
        if native_toolkit.exists():
            print(f"[+] Native toolkit found: {native_toolkit}")
            sys.path.insert(0, str(native_toolkit))
            return True
        return False
    
    def get_restore_command(self, ipsw_path, device_ecid=None):
        """Get idevicerestore command with codespace integration."""
        if not self.restore_config['idevicerestore_path']:
            print("[-] idevicerestore not found")
            return None
        
        cmd = [self.restore_config['idevicerestore_path']]
        
        # Add custom firmware flag for unsigned iOS
        if self.restore_config['allow_unsigned']:
            cmd.extend(['-c'])
        
        # Add erase mode
        cmd.extend(['-e'])
        
        # Add ECID if specified
        if device_ecid:
            cmd.extend(['-u', device_ecid])
        
        # Add IPSW path
        cmd.append(str(ipsw_path))
        
        return cmd
    
    def prepare_environment(self):
        """Prepare environment for codespace restore."""
        print("=" * 60)
        print("CODESPACE ENVIRONMENT SETUP")
        print("=" * 60)
        
        # Setup TSS bypass
        tss_ready = self.setup_tss_bypass()
        
        # Setup transport layer
        transport_ready = self.setup_transport_layer()
        
        print()
        print("=" * 60)
        print("ENVIRONMENT STATUS")
        print("=" * 60)
        print(f"TSS Bypass: {'READY' if tss_ready else 'MANUAL SETUP REQUIRED'}")
        print(f"Transport Layer: {'READY' if transport_ready else 'NOT READY'}")
        print(f"idevicerestore: {self.restore_config['idevicerestore_path'] or 'NOT FOUND'}")
        print()
        
        return tss_ready and transport_ready

def main():
    """Main configuration setup."""
    config = CodespaceConfig()
    
    # Prepare environment
    config.prepare_environment()
    
    # Show restore command for real IPSW
    real_ipsw = config.firmware_dir / "iPhone18,5_26.5.2_23F84_Restore.ipsw"
    if real_ipsw.exists():
        print("=" * 60)
        print("RESTORE COMMAND FOR REAL IPSW")
        print("=" * 60)
        cmd = config.get_restore_command(real_ipsw)
        if cmd:
            print(" ".join(cmd))
        print()
        print("[!] Run this command manually in your terminal")
        print("[!] No timeouts - let it complete naturally")
        print()

if __name__ == "__main__":
    main()
