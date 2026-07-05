"""E4-4: compose healthcheck 用の最小 HTTP サーバ(E9 常駐ワーカー前の暫定スケルトン)。"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer


class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path.rstrip("/") == "/healthz":
            body = json.dumps({"status": "ok"}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_response(404)
        self.end_headers()

    def log_message(self, _format: str, *_args: object) -> None:
        return


def run_health_server(*, host: str = "0.0.0.0", port: int = 8081) -> None:
    server = HTTPServer((host, port), _HealthHandler)
    server.serve_forever()


__all__ = ["run_health_server"]
