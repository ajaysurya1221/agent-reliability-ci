"""Loopback Ollama fixture for the native Board-0 rehearsal."""

from __future__ import annotations

import errno
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import offline_model
import pin
from common import ROOT, Row, read, registry


class FakeOllama:
    def __init__(self) -> None:
        config = ROOT / "models.json"
        self.version = read(config)["ollama"]
        registered = registry(config)
        slots = registered["slots"]
        self.tags = [
            {"name": s["tag"], "digest": s["digest"]} for s in slots + registered["spares"]
        ]
        self.echo_tag = slots[-1]["tag"]
        self.loaded: str | None = None
        self.tasks = {
            r["ask"]: r | {"key_id": r["id"]} for r in read(ROOT / "tasks/tasks.json")["tasks"]
        }

    def handle(self, method: str, path: str, body: bytes = b"") -> tuple[int, bytes]:
        reply: Row
        if (method, path) == ("GET", "/api/version"):
            reply = {"version": self.version}
        elif (method, path) == ("GET", "/api/tags"):
            reply = {"models": self.tags}
        elif (method, path) == ("GET", "/api/ps"):
            reply = {
                "models": [
                    r | {"context_length": 32768} for r in self.tags if r["name"] == self.loaded
                ]
            }
        elif method == "POST" and path in ("/api/show", "/api/chat"):
            payload = json.loads(body)
            tag = payload["model"]
            if not any(s["name"] == tag for s in self.tags):
                return 404, b'{"error":"unknown model"}'
            if path == "/api/show":
                reply = {"parameters": "num_ctx 32768"}
            else:
                self.loaded = tag
                if payload["tools"] != pin.TOY_TOOLS:
                    task = self.tasks[payload["messages"][1]["content"]]
                    return offline_model.chat(body, task)
                if tag == self.echo_tag:
                    msg = {"role": "assistant", "content": payload["messages"][1]["content"]}
                    reply = {"model": tag, "done": True, "message": msg}
                else:
                    _, raw = pin.toy_chat(body)
                    reply = json.loads(raw)
                reply["done_reason"] = "stop"
        else:
            return 404, b'{"error":"unknown endpoint"}'
        return 200, json.dumps(reply).encode()


def main() -> None:
    # The offline policy consults this seed only to enable explicitly planted FIFO faults.
    os.environ.pop("BOARD0_REHEARSAL_FAULTS", None)
    os.environ["ARCI_SEED"] = "0"
    fixture = FakeOllama()

    class Handler(BaseHTTPRequestHandler):
        def serve(self) -> None:
            try:
                length = int(self.headers.get("Content-Length", "0"))
                status, data = fixture.handle(self.command, self.path, self.rfile.read(length))
            except (KeyError, ValueError, TypeError, IndexError) as exc:
                status, data = 400, json.dumps({"error": str(exc)}).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        do_GET = do_POST = serve

    class Server(HTTPServer):
        allow_reuse_address = False
        allow_reuse_port = False

    try:
        server = Server(("127.0.0.1", 11434), Handler)
    except OSError as exc:
        if exc.errno == errno.EADDRINUSE:
            raise SystemExit("127.0.0.1:11434 already in use") from exc
        raise
    with server:
        print("READY", flush=True)
        server.serve_forever()


if __name__ == "__main__":
    main()
