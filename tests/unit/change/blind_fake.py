"""Offline test command for the black-box check-change tests."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import signal
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import TypedDict, cast


class Settings(TypedDict):
    case: str
    tasks: int
    fmt: str
    fault: str
    target: str


def emit(path: Path, fmt: str, rows: list[tuple[str, str]], stamp: int, label: int | None) -> None:
    if fmt == "junit":
        root = ET.Element("testsuites")
        suite = ET.SubElement(root, "testsuite", timestamp=f"2026-01-01T00:00:{stamp:02}")
        for name, outcome in rows:
            cell = ET.SubElement(suite, "testcase", classname="suite", name=name)
            if outcome != "pass":
                ET.SubElement(cell, "failure" if outcome == "fail" else "error")
        ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)
        return
    records = [
        {"task_id": name, "outcome": outcome, **({"round": label} if label is not None else {})}
        for name, outcome in rows
    ]
    with path.open("w", newline="", encoding="utf-8") as stream:
        if fmt == "jsonl":
            stream.writelines(json.dumps(record) + "\n" for record in records)
        else:
            writer = csv.DictWriter(
                stream, ["task_id", "outcome"] + (["round"] if label is not None else [])
            )
            writer.writeheader()
            writer.writerows(records)


def main() -> int:
    settings = cast(Settings, json.loads(Path("settings.json").read_text()))
    case, fault = settings["case"], settings["fault"]
    arm = os.environ["ARCI_CHANGE_ARM"]
    number = int(os.environ["ARCI_CHANGE_ROUND"])
    out = Path(sys.argv[1].removeprefix("--junitxml="))
    print(f"stdout {arm} {number}", flush=True)
    print(f"stderr {arm} {number}", file=sys.stderr, flush=True)
    campaign = out.parent.parent
    files: dict[str, tuple[int, str]] = {}
    if number in (1, 2):
        for path in campaign.rglob("*"):
            if path.is_file() and (
                path.parent.name in ("discovery", "round-001", f"round-{number:03}")
                or path.parent == campaign
            ):
                data = path.read_bytes()
                files[str(path.relative_to(campaign))] = (
                    len(data),
                    hashlib.sha256(data).hexdigest(),
                )
    event = dict(arm=arm, number=number, out=str(out), args=sys.argv[2:], files=files)
    with Path("launches.jsonl").open("a", encoding="utf-8") as log:
        log.write(json.dumps(event) + "\n")

    target = settings["target"]
    if number == 2 and target == "first":
        # Discovery plus two launches in round one precede the first arm in round two.
        targeted = len(Path("launches.jsonl").read_text().splitlines()) == 4
    else:
        targeted = arm == target
    active = fault if number == 2 and targeted else ""
    if active == "empty":
        out.touch()
        return 0
    if active == "invalid":
        out.write_text("<testsuites>")
        return 0
    if active == "elsewhere":
        out = Path("misplaced.xml")
    if fault == "preexisting" and number == 2:
        other = "baseline" if arm == "candidate" else "candidate"
        out.with_name(other + out.suffix).write_text("preexisting evidence")

    rows: list[tuple[str, str]] = []
    for index in range(settings["tasks"]):
        name = "café au lait" if index == 0 else f"task-{index:02}"
        lost = arm == "candidate" and (case == "loss" or (case == "two-losses" and index < 2))
        outcome = "fail" if number == 0 or lost or case == "both-fail" else "pass"
        if active in ("one-error", "two-errors") and index < (1 if active == "one-error" else 2):
            outcome = "error"
        if active != "missing" or index != 0:
            rows.append((name, outcome))
    if active == "unknown":
        rows.append(("unregistered", "pass"))
    if active == "duplicate":
        rows.append(rows[0])
    label: int | None = number + 1 if active == "label" else number
    if number == 0:
        label = {"discovery-label": 2, "discovery-zero": 0}.get(fault)
    emit(out, settings["fmt"], rows, 1 if active == "timestamp" else number, label)
    if active == "timeout":
        time.sleep(4)
        Path("finished-sleep").touch()
    if active == "signal":
        os.kill(os.getpid(), signal.SIGTERM)
    if active == "status" or (number == 0 and fault == "discovery-status"):
        return 2
    if active == "unreadable":
        out.chmod(0)
        if os.access(out, os.R_OK):
            # Privileged CI can still open mode-000 files. Force an OS read error there.
            out.unlink()
            out.symlink_to(out.name)
    if (
        number == 1
        and fault == "cannot-start"
        and len(Path("launches.jsonl").read_text().splitlines()) == 3
    ):
        Path("candidate-python").unlink()
    return int(any(outcome == "fail" for _, outcome in rows))


if __name__ == "__main__":
    sys.exit(main())
