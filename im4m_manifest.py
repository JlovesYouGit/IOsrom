import hashlib
import json
import os
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class AttestationToken:
    token_id: str = field(default_factory=lambda: str(uuid.uuid4())[:16])
    key_id: str = ""
    enclave_key_id: str = ""
    algorithm: str = "ECDSA_P256"
    signature: str = ""
    payload_hash: str = ""
    issued_at: float = field(default_factory=time.time)
    expires_at: float = field(default_factory=lambda: time.time() + 3600)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Im4mManifest:
    schema: str = "im4m/v1"
    manifest_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    generated_at: float = field(default_factory=time.time)
    device_id: str = ""
    enclave_keys: list[dict[str, Any]] = field(default_factory=list)
    signing_materials: list[dict[str, Any]] = field(default_factory=list)
    attestations: list[dict[str, Any]] = field(default_factory=list)
    manifest_hash: str = ""
    saved_path: str = ""


def generate_im4m_manifest(
    extract_result: dict[str, Any] | None = None,
    device_id: str = "",
    output_path: str | None = None,
) -> Im4mManifest:
    manifest = Im4mManifest(device_id=device_id or _get_device_id())

    if extract_result is None:
        from enclave import extract_enclave_keys
        extract_result = asdict(extract_enclave_keys(manifest.device_id))

    manifest.enclave_keys = extract_result.get("keys", [])
    manifest.signing_materials = extract_result.get("signing_materials", [])

    attestations = _generate_attestations(manifest, extract_result)
    manifest.attestations = attestations

    manifest.manifest_hash = _compute_manifest_hash(manifest)

    if output_path is None:
        output_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "im4m_manifest.json"
        )

    manifest.saved_path = output_path
    _save_manifest(manifest, output_path)

    return manifest


def _hash_content(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()


def _get_device_id() -> str:
    import os as _os
    hostname = _os.uname().nodename if hasattr(_os, "uname") else "unknown"
    machine = _os.uname().machine if hasattr(_os, "uname") else "unknown"
    raw = f"vemex-im4m-{hostname}:{machine}:{time.time()}".encode()
    return hashlib.sha256(raw).hexdigest()[:16]


def _generate_attestations(
    manifest: Im4mManifest, extract_result: dict[str, Any]
) -> list[dict[str, Any]]:
    attestations: list[dict[str, Any]] = []

    for key in extract_result.get("keys", []):
        key_id = key.get("key_id", "")
        pub = key.get("public_key", "")

        payload = {
            "key_id": key_id,
            "public_key": pub,
            "key_type": key.get("key_type", "ECDSA_P256"),
            "enclave_type": key.get("enclave_type", "secure_enclave"),
            "device_id": manifest.device_id,
            "manifest_id": manifest.manifest_id,
            "timestamp": manifest.generated_at,
        }

        payload_json = json.dumps(payload, sort_keys=True)
        payload_hash = hashlib.sha256(payload_json.encode()).hexdigest()

        sig = _sign_payload(payload_json, key)

        att = AttestationToken(
            key_id=key_id,
            enclave_key_id=key.get("key_id", ""),
            algorithm="ECDSA_P256",
            signature=sig,
            payload_hash=payload_hash,
            metadata=key.get("metadata", {}),
        )
        attestations.append(asdict(att))

    for mat in extract_result.get("signing_materials", []):
        payload = {
            "material_id": mat.get("material_id", ""),
            "content_hash": mat.get("content_hash", ""),
            "algorithm": mat.get("algorithm", "SHA256withECDSA"),
            "device_id": manifest.device_id,
            "manifest_id": manifest.manifest_id,
            "timestamp": manifest.generated_at,
        }

        payload_json = json.dumps(payload, sort_keys=True)
        payload_hash = hashlib.sha256(payload_json.encode()).hexdigest()

        sig = _sign_payload(payload_json, {})

        att = AttestationToken(
            key_id=_hash_content(payload_json)[:12],
            algorithm="SHA256withECDSA",
            signature=sig,
            payload_hash=payload_hash,
            metadata={"material_type": mat.get("material_type", "")},
        )
        attestations.append(asdict(att))

    return attestations


def _sign_payload(payload_json: str, key: dict[str, Any]) -> str:
    priv_ref = key.get("private_key_ref", "")
    raw = f"{priv_ref}:{payload_json}:{time.time()}".encode()
    sig = hashlib.sha256(raw).hexdigest()
    return f"0x{sig}"


def _compute_manifest_hash(manifest: Im4mManifest) -> str:
    payload = {
        "schema": manifest.schema,
        "manifest_id": manifest.manifest_id,
        "generated_at": manifest.generated_at,
        "device_id": manifest.device_id,
        "key_count": len(manifest.enclave_keys),
        "material_count": len(manifest.signing_materials),
        "attestation_count": len(manifest.attestations),
    }
    payload_json = json.dumps(payload, sort_keys=True)
    return hashlib.sha256(payload_json.encode()).hexdigest()


def _save_manifest(manifest: Im4mManifest, path: str) -> None:
    doc = asdict(manifest)
    doc["generated_at_iso"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(manifest.generated_at))
    doc["attestations"] = [
        {**att, "issued_at_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(att["issued_at"]))}
        for att in doc.get("attestations", [])
    ]

    os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
    with open(path, "w") as f:
        json.dump(doc, f, indent=2, default=str)


def load_manifest(path: str) -> Im4mManifest | None:
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r") as f:
            data = json.load(f)
        manifest = Im4mManifest(
            schema=data.get("schema", "im4m/v1"),
            manifest_id=data.get("manifest_id", ""),
            generated_at=data.get("generated_at", time.time()),
            device_id=data.get("device_id", ""),
            enclave_keys=data.get("enclave_keys", []),
            signing_materials=data.get("signing_materials", []),
            attestations=data.get("attestations", []),
            manifest_hash=data.get("manifest_hash", ""),
            saved_path=data.get("saved_path", path),
        )
        return manifest
    except (json.JSONDecodeError, OSError):
        return None


def verify_manifest(manifest: Im4mManifest) -> dict[str, Any]:
    expected_hash = _compute_manifest_hash(manifest)
    valid = expected_hash == manifest.manifest_hash

    attestation_results = []
    for att in manifest.attestations:
        att_valid = bool(att.get("signature")) and bool(att.get("payload_hash"))
        attestation_results.append({
            "token_id": att.get("token_id", ""),
            "valid": att_valid,
            "payload_hash": att.get("payload_hash", ""),
        })

    return {
        "manifest_id": manifest.manifest_id,
        "manifest_hash_valid": valid,
        "expected_hash": expected_hash,
        "actual_hash": manifest.manifest_hash,
        "attestation_count": len(manifest.attestations),
        "attestations_valid": all(a["valid"] for a in attestation_results),
        "attestation_details": attestation_results,
        "verified_at": time.time(),
    }