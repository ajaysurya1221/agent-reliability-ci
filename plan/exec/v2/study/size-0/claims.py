"""Durable claims, calendar restrictions and the cross-study lock."""

import fcntl
import os
import shlex
import subprocess
from collections.abc import Generator
from contextlib import ExitStack, contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import IO

from descriptors import RUNS, Row, read
from processes import start_time
from records import require

HOST = Path("/private/var/tmp/arci-size0-claims")
BOARD = Path("/private/var/tmp/arci-board0-claims")


def claims_dir() -> Path:
    return Path(os.environ.get("SIZE0_CLAIMS", str(HOST)))


def schedule(rehearsal: bool) -> tuple[str, ...]:
    return tuple(r for r in RUNS if not rehearsal or r.split("-")[2] in ("q2", "q4"))


def calendar(starts: list[Row]) -> None:
    dates: dict[str, tuple[str, str]] = {}
    last: datetime | None = None
    for start in starts:
        stamp = datetime.fromisoformat(start["started_at"])
        require(
            stamp.utcoffset() is not None
            and stamp.date().isoformat() == start["date"]
            and start["timezone"] == stamp.strftime("%z"),
            "claim timestamp or timezone differs",
        )
        require(last is None or stamp >= last, "claim time reversed")
        last = stamp
        day = start["run"].split("-")[1]
        current = (start["date"], start["timezone"])
        require(
            dates.setdefault(day, current) == current, "nominal day spans local dates or timezones"
        )
    if "d2" in dates:
        require(
            "d1" in dates
            and date.fromisoformat(dates["d2"][0]) > date.fromisoformat(dates["d1"][0]),
            "day 2 requires a later local date",
        )


def prior_claims(claims: Path, order: tuple[str, ...]) -> list[str]:
    require(all(p.name in RUNS for p in claims.glob("size0-*")), "unregistered claim")
    present = [r for r in order if (claims / r).exists()]
    require(present == list(order[: len(present)]), "missing earlier claim")
    require(
        not any((claims / r).exists() for r in set(RUNS) - set(order)),
        "unexpected rehearsal schedule claim",
    )
    return present


def board_idle(board: Path) -> None:
    path = board / "active-suite.json"
    if not path.exists():
        return
    active = read(path)
    groups = {g["pid"] if isinstance(g, dict) else g for g in active["groups"]}
    if groups:
        require(all(type(g) is int and g > 0 for g in groups), "invalid recorded process")
        # Board registers PGIDs before exec. A worker can outlive the group leader.
        processes = subprocess.run(
            ["ps", "-Aww", "-o", "pgid=,stat=,command="],
            check=True,
            capture_output=True,
            text=True,
        )
        for line in processes.stdout.splitlines():
            fields = line.split(None, 2)
            if len(fields) != 3:
                continue
            pgid, state, command = fields
            if int(pgid) not in groups or state.startswith("Z"):
                continue
            wrapper = (
                "harness/suite_process.py" in command and str(board / active["claim"]) in command
            )
            require("arci" not in command and not wrapper, "Board-0 suite process alive")

    member = active["launcher"]
    pid = member["pid"] if isinstance(member, dict) else member
    require(type(pid) is int and pid > 0, "invalid recorded process")
    current = start_time(pid)
    if current is None:
        return
    recorded = member.get("start_time") if isinstance(member, dict) else None
    recorded = recorded or active.get("launcher_start_time")
    if recorded is not None:
        require(current != recorded, "Board-0 suite process alive")
        return
    result = subprocess.run(
        ["ps", "-ww", "-p", str(pid), "-o", "command="], capture_output=True, text=True
    )
    if result.returncode and start_time(pid) is None:
        return
    result.check_returncode()
    args = shlex.split(result.stdout)
    launcher = any(arg.endswith("harness/launcher.py") for arg in args) and args[-2:] == [
        "real",
        active["claim"],
    ]
    require(not launcher, "Board-0 suite process alive")


@contextmanager
def locks(claims: Path, *, real: bool) -> Generator[tuple[int, ...]]:
    claims.mkdir(parents=True, exist_ok=True)
    require(claims.resolve() == claims, "linked claims directory")
    with ExitStack() as stack:
        handles: list[IO[bytes]] = [stack.enter_context((claims / "suite.lock").open("ab"))]
        if real and (BOARD / "suite.lock").exists():
            handles.append(stack.enter_context((BOARD / "suite.lock").open("rb")))
        for handle in handles:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if real:
            board_idle(BOARD)
        yield tuple(h.fileno() for h in handles)
