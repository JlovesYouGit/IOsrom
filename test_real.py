#!/usr/bin/env python3
"""Real test of native toolkit against connected iPhone 7 Plus in Recovery mode."""
import sys
import json
from pathlib import Path

# Add repo to path for native_toolkit import
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from native_toolkit.transport import NativeTransport, DeviceMode
from native_toolkit.states import DeviceStateMachine, StateEvent
from native_toolkit.exceptions import DeviceNotFoundError


def main():
    print("=" * 60)
    print("NATIVE TOOLKIT - REAL DEVICE TEST")
    print("=" * 60)
    
    # Test 1: Direct transport probe
    print("\n[TEST 1] NativeTransport.probe()")
    transport = NativeTransport()
    try:
        devices = transport.probe()
        if not devices:
            print("[-] No devices detected via transport.probe()")
        else:
            for i, dev in enumerate(devices):
                print(f"[+] Device {i}:")
                print(f"    Mode      : {dev.mode.value}")
                print(f"    Product   : {dev.product}")
                print(f"    Model     : {dev.model}")
                print(f"    Name      : {dev.name}")
                print(f"    ECID      : {dev.ecid}")
                print(f"    CPID      : {dev.cpid}")
                print(f"    Board ID  : {dev.board_id}")
                print(f"    Firmware  : {dev.firmware_version}")
                print(f"    NONC      : {dev.nonce}")
                print(f"    SNON      : {dev.snon}")
                print(f"    SRNM      : {dev.srnm}")
                print(f"    SRTG      : {dev.srtg}")
                print(f"    Raw lines : {len(dev.raw.splitlines())}")
    except Exception as e:
        print(f"[-] Transport probe failed: {type(e).__name__}: {e}")
    
    # Test 2: State machine detection
    print("\n[TEST 2] DeviceStateMachine.probe()")
    sm = DeviceStateMachine()
    try:
        state = sm.probe()
        print(f"[+] Current state: {state.name}")
        print(f"    Device: {sm.ctx.device.name if sm.ctx.device else 'None'}")
    except DeviceNotFoundError:
        print("[-] Device not found in state machine probe")
    except Exception as e:
        print(f"[-] State machine probe failed: {type(e).__name__}: {e}")
    
    # Test 3: Wait for specific state
    print("\n[TEST 3] wait_for_state('recovery', timeout=5)")
    sm2 = DeviceStateMachine()
    try:
        state = sm2.wait_for_state("recovery", timeout=5.0)
        print(f"[+] Reached state: {state.name}")
        print(f"    Device info available: {sm2.ctx.device is not None}")
    except TimeoutError:
        print("[-] Timeout waiting for recovery state (device may have disconnected)")
    except DeviceNotFoundError:
        print("[-] Device not found during wait")
    except Exception as e:
        print(f"[-] wait_for_state failed: {type(e).__name__}: {e}")
    
    # Test 4: Verify libirecovery direct access
    print("\n[TEST 4] Direct LibIRecovery device_query()")
    try:
        from native_toolkit.transport import LibIRecovery
        irec = LibIRecovery()
        client = irec.device_new()
        query = irec.device_query(client)
        irec.device_close(client)
        if query:
            print("[+] Direct query succeeded:")
            for line in query.splitlines()[:15]:
                print(f"    {line}")
        else:
            print("[-] Direct query returned empty")
    except Exception as e:
        print(f"[-] Direct query failed: {type(e).__name__}: {e}")
    
    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
