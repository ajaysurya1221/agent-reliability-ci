"""Native test server. Exclusive bind is the first operation on the study port."""

import json
import os
import socket
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


# Installed metadata belongs to the fake server, independent of any study roster.
def installed() -> dict[str, dict[str, Any]]:
    sizes = [
        ("fixture-q2:example", "Qwen", "2B"),
        ("qwen3.5:4b-mlx-ctx32k", "Qwen", "4B"),
        ("fixture-q9:example", "Qwen", "9B"),
        ("gemma4:12b-mlx-ctx32k", "Gemma", "12B"),
    ]
    return {
        tag: dict(
            digest=str(i) * 64,
            family=family,
            size=size,
            format="fixture",
            quantization="fixture-Q4",
        )
        for i, (tag, family, size) in enumerate(sizes, 1)
    }


def serve(control: Path) -> None:
    sys.path.insert(0, str(ROOT / "agent"))
    import httpx
    from standin import respond

    slots = installed()
    loaded = ""

    class Handler(BaseHTTPRequestHandler):
        def reply(self, body: Any, stream: bool = False, *, drop: bool = False) -> None:
            raw = json.dumps(body).encode() + b"\n"
            if stream:
                intermediate = {
                    "model": body["model"],
                    "message": {"role": "assistant", "content": ""},
                }
                raw = json.dumps(intermediate).encode() + b"\n" + raw
            self.send_response(200)
            self.send_header(
                "Content-Type", "application/x-ndjson" if stream else "application/json"
            )
            self.send_header("Content-Length", str(len(raw) + int(drop)))
            self.end_headers()
            self.wfile.write(raw)
            if drop:
                self.close_connection = True

        def do_GET(self) -> None:
            if self.path == "/api/version":
                self.reply({"version": "0.32.14"})
            elif self.path == "/api/tags":
                self.reply(
                    {"models": [{"name": tag, "digest": r["digest"]} for tag, r in slots.items()]}
                )
            elif self.path == "/api/ps":
                self.reply(
                    {
                        "models": [
                            {
                                "name": loaded,
                                "digest": slots[loaded]["digest"],
                                "context_length": 32768,
                            }
                        ]
                        if loaded
                        else []
                    }
                )
            else:
                self.send_error(404)

        def do_POST(self) -> None:
            nonlocal loaded
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            tag = body["model"]
            row = slots[tag]
            if self.path == "/api/show":
                self.reply(
                    {
                        "template": "native fixture " + tag,
                        "parameters": "num_ctx 32768",
                        "details": {
                            "family": row["family"],
                            "parameter_size": row["size"],
                            "format": row["format"],
                            "quantization_level": row["quantization"],
                        },
                    }
                )
                return
            if (
                self.path != "/api/chat"
                or body["think"] is not False
                or body["stream"] is not True
                or body["options"] != {"temperature": 0.7}
            ):
                self.send_error(400)
                return
            cold = loaded != tag
            loaded = tag
            last = body["messages"][-1]
            frame: dict[str, Any]
            drop = False
            if body["tools"][0]["function"]["name"] == "read_pebble":
                msg: dict[str, Any] = {"role": "assistant", "content": ""}
                if last["role"] == "tool":
                    msg["content"] = last["content"]
                else:
                    pebble = last["content"].rstrip("?").split()[-1]
                    msg["tool_calls"] = [
                        {"function": {"name": "read_pebble", "arguments": {"pebble": pebble}}}
                    ]
                frame = {"model": tag, "message": msg, "done": True, "done_reason": "stop"}
            else:
                frame = respond(httpx.Request("POST", "http://fixture/api/chat", json=body)).json()
                if last.get("content") == "null" and (control / "drop-next").exists():
                    (control / "drop-next").unlink()
                    drop = True
                    frame = {
                        "model": tag,
                        "done": False,
                        "message": {"role": "assistant", "content": "partial"},
                    }
            if (
                (control / "malformed-next").exists()
                and (
                    last.get("content") == "null"
                    or body["tools"][0]["function"]["name"] == "read_pebble"
                )
                and not drop
            ):
                (control / "malformed-next").unlink()
                frame["message"]["tool_calls"] = [{"function": {"name": "bad", "arguments": 7}}]
            if (control / "hold-worker").exists():
                (control / "worker-in-chat").touch()
                while (control / "hold-worker").exists():
                    time.sleep(0.05)
            self.reply(frame | {"load_duration": 1000000 if cold else 1000}, True, drop=drop)

        def log_message(self, format: str, *args: object) -> None:
            pass

    # A listener on another local interface (including IPv6-only) also blocks rehearsal.
    # bind() checks availability without connecting to or querying any listener.
    for family, address in ((socket.AF_INET, "0.0.0.0"), (socket.AF_INET6, "::")):
        if family == socket.AF_INET6 and not socket.has_ipv6:
            continue
        with socket.socket(family, socket.SOCK_STREAM) as probe:
            probe.bind((address, 11434))
    with ThreadingHTTPServer(("127.0.0.1", 11434), Handler) as server:
        (control / "ready").write_text(str(os.getpid()))
        server.serve_forever()


if __name__ == "__main__":
    serve(Path(sys.argv[1]))
