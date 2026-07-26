#!/usr/bin/env python3
"""Device state machine and mode transitions."""
import time
import subprocess
from pathlib import Path
from typing import Optional
from enum import Enum, auto
from dataclasses import dataclass

from .exceptions import (
    DeviceNotFoundError,
    DeviceStateError,
    NativeToolkitError,
    TransportError,
)
from .transport import DeviceMode, DeviceInfo, NativeTransport


class StateEvent(Enum):
    """Events that trigger state transitions."""
    DETECT = auto()
    USB_CONNECT = auto()
    DFU_ENTER = auto()
    RECOVERY_ENTER = auto()
    NORMAL_ENTER = auto()
    iBSS_LOADED = auto()
    iBEC_LOADED = auto()
    RAMDISK_BOOTED = auto()
    KERNEL_BOOTED = auto()
    EXPLOIT_SUCCESS = auto()
    EXPLOIT_FAIL = auto()
    RESET = auto()
    USB_DISCONNECT = auto()


@dataclass
class StateContext:
    """Mutable state container passed through the state machine."""
    device: Optional[DeviceInfo] = None
    usb_path: Optional[str] = None
    udid: Optional[str] = None
    ibss_loaded: bool = False
    ibec_loaded: bool = False
    ramdisk_loaded: bool = False
    kernel_booted: bool = False
    exploit_complete: bool = False
    last_error: Optional[str] = None
    attempt_count: int = 0


class DeviceState:
    """Base state class."""
    name = "base"
    allowed_transitions = []
    
    def on_enter(self, ctx: StateContext) -> None:
        pass
    
    def on_exit(self, ctx: StateContext) -> None:
        pass
    
    def handle(self, event: StateEvent, ctx: StateContext) -> "DeviceState":
        raise NotImplementedError


class NoDeviceState(DeviceState):
    name = "no_device"
    allowed_transitions = ["detecting"]
    
    def handle(self, event: StateEvent, ctx: StateContext) -> DeviceState:
        if event == StateEvent.DETECT:
            return DetectingState()
        return self


class DetectingState(DeviceState):
    name = "detecting"
    allowed_transitions = ["no_device", "normal", "recovery", "dfu"]
    
    def __init__(self):
        self.transport = NativeTransport()
    
    def on_enter(self, ctx: StateContext) -> None:
        ctx.attempt_count += 1
    
    def handle(self, event: StateEvent, ctx: StateContext) -> DeviceState:
        if event == StateEvent.DETECT:
            devices = self.transport.probe()
            if not devices:
                if ctx.attempt_count > 3:
                    raise DeviceNotFoundError("Device not detected after multiple attempts")
                return self  # retry
            
            dev = devices[0]
            ctx.device = dev
            ctx.udid = self._extract_udid(dev.raw)
            
            if dev.mode == DeviceMode.NORMAL:
                return NormalState()
            elif dev.mode == DeviceMode.RECOVERY:
                return RecoveryState()
            elif dev.mode == DeviceMode.DFU:
                return DfuState()
        
        return self
    
    def _extract_udid(self, raw: str) -> Optional[str]:
        # UDID extraction from various formats
        for line in raw.splitlines():
            if "UniqueDeviceID" in line:
                return line.split(":", 1)[1].strip()
            if line.startswith("a9285ad0"):
                return line.strip()
        return None


class NormalState(DeviceState):
    name = "normal"
    allowed_transitions = ["no_device", "recovery", "dfu"]
    
    def handle(self, event: StateEvent, ctx: StateContext) -> DeviceState:
        if event == StateEvent.RECOVERY_ENTER:
            return RecoveryState()
        elif event == StateEvent.DFU_ENTER:
            return DfuState()
        elif event == StateEvent.USB_DISCONNECT:
            ctx.device = None
            return NoDeviceState()
        return self


class RecoveryState(DeviceState):
    name = "recovery"
    allowed_transitions = ["normal", "dfu", "pwned_recovery", "no_device"]
    transport = NativeTransport()
    
    def on_enter(self, ctx: StateContext) -> None:
        print(f"[+] Device in Recovery mode: {ctx.device.name if ctx.device else 'unknown'}")
    
    def handle(self, event: StateEvent, ctx: StateContext) -> DeviceState:
        if event == StateEvent.NORMAL_ENTER:
            return NormalState()
        elif event == StateEvent.DFU_ENTER:
            return DfuState()
        elif event == StateEvent.USB_DISCONNECT:
            ctx.device = None
            return NoDeviceState()
        return self
    
    def enter_dfu(self, ctx: StateContext) -> "DfuState":
        """Attempt to transition recovery -> DFU via recovery commands."""
        if not ctx.device:
            raise DeviceStateError("dfu", "none")
        
        try:
            rc = self.transport.open_recovery(ctx.udid)
            # Send DFU enter command sequence
            cmds = [
                "setenv auto-boot false",
                "saveenv",
            ]
            for cmd in cmds:
                self.transport.irec.device_command(rc, cmd)
            
            self.transport.close(rc)
            time.sleep(1)
            return DfuState()
        except Exception as e:
            raise DeviceStateError("dfu", f"recovery (command failed: {e})")


class DfuState(DeviceState):
    name = "dfu"
    allowed_transitions = ["recovery", "pwned_recovery", "no_device"]
    transport = NativeTransport()
    
    def on_enter(self, ctx: StateContext) -> None:
        print("[+] Device in DFU mode - ready for exploit payload")
    
    def handle(self, event: StateEvent, ctx: StateContext) -> DeviceState:
        if event == StateEvent.RECOVERY_ENTER:
            return RecoveryState()
        elif event == StateEvent.EXPLOIT_SUCCESS:
            return PwnedRecoveryState()
        elif event == StateEvent.USB_DISCONNECT:
            ctx.device = None
            return NoDeviceState()
        return self
    
    def load_ibss(self, ctx: StateContext, ibss_path: str) -> None:
        """Load iBSS from DFU mode."""
        if not ctx.device or ctx.device.mode != DeviceMode.DFU:
            raise DeviceStateError("dfu", ctx.device.mode.value if ctx.device else "unknown")
        
        try:
            rc = self.transport.irec.device_new()
            print(f"[+] Loading iBSS: {Path(ibss_path).name}")
            self.transport.irec.device_receive(rc, "DFU")
            self.transport.irec.device_send_file(rc, ibss_path)
            self.transport.irec.device_execute(rc, b"")
            time.sleep(2)
            self.transport.close(rc)
            ctx.ibss_loaded = True
        except Exception as e:
            raise ExploitError(f"iBSS load failed: {e}")


class PwnedRecoveryState(DeviceState):
    name = "pwned_recovery"
    allowed_transitions = ["booted_ramdisk", "booted_kernel", "normal", "no_device"]
    transport = NativeTransport()
    
    def on_enter(self, ctx: StateContext) -> None:
        print("[+] Device is in pwned Recovery mode - signature checks bypassed")
        ctx.exploit_complete = True
    
    def handle(self, event: StateEvent, ctx: StateContext) -> DeviceState:
        if event == StateEvent.RAMDISK_BOOTED:
            return BootedRamdiskState()
        elif event == StateEvent.KERNEL_BOOTED:
            return BootedKernelState()
        elif event == StateEvent.NORMAL_ENTER:
            return NormalState()
        elif event == StateEvent.USB_DISCONNECT:
            ctx.device = None
            return NoDeviceState()
        return self
    
    def load_ibec(self, ctx: StateContext, ibec_path: str) -> None:
        """Load iBEC after iBSS to reach pwned recovery."""
        if not ctx.ibss_loaded:
            raise DeviceStateError("ibec", "ibss not loaded")
        
        try:
            rc = self.transport.irec.device_new()
            print(f"[+] Loading iBEC: {Path(ibec_path).name}")
            self.transport.irec.device_send_file(rc, ibec_path)
            self.transport.irec.device_execute(rc, b"")
            time.sleep(2)
            self.transport.close(rc)
            ctx.ibec_loaded = True
        except Exception as e:
            raise ExploitError(f"iBEC load failed: {e}")


class BootedRamdiskState(DeviceState):
    name = "booted_ramdisk"
    allowed_transitions = ["booted_kernel", "normal", "no_device"]
    
    def handle(self, event: StateEvent, ctx: StateContext) -> DeviceState:
        if event == StateEvent.KERNEL_BOOTED:
            return BootedKernelState()
        elif event == StateEvent.NORMAL_ENTER:
            return NormalState()
        elif event == StateEvent.USB_DISCONNECT:
            ctx.device = None
            return NoDeviceState()
        return self


class BootedKernelState(DeviceState):
    name = "booted_kernel"
    allowed_transitions = ["normal", "no_device"]
    
    def on_enter(self, ctx: StateContext) -> None:
        print("[+] Kernel booted successfully")
        ctx.kernel_booted = True
    
    def handle(self, event: StateEvent, ctx: StateContext) -> DeviceState:
        if event == StateEvent.NORMAL_ENTER:
            return NormalState()
        elif event == StateEvent.USB_DISCONNECT:
            ctx.device = None
            return NoDeviceState()
        return self


class DeviceStateMachine:
    """Manages device state transitions and enforces valid paths."""
    
    def __init__(self):
        self.state = NoDeviceState()
        self.ctx = StateContext()
        self.transport = NativeTransport()
    
    def current_state(self) -> str:
        return self.state.name
    
    def dispatch(self, event: StateEvent) -> DeviceState:
        """Process an event and transition state if valid."""
        next_state = self.state.handle(event, self.ctx)
        if next_state is not self.state:
            self.state.on_exit(self.ctx)
            self.state = next_state
            self.state.on_enter(self.ctx)
        return self.state
    
    def probe(self) -> DeviceState:
        """Trigger a detection cycle."""
        try:
            return self.dispatch(StateEvent.DETECT)
        except DeviceNotFoundError:
            self.state = NoDeviceState()
            raise
    
    def wait_for_state(self, target_state_name: str, timeout: float = 60.0,
                       poll_interval: float = 2.0) -> DeviceState:
        """Poll probe() until target state or timeout."""
        import time
        start = time.time()
        deadline = start + timeout
        
        while time.time() < deadline:
            try:
                self.probe()
                if self.state.name == target_state_name:
                    return self.state
            except DeviceNotFoundError:
                pass
            
            # Also check for USB disconnect/reconnect during transient states
            time.sleep(poll_interval)
        
        raise TimeoutError(f"Timeout waiting for state '{target_state_name}'; "
                          f"current: {self.state.name}")
