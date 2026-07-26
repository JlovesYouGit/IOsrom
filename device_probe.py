#!/usr/bin/env python3
"""
Device Probe Module - Native toolkit state machine and transport layer
Probes iOS devices via irecovery, loads iBSS/iBEC, connects, and boots.
"""
import subprocess
import time
import sys
import enum
from pathlib import Path
from typing import Optional, List, Dict, Callable
from utils import PathConfig

cfg = PathConfig()
chargfast = cfg.chargfast_dir
extracted = chargfast / "extracted"
irecovery = cfg.resolve_irecovery()


class DeviceState(enum.Enum):
    IDLE = "idle"
    PROBING = "probing"
    CONNECTING = "connecting"
    LOADING_IBSS = "loading_ibss"
    LOADING_IBEC = "loading_ibec"
    BOOTING = "booting"
    READY = "ready"
    FAILED = "failed"


class TransportLayer:
    def __init__(self, irecovery_path: Path = None, workdir: Path = None):
        self.irecovery = irecovery_path or cfg.resolve_irecovery()
        self.workdir = workdir or chargfast
        self._last_output: Optional[str] = None
        self._last_returncode: Optional[int] = None

    def send(self, command: str, timeout: int = 15) -> Dict[str, Optional[str]]:
        try:
            result = subprocess.run(
                [str(self.irecovery), "-c", command],
                cwd=str(self.workdir),
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
            self._last_output = result.stdout
            self._last_returncode = result.returncode
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
            }
        except subprocess.TimeoutExpired:
            self._last_output = None
            self._last_returncode = -1
            return {
                "success": False,
                "stdout": None,
                "stderr": "Command timed out",
                "returncode": -1,
            }
        except FileNotFoundError:
            self._last_output = None
            self._last_returncode = -1
            return {
                "success": False,
                "stdout": None,
                "stderr": f"irecovery not found at {self.irecovery}",
                "returncode": -1,
            }
        except Exception as e:
            self._last_output = None
            self._last_returncode = -1
            return {
                "success": False,
                "stdout": None,
                "stderr": str(e),
                "returncode": -1,
            }

    def upload(self, filepath: Path, timeout: int = 30) -> Dict[str, Optional[str]]:
        try:
            result = subprocess.run(
                [str(self.irecovery), "-f", str(filepath)],
                cwd=str(self.workdir),
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
            self._last_output = result.stdout
            self._last_returncode = result.returncode
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
            }
        except subprocess.TimeoutExpired:
            self._last_output = None
            self._last_returncode = -1
            return {
                "success": False,
                "stdout": None,
                "stderr": "Upload timed out",
                "returncode": -1,
            }
        except FileNotFoundError:
            self._last_output = None
            self._last_returncode = -1
            return {
                "success": False,
                "stdout": None,
                "stderr": f"irecovery not found at {self.irecovery}",
                "returncode": -1,
            }
        except Exception as e:
            self._last_output = None
            self._last_returncode = -1
            return {
                "success": False,
                "stdout": None,
                "stderr": str(e),
                "returncode": -1,
            }

    def query(self, timeout: int = 10) -> Dict[str, Optional[str]]:
        return self.send("query", timeout=timeout)

    def get_last_output(self) -> Optional[str]:
        return self._last_output

    def get_last_returncode(self) -> Optional[int]:
        return self._last_returncode


class DeviceProbe:
    def __init__(self):
        self.state = DeviceState.IDLE
        self.transport = TransportLayer()
        self.device_info: Optional[str] = None
        self.ibss_loaded: bool = False
        self.ibec_loaded: bool = False
        self.boot_attempted: bool = False
        self.boot_successful: bool = False
        self._transitions: List[str] = []
        self._error_message: Optional[str] = None

    def _transition(self, new_state: DeviceState, message: str = "") -> None:
        old_state = self.state
        self.state = new_state
        self._transitions.append(f"{old_state.value} -> {new_state.value}")
        if message:
            print(f"[STATE] {old_state.value} -> {new_state.value}: {message}")
        else:
            print(f"[STATE] {old_state.value} -> {new_state.value}")

    def _fail(self, message: str) -> None:
        self._error_message = message
        self._transition(DeviceState.FAILED, message)

    def probe_device(self) -> bool:
        self._transition(DeviceState.PROBING, "Probing device via transport layer")

        result = self.transport.query()
        if result["success"] and result["stdout"]:
            self.device_info = result["stdout"].strip()
            self._transition(DeviceState.CONNECTING, f"Device found:\n{self.device_info}")
            return True

        print("[-] No device detected via irecovery query")
        print("[!] Ensure device is in DFU mode and connected via USB")
        self._fail("No device detected")
        return False

    def load_ibss(self) -> bool:
        if self.state not in (DeviceState.CONNECTING, DeviceState.LOADING_IBEC):
            self._fail(f"Cannot load iBSS from state {self.state.value}")
            return False

        self._transition(DeviceState.LOADING_IBSS, "Loading iBSS firmware")

        ibss_path = extracted / "Firmware/dfu/iBSS.k48ap.RELEASE.dfu"
        if not ibss_path.exists():
            self._fail(f"iBSS file not found: {ibss_path}")
            return False

        result = self.transport.upload(ibss_path)
        if not result["success"]:
            self._fail(f"iBSS upload failed: {result['stderr']}")
            return False

        result = self.transport.send("go")
        if not result["success"]:
            self._fail(f"iBSS go command failed: {result['stderr']}")
            return False

        time.sleep(2)
        self.ibss_loaded = True
        print("[+] iBSS loaded successfully")
        return True

    def load_ibec(self) -> bool:
        if self.state not in (DeviceState.LOADING_IBSS, DeviceState.CONNECTING):
            self._fail(f"Cannot load iBEC from state {self.state.value}")
            return False

        self._transition(DeviceState.LOADING_IBEC, "Loading iBEC firmware")

        ibec_path = extracted / "Firmware/dfu/iBEC.k48ap.RELEASE.dfu"
        if not ibec_path.exists():
            self._fail(f"iBEC file not found: {ibec_path}")
            return False

        result = self.transport.upload(ibec_path)
        if not result["success"]:
            self._fail(f"iBEC upload failed: {result['stderr']}")
            return False

        result = self.transport.send("go")
        if not result["success"]:
            self._fail(f"iBEC go command failed: {result['stderr']}")
            return False

        time.sleep(2)
        self.ibec_loaded = True
        print("[+] iBEC loaded successfully")
        return True

    def attempt_connection(self) -> bool:
        if self.state == DeviceState.IDLE:
            self._transition(DeviceState.CONNECTING, "Attempting device connection")

        result = self.transport.query()
        if result["success"] and result["stdout"]:
            self.device_info = result["stdout"].strip()
            print(f"[+] Device connected:\n{self.device_info}")
            return True

        print("[-] Connection attempt failed")
        self._fail("Connection attempt failed")
        return False

    def boot(self, boot_type: str = "ramdisk") -> bool:
        if self.state not in (DeviceState.LOADING_IBEC, DeviceState.CONNECTING, DeviceState.LOADING_IBSS):
            self._fail(f"Cannot boot from state {self.state.value}")
            return False

        self._transition(DeviceState.BOOTING, f"Booting with type: {boot_type}")
        self.boot_attempted = True

        if boot_type == "ramdisk":
            success = self._boot_ramdisk()
        elif boot_type == "restore":
            success = self._boot_restore()
        elif boot_type == "ssh":
            success = self._boot_ssh()
        else:
            success = self._boot_ramdisk()

        if success:
            self.boot_successful = True
            self._transition(DeviceState.READY, "Boot successful")
        else:
            self._fail("Boot failed")

        return success

    def _boot_ramdisk(self) -> bool:
        print("[+] Booting ramdisk...")
        ramdisk_path = extracted / "038-1437-004.dmg"
        if ramdisk_path.exists():
            self.transport.upload(ramdisk_path)
            self.transport.send("ramdisk")

        dt_path = extracted / "Firmware/all_flash/all_flash.k48ap.production/DeviceTree.k48ap.img3"
        if dt_path.exists():
            self.transport.upload(dt_path)
            self.transport.send("devicetree")

        kernel_path = extracted / "kernelcache.release.k48"
        if kernel_path.exists():
            self.transport.upload(kernel_path)

        result = self.transport.send("bootx")
        if result["success"]:
            print("[+] Ramdisk boot command sent")
            time.sleep(2)
            return True

        print("[-] Ramdisk boot failed")
        return False

    def _boot_restore(self) -> bool:
        print("[+] Booting ERASE ramdisk for restore...")
        ramdisk_path = extracted / "038-1449-004.dmg"
        if ramdisk_path.exists():
            self.transport.upload(ramdisk_path)
            self.transport.send("ramdisk")

        dt_path = extracted / "Firmware/all_flash/all_flash.k48ap.production/DeviceTree.k48ap.img3"
        if dt_path.exists():
            self.transport.upload(dt_path)
            self.transport.send("devicetree")

        kernel_path = extracted / "kernelcache.release.k48"
        if kernel_path.exists():
            self.transport.upload(kernel_path)

        self.transport.send("setenv boot-args rd=md0 nand-enable-reformat=1 -v")
        self.transport.send("saveenv")
        result = self.transport.send("bootx")

        if result["success"]:
            print("[+] Restore boot command sent")
            time.sleep(90)
            return True

        print("[-] Restore boot failed")
        return False

    def _boot_ssh(self) -> bool:
        print("[+] Booting ramdisk with SSH enabled...")
        ramdisk_path = extracted / "038-1449-004.dmg"
        if ramdisk_path.exists():
            self.transport.upload(ramdisk_path)
            self.transport.send("ramdisk")

        dt_path = extracted / "Firmware/all_flash/all_flash.k48ap.production/DeviceTree.k48ap.img3"
        if dt_path.exists():
            self.transport.upload(dt_path)
            self.transport.send("devicetree")

        kernel_path = extracted / "kernelcache.release.k48"
        if kernel_path.exists():
            self.transport.upload(kernel_path)

        self.transport.send("setenv boot-args rd=md0 -v")
        result = self.transport.send("bootx")

        if result["success"]:
            print("[+] SSH boot command sent")
            print("[+] If it boots, connect via USB and use iproxy:")
            print("    iproxy 2222 22")
            print("    ssh root@localhost -p 2222")
            print("    password: alpine")
            time.sleep(2)
            return True

        print("[-] SSH boot failed")
        return False

    def run_full_probe(self, boot_mode: str = "ramdisk") -> bool:
        print("=" * 50)
        print("DEVICE PROBE - Native Toolkit State Machine")
        print("=" * 50)

        steps = [
            ("Probe Device", self.probe_device),
            ("Load iBSS", self.load_ibss),
            ("Load iBEC", self.load_ibec),
            ("Boot Device", lambda: self.boot(boot_mode)),
        ]

        for step_name, step_func in steps:
            print(f"\n[STEP] {step_name}")
            try:
                if not step_func():
                    print(f"[-] Step failed: {step_name}")
                    return False
                print(f"[+] Step complete: {step_name}")
            except Exception as e:
                print(f"[-] Step error: {step_name} - {e}")
                self._fail(str(e))
                return False

        print("\n" + "=" * 50)
        print("PROBE COMPLETE")
        print(f"State: {self.state.value}")
        print(f"Transitions: {' -> '.join(t for t in self._transitions)}")
        print(f"iBSS loaded: {self.ibss_loaded}")
        print(f"iBEC loaded: {self.ibec_loaded}")
        print(f"Boot attempted: {self.boot_attempted}")
        print(f"Boot successful: {self.boot_successful}")
        print("=" * 50)
        return True

    def get_state_history(self) -> List[str]:
        return list(self._transitions)

    def get_error(self) -> Optional[str]:
        return self._error_message

    def reset(self) -> None:
        self.state = DeviceState.IDLE
        self.device_info = None
        self.ibss_loaded = False
        self.ibec_loaded = False
        self.boot_attempted = False
        self.boot_successful = False
        self._transitions.clear()
        self._error_message = None
        print("[+] Device probe reset to IDLE state")


def main():
    if len(sys.argv) < 2:
        print("Usage: python device_probe.py <command> [options]")
        print("\nCommands:")
        print("  probe       - Probe device and load iBSS/iBEC")
        print("  connect     - Attempt device connection")
        print("  boot        - Attempt to boot (ramdisk/restore/ssh)")
        print("  full        - Run full probe chain (probe -> iBSS -> iBEC -> boot)")
        print("  reset       - Reset state machine to IDLE")
        print("\nOptions:")
        print("  --mode <ramdisk|restore|ssh>  - Boot mode (default: ramdisk)")
        sys.exit(1)

    command = sys.argv[1].lower()
    probe = DeviceProbe()

    boot_mode = "ramdisk"
    for i in range(2, len(sys.argv)):
        if sys.argv[i] == "--mode" and i + 1 < len(sys.argv):
            boot_mode = sys.argv[i + 1]

    if command == "probe":
        if probe.probe_device():
            print("[+] Device probed successfully")
        else:
            print("[-] Device probe failed")
            sys.exit(1)

    elif command == "connect":
        if probe.attempt_connection():
            print("[+] Device connected successfully")
        else:
            print("[-] Connection failed")
            sys.exit(1)

    elif command == "boot":
        if probe.state == DeviceState.IDLE:
            probe.probe_device()
            probe.load_ibss()
            probe.load_ibec()
        if probe.boot(boot_mode):
            print("[+] Boot successful")
        else:
            print("[-] Boot failed")
            sys.exit(1)

    elif command == "full":
        if not probe.run_full_probe(boot_mode):
            print("[-] Full probe failed")
            if probe.get_error():
                print(f"    Error: {probe.get_error()}")
            sys.exit(1)
        print("[+] Full probe completed successfully")

    elif command == "reset":
        probe.reset()

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()