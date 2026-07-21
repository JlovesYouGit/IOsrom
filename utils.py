#!/usr/bin/env python3
"""Shared utilities for iOS firmware tools."""
import os
import sys
import subprocess
import logging
from pathlib import Path
from typing import Optional, List

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


class PathConfig:
    """Centralized path configuration."""
    
    def __init__(self, base_dir: Optional[str] = None):
        self.base_dir = Path(base_dir or os.environ.get('IOS_TOOLS_BASE', 'N:/ROMLOADDER'))
        self.chargfast_dir = self.base_dir / 'chargfast via usb'
        self.extracted_dir = self.chargfast_dir / 'extracted'
        self.firmware_dir = self.base_dir / 'firmware'
        self.output_dir = self.base_dir / 'output'
        
        for directory in [self.chargfast_dir, self.extracted_dir, self.firmware_dir, self.output_dir]:
            directory.mkdir(parents=True, exist_ok=True)
    
    def irecovery(self) -> Path:
        return self.chargfast_dir / 'irecovery.exe'
    
    def idevicerestore(self) -> Path:
        return self.chargfast_dir / 'idevicerestore.exe'
    
    def ipsw(self, filename: str) -> Path:
        return self.base_dir / filename


def run_command(
    cmd: List[str],
    cwd: Optional[Path] = None,
    timeout: int = 60,
    capture: bool = True
) -> subprocess.CompletedProcess:
    """Run a command with proper error handling."""
    try:
        result = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            capture_output=capture,
            text=True,
            timeout=timeout,
            check=False
        )
        return result
    except subprocess.TimeoutExpired:
        logger.error(f"Command timed out: {' '.join(cmd)}")
        raise
    except FileNotFoundError:
        logger.error(f"Command not found: {cmd[0]}")
        raise
    except Exception as e:
        logger.error(f"Command failed: {' '.join(cmd)} - {e}")
        raise


def validate_hex(value: str, expected_length: Optional[int] = None) -> str:
    """Validate and normalize hex string."""
    cleaned = value.replace('0x', '').replace(':', '').strip()
    if expected_length and len(cleaned) != expected_length:
        raise ValueError(f"Expected {expected_length} hex chars, got {len(cleaned)}")
    try:
        int(cleaned, 16)
    except ValueError:
        raise ValueError(f"Invalid hex string: {value}")
    return cleaned


def backup_file(path: Path) -> Optional[Path]:
    """Create backup of file before modification."""
    if not path.exists():
        return None
    backup = path.with_suffix(path.suffix + '.backup')
    counter = 1
    while backup.exists():
        backup = path.with_suffix(f"{path.suffix}.backup.{counter}")
        counter += 1
    import shutil
    shutil.copy2(path, backup)
    logger.info(f"Backed up: {path} -> {backup}")
    return backup
