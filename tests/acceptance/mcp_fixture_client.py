"""A scripted MCP client standing in for a real agent CLI. FROZEN.

    python mcp_fixture_client.py --mcp-config FILE --variant VARIANT

Variants: good, fragile, liar, hang, chatty, direct, plus three that probe the boundary itself:
badargs (one malformed tools/call, then behaves like good), double (two fetches, for large
recordings) and pipeline (two large requests written back to back before reading anything).

It reads a standard `{"mcpServers": {name: {command, args, env}}}` config, spawns the ONE server
it finds there over stdio, and behaves like the matching in-process fixture agent. Exit status 0
is the agent's claim of success.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


class Session:
    def __init__(self, config_path: str) -> None:
        servers = json.loads(Path(config_path).read_text())["mcpServers"]
        (entry,) = servers.values()
        self.proc = subprocess.Popen(
            [entry["command"], *entry.get("args", [])],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            env={**os.environ, **entry.get("env", {})},
            text=True,
        )
        self.next_id = 0

    def send(self, message: dict[str, Any]) -> None:
        assert self.proc.stdin is not None
        self.proc.stdin.write(json.dumps(message) + "\n")
        self.proc.stdin.flush()

    def rpc(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self.next_id += 1
        request_id = f"req-{self.next_id}"
        self.send({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}})
        assert self.proc.stdout is not None
        while True:
            line = self.proc.stdout.readline()
            if not line:
                raise SystemExit(8)  # the server went away
            reply = json.loads(line)
            if reply.get("id") == request_id:
                return reply

    def call(self, name: str, **arguments: Any) -> tuple[bool, Any]:
        reply = self.rpc("tools/call", {"name": name, "arguments": arguments})
        result = reply.get("result")
        if "error" in reply or not isinstance(result, dict) or result.get("isError"):
            return False, None
        content = result.get("content") or []
        return True, json.loads(content[0]["text"]) if content else None

    def close(self) -> None:
        assert self.proc.stdin is not None
        self.proc.stdin.close()
        self.proc.wait(timeout=10)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mcp-config", required=True)
    parser.add_argument("--variant", required=True)
    parser.add_argument("--pid-dir", default=None)
    args = parser.parse_args()
    if args.pid_dir:
        (Path(args.pid_dir) / "client.pid").write_text(str(os.getpid()))
    if args.variant == "liar":
        return 0
    session = Session(args.mcp_config)
    session.rpc(
        "initialize",
        {
            "protocolVersion": "2026-07-28",
            "capabilities": {},
            "clientInfo": {"name": "arci-fixture-client", "version": "0"},
        },
    )
    session.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
    tools = session.rpc("tools/list")["result"]["tools"]
    if sorted(t["name"] for t in tools) != ["fetch", "log", "store"]:
        return 9  # discovery traffic must pass through the boundary untouched

    if args.variant == "chatty":
        for i in range(50):
            session.call("log", msg=f"line {i}")
        session.close()
        return 0
    if args.variant == "direct":
        session.call("log", msg="start")
        session.close()
        return 0

    if args.variant == "badargs":
        # A client bug: `arguments` must be an object. The boundary must answer with a JSON-RPC
        # error and carry on; this is the agent's mistake, never a harness fault.
        reply = session.rpc("tools/call", {"name": "fetch", "arguments": []})
        if "error" not in reply:
            return 7
    if args.variant == "pipeline":
        # Two large requests, written before reading either reply. A boundary that writes
        # synchronously from its only reader loop deadlocks here.
        assert session.proc.stdin is not None and session.proc.stdout is not None
        wanted = set()
        for n in (1, 2):
            wanted.add(f"pipe-{n}")
            session.send(
                {
                    "jsonrpc": "2.0",
                    "id": f"pipe-{n}",
                    "method": "ping",
                    "params": {"pad": "y" * 300_000},
                }
            )
        while wanted:
            line = session.proc.stdout.readline()
            if not line:
                return 8
            wanted.discard(json.loads(line).get("id"))

    session.call("log", msg="start")
    if args.variant == "double":
        session.call("fetch", key="first")
    attempts = 1 if args.variant in {"fragile", "hang"} else 3
    value: Any = None
    for _ in range(attempts):
        ok, payload = session.call("fetch", key="answer")
        if ok and isinstance(payload, dict):
            value = payload.get("value")
            break
    if args.variant == "hang":
        time.sleep(300)
    session.call("store", value=value)
    session.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
