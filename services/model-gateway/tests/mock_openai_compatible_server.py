"""OpenAI互換APIモック(E4-5: Ollama代替、Anthropic互換モック兼用)。

`/v1/chat/completions` へ POST されると、リクエストヘッダ/ボディに応じた
固定応答を返し、ルーティング先検証に使う。
"""

from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, HTTPServer


class _MockHandler(BaseHTTPRequestHandler):
    backend_label: str = "unknown"

    def do_POST(self) -> None:
        path = self.path.rstrip("/")
        if path == "/v1/chat/completions":
            self._handle_openai_chat()
            return
        if path == "/v1/messages":
            self._handle_anthropic_messages()
            return
        if path == "/api/chat":
            self._handle_ollama_chat()
            return
        self.send_response(404)
        self.end_headers()

    def _read_json_body(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length) if length else b"{}"
        return json.loads(body.decode() or "{}")

    def _handle_openai_chat(self) -> None:
        payload = self._read_json_body()
        model = payload.get("model", "")
        response = {
            "id": "mock-chatcmpl",
            "object": "chat.completion",
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": f"mock-response-from-{self.backend_label}",
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            "mock_backend": self.backend_label,
        }
        self._write_json(200, response)

    def _handle_anthropic_messages(self) -> None:
        payload = self._read_json_body()
        model = payload.get("model", "")
        response = {
            "id": "mock-msg",
            "type": "message",
            "role": "assistant",
            "model": model,
            "content": [
                {
                    "type": "text",
                    "text": f"mock-response-from-{self.backend_label}",
                }
            ],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 1, "output_tokens": 1},
            "mock_backend": self.backend_label,
        }
        self._write_json(200, response)

    def _handle_ollama_chat(self) -> None:
        payload = self._read_json_body()
        model = payload.get("model", "")
        response = {
            "model": model,
            "created_at": "2026-01-01T00:00:00Z",
            "message": {
                "role": "assistant",
                "content": f"mock-response-from-{self.backend_label}",
            },
            "done": True,
            "mock_backend": self.backend_label,
        }
        self._write_json(200, response)

    def _write_json(self, status: int, payload: dict) -> None:
        encoded = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, _format: str, *_args: object) -> None:
        return


def main() -> None:
    parser = argparse.ArgumentParser(description="OpenAI-compatible mock server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--backend-label", required=True)
    args = parser.parse_args()

    handler = type(
        "LabelledMockHandler",
        (_MockHandler,),
        {"backend_label": args.backend_label},
    )
    server = HTTPServer((args.host, args.port), handler)
    print(f"mock server ({args.backend_label}) listening on {args.host}:{args.port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
