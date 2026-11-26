"""Serial read-only relay for the released stdio ToolSet bridge."""

import json
import os
import subprocess
import sys
from importlib.util import find_spec
from pathlib import Path
from typing import Any

from common import ROOT, Row, need, read, sha
from worlds import check_opening, rows


def main() -> None:
    work = Path(os.environ["ARCI_WORKDIR"])
    taskfile = Path(os.environ["ARCI_TASK_FILE"])
    task = read(taskfile)
    server_task = work / "desk-task.json"
    server_task.write_text(json.dumps(task["task"]))
    seed = int(os.environ["ARCI_SEED"])
    family = task["family"]
    folder, module = {
        "orders": ("orderdesk", "orderdesk_world"),
        "calendar": ("calendardesk", "calendar_world"),
    }[family]

    allowed = (
        ["lookup_order", "check_stock"] if family == "orders" else ["lookup_event", "check_room"]
    )
    need("board_opening" not in allowed, "reserved tool name")
    first = task["opening"]["name"]
    need(first in allowed, "unadvertised opening")
    spec = find_spec("arci.mcp_toolset_server")
    assert spec and spec.origin
    bridge = Path(spec.origin)
    # Only the selected desk, installed ARCI and interpreter dependencies are visible upstream.
    env = {
        "PATH": os.defpath,
        "PYTHONDONTWRITEBYTECODE": "1",
        "LC_ALL": "C",
        "TZ": "UTC",
        "HOME": str(work),
        "PYTHONPATH": os.pathsep.join([str(ROOT / folder), str(bridge.parents[1])]),
    }
    prefix = (
        []
        if os.environ.get("BOARD0_NO_SANDBOX") == "1"
        else ["sandbox-exec", "-p", "(version 1)(allow default)(deny network*)"]
    )
    argv = [
        sys.executable,
        "-P",
        "-m",
        "arci.mcp_toolset_server",
        "--toolset",
        module + ":make_tools",
        "--tools",
        ",".join(allowed),
        "--workdir",
        str(work),
        "--seed",
        str(seed),
        "--task-file",
        str(server_task),
    ]
    with (
        (work / "ledger.jsonl").open("x") as ledger,
        subprocess.Popen(
            prefix + argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, env=env
        ) as proc,
    ):
        assert proc.stdin and proc.stdout

        def note(record: Row) -> None:
            ledger.write(json.dumps(record, ensure_ascii=False) + "\n")
            ledger.flush()

        note(
            {
                "record": "start",
                "family": family,
                "key_id": task["key_id"],
                "seed": seed,
                "module": module,
                "world_sha256": sha((ROOT / folder / (module + ".py")).read_bytes()),
                "bridge_sha256": sha(bridge.read_bytes()),
            }
        )
        seq = 0
        try:
            for line in sys.stdin.buffer:
                req = json.loads(line)
                method = req.get("method")
                proc.stdin.write(json.dumps(req).encode() + b"\n")
                proc.stdin.flush()
                if "id" not in req:
                    continue
                reply = json.loads(proc.stdout.readline())
                need(reply["id"] == req["id"], "bridge response id")
                if method == "tools/list":
                    tools = reply["result"]["tools"]
                    note({"record": "tools", "tools": tools})
                if method == "tools/call":
                    params = req["params"]
                    result: Any = reply.get("result", {"error": reply.get("error")})
                    note(
                        {
                            "record": "call",
                            "seq": seq,
                            "tool": params["name"],
                            "arguments": params["arguments"],
                            "server_reply": result,
                            "passed_on": result,
                        }
                    )
                    if seq == 0:
                        need(params == task["opening"], "scripted opening")
                        check_opening(rows()[task["key_id"]], seed, result)
                    seq += 1
                print(json.dumps(reply), flush=True)
        finally:
            proc.stdin.close()
            proc.wait(timeout=5)


if __name__ == "__main__":
    main()
