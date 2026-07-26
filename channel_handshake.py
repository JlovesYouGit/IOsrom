import hashlib
import json
import os
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class HandshakeRequest:
    channel_id: str = ""
    client_nonce: str = ""
    protocol: str = "vemex/v1"
    capabilities: list[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)
    client_id: str = ""


@dataclass
class HandshakeResponse:
    channel_id: str = ""
    server_nonce: str = ""
    session_token: str = ""
    accepted: bool = False
    protocol: str = "vemex/v1"
    manifest_ref: str = ""
    enclave_key_ref: str = ""
    expires_at: float = field(default_factory=lambda: time.time() + 7200)
    server_timestamp: float = field(default_factory=time.time)
    error: str | None = None


@dataclass
class ChannelSession:
    session_id: str = field(default_factory=lambda: str(uuid.uuid4())[:16])
    channel_id: str = ""
    client_id: str = ""
    accepted: bool = False
    manifest_ref: str = ""
    enclave_key_ref: str = ""
    session_token: str = ""
    created_at: float = field(default_factory=time.time)
    expires_at: float = field(default_factory=lambda: time.time() + 7200)
    active: bool = True


_SESSIONS: dict[str, ChannelSession] = {}


def accept_handshake(request: HandshakeRequest | None = None, **kwargs: Any) -> HandshakeResponse:
    if request is None:
        request = HandshakeRequest(**kwargs)

    response = HandshakeResponse(channel_id=request.channel_id)

    if not request.channel_id:
        response.error = "channel_id is required"
        return response

    if not request.client_nonce:
        response.error = "client_nonce is required"
        return response

    server_nonce = _generate_nonce()
    session_token = _derive_session_token(request, server_nonce)

    manifest_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "im4m_manifest.json"
    )
    manifest_ref = _compute_ref(manifest_path)

    enclave_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "enclave_extract.json"
    )
    enclave_key_ref = _compute_ref(enclave_path)

    session = ChannelSession(
        channel_id=request.channel_id,
        client_id=request.client_id,
        accepted=True,
        manifest_ref=manifest_ref,
        enclave_key_ref=enclave_key_ref,
        session_token=session_token,
    )

    _SESSIONS[session.session_id] = session

    response.channel_id = request.channel_id
    response.server_nonce = server_nonce
    response.session_token = session_token
    response.accepted = True
    response.manifest_ref = manifest_ref
    response.enclave_key_ref = enclave_key_ref

    return response


def get_session(session_id: str) -> ChannelSession | None:
    session = _SESSIONS.get(session_id)
    if session is None:
        return None
    if time.time() > session.expires_at:
        session.active = False
        return None
    return session


def list_sessions() -> list[dict[str, Any]]:
    now = time.time()
    return [
        asdict(s) for s in _SESSIONS.values()
        if s.active and now <= s.expires_at
    ]


def _generate_nonce() -> str:
    raw = os.urandom(32)
    return hashlib.sha256(raw).hexdigest()[:32]


def _derive_session_token(request: HandshakeRequest, server_nonce: str) -> str:
    raw = f"{request.channel_id}:{request.client_nonce}:{server_nonce}:{request.timestamp}:vemex".encode()
    return hashlib.sha256(raw).hexdigest()


def _compute_ref(path: str) -> str:
    if not os.path.exists(path):
        return ""
    st = os.stat(path)
    raw = f"{path}:{st.st_size}:{st.st_mtime}".encode()
    return hashlib.sha256(raw).hexdigest()[:16]