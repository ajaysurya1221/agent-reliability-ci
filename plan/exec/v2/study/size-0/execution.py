"""Supervise the released CLI and retain its locks through worker-group cleanup."""

import json
import os
import signal
import subprocess
import sys
import time
from contextlib import suppress
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from processes import group_alive, start_time
from records import atomic_json


def now() -> str:
    return datetime.now().astimezone().isoformat()


def registered_cli(work: Path, fd: int, argv: list[str]) -> int:
    from arci import cli, runner

    def spawn(args: list[str], **kwargs: Any) -> subprocess.Popen[Any]:
        if not kwargs.get("start_new_session"):
            raise ValueError("unexpected worker process layout")
        return subprocess.Popen(
            [sys.executable, "-IB", __file__, "register", str(work), str(fd), *args],
            pass_fds=(fd,),
            **kwargs,
        )

    processes = SimpleNamespace(**(vars(subprocess) | {"Popen": spawn}))
    print("Starting registered ARCI run", flush=True)
    with patch.object(runner, "subprocess", processes):
        return cli.main(argv)


def cleanup(work: Path) -> bool:
    survived = False
    for path in (work / "groups").glob("*.json"):
        group = json.loads(path.read_bytes())
        pid, started = group["pid"], group["start_time"]
        if group_alive(pid, started):
            survived = True
            with suppress(ProcessLookupError):
                try:
                    os.killpg(pid, signal.SIGKILL)
                except PermissionError:
                    # Do not release either lock on a signal-permission failure.
                    print(
                        f"worker group {pid}: termination denied; waiting for exit",
                        file=sys.stderr,
                        flush=True,
                    )
            while group_alive(pid, started):
                time.sleep(0.05)
    return survived


def execute(work: Path, argv: list[str], locks: tuple[int, ...]) -> int:
    record: dict[str, Any] = dict(started_at=now(), ended_at=None, exit_code=None, pid=None)
    path = work / "execution.json"
    with (work / "arci.log").open("xb", buffering=0) as log:
        atomic_json(path, record)
        (work / "groups").mkdir()
        reader, writer = os.pipe()
        try:
            if argv[:1] == ["run"]:
                argv = [sys.executable, "-IBu", __file__, "cli", str(work), str(writer), *argv]
            with subprocess.Popen(
                argv,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                pass_fds=(*locks, writer),
            ) as child:
                os.close(writer)
                writer = -1
                record.update(pid=child.pid, start_time=start_time(child.pid))
                atomic_json(path, record)
                code = child.wait()
            # A worker forked just before CLI death inherits the write end until
            # its group record is published. EOF closes that registration race.
            os.read(reader, 1)
            record["exit_code"] = code
            if cleanup(work):
                record["status"] = "interrupted, worker survived"
                return code or 1
            return code
        finally:
            os.close(reader)
            if writer >= 0:
                os.close(writer)
            record["ended_at"] = now()
            atomic_json(path, record)


if __name__ == "__main__":
    if sys.argv[1] in ("register", "cli"):
        work, fd = Path(sys.argv[2]), int(sys.argv[3])
        if sys.argv[1] == "cli":
            sys.exit(registered_cli(work, fd, sys.argv[4:]))
        pid = os.getpid()
        started = start_time(pid)
        if started is None or os.getpgrp() != pid:
            sys.exit("worker group registration failed")
        atomic_json(work / "groups" / f"{pid}-{started}.json", dict(pid=pid, start_time=started))
        os.close(fd)
        os.execv(sys.argv[4], sys.argv[4:])
    sys.exit(
        execute(
            Path(sys.argv[1]), sys.argv[2:], tuple(map(int, os.environ["SIZE0_LOCKS"].split(",")))
        )
    )
