"""Small offline child used by check-change CLI tests and the two-command smoke run."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from xml.etree import ElementTree as ET


def main() -> int:
    mode, size, output, *extra = sys.argv[1:]
    path = Path(output.removeprefix("--junitxml="))
    arm = os.environ["ARCI_CHANGE_ARM"]
    r = int(os.environ["ARCI_CHANGE_ROUND"])
    root = path.parent.parent
    with (root.parent / "calls.jsonl").open("a", encoding="utf-8") as calls:
        print(json.dumps([r, arm]), file=calls)
    if mode == "snapshot":
        names = ["rule.yaml", "rule.sha256", "plan.json"]
        print(json.dumps({k: (root / k).read_text() for k in names if (root / k).exists()}))
    else:
        print(json.dumps([str(Path.cwd()), str(path), *extra]))
    print("child stderr", file=sys.stderr)
    if mode == "missing-discovery" and r == 0:
        return 0
    if mode == "verbose":
        for stream in (sys.stdout, sys.stderr):
            stream.write("x" * (3 * 1024 * 1024))
    if mode.startswith("tree-") and r == 0:
        # The PID file ensures the grandchild exists before the wrapper exits or times out.
        ready = root.parent / "worker.pid"
        subprocess.Popen([sys.executable, __file__, "helper", str(ready)])
        while not ready.exists():
            time.sleep(0.005)
        if mode == "tree-error":
            return 7
        if mode == "tree-timeout":
            time.sleep(20)
        if mode == "tree-signal":
            os.kill(os.getpid(), signal.SIGTERM)
    if (mode == "cancel" and r == 0) or (mode == "cancel-changed-plan" and r == 1):
        if mode == "cancel-changed-plan":
            (root / "plan.json").write_text("changed during launch")
        helper = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(20)"])
        ready = root.parent / "launch.pid"
        temp = ready.with_suffix(".tmp")
        temp.write_text(f"{os.getpid()} {helper.pid}")
        temp.rename(ready)
        time.sleep(20)
    if mode.startswith("overwrite-") and r == 2:
        earlier = root / "round-001" / mode.removeprefix("overwrite-")
        earlier.write_bytes(b"changed by next round")
    if mode.startswith("registration-") and r == 1:
        _, action, name = mode.split("-")
        target = root / name
        if action == "delete":
            target.unlink()
        else:
            with target.open("ab") as stream:
                stream.write(b" ")
    if mode.startswith("decision-") and r == 4:
        target = root / f"round-{int(mode.removeprefix('decision-')):03d}/decision.json"
        target.write_bytes((root / "round-001/decision.json").read_bytes())
    if mode == "linked-result" and r == 0:
        path.symlink_to(root.parent / "fixture.csv")
        return 0
    if mode == "fifo" and r == 0:
        os.mkfifo(path)
        return 0
    if mode == "linked-directory" and r == 1:
        original = root / "original-directory"
        path.parent.rename(original)
        path.parent.symlink_to(original, target_is_directory=True)
    if mode == "reader-error" and r == 2:
        path.write_text('{"task_id":"task-0","outcome":"pass","extra":1e9999999999999999999}')
        return 0
    if r == 2:
        if mode == "timeout":
            time.sleep(30)
        if mode == "signal":
            os.kill(os.getpid(), signal.SIGTERM)
        if mode == "exit7":
            return 7
        if mode == "missing":
            return 0
        if mode == "empty":
            path.touch()
            return 0
        if mode == "unreadable":
            path.write_bytes(b"\xff")
            return 0
        if mode == "preexisting":
            other = "baseline" if arm == "candidate" else "candidate"
            path.with_stem(other).write_text("already here")
    rows: list[dict[str, str | int]] = []
    for n in range(int(size)):
        outcome = "pass"
        loss = mode.startswith("lose") and arm == "candidate" and n < int(mode[4:])
        if r == 0 or mode == "fail" or loss or (mode == "single" and r == 1 and n == 0):
            outcome = "fail"
        if mode.startswith("errors") and arm == "candidate" and r == 1:
            if n == 0:
                continue
            if n < int(mode.removeprefix("errors")):
                outcome = "error"
        task = f"task-{n}"
        if mode == "flag-name" and n == 0:
            task = "--markdown PATH or --json PATH"
            if arm == "candidate" and r == 1:
                outcome = "fail"
        if mode == "unknown" and r == 2 and n == 1:
            task = "unregistered"
        if mode == "duplicate" and r == 2 and n == 1:
            task = "task-0"
        number = r + 1 if mode == "badround" and r == 2 else r
        rows.append({"task_id": task, "outcome": outcome, "round": number})
    if path.suffix == ".csv":
        path.write_text(
            "task_id,outcome,round\n"
            + "".join(f"{row['task_id']},{row['outcome']},{row['round']}\n" for row in rows)
        )
    elif path.suffix == ".jsonl":
        path.write_text("".join(json.dumps(row) + "\n" for row in rows))
    else:
        stamp = str(min(1, r)) if mode == "timestamp" else str(r)
        if mode == "same-instant":
            stamp = (
                ("2026-01-05T00:00:00Z" if r == 1 else "2026-01-05T01:00:00.000+01:00")
                if r
                else "discovery"
            )
        if mode == "nanoseconds":
            stamp = f"2026-01-05T00:00:00.000000{r:03d}Z"
        suite = ET.Element("testsuite", timestamp=stamp)
        for row in rows:
            case = ET.SubElement(suite, "testcase", classname="suite", name=str(row["task_id"]))
            if row["outcome"] != "pass":
                ET.SubElement(case, "error" if row["outcome"] == "error" else "failure")
        ET.ElementTree(suite).write(path, encoding="utf-8")
    return int(any(row["outcome"] != "pass" for row in rows))


if __name__ == "__main__":
    if sys.argv[1] == "helper":
        worker = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(20)"])
        ready = Path(sys.argv[2])
        temp = ready.with_suffix(".tmp")
        temp.write_text(f"{os.getpid()} {worker.pid}")
        temp.rename(ready)
        worker.wait()
    else:
        raise SystemExit(main())
