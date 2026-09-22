"""A tiny stdio MCP server (revision 2026-07-28 subset) used as the environment. FROZEN.

    python mcp_fixture_server.py --workdir DIR [--pid-dir DIR] [--marker FILE] [--task-results]

State lives in DIR/state.json so a trusted snapshot function can read it after the agent exits.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

TOOLS = [
    {"name": name, "description": name, "inputSchema": {"type": "object"}}
    for name in ("fetch", "store", "log")
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workdir", required=True)
    parser.add_argument("--pid-dir", default=None)
    parser.add_argument("--marker", default=None)
    parser.add_argument("--task-results", action="store_true")
    parser.add_argument(
        "--malformed", action="store_true", help="tools/call results have a bad shape"
    )
    parser.add_argument("--big", action="store_true", help="pad ping and fetch results to ~700 KB")
    parser.add_argument(
        "--extra-tool", default=None, help="advertise one more tool name (reserved-name probe)"
    )
    args = parser.parse_args()
    tools = list(TOOLS)
    if args.extra_tool:
        tools.append(
            {"name": args.extra_tool, "description": "x", "inputSchema": {"type": "object"}}
        )
    if args.marker:
        Path(args.marker).write_text("server started")
    if args.pid_dir:
        (Path(args.pid_dir) / "server.pid").write_text(str(os.getpid()))
    state_path = Path(args.workdir) / "state.json"
    state: dict[str, Any] = {"stored": None, "log": []}

    def save() -> None:
        state_path.write_text(json.dumps(state, sort_keys=True))

    def text(value: Any) -> dict[str, Any]:
        return {
            "resultType": "complete",
            "content": [{"type": "text", "text": json.dumps(value, sort_keys=True)}],
            "isError": False,
        }

    save()
    for line in sys.stdin:
        if not line.strip():
            continue
        message = json.loads(line)
        if "id" not in message:  # a notification
            continue
        method, params = message.get("method"), message.get("params") or {}
        result: dict[str, Any] | None = None
        error: dict[str, Any] | None = None
        if method == "initialize":
            result = {
                "protocolVersion": "2026-07-28",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "arci-fixture", "version": "0"},
            }
        elif method == "ping":
            result = {"pad": "x" * 700_000} if args.big else {}
        elif method == "tools/list":
            result = {"tools": tools}
        elif method == "tools/call" and args.task_results:
            result = {"resultType": "task", "taskId": "t-1", "status": "working"}
        elif method == "tools/call" and args.malformed:
            result = {"content": "not an array", "isError": "true"}
        elif method == "tools/call":
            name, arguments = params.get("name"), params.get("arguments") or {}
            if name == "fetch":
                payload = {"key": arguments.get("key"), "value": 42}
                if args.big:
                    payload["pad"] = "x" * 700_000
                result = text(payload)
            elif name == "store":
                state["stored"] = arguments.get("value")
                save()
                result = text({"stored": True})
            elif name == "log":
                state["log"].append(arguments.get("msg"))
                save()
                result = text(None)
            else:
                error = {"code": -32602, "message": f"unknown tool {name}"}
        else:
            error = {"code": -32601, "message": f"method not found: {method}"}
        reply: dict[str, Any] = {"jsonrpc": "2.0", "id": message["id"]}
        if error is not None:
            reply["error"] = error
        else:
            reply["result"] = result
        sys.stdout.write(json.dumps(reply) + "\n")
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
