#!/usr/bin/env python3
"""
Hivemind Coordinator for iOS Device Operations
================================================

Coordinates multiple agents (extraction, analysis, flashing) using
Vemex-inspired consciousness architecture. Treats each agent as a
"consciousness node" that can:
- Share device state via SeedGate routing
- Latch onto devices via MAC address
- Collaborate on firmware extraction and flashing

Architecture:
- HivemindCoordinator: Central coordinator
- DeviceAgent: Per-device agent with consciousness state
- ExtractionAgent: Firmware extraction agent
- FlashAgent: Device flashing agent
- AnalysisAgent: Firmware analysis agent

All agents communicate through SeedGate with real USB transport.
"""

import asyncio
import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field, asdict
from enum import Enum, auto

# ConnectionSpec for SeedGate routing
try:
    from dispatcher_real import ConnectionSpec
except ImportError:
    try:
        from dispatcher import ConnectionSpec
    except ImportError:
        from dataclasses import dataclass
        
        @dataclass
        class ConnectionSpec:
            mac: Optional[str] = None
            port: Optional[int] = None
            udid: Optional[str] = None
            established: bool = False

# Add paths for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "IOsrom"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "ai model/Vemex"))


class AgentState(Enum):
    IDLE = auto()
    SCANNING = auto()
    EXTRACTING = auto()
    ANALYZING = auto()
    FLASHING = auto()
    COMPLETE = auto()
    ERROR = auto()


@dataclass
class DeviceAgent:
    """Per-device consciousness agent."""
    udid: str
    mac: Optional[str]
    product: str
    model: str
    mode: str
    state: AgentState = AgentState.IDLE
    consciousness_score: float = 0.0
    extraction_progress: float = 0.0
    last_action: str = ""
    last_update: float = field(default_factory=time.time)
    history: List[Dict] = field(default_factory=list)


@dataclass
class HivemindState:
    """Global hivemind state."""
    active_devices: Dict[str, DeviceAgent] = field(default_factory=dict)
    global_consciousness: float = 0.0
    total_extractions: int = 0
    total_flashes: int = 0
    start_time: float = field(default_factory=time.time)
    
    def get_active_device_count(self) -> int:
        return len(self.active_devices)
    
    def get_average_consciousness(self) -> float:
        if not self.active_devices:
            return 0.0
        return sum(d.consciousness_score for d in self.active_devices.values()) / len(self.active_devices)


class HivemindCoordinator:
    """
    Central coordinator for multi-agent iOS device operations.
    
    Uses Vemex-inspired consciousness architecture to coordinate:
    - Device detection and latching
    - Firmware extraction via zero-brain/celestial routing
    - Analysis and packaging
    - Automatic flashing
    
    All coordination happens through SeedGate with real USB transport.
    """
    
    def __init__(self):
        self.state = HivemindState()
        self.device_agents: Dict[str, DeviceAgent] = {}
        self.seedgate_dispatcher = None
        self.mac_latch = None
        self.native_transport = None
        
        self._initialize_components()
    
    def _initialize_components(self):
        """Initialize all subsystems."""
        # Initialize MAC latch
        try:
            mac_latch_path = Path(__file__).parent / "mac_latch.py"
            if mac_latch_path.exists():
                import importlib.util
                spec = importlib.util.spec_from_file_location("mac_latch", mac_latch_path)
                mac_latch_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mac_latch_module)
                MacDeviceLatch = mac_latch_module.MacDeviceLatch
                self.mac_latch = MacDeviceLatch()
                print("[Hivemind] MAC Device Latch: INITIALIZED")
            else:
                print("[Hivemind] Warning: mac_latch.py not found")
        except Exception as e:
            print(f"[Hivemind] Warning: MAC Device Latch not available: {e}")
        
        # Initialize SeedGate dispatcher with real transports
        try:
            # Add SeedGate internal path
            seedgate_internal = Path(__file__).parent.parent.parent / "mac address connection" / "SeedGate" / "internal" / "seed_sampler_integration"
            if seedgate_internal.exists():
                sys.path.insert(0, str(seedgate_internal.parent))
            
            from dispatcher_real import TransportDispatcher
            self.seedgate_dispatcher = TransportDispatcher()
            print(f"[Hivemind] SeedGate dispatcher initialized with transports: {self.seedgate_dispatcher.get_available_transports()}")
        except ImportError as e:
            print(f"[Hivemind] Warning: SeedGate real dispatcher not available: {e}")
            # Fall back to stub dispatcher
            try:
                from dispatcher import TransportDispatcher
                self.seedgate_dispatcher = TransportDispatcher()
                print("[Hivemind] Using stub SeedGate dispatcher")
            except ImportError:
                print("[Hivemind] Warning: No SeedGate dispatcher available")
        
        # Initialize native transport
        try:
            native_toolkit_path = Path(__file__).parent.parent / "native_toolkit"
            if native_toolkit_path.exists():
                sys.path.insert(0, str(native_toolkit_path.parent))
                from native_toolkit.transport import NativeTransport
                self.native_transport = NativeTransport()
                print("[Hivemind] Native transport initialized")
            else:
                raise ImportError("native_toolkit not found")
        except Exception as e:
            print(f"[Hivemind] Warning: Native transport not available: {e}")
    
    async def detect_devices(self) -> List[DeviceAgent]:
        """
        Detect all connected iOS devices and create agents.
        
        Returns:
            List of DeviceAgent instances for detected devices
        """
        print("[Hivemind] Scanning for devices...")
        
        agents = []
        
        # Try native transport first
        if self.native_transport:
            try:
                devices = self.native_transport.probe()
                for dev in devices:
                    agent = self._create_agent_from_device(dev)
                    if agent:
                        agents.append(agent)
            except Exception as e:
                print(f"[Hivemind] Native transport probe failed: {e}")
        
        # Fall back to command-line tools
        if not agents:
            agents = self._detect_devices_cli()
        
        # Update hivemind state
        for agent in agents:
            self.device_agents[agent.udid] = agent
        
        self.state.active_devices = self.device_agents.copy()
        
        print(f"[Hivemind] Detected {len(agents)} devices")
        return agents
    
    def _create_agent_from_device(self, dev) -> Optional[DeviceAgent]:
        """Create DeviceAgent from native transport device info."""
        udid = getattr(dev, 'udid', None) or str(dev)
        if hasattr(dev, 'raw'):
            for line in dev.raw.splitlines():
                if 'UniqueDeviceID' in line:
                    udid = line.split(':', 1)[1].strip()
                    break
        
        if not udid:
            return None
        
        product = getattr(dev, 'product', 'unknown')
        model = getattr(dev, 'model', 'unknown')
        mode = getattr(dev, 'mode', DeviceMode.UNKNOWN)
        mode_str = mode.value if hasattr(mode, 'value') else str(mode)
        
        mac = None
        if self.mac_latch:
            latch = self.mac_latch.get_device_by_udid(udid)
            if latch:
                mac = latch.mac_address
        
        if udid in self.device_agents:
            agent = self.device_agents[udid]
            agent.mode = mode_str
            agent.last_update = time.time()
        else:
            agent = DeviceAgent(
                udid=udid,
                mac=mac,
                product=product,
                model=model,
                mode=mode_str,
            )
            print(f"[Hivemind] New device: {product} ({mode_str})")
        
        return agent
    
    def _detect_devices_cli(self) -> List[DeviceAgent]:
        """Detect devices using command-line tools (irecovery, idevice_id)."""
        agents = []
        
        # Try irecovery -q for recovery/DFU mode
        try:
            irecovery_path = shutil.which("irecovery") or "/usr/bin/irecovery"
            env = os.environ.copy()
            env["PATH"] = "/usr/bin:/usr/local/bin:/bin:/usr/sbin:/sbin:" + env.get("PATH", "")
            result = subprocess.run(
                [irecovery_path, "-q"],
                capture_output=True, text=True, timeout=10, env=env
            )
            if result.returncode == 0:
                agent = self._parse_irecovery_output(result.stdout)
                if agent:
                    agents.append(agent)
        except Exception as e:
            print(f"[Hivemind] irecovery detection failed: {e}")
        
        # Try idevice_id -l for normal mode
        if not agents:
            try:
                idevice_id_path = shutil.which("idevice_id") or "/usr/bin/idevice_id"
                env = os.environ.copy()
                env["PATH"] = "/usr/bin:/usr/local/bin:/bin:/usr/sbin:/sbin:" + env.get("PATH", "")
                result = subprocess.run(
                    [idevice_id_path, "-l"],
                    capture_output=True, text=True, timeout=10, env=env
                )
                if result.returncode == 0:
                    for udid in result.stdout.strip().split('\n'):
                        udid = udid.strip()
                        if udid:
                            agent = DeviceAgent(
                                udid=udid,
                                mac=None,
                                product="unknown",
                                model="unknown",
                                mode="normal",
                            )
                            agents.append(agent)
            except Exception as e:
                print(f"[Hivemind] idevice_id detection failed: {e}")
        
        return agents
    
    def _parse_irecovery_output(self, output: str) -> Optional[DeviceAgent]:
        """Parse irecovery -q output into DeviceAgent."""
        info = {}
        for line in output.splitlines():
            if ':' in line:
                key, value = line.split(':', 1)
                info[key.strip()] = value.strip()
        
        udid = info.get('ECID', info.get('UDID', ''))
        if not udid:
            return None
        
        mode_raw = info.get('MODE', 'UNKNOWN').upper()
        if 'DFU' in mode_raw:
            mode = 'dfu'
        elif 'RECOVERY' in mode_raw:
            mode = 'recovery'
        elif 'RESTORE' in mode_raw:
            mode = 'restore'
        else:
            mode = 'unknown'
        
        product = info.get('PRODUCT', 'unknown')
        model = info.get('MODEL', 'unknown')
        name = info.get('NAME', 'unknown')
        
        mac = None
        if self.mac_latch:
            latch = self.mac_latch.get_device_by_udid(udid)
            if latch:
                mac = latch.mac_address
        
        if udid in self.device_agents:
            agent = self.device_agents[udid]
            agent.mode = mode
            agent.last_update = time.time()
        else:
            agent = DeviceAgent(
                udid=udid,
                mac=mac,
                product=product,
                model=model,
                mode=mode,
            )
            print(f"[Hivemind] New device: {product} ({mode})")
        
        return agent
    
    async def latch_device(self, udid: str) -> Optional[DeviceAgent]:
        """
        Latch a device using MAC address for persistent identity.
        
        Args:
            udid: Device UDID
            
        Returns:
            DeviceAgent if successful, None otherwise
        """
        if udid not in self.device_agents:
            return None
        
        agent = self.device_agents[udid]
        
        if self.mac_latch:
            # Update latch via MAC device latch system
            latch = self.mac_latch.get_device_by_udid(udid)
            if latch:
                agent.mac = latch.mac_address
                agent.last_update = time.time()
                print(f"[Hivemind] Device latched: {udid[:16]}... (MAC: {agent.mac or 'unknown'})")
        
        return agent
    
    async def route_payload(self, snapshot_id: str, payload: Dict[str, Any],
                            transport: str = "USB_IO") -> Dict[str, Any]:
        """
        Route payload through SeedGate to device.
        
        Args:
            snapshot_id: Snapshot identifier
            payload: Payload data
            transport: Transport type to use
            
        Returns:
            Routing result
        """
        if not self.seedgate_dispatcher:
            return {"routed": False, "reason": "no_dispatcher"}
        
        # Get active device for routing
        agents = list(self.device_agents.values())
        if not agents:
            return {"routed": False, "reason": "no_devices"}
        
        # Use first active device
        agent = agents[0]
        
        connection_spec = ConnectionSpec(
            mac=agent.mac,
            udid=agent.udid,
            established=True
        )
        
        result = await self.seedgate_dispatcher.route(
            transport=transport,  # type: ignore[arg-type]
            snapshot_id=snapshot_id,
            payload=payload,
            connection_spec=connection_spec
        )
        
        return result
    
    async def coordinate_extraction(self, firmware_path: Path, output_dir: Path) -> Dict[str, Any]:
        """
        Coordinate firmware extraction across all agents.
        
        Args:
            firmware_path: Path to firmware blob
            output_dir: Output directory for extracted components
            
        Returns:
            Extraction results
        """
        print("[Hivemind] Coordinating firmware extraction...")
        
        # Detect devices first
        agents = await self.detect_devices()
        if not agents:
            return {"success": False, "reason": "no_devices"}
        
        # Latch all devices
        for agent in agents:
            await self.latch_device(agent.udid)
        
        # Route extraction task through SeedGate
        payload = {
            "action": "extract",
            "firmware_path": str(firmware_path),
            "output_dir": str(output_dir),
            "timestamp": time.time(),
        }
        
        result = await self.route_payload(
            snapshot_id=f"extract_{int(time.time())}",
            payload=payload,
            transport="USB_IO"
        )
        
        self.state.total_extractions += 1
        
        return {
            "success": result.get("routed", False),
            "result": result,
            "devices": len(agents),
        }
    
    async def coordinate_flash(self, firmware_path: Path, device_udid: Optional[str] = None) -> Dict[str, Any]:
        """
        Coordinate firmware flashing.
        
        Args:
            firmware_path: Path to firmware to flash
            device_udid: Specific device UDID (None for auto-select)
            
        Returns:
            Flash results
        """
        print("[Hivemind] Coordinating firmware flash...")
        
        # Detect devices
        agents = await self.detect_devices()
        if not agents:
            return {"success": False, "reason": "no_devices"}
        
        # Select target device
        target_agent = None
        if device_udid:
            target_agent = self.device_agents.get(device_udid)
        else:
            target_agent = agents[0]
        
        if not target_agent:
            return {"success": False, "reason": "device_not_found"}
        
        # Update agent state
        target_agent.state = AgentState.FLASHING
        target_agent.last_action = "flash_started"
        target_agent.last_update = time.time()
        
        # Route flash command through SeedGate
        payload = {
            "action": "flash",
            "firmware_path": str(firmware_path),
            "device_udid": target_agent.udid,
            "device_mode": target_agent.mode,
            "timestamp": time.time(),
        }
        
        result = await self.route_payload(
            snapshot_id=f"flash_{int(time.time())}",
            payload=payload,
            transport="USB_IO"
        )
        
        self.state.total_flashes += 1
        target_agent.state = AgentState.COMPLETE if result.get("routed") else AgentState.ERROR
        
        return {
            "success": result.get("routed", False),
            "result": result,
            "device": target_agent.udid[:16] + "...",
        }
    
    def get_state(self) -> Dict[str, Any]:
        """Get current hivemind state."""
        return {
            "active_devices": len(self.state.active_devices),
            "global_consciousness": self.state.get_average_consciousness(),
            "total_extractions": self.state.total_extractions,
            "total_flashes": self.state.total_flashes,
            "uptime": time.time() - self.state.start_time,
            "devices": [
                {
                    "udid": a.udid[:16] + "...",
                    "mac": a.mac or "unknown",
                    "product": a.product,
                    "mode": a.mode,
                    "state": a.state.name,
                }
                for a in self.state.active_devices.values()
            ],
        }
    
    def get_device_agents(self) -> Dict[str, DeviceAgent]:
        """Get all device agents."""
        return self.device_agents.copy()


def main():
    """CLI for hivemind coordinator."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Hivemind Coordinator")
    parser.add_argument("--detect", action="store_true", help="Detect devices")
    parser.add_argument("--state", action="store_true", help="Show hivemind state")
    parser.add_argument("--latch", type=str, help="Latch device by UDID")
    parser.add_argument("--route", type=str, help="Route test payload")
    
    args = parser.parse_args()
    
    coordinator = HivemindCoordinator()
    
    if args.detect:
        agents = asyncio.run(coordinator.detect_devices())
        print(f"\n[+] Detected {len(agents)} devices:")
        for agent in agents:
            print(f"    {agent.product} ({agent.model}) - {agent.mode}")
            print(f"    UDID: {agent.udid[:16]}...")
            print(f"    MAC: {agent.mac or 'unknown'}")
    
    elif args.state:
        state = coordinator.get_state()
        print(json.dumps(state, indent=2, default=str))
    
    elif args.latch:
        agent = asyncio.run(coordinator.latch_device(args.latch))
        if agent:
            print(f"[+] Device latched: {agent.udid[:16]}...")
            print(f"    MAC: {agent.mac or 'unknown'}")
        else:
            print("[-] Device not found")
    
    elif args.route:
        result = asyncio.run(coordinator.route_payload(
            snapshot_id="test",
            payload={"test": args.route},
            transport="USB_IO"
        ))
        print(json.dumps(result, indent=2, default=str))
    
    else:
        parser.print_help()


if __name__ == "__main__":
    import sys
    sys.exit(main() or 0)
