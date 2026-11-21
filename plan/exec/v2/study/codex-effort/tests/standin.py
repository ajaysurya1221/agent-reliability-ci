#!/Users/ajay/Developer/.arci-worktrees/codex-effort-agent-env/bin/python
"""Scripted local executable. Its private script is supplied only by the tests."""

from __future__ import annotations

import base64
import json
import os
import signal
import sys
import time
from pathlib import Path


def event(kind: str, **data: object) -> None:
    print(json.dumps({"type": kind, **data}), flush=True)


def main() -> None:
    assert (
        sys.executable == "/Users/ajay/Developer/.arci-worktrees/codex-effort-agent-env/bin/python"
    )
    args = sys.argv[1:]
    if args == ["--version"]:
        print("standin 1")
        return
    script = json.loads(Path(os.environ["STANDIN_SCRIPT"]).read_bytes())
    task = args[-1]
    effort = args[4]
    assert args == [
        "exec",
        "-m",
        "gpt-6.2-astra",
        "-c",
        effort,
        "-s",
        "workspace-write",
        "-c",
        'approval_policy="never"',
        "--skip-git-repo-check",
        "--json",
        "--ephemeral",
        "-o",
        args[-2],
        task,
    ]
    assert effort in ('model_reasoning_effort="high"', 'model_reasoning_effort="xhigh"')
    assert not Path(".git").exists() and sys.stdin.read() == ""
    assert os.environ["GIT_TERMINAL_PROMPT"] == "0"
    mode = script["mode"]
    if mode == "two-rounds":
        mode = "correct" if effort.endswith('"xhigh"') else "wrong"
    elif mode == "intermittent":
        arm = "baseline" if effort.endswith('"xhigh"') else "candidate"
        mode = "quota" if arm == script["first_effort"][task] else "empty"
    assert (
        os.environ["PATH"].split(os.pathsep)[0]
        == "/Users/ajay/Developer/.arci-worktrees/codex-effort-agent-env/bin"
    )
    assert Path(os.environ["PYTHONPATH"]) == Path.cwd() / "src"
    assert not Path(args[-2]).is_relative_to(Path.cwd())
    if mode == "no-stream":
        raise SystemExit(1)
    if mode == "stream":
        for item in script["events"]:
            print(json.dumps(item).replace("$EXPORT", str(Path.cwd())), flush=True)
        if script.get("stall"):
            time.sleep(30)
        if script.get("signal"):
            os.kill(os.getpid(), signal.SIGTERM)
        raise SystemExit(script.get("rc", 0))
    event("thread.started", thread_id="standin-thread")
    event("turn.started")
    if mode != "unknown-stall":
        event("item.started", item={"id": "item_0", "type": "command_execution", "command": "pwd"})
        event(
            "item.completed",
            item={
                "id": "item_0",
                "type": "command_execution",
                "command": "pwd",
                "exit_code": 0,
                "aggregated_output": str(Path.cwd()),
            },
        )
    for item in script.get("events", []):
        print(json.dumps(item).replace("$EXPORT", str(Path.cwd())), flush=True)
    files = script["answers"][task]
    if mode == "correct":
        for name, data in files.items():
            Path(name).write_bytes(base64.b64decode(data))
    elif mode == "wrong":
        with Path(next(iter(files))).open("a") as f:
            f.write("\n# No behaviour change.\n")
    elif mode == "outside":
        Path("unregistered.txt").write_text("outside")
    elif mode == "test":
        Path("tests/test_extra.py").write_text("def test_green(): pass\n")
    elif mode == "ignored":
        Path(".pytest_cache").mkdir()
        Path(".pytest_cache/standin").write_text("ignored by git")
    elif mode in ("sleep", "unknown-stall"):
        if mode == "sleep":
            event(
                "item.started",
                item={
                    "type": "command_execution",
                    "id": "busy",
                    "command": "python -m pytest",
                    "cwd": str(Path.cwd()),
                },
            )
        time.sleep(30)
    elif mode in {"quota", "auth", "rate", "server", "transport", "retry", "service-stall"}:
        diagnostic = {
            "quota": "quota exceeded",
            "auth": "authentication failed",
            "rate": "HTTP 429",
            "server": "HTTP 503",
            "transport": "stream disconnected before completion",
            "retry": "exhausted all retries",
            "service-stall": "reconnecting after transport error",
        }[mode]
        event("error", message=diagnostic)
        if mode == "service-stall":
            time.sleep(30)
        event("turn.failed", error={"message": diagnostic})
        raise SystemExit(1)
    elif mode in {"crash", "unknown"}:
        event(
            "item.completed",
            item={
                "type": "command_execution",
                "id": "item_1",
                "command": "pwd",
                "exit_code": 0,
                "aggregated_output": "ERROR: quota exceeded",
            },
        )
        print("ERROR: HTTP 503", file=sys.stderr)
        if mode == "crash":
            event("error", message="agent crashed")
        else:
            event("turn.failed", error={"message": "stopped"})
        raise SystemExit(1)
    elif mode != "empty":
        raise ValueError(mode)
    Path(args[-2]).write_text("stand-in final answer")
    event("turn.completed", usage={})


if __name__ == "__main__":
    main()
