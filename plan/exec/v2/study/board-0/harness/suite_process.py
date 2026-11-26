"""Record each live process group before it can start study work."""

from __future__ import annotations

import fcntl
import json
import os
import subprocess
import sys
import time
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from agent import atomic_json


@contextmanager
def locked_file(path: Path, seconds: float) -> Generator[None, None, None]:
    with path.open("a") as lock:
        until = time.monotonic() + seconds
        while True:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= until:
                    raise TimeoutError(f"{path.stem} lock deadline") from None
                time.sleep(0.05)
        yield


@contextmanager
def registry(root: Path) -> Generator[Path, None, None]:
    with locked_file(root / "members.lock", 30):
        yield root / "active-suite.json"


def alive(pid: int, *, group: bool = False) -> bool:
    if pid <= 0:
        raise ValueError("invalid recorded process")
    try:
        (os.killpg if group else os.kill)(pid, 0)
    except ProcessLookupError:
        return False
    return True


def clear(root: Path, *, finishing: Path | None = None) -> None:
    """Caller holds the suite lock. A detached descendant keeps its group alive."""
    with registry(root) as path:
        if not path.exists():
            return
        active = json.loads(path.read_bytes())
        owner = finishing == root / active["claim"] and active["launcher"] == os.getpid()
        if (not owner and alive(active["launcher"])) or any(
            alive(pid, group=True) for pid in active["groups"]
        ):
            raise ValueError("previous suite processes still active")
        path.unlink()


def enter_group(directory: Path) -> None:
    with registry(directory.parent) as path:
        active = json.loads(path.read_bytes())
        if active["claim"] != directory.name or os.getpgrp() != os.getpid():
            raise ValueError("inactive claim or missing process group")
        active["groups"] = [pid for pid in active["groups"] if alive(pid, group=True)]
        active["groups"].append(os.getpid())
        atomic_json(path, active)


def command(directory: Path, mode: str, argv: list[str]) -> list[str]:
    return [sys.executable, "-PB", str(Path(__file__).resolve()), str(directory), mode, *argv]


@contextmanager
def trial_clock(runner: Any) -> Generator[None, None, None]:
    encode = runner.canonical_json

    def capture(value: Any) -> bytes:
        data = encode(value)
        if isinstance(value, dict) and "deadline_monotonic" in value and "workdir" in value:
            (Path(value["workdir"]) / "board-deadline").write_text(str(value["deadline_monotonic"]))
        return data

    with patch.object(runner, "canonical_json", capture):
        yield


def run(directory: Path, argv: list[str]) -> int:
    from arci import cli, runner

    # ARCI starts each agent, boundary and grader in its own session. The child
    # registers that group before exec. Its ordinary descendants inherit the group.
    def spawn(args: list[str], **kwargs: Any) -> subprocess.Popen[Any]:
        if not kwargs.get("start_new_session"):
            raise ValueError("unregistered runner process layout")
        return subprocess.Popen(command(directory, "exec", args), **kwargs)

    processes = SimpleNamespace(**(vars(subprocess) | {"Popen": spawn}))
    with trial_clock(runner), patch.object(runner, "subprocess", processes):
        return cli.main(argv)


if __name__ == "__main__":
    directory = Path(sys.argv[1])
    enter_group(directory)
    if sys.argv[2] == "exec":
        os.execvp(sys.argv[3], sys.argv[3:])
    if sys.argv[2] != "run":
        raise ValueError("unknown suite process mode")
    raise SystemExit(run(directory, sys.argv[3:]))
