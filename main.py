import argparse
import json
import sys
import threading
import time
import uvicorn

from api_server import APIServer
from terminal_cli import TerminalCLI


def main() -> int:
    parser = argparse.ArgumentParser(description="Light-ASI LLM Gateway")
    parser.add_argument("--serve", nargs="?", const=8000, type=int, help="Launch HTTP API server")
    parser.add_argument("--nodes", type=int, default=10, help="Bootstrap node count")
    parser.add_argument("--ingest-interval", type=float, default=60.0, help="Background ingestion interval in seconds")
    args = parser.parse_args()

    shared = APIServer(port=args.serve or 8000)
    shared.graph.bootstrap(count=args.nodes)

    if args.serve:
        admin_token = shared.get_admin_token()
        print(f"Light-ASI Gateway starting on http://127.0.0.1:{args.serve}")
        print(f"Admin token: {admin_token}")
        print("Endpoints:")
        print("  POST /auth/token")
        print("  POST /query")
        print("  POST /index")
        print("  POST /search")
        print("  POST /ingest")
        print("  GET  /stats")
        print("  GET  /emerge")
        print("  GET  /health")
        print("  GET  /ping/active")
        print("  GET  /ping/inactive")
        print("  POST /xspace/scan")
        print("  POST /chainnet/validate")
        print("  POST /chainnet/balance")
        print("  POST /chainnet/cast")
        print("  POST /enclave/extract")
        print("  POST /enclave/save")
        print("  POST /im4m/manifest")
        print("  GET  /im4m/manifest")
        print("  POST /im4m/verify")
        print("  POST /channel/handshake")
        print("  GET  /channel/sessions")
        print("  GET  /channel/session/<id>")
        print("  GET  /device/detect")
        print("  GET  /device/details/<udid>")
        print("  POST /device/flash")
        print("  POST /device/save")
        print("  POST /seednet/scan")
        print("  GET  /seednet/commitments")
        print("  GET  /seednet/threats")
        print("  GET  /seednet/catalog")
        print("  GET  /device/firmware")
        print("  GET  /device/firmware/manifest")
        print("  POST /device/firmware/update")
        print("  GET  /cloud/status")
        print("  POST /cloud/auth")
        print("  POST /cloud/sync")
        print("  POST /cloud/push")
        print("  POST /cloud/pull")
        print("  POST /cloud/sync/<filename>")

        def background_ingest() -> None:
            while True:
                time.sleep(args.ingest_interval)
                print("[ingest] scheduled ingestion cycle")

        t = threading.Thread(target=background_ingest, daemon=True)
        t.start()

        uvicorn.run(shared, host="127.0.0.1", port=args.serve, log_level="info")
        return 0

    cli = TerminalCLI(shared.graph, shared.pings, shared.xspace)
    cli.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
