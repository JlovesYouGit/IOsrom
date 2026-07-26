import os
import json
import secrets
import time
from dataclasses import asdict
from typing import Any

from node_graph import NodeGraph
from ping_manager import PingManager
from hashgate import XSpace
from chainnet import validate_p2pkh_address, check_balance, cast_to_xpub, complete_cast
from seednet import scan_dir, detect_threats, summary, Seed, Threat
from enclave import extract_enclave_keys, save_extract_result
from im4m_manifest import generate_im4m_manifest, load_manifest, verify_manifest
from channel_handshake import accept_handshake, get_session, list_sessions, HandshakeRequest
from device_detect import detect_devices, get_device_details, save_detect_result, flash_device
from icloud_sync import ICloudSync, get_cloud_sync, HAS_PYICLOUD


class AuthManager:
    def __init__(self) -> None:
        self.tokens: dict[str, dict[str, Any]] = {}
        self.admin_token = secrets.token_urlsafe(32)

    def login(self, password: str | None = None) -> str:
        token = secrets.token_urlsafe(32)
        self.tokens[token] = {
            "created_at": time.time(),
            "role": "admin" if (password or os.environ.get("ADMIN_PASSWORD")) == "admin" else "user",
        }
        return token

    def admin_login(self) -> str:
        return self.admin_token

    def validate(self, token: str | None) -> dict[str, Any]:
        if not token:
            return {"valid": False, "role": None}
        if token == self.admin_token:
            return {"valid": True, "role": "admin"}
        if token in self.tokens:
            return {"valid": True, "role": self.tokens[token]["role"]}
        return {"valid": False, "role": None}


class APIServer:
    def __init__(self, host: str = "127.0.0.1", port: int = 8000) -> None:
        self.host = host
        self.port = port
        self.graph = NodeGraph()
        self.pings = PingManager(self.graph)
        self.xspace = XSpace()
        self.auth = AuthManager()
        self.graph.bootstrap()
        self.seeds: list[Seed] = []
        self.threats: list[Threat] = []
        self.start_time = time.time()
        self.cloud_sync = get_cloud_sync(config_dir=os.path.dirname(os.path.abspath(__file__)))

    def handle_request(self, method: str, path: str, headers: dict[str, str], body: bytes) -> tuple[int, str, str]:
        auth_header = headers.get("authorization", "")
        token = auth_header.replace("Bearer ", "").strip() if auth_header.startswith("Bearer ") else None

        if path == "/auth/token" and method == "POST":
            token_resp = self.auth.login()
            body_data = json.loads(body.decode()) if body else {}
            pw = body_data.get("password")
            if pw == "admin":
                token_resp = self.auth.admin_login()
            return 200, "application/json", json.dumps({"token": token_resp, "role": "admin" if pw == "admin" else "user"})

        if path == "/health" and method == "GET":
            return 200, "application/json", json.dumps({"status": "ok", "uptime": round(time.time() - self.start_time, 2)})

        if path == "/stats" and method == "GET":
            return 200, "application/json", json.dumps(self.graph.get_stats())

        if path == "/emerge" and method == "GET":
            return 200, "application/json", json.dumps(self.graph.emerge_status())

        if method == "POST" and path == "/query":
            auth = self.auth.validate(token)
            if not auth["valid"]:
                return 401, "application/json", json.dumps({"error": "Unauthorized"})
            body_data = json.loads(body.decode()) if body else {}
            query = body_data.get("query", "")
            top_k = int(body_data.get("top_k", 5))
            results = self.graph.search(query, top_k=top_k)
            return 200, "application/json", json.dumps({"query": query, "results": results})

        if method == "POST" and path == "/index":
            auth = self.auth.validate(token)
            if not auth["valid"]:
                return 401, "application/json", json.dumps({"error": "Unauthorized"})
            body_data = json.loads(body.decode()) if body else {}
            text = body_data.get("text", "")
            if not text:
                return 400, "application/json", json.dumps({"error": "text is required"})
            node = self.graph.index_text(text)
            return 200, "application/json", json.dumps({"id": node.id, "label": node.label})

        if method == "POST" and path == "/search":
            auth = self.auth.validate(token)
            if not auth["valid"]:
                return 401, "application/json", json.dumps({"error": "Unauthorized"})
            body_data = json.loads(body.decode()) if body else {}
            query = body_data.get("query", "")
            top_k = int(body_data.get("top_k", 5))
            results = self.graph.search(query, top_k=top_k)
            return 200, "application/json", json.dumps({"query": query, "results": results})

        if method == "POST" and path == "/ingest":
            auth = self.auth.validate(token)
            if not auth["valid"]:
                return 401, "application/json", json.dumps({"error": "Unauthorized"})
            body_data = json.loads(body.decode()) if body else {}
            targets = body_data.get("targets", [])
            if not targets:
                return 400, "application/json", json.dumps({"error": "targets list is required"})
            result = self.pings.check_list(targets)
            self.pings.register_to_graph()
            return 200, "application/json", json.dumps({"ingested": len(targets), "active": len(result["active"]), "inactive": len(result["inactive"])})

        if path == "/ping/active" and method == "GET":
            return 200, "application/json", json.dumps({"active": [asdict(r) for r in self.pings.active_list]})

        if path == "/ping/inactive" and method == "GET":
            return 200, "application/json", json.dumps({"inactive": [asdict(r) for r in self.pings.inactive_list]})

        if path == "/xspace" and method == "GET":
            return 200, "application/json", json.dumps(self.xspace.get_x_space())

        if method == "POST" and path == "/xspace/gate":
            body_data = json.loads(body.decode()) if body else {}
            host = body_data.get("host", "")
            port = int(body_data.get("port", 0))
            protocol = body_data.get("protocol", "tcp")
            gate = self.xspace.add_gate(host, port, protocol)
            return 200, "application/json", json.dumps({"gate": asdict(gate)})

        if method == "POST" and path == "/xspace/mirror":
            body_data = json.loads(body.decode()) if body else {}
            host = body_data.get("host", "")
            port = int(body_data.get("port", 0))
            source_gate_id = body_data.get("source_gate_id", "")
            content_hash = body_data.get("content_hash", "")
            mirror = self.xspace.add_mirror(host, port, source_gate_id, content_hash)
            return 200, "application/json", json.dumps({"mirror": asdict(mirror)})

        if method == "POST" and path == "/xspace/query":
            body_data = json.loads(body.decode()) if body else {}
            query = body_data.get("query", "")
            results = self.xspace.git_like_query(query)
            return 200, "application/json", json.dumps(results)

        if method == "POST" and path == "/xspace/retrieve":
            auth = self.auth.validate(token)
            if not auth["valid"]:
                return 401, "application/json", json.dumps({"error": "Unauthorized"})
            body_data = json.loads(body.decode()) if body else {}
            content_hash = body_data.get("content_hash", "")
            threshold = float(body_data.get("threshold", 0.8))
            if not content_hash:
                return 400, "application/json", json.dumps({"error": "content_hash is required"})
            mirrors = self.xspace.retrieve_mirror(content_hash, threshold=threshold)
            return 200, "application/json", json.dumps({"query": content_hash, "threshold": threshold, "mirrors": mirrors})

        if method == "POST" and path == "/xspace/scan":
            auth = self.auth.validate(token)
            if not auth["valid"]:
                return 401, "application/json", json.dumps({"error": "Unauthorized"})
            body_data = json.loads(body.decode()) if body else {}
            target = body_data.get("target", "")
            if not target:
                return 400, "application/json", json.dumps({"error": "target host or CIDR is required"})
            from xspace_scanner import XSpaceScanner
            scanner = XSpaceScanner(self.xspace)
            if "/" in target:
                result = scanner.scan_network(target)
            else:
                items = scanner.scan_host(target)
                result = {"host": target, "discovered": len(items), "items": items}
            return 200, "application/json", json.dumps(result)

        if method == "POST" and path == "/chainnet/validate":
            body_data = json.loads(body.decode()) if body else {}
            address = body_data.get("address", "")
            if not address:
                return 400, "application/json", json.dumps({"error": "address is required"})
            result = validate_p2pkh_address(address)
            return 200, "application/json", json.dumps(result)

        if method == "POST" and path == "/chainnet/balance":
            body_data = json.loads(body.decode()) if body else {}
            address = body_data.get("address", "")
            if not address:
                return 400, "application/json", json.dumps({"error": "address is required"})
            result = check_balance(address)
            return 200, "application/json", json.dumps(result)

        if method == "POST" and path == "/chainnet/cast":
            auth = self.auth.validate(token)
            if not auth["valid"]:
                return 401, "application/json", json.dumps({"error": "Unauthorized"})
            body_data = json.loads(body.decode()) if body else {}
            sender = body_data.get("sender")  # optional, defaults to .env ADR
            xpub = body_data.get("xpub")      # optional, defaults to .env ADR2
            btc_amount = body_data.get("btc_amount")  # optional, defaults to .env BTC_AMOUNT
            if btc_amount is not None:
                btc_amount = float(btc_amount)
            derivation_count = int(body_data.get("derivation_count", 1))
            start_index = int(body_data.get("start_index", 0))
            result = cast_to_xpub(
                sender=sender,
                xpub=xpub,
                btc_amount=btc_amount,
                derivation_count=derivation_count,
                start_index=start_index,
            )
            return 200, "application/json", json.dumps(result)

        if method == "POST" and path == "/chainnet/cast/complete":
            auth = self.auth.validate(token)
            if not auth["valid"]:
                return 401, "application/json", json.dumps({"error": "Unauthorized"})
            body_data = json.loads(body.decode()) if body else {}
            private_key_wif = body_data.get("key")  # optional, defaults to .env KEY
            fee_sat = int(body_data.get("fee_sat", 1000))
            derivation_count = int(body_data.get("derivation_count", 1))
            # Build cast first, then complete
            cast = cast_to_xpub(derivation_count=derivation_count)
            result = complete_cast(cast, private_key_wif=private_key_wif, fee_sat=fee_sat)
            return 200, "application/json", json.dumps(result)

        if method == "POST" and path == "/seednet/scan":
            body_data = json.loads(body.decode()) if body else {}
            root = body_data.get("root", ".")
            gate_threshold = int(body_data.get("gate_threshold", 1))
            self.seeds = scan_dir(root)
            self.threats = detect_threats(self.seeds)
            stats = summary(self.seeds, self.threats)
            commitments = [s.commitment for s in self.seeds if s.commitment]
            for seed in self.seeds:
                if not seed.commitment:
                    continue
                occurrences = sum(1 for s in self.seeds if s.value_sha256 == seed.value_sha256)
                if occurrences >= gate_threshold:
                    gate = self.xspace.add_gate(
                        host=f"seed:{seed.kind}",
                        port=0,
                        protocol="seednet",
                        metadata={
                            "kind": seed.kind,
                            "value_sha256": seed.value_sha256,
                            "file_sha256": seed.file_sha256,
                            "address": seed.address,
                            "line": seed.line,
                            "occurrences": occurrences,
                            "commitment": seed.commitment,
                        },
                    )
                    seed.commitment["gate_id"] = gate.id

            doc = {
                "schema": 1,
                "generated_at": int(time.time()),
                "root": os.path.abspath(root),
                "stats": stats,
                "commitments": commitments,
                "seeds": [asdict(s) for s in self.seeds],
                "threats": [asdict(t) for t in self.threats],
            }
            out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "seednet_catalog.json")
            with open(out_path, "w") as f:
                json.dump(doc, f, indent=2)
            doc["saved_to"] = out_path
            return 200, "application/json", json.dumps(doc)

        if path == "/seednet/commitments" and method == "GET":
            commitments = [s.commitment for s in self.seeds if s.commitment]
            return 200, "application/json", json.dumps({"count": len(commitments), "commitments": commitments})

        if path == "/seednet/threats" and method == "GET":
            return 200, "application/json", json.dumps({"count": len(self.threats), "threats": [asdict(t) for t in self.threats]})

        if path == "/seednet/catalog" and method == "GET":
            catalog_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "seednet_catalog.json")
            if not os.path.exists(catalog_path):
                return 404, "application/json", json.dumps({"error": "No catalog found. Run POST /seednet/scan first."})
            with open(catalog_path, "r") as f:
                doc = json.load(f)
            return 200, "application/json", json.dumps(doc)

        if method == "POST" and path == "/enclave/extract":
            body_data = json.loads(body.decode()) if body else {}
            device_id = body_data.get("device_id", "")
            result = extract_enclave_keys(device_id=device_id)
            return 200, "application/json", json.dumps(asdict(result))

        if method == "POST" and path == "/enclave/save":
            body_data = json.loads(body.decode()) if body else {}
            device_id = body_data.get("device_id", "")
            output_path = body_data.get("output_path", None)
            result = extract_enclave_keys(device_id=device_id)
            saved = save_extract_result(result, output_path=output_path)
            return 200, "application/json", json.dumps({"saved_to": saved, **asdict(result)})

        if method == "POST" and path == "/im4m/manifest":
            body_data = json.loads(body.decode()) if body else {}
            device_id = body_data.get("device_id", "")
            output_path = body_data.get("output_path", None)
            extract_result = body_data.get("extract_result", None)
            manifest = generate_im4m_manifest(
                extract_result=extract_result,
                device_id=device_id,
                output_path=output_path,
            )
            return 200, "application/json", json.dumps(asdict(manifest))

        if method == "GET" and path == "/im4m/manifest":
            manifest_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "im4m_manifest.json")
            manifest = load_manifest(manifest_path)
            if manifest is None:
                return 404, "application/json", json.dumps({"error": "No manifest found. Run POST /im4m/manifest first."})
            return 200, "application/json", json.dumps(asdict(manifest))

        if method == "POST" and path == "/im4m/verify":
            manifest_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "im4m_manifest.json")
            manifest = load_manifest(manifest_path)
            if manifest is None:
                return 404, "application/json", json.dumps({"error": "No manifest found."})
            verification = verify_manifest(manifest)
            return 200, "application/json", json.dumps(verification)

        if method == "POST" and path == "/channel/handshake":
            body_data = json.loads(body.decode()) if body else {}
            channel_id = body_data.get("channel_id", "")
            client_nonce = body_data.get("client_nonce", "")
            client_id = body_data.get("client_id", "")
            capabilities = body_data.get("capabilities", [])
            protocol = body_data.get("protocol", "vemex/v1")
            req = HandshakeRequest(
                channel_id=channel_id,
                client_nonce=client_nonce,
                client_id=client_id,
                capabilities=capabilities,
                protocol=protocol,
            )
            response = accept_handshake(req)
            return 200, "application/json", json.dumps(asdict(response))

        if path == "/channel/sessions" and method == "GET":
            sessions = list_sessions()
            return 200, "application/json", json.dumps({"sessions": sessions, "count": len(sessions)})

        if path.startswith("/channel/session/") and method == "GET":
            session_id = path.split("/channel/session/")[-1].strip("/")
            session = get_session(session_id)
            if session is None:
                return 404, "application/json", json.dumps({"error": "Session not found or expired."})
            return 200, "application/json", json.dumps(asdict(session))

        if method == "GET" and path == "/device/detect":
            result = detect_devices()
            return 200, "application/json", json.dumps(asdict(result))

        if method == "GET" and path.startswith("/device/details/"):
            udid = path.split("/device/details/")[-1].strip("/")
            details = get_device_details(udid)
            if details is None:
                return 404, "application/json", json.dumps({"error": f"Device {udid} not found"})
            return 200, "application/json", json.dumps(details)

        if method == "POST" and path == "/device/flash":
            body_data = json.loads(body.decode()) if body else {}
            udid = body_data.get("udid", "")
            ipsw_path = body_data.get("ipsw_path", None)
            result = flash_device(udid, ipsw_path)
            return 200, "application/json", json.dumps(result)

        if method == "POST" and path == "/device/save":
            result = detect_devices()
            saved = save_detect_result(result)
            return 200, "application/json", json.dumps({"saved_to": saved, **asdict(result)})

        if path == "/device/firmware" and method == "GET":
            from device_detect import _load_firmware_manifest
            manifest = _load_firmware_manifest()
            return 200, "application/json", json.dumps(manifest)

        if path == "/device/firmware/manifest" and method == "GET":
            manifest_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "firmware_manifest.json")
            if not os.path.exists(manifest_path):
                return 404, "application/json", json.dumps({"error": "No firmware manifest found"})
            with open(manifest_path, "r") as f:
                manifest = json.load(f)
            return 200, "application/json", json.dumps(manifest)

        if method == "POST" and path == "/device/firmware/update":
            body_data = json.loads(body.decode()) if body else {}
            firmware_entry = body_data.get("firmware", {})
            if not firmware_entry:
                return 400, "application/json", json.dumps({"error": "firmware entry is required"})
            from device_detect import _load_firmware_manifest, FIRMWARE_MANIFEST_PATH
            manifest = _load_firmware_manifest()
            firmwares = manifest.get("firmwares", [])
            firmwares.append(firmware_entry)
            manifest["firmwares"] = firmwares
            manifest["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            with open(FIRMWARE_MANIFEST_PATH, "w") as f:
                json.dump(manifest, f, indent=2)
            return 200, "application/json", json.dumps({"updated": True, "manifest": manifest})

        if path == "/cloud/status" and method == "GET":
            status = self.cloud_sync.get_status()
            return 200, "application/json", json.dumps(status)

        if method == "POST" and path == "/cloud/auth":
            try:
                self.cloud_sync.authenticate()
                return 200, "application/json", json.dumps({"authenticated": True, "user": self.cloud_sync.username})
            except CloudSyncError as e:
                return 401, "application/json", json.dumps({"authenticated": False, "error": str(e)})

        if method == "POST" and path == "/cloud/sync":
            try:
                result = self.cloud_sync.sync_all()
                return 200, "application/json", json.dumps(result)
            except CloudSyncError as e:
                return 500, "application/json", json.dumps({"error": str(e)})

        if method == "POST" and path == "/cloud/push":
            try:
                result = self.cloud_sync.push_all()
                return 200, "application/json", json.dumps(result)
            except CloudSyncError as e:
                return 500, "application/json", json.dumps({"error": str(e)})

        if method == "POST" and path == "/cloud/pull":
            try:
                result = self.cloud_sync.pull_all()
                return 200, "application/json", json.dumps(result)
            except CloudSyncError as e:
                return 500, "application/json", json.dumps({"error": str(e)})

        if method == "POST" and path.startswith("/cloud/sync/"):
            filename = path.split("/cloud/sync/")[-1].strip("/")
            if not filename:
                return 400, "application/json", json.dumps({"error": "filename is required"})
            try:
                result = self.cloud_sync.sync_file(filename)
                return 200, "application/json", json.dumps(result)
            except CloudSyncError as e:
                return 500, "application/json", json.dumps({"error": str(e)})

        return 404, "application/json", json.dumps({"error": "Not found"})

    def get_admin_token(self) -> str:
        return self.auth.admin_token

    async def __call__(self, scope: dict, receive, send) -> None:
        if scope["type"] != "http":
            await send({"type": "http.response.start", "status": 404, "headers": [[b"content-type", b"application/json"]]})
            await send({"type": "http.response.body", "body": b'{"error":"Not found"}'})
            return

        method = scope.get("method", "GET")
        path = scope.get("path", "/")
        headers = {}
        for key, value in scope.get("headers", []):
            headers[key.decode()] = value.decode()

        body = b""
        if method == "POST":
            while True:
                message = await receive()
                if message["type"] == "http.request":
                    body += message.get("body", b"")
                    if not message.get("more_body", False):
                        break

        status, content_type, response_body = self.handle_request(method, path, headers, body)

        await send({"type": "http.response.start", "status": status, "headers": [[b"content-type", content_type.encode()]]})
        await send({"type": "http.response.body", "body": response_body.encode()})
