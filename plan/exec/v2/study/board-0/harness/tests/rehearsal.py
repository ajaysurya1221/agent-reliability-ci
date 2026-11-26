"""Drive both dates with the identical runner, release gate, and publication pipeline."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import zipfile
from datetime import date
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pin
from common import LIST, NOTE, ROOT, lines, models, need, read, schedule
from inputs import descriptors, digests, sources
from launcher import execute, prepare, roster
from publication import assemble, pack, report


def altered(original: Path, output: Path, member: str, field: str) -> Path:
    with (
        zipfile.ZipFile(original) as src,
        zipfile.ZipFile(output, "x", zipfile.ZIP_DEFLATED) as dest,
    ):
        for name in src.namelist():
            data = src.read(name)
            if field == "missing" and name == "result.md":
                continue
            if field == "report" and name == "result.md":
                data = data.replace(b"orders 8/8", b"orders 0/8", 1)
            if field == "totals" and name.startswith("runs/board0-d1-M1-E/count_"):
                obj = json.loads(data)
                obj["arms"]["baseline"]["all"]["passed"] = 0
                data = json.dumps(obj).encode()
            if name == member and field in ("rule", "grade", "verdict"):
                if field == "grade":
                    first, rest = data.split(b"\n", 1)
                    t = json.loads(first)
                    t["outcome"] = "FAIL" if t["outcome"] == "PASS" else "PASS"
                    data = json.dumps(t).encode() + b"\n" + rest
                else:
                    obj = json.loads(data)
                    if field == "rule":
                        obj["rule"]["delta"] = "1/5"
                    else:
                        obj["verdict"] = "PASS" if obj["verdict"] != "PASS" else "BLOCK"
                    data = json.dumps(obj).encode()
            dest.writestr(name, data)
        if field == "extra":
            dest.writestr("extra.txt", "unexpected")
    side = output.with_suffix(".zip.sha256")
    side.write_text(hashlib.sha256(output.read_bytes()).hexdigest() + "  " + output.name + "\n")
    return side


def checker(path: Path, sidecar: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-IB",
            str(ROOT / "harness/check_evidence.py"),
            str(path),
            str(sidecar),
            *extra,
        ],
        capture_output=True,
        text=True,
        timeout=240,
    )


def main() -> None:
    need(
        ROOT.is_relative_to(Path(os.environ["TMPDIR"]).resolve().parent), "temporary rehearsal only"
    )
    shutil.copyfile(ROOT / "models.example.json", ROOT / "models.json")
    slots = models(ROOT / "models.json", offline=True)
    prepare(slots, offline=True)
    (ROOT / LIST).write_text(digests(sources()))
    import audit

    first = audit.specs(audit.compiled(ROOT / "runs/board0-d1-M1-E/descriptor.yaml"), 1)
    os.environ["BOARD0_REHEARSAL_FAULTS"] = json.dumps(
        {s.task_id: s.seed for s in first if s.task_id in ("O-o1", "O-o2", "O-o3", "O-o5", "K-k8")}
    )
    # Historical fixtures intentionally contain no gradeable transcripts.
    (ROOT / "pins").mkdir()
    for i in range(1, 6):
        run = f"board0-pin-M{i}"
        (ROOT / "pins" / (run + ".json")).write_text(json.dumps({"run": run}))
    execute(slots[0]["pin"], slots, offline=True)

    def echo(body: bytes) -> tuple[int, bytes]:
        req = json.loads(body)
        return 200, json.dumps(
            {
                "model": req["model"],
                "done": True,
                "message": {"role": "assistant", "content": req["messages"][1]["content"]},
            }
        ).encode()

    with patch.object(pin, "toy_chat", echo):
        try:
            execute(slots[1]["pin"], slots, offline=True)
        except pin.PinFailed:
            pass
        else:
            raise AssertionError("echo passed the corrected pin")
    execute("board0-pin2-S1", slots, offline=True)
    slots = roster(offline=True)
    need(slots[1]["pin"] == "board0-pin2-S1", "spare did not take second slot")
    prepare(slots, offline=True)
    (ROOT / NOTE).write_text(digests(descriptors(slots)))
    (ROOT / LIST).write_text(digests(sources()))
    for run in schedule(slots):
        if "-pin2-" in run:
            continue
        day = date(2000, 1, 2 if "-d2-" in run else 1)
        execute(run, slots, offline=True, today=day)
    measured = lines(ROOT / "runs/board0-d1-M1-E/trials.jsonl")
    charged = next(t for t in measured if t["task_id"] == "O-o3" and t["arm"] == "baseline")
    need(
        charged["usage"]["tool_calls"] == 12 and charged["outcome"] == "PASS",
        "final text at the released budget",
    )
    for tid, stop, calls in [
        ("O-o1", "completed", 12),
        ("K-k8", "completed", 9),
        ("O-o5", "timeout", 1),
    ]:
        trial = next(t for t in measured if t["task_id"] == tid and t["arm"] == "candidate")
        need(
            trial["termination"] == stop
            and trial["usage"]["tool_calls"] == calls
            and trial["outcome"] == "FAIL"
            and trial["final_state"]["answer"] is None,
            f"{tid} budget outcome",
        )
    affected = read(ROOT / "runs/board0-d1-M1-E/count_b.json")
    need(affected["signs"]["errored"] == 1, "truncated reply not counted")
    baseline = affected["arms"]["baseline"]["all"]
    need(0 < baseline["exact"] < baseline["passed"] < baseline["retrieved"], "plain-text totals")
    outcomes = {t["task_id"]: t["outcome"] for t in measured if t["arm"] == "baseline"}
    for tid in ("O-o2", "O-o3", "O-o4", "K-k1", "K-k7"):
        need(outcomes[tid] == "PASS", f"{tid} expected text pass")
    for tid in ("O-o6", "O-o7", "O-o8", "K-k2", "K-k6"):
        need(outcomes[tid] == "FAIL", f"{tid} expected text fail")
    need(
        any(t["final_state"]["answer"] == "" and t["outcome"] == "FAIL" for t in measured),
        "missing empty terminal text",
    )
    (ROOT / "result.md").write_text(report(slots, offline=True))
    assemble(ROOT / "assembled", slots, offline=True)
    archive = ROOT / "stand-in.zip"
    pack(archive, slots, offline=True)
    good = checker(archive, archive.with_suffix(".zip.sha256"), "--rehearsal")
    need(good.returncode == 0, good.stderr)
    print(good.stdout.strip(), flush=True)
    prod = checker(archive, archive.with_suffix(".zip.sha256"))
    need(
        prod.returncode != 0 and "model inventory" in prod.stderr,
        "stand-in passed production check",
    )
    for field, filename, reason in [
        ("grade", "trials.jsonl", "trial grade"),
        ("rule", "descriptor.yaml", "digest differs"),
        ("verdict", "decision.json", "audit figures"),
        ("totals", "", "regraded counts"),
        ("report", "", "result.md differs"),
        ("missing", "", "archive inventory"),
        ("extra", "", "archive inventory"),
    ]:
        changed = ROOT / (field + ".zip")
        side = altered(archive, changed, "runs/board0-d1-M1-E/" + filename, field)
        bad = checker(changed, side, "--rehearsal")
        need(bad.returncode != 0 and reason in bad.stderr, bad.stdout + bad.stderr)
        print(f"Rejected changed {field}", flush=True)
    print("PASS Board-0 FIFO rehearsal, two slots on both days, seven altered packs rejected")


if __name__ == "__main__":
    main()
