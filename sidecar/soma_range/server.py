"""Loopback-only, stateless HTTP scaffold. Never expose to a network."""
import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from .contracts import Observation
from .runtime import decide

MAX_BODY = 16384


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args: object) -> None:
        pass  # Do not log observation bodies or private content.

    def send_json(self, status: int, value: dict) -> None:
        body = json.dumps(value).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path == "/health":
            self.send_json(200, {"status": "ok", "adapter": "offline-stub"})
        else:
            self.send_json(404, {"error": "not found"})

    def do_POST(self) -> None:
        if self.path != "/v1/decision":
            self.send_json(404, {"error": "not found"})
            return
        try:
            if self.headers.get("Transfer-Encoding"):
                raise ValueError("chunking unsupported")
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= MAX_BODY:
                raise ValueError("invalid body size")
            data = json.loads(self.rfile.read(size))
            if not isinstance(data, dict) or set(data) != {"observation", "horizon_arm"}:
                raise ValueError("invalid envelope")
            result = decide(Observation.parse(data["observation"]), data["horizon_arm"])
        except (ValueError, TypeError, UnicodeError):
            self.send_json(400, {"error": "invalid v1 decision request"})
            return
        self.send_json(200, result.wire())

    def setup(self) -> None:
        super().setup()
        self.connection.settimeout(5)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    with ThreadingHTTPServer(("127.0.0.1", args.port), Handler) as server:
        print(f"Offline sidecar: http://127.0.0.1:{server.server_port}", flush=True)
        server.serve_forever()


if __name__ == "__main__":
    main()
