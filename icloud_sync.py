"""
iCloud Sync Module - Cloud support for parent device synchronization
Manages data synchronization between local files and iCloud Drive.
"""

import json
import os
import sys
import time
import hashlib
from datetime import datetime
from typing import Any, Optional
from pathlib import Path

try:
    from pyicloud import PyiCloudService
    from pyicloud.services.drive import DriveNode
    HAS_PYICLOUD = True
except ImportError:
    HAS_PYICLOUD = False

CLOUD_CONFIG_FILE = "cloud_config.json"
ICLOUD_DRIVE_DIR = "SatoshiNM"
SYNCED_FILES = [
    "credentials.json",
    "private_keys.json",
    "balance_history.json",
    "seednet_catalog.json",
    "enclave_extract.json",
    "im4m_manifest.json",
    "device_detect.json",
]


class CloudSyncError(Exception):
    pass


class ICloudSync:
    def __init__(self, username: str = None, password: str = None, config_dir: str = "."):
        self.username = username or os.getenv("ICLOUD_EMAIL", "jhan.flores@icloud.com")
        self.password = password or os.getenv("ICLOUD_PASSWORD", "Cupeiroza14-14")
        self.config_dir = config_dir
        self.config_path = os.path.join(config_dir, CLOUD_CONFIG_FILE)
        self.api: Optional[PyiCloudService] = None
        self.drive: Optional[Any] = None
        self._authenticated = False
        self._last_sync = None

    def _load_config(self) -> dict:
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {}
        return {}

    def _save_config(self, config: dict):
        with open(self.config_path, "w") as f:
            json.dump(config, f, indent=2)

    def authenticate(self) -> bool:
        if not HAS_PYICLOUD:
            raise CloudSyncError("pyicloud is not installed. Run: pip install pyicloud")

        try:
            self.api = PyiCloudService(self.username, self.password)
            self.drive = self.api.drive
            self._authenticated = True

            config = self._load_config()
            config["authenticated"] = True
            config["last_auth"] = datetime.now().isoformat()
            config["username"] = self.username
            self._save_config(config)

            return True
        except Exception as e:
            raise CloudSyncError(f"iCloud authentication failed: {str(e)}")

    def is_authenticated(self) -> bool:
        return self._authenticated and self.api is not None

    def _get_drive_node(self) -> DriveNode:
        if not self.drive:
            raise CloudSyncError("Not authenticated. Call authenticate() first.")

        app_data = self.drive[ICLOUD_DRIVE_DIR]
        if app_data is None:
            raise CloudSyncError(f"iCloud Drive directory '{ICLOUD_DRIVE_DIR}' not found.")
        return app_data

    def upload_file(self, local_path: str, remote_name: str = None) -> dict:
        if not self._authenticated:
            raise CloudSyncError("Not authenticated. Call authenticate() first.")

        remote_name = remote_name or os.path.basename(local_path)
        local_full = os.path.join(self.config_dir, local_path)

        if not os.path.exists(local_full):
            raise CloudSyncError(f"Local file not found: {local_full}")

        try:
            with open(local_full, "rb") as f:
                data = f.read()

            node = self._get_drive_node()
            remote_file = node[remote_name]
            if remote_file is None:
                remote_file = node.create_file(remote_name, data)
            else:
                remote_file.write(data)

            result = {
                "action": "upload",
                "file": remote_name,
                "size": len(data),
                "timestamp": datetime.now().isoformat(),
                "success": True,
            }
            return result
        except Exception as e:
            raise CloudSyncError(f"Upload failed for {remote_name}: {str(e)}")

    def download_file(self, remote_name: str, local_path: str = None) -> dict:
        if not self._authenticated:
            raise CloudSyncError("Not authenticated. Call authenticate() first.")

        local_path = local_path or os.path.join(self.config_dir, remote_name)

        try:
            node = self._get_drive_node()
            remote_file = node[remote_name]
            if remote_file is None:
                raise CloudSyncError(f"Remote file not found: {remote_name}")

            data = remote_file.read()
            with open(local_path, "wb") as f:
                f.write(data)

            result = {
                "action": "download",
                "file": remote_name,
                "size": len(data),
                "local_path": local_path,
                "timestamp": datetime.now().isoformat(),
                "success": True,
            }
            return result
        except Exception as e:
            raise CloudSyncError(f"Download failed for {remote_name}: {str(e)}")

    def sync_file(self, filename: str) -> dict:
        local_path = os.path.join(self.config_dir, filename)
        local_hash = self._file_hash(local_path) if os.path.exists(local_path) else None

        try:
            remote_node = self._get_drive_node()
            remote_file = remote_node[filename]

            if remote_file is None:
                if os.path.exists(local_path):
                    return self.upload_file(filename)
                return {"action": "skip", "file": filename, "reason": "not found locally or remotely"}

            remote_hash = self._remote_hash(remote_file)
            if local_hash == remote_hash:
                return {"action": "skip", "file": filename, "reason": "already in sync"}

            if remote_file.date_modified > datetime.fromtimestamp(os.path.getmtime(local_path)):
                return self.download_file(filename)
            else:
                return self.upload_file(filename)

        except CloudSyncError:
            raise
        except Exception as e:
            raise CloudSyncError(f"Sync failed for {filename}: {str(e)}")

    def sync_all(self) -> dict:
        if not self._authenticated:
            raise CloudSyncError("Not authenticated. Call authenticate() first.")

        results = {
            "timestamp": datetime.now().isoformat(),
            "files": [],
            "success": True,
        }

        for filename in SYNCED_FILES:
            try:
                result = self.sync_file(filename)
                results["files"].append(result)
            except CloudSyncError as e:
                results["files"].append({"file": filename, "success": False, "error": str(e)})
                results["success"] = False

        self._last_sync = datetime.now().isoformat()
        config = self._load_config()
        config["last_sync"] = self._last_sync
        self._save_config(config)

        return results

    def push_all(self) -> dict:
        if not self._authenticated:
            raise CloudSyncError("Not authenticated. Call authenticate() first.")

        results = {
            "timestamp": datetime.now().isoformat(),
            "files": [],
            "success": True,
        }

        for filename in SYNCED_FILES:
            try:
                result = self.upload_file(filename)
                results["files"].append(result)
            except CloudSyncError as e:
                results["files"].append({"file": filename, "success": False, "error": str(e)})
                results["success"] = False

        self._last_sync = datetime.now().isoformat()
        config = self._load_config()
        config["last_sync"] = self._last_sync
        self._save_config(config)

        return results

    def pull_all(self) -> dict:
        if not self._authenticated:
            raise CloudSyncError("Not authenticated. Call authenticate() first.")

        results = {
            "timestamp": datetime.now().isoformat(),
            "files": [],
            "success": True,
        }

        for filename in SYNCED_FILES:
            try:
                result = self.download_file(filename)
                results["files"].append(result)
            except CloudSyncError as e:
                results["files"].append({"file": filename, "success": False, "error": str(e)})
                results["success"] = False

        self._last_sync = datetime.now().isoformat()
        config = self._load_config()
        config["last_sync"] = self._last_sync
        self._save_config(config)

        return results

    def get_status(self) -> dict:
        config = self._load_config()
        status = {
            "authenticated": self.is_authenticated(),
            "username": self.username,
            "last_sync": config.get("last_sync"),
            "last_auth": config.get("last_auth"),
            "synced_files": SYNCED_FILES,
            "has_pyicloud": HAS_PYICLOUD,
        }

        if self.is_authenticated():
            try:
                node = self._get_drive_node()
                status["drive_accessible"] = True
                remote_files = []
                for child in node.children():
                    remote_files.append(child.name)
                status["remote_files"] = remote_files
            except Exception as e:
                status["drive_accessible"] = False
                status["drive_error"] = str(e)

        return status

    def _file_hash(self, path: str) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            while chunk := f.read(8192):
                h.update(chunk)
        return h.hexdigest()

    def _remote_hash(self, remote_file) -> str:
        data = remote_file.read()
        return hashlib.sha256(data).hexdigest()


_cloud_sync: Optional[ICloudSync] = None


def get_cloud_sync(username: str = None, password: str = None, config_dir: str = ".") -> ICloudSync:
    global _cloud_sync
    if _cloud_sync is None:
        _cloud_sync = ICloudSync(username=username, password=password, config_dir=config_dir)
    return _cloud_sync
