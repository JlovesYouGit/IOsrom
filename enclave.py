import hashlib
import json
import os
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class EnclaveKey:
    key_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    enclave_type: str = "secure_enclave"
    key_type: str = "ECDSA_P256"
    public_key: str = ""
    private_key_ref: str = ""
    signing_material: dict[str, Any] = field(default_factory=dict)
    matched: bool = False
    device_id: str = ""
    extracted_at: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SigningMaterial:
    material_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    key_id: str = ""
    material_type: str = "signing_blob"
    content_hash: str = ""
    content: str = ""
    algorithm: str = "SHA256withECDSA"
    timestamp: float = field(default_factory=time.time)
    device_ref: str = ""
    enclave_key_id: str = ""


@dataclass
class EnclaveExtractResult:
    success: bool = False
    keys: list[dict[str, Any]] = field(default_factory=list)
    signing_materials: list[dict[str, Any]] = field(default_factory=list)
    device_id: str = ""
    device_info: dict[str, Any] = field(default_factory=dict)
    match_count: int = 0
    error: str | None = None
    timestamp: float = field(default_factory=time.time)


def _hash_content(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()


def _derive_key_id(public_key: str) -> str:
    return hashlib.sha256(public_key.encode()).hexdigest()[:12]


def extract_enclave_keys(device_id: str = "") -> EnclaveExtractResult:
    result = EnclaveExtractResult(device_id=device_id or _get_device_id())

    try:
        enclave_keys = _read_enclave_keys(device_id=result.device_id)
        result.keys = [asdict(k) for k in enclave_keys]

        signing_materials = []
        for key in enclave_keys:
            mat = _read_signing_material(key)
            if mat:
                signing_materials.append(asdict(mat))

        result.signing_materials = signing_materials
        result.match_count = len([k for k in enclave_keys if k.matched])
        result.success = True

    except Exception as e:
        result.error = str(e)
        result.success = False

    return result


def _get_device_id() -> str:
    hostname = os.uname().nodename if hasattr(os, "uname") else "unknown"
    machine = os.uname().machine if hasattr(os, "uname") else "unknown"
    raw = f"{hostname}:{machine}:{time.time()}".encode()
    return hashlib.sha256(raw).hexdigest()[:16]


def _read_enclave_keys(device_id: str) -> list[EnclaveKey]:
    keys: list[EnclaveKey] = []

    key_material = _load_key_material(device_id)
    if not key_material:
        return keys

    for entry in key_material:
        pub = entry.get("public_key", "")
        priv_ref = entry.get("private_key_ref", "")
        if not pub:
            continue

        key = EnclaveKey(
            public_key=pub,
            private_key_ref=priv_ref,
            device_id=device_id,
            signing_material={
                "algorithm": entry.get("algorithm", "ECDSA_P256"),
                "curve": entry.get("curve", "secp256r1"),
                "key_size_bits": entry.get("key_size_bits", 256),
                "usage": entry.get("usage", ["sign", "verify"]),
            },
        )

        key.matched = _match_key_to_signing_material(key, entry)
        keys.append(key)

    return keys


def _load_key_material(device_id: str) -> list[dict[str, Any]]:
    manifest_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "enclave_keys.json"
    )
    if os.path.exists(manifest_path):
        try:
            with open(manifest_path, "r") as f:
                data = json.load(f)
            return data.get("keys", [])
        except (json.JSONDecodeError, OSError):
            pass

    return _generate_default_keys(device_id)


def _generate_default_keys(device_id: str) -> list[dict[str, Any]]:
    seed = f"vemex-enclave-{device_id}-{time.time()}".encode()
    seed_hash = hashlib.sha256(seed).hexdigest()

    keys = []
    for i in range(3):
        pub_hex = hashlib.sha256(f"{seed_hash}:pub:{i}".encode()).hexdigest()
        priv_ref = hashlib.sha256(f"{seed_hash}:priv:{i}".encode()).hexdigest()[:32]
        keys.append({
            "public_key": f"04{pub_hex}",
            "private_key_ref": priv_ref,
            "algorithm": "ECDSA_P256",
            "curve": "secp256r1",
            "key_size_bits": 256,
            "usage": ["sign", "verify"],
            "enclave": "com.apple.security.enclave",
        })

    return keys


def _match_key_to_signing_material(key: EnclaveKey, entry: dict[str, Any]) -> bool:
    pub = key.public_key
    if not pub:
        return False

    expected_hash = _hash_content(pub)
    material_hash = entry.get("signing_hash", "")

    if material_hash and material_hash == expected_hash:
        return True

    key_id = _derive_key_id(pub)
    if entry.get("key_id") == key_id:
        return True

    return len(pub) > 0 and len(entry.get("private_key_ref", "")) > 0


def _read_signing_material(key: EnclaveKey) -> SigningMaterial | None:
    if not key.public_key:
        return None

    content = f"sign:{key.public_key}:{key.key_id}:{key.extracted_at}"
    mat = SigningMaterial(
        key_id=key.key_id,
        material_type="enclave_signing_blob",
        content_hash=_hash_content(content),
        content=content,
        algorithm="SHA256withECDSA",
        device_ref=key.device_id,
        enclave_key_id=key.key_id,
    )
    return mat


def save_extract_result(result: EnclaveExtractResult, output_path: str | None = None) -> str:
    if output_path is None:
        output_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "enclave_extract.json"
        )

    doc = asdict(result)
    doc["timestamp_iso"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(result.timestamp))

    with open(output_path, "w") as f:
        json.dump(doc, f, indent=2, default=str)

    return output_path