"""A scripted MCP agent: one stdio session, newline-delimited JSON-RPC, standard library only.

    python -P -m agent --mcp-config FILE --task-file FILE --variant retry|fragile

It starts the one server in the config, initializes, lists tools, fetches the task's key and
stores the value. `retry` retries a failed fetch up to 3 times; `fragile` gives up on the first
error. Exit 0: done (the agent's claim of success); 1: gave up; 75: infrastructure problem.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path
from typing import Any

RETRIES = {"retry": 3, "fragile": 0}
INFRA = 75  # EX_TEMPFAIL: the trial is a harness ERROR, not the agent's failure


class Session:
    """One server process and one connection; one request in flight at a time."""

    def __init__(self, config_path: str) -> None:
        (entry,) = json.loads(Path(config_path).read_text("utf-8"))["mcpServers"].values()
        self.proc = subprocess.Popen(
            [entry["command"], *entry.get("args", [])],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            env={**os.environ, **entry.get("env", {})},
            text=True,
        )
        self.last_id = 0

    def send(self, method: str, params: dict[str, Any], *, notify: bool = False) -> Any:
        assert self.proc.stdin is not None and self.proc.stdout is not None
        message: dict[str, Any] = {"jsonrpc": "2.0", "method": method, "params": params}
        if not notify:
            self.last_id += 1
            message["id"] = self.last_id
        self.proc.stdin.write(json.dumps(message) + "\n")
        self.proc.stdin.flush()
        while not notify:
            line = self.proc.stdout.readline()
            if not line:
                raise ConnectionError("the MCP server closed the session")
            reply: Any = json.loads(line)
            if reply.get("id") == self.last_id:
                return reply
        return None

    def call(self, name: str, **arguments: str) -> Any:
        """The tool's JSON value, or None for an error result."""
        result: Any = self.send("tools/call", {"name": name, "arguments": arguments}).get("result")
        if not isinstance(result, dict) or result.get("isError") or not result.get("content"):
            return None
        return json.loads(result["content"][0]["text"])

    def close(self) -> None:
        try:
            assert self.proc.stdin is not None
            self.proc.stdin.close()
            self.proc.wait(timeout=10)
        except (OSError, subprocess.TimeoutExpired):
            self.proc.kill()


def work(session: Session, key: str, retries: int) -> bool:
    client = {"name": "recipe-agent", "version": "1"}
    init = {"protocolVersion": "2026-07-28", "capabilities": {}, "clientInfo": client}
    session.send("initialize", init)
    session.send("notifications/initialized", {}, notify=True)
    listed: Any = session.send("tools/list", {})["result"]["tools"]
    if {"fetch", "store"} - {tool["name"] for tool in listed}:
        raise ConnectionError("the server does not offer fetch and store")
    for _attempt in range(1 + retries):
        fetched = session.call("fetch", key=key)
        if isinstance(fetched, dict) and isinstance(fetched.get("value"), str):
            stored = session.call("store", key=key, value=fetched["value"])
            return isinstance(stored, dict) and stored.get("stored") is True
    return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mcp-config", required=True)
    parser.add_argument("--task-file", required=True)
    parser.add_argument("--variant", choices=sorted(RETRIES), required=True)
    args = parser.parse_args()
    try:
        key = str(json.loads(Path(args.task_file).read_text("utf-8"))["key"])
        session = Session(args.mcp_config)
    except (OSError, ValueError, KeyError, TypeError):
        return INFRA
    try:
        done = work(session, key, RETRIES[args.variant])
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return INFRA
    finally:
        session.close()
    return 0 if done else 1


if __name__ == "__main__":
    raise SystemExit(main())
