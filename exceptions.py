#!/usr/bin/env python3
"""Custom exceptions for Native iOS Toolkit."""
from typing import Optional


class NativeToolkitError(Exception):
    """Base exception for all toolkit errors."""
    pass


class DeviceNotFoundError(NativeToolkitError):
    """ Raised when no iOS device is detected."""
    pass


class DeviceStateError(NativeToolkitError):
    """Raised when device is in unexpected state for requested operation."""
    def __init__(self, expected: str, actual: str):
        self.expected = expected
        self.actual = actual
        super().__init__(f"Expected device state '{expected}', but got '{actual}'")


class ExploitError(NativeToolkitError):
    """Raised when exploit delivery fails."""
    pass


class RestoreError(NativeToolkitError):
    """Raised when restore operation fails."""
    pass


class SignatureError(NativeToolkitError):
    """Raised when signature verification fails."""
    pass


class FirmwareError(NativeToolkitError):
    """Raised when firmware component is invalid or missing."""
    pass


class TransportError(NativeToolkitError):
    """Raised when USB/transport communication fails."""
    def __init__(self, message: str, cause: Optional[Exception] = None):
        super().__init__(message)
        self.cause = cause
