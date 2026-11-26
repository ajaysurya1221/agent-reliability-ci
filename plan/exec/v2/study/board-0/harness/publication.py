"""Board report, exact publication allowlist and detached archive digest."""

from __future__ import annotations

import hashlib
import os
import tempfile
import zipfile
from pathlib import Path

from common import ROOT, SIDES, Row, need, read
from inputs import file, inventory
from privacy import operator_identifiers, safe_bytes


def rating(trials: list[Row], rows: dict[str, Row]) -> Row:
    passed = {r["task_id"] for r in trials if r["outcome"] == "PASS"}
    counts = {f: sum(rows[k]["family"] == f for k in passed) for f in ("orders", "calendar")}
    return {"families": counts, "rated": min(counts.values()) >= 6}


def report(slots: list[Row], *, offline: bool = False) -> str:
    out = ["# Board-0" + (" FIFO stand-in rehearsal" if offline else ""), ""]
    criteria = [
        "## Criteria",
        "",
        "| Slot | Day | BLOCK | PASS | INCONCLUSIVE | Orders stock | Orders empty | "
        "Calendar stock | Calendar empty |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for m in slots:
        for d in (1, 2):
            prefix = f"board0-d{d}-{m['slot']}"
            c = ROOT / "clean" / (prefix + "-clean.json")
            e = ROOT / "runs" / (prefix + "-E")
            out.extend([f"## {m['slot']} · day {d} · {m['tag']}", ""])
            if not c.exists():
                out.extend(["Incomplete model-day.", ""])
                continue
            clean = read(c)
            out.append(
                f"Clean tasks passing at least once: orders {clean['families']['orders']}/8, "
                f"calendar {clean['families']['calendar']}/8. "
                + ("Status: rated." if clean["rated"] else "Status: not rated.")
            )
            if not (e / "audit.json").exists():
                out.extend(["Measured run incomplete.", ""])
                continue
            counts = read(e / "count_a.json")
            decision = read(e / "decision.json")
            audit = read(e / "audit.json")
            elapsed = clean["seconds"] + audit["seconds"]
            out.extend(
                [
                    f"{decision['verdict']} at round {decision['stopped_at_round']}. "
                    f"Clean plus measured elapsed time {elapsed:.2f} seconds.",
                    "",
                    "| Arm | Passes | Orders | Calendar | Retrieved | Exact |",
                    "|---|---:|---:|---:|---:|---:|",
                ]
            )
            rates = []
            for side, label in zip(SIDES, ("stock-sentence", "empty-as-given"), strict=True):
                a = counts["arms"][side]
                passing = [
                    f"{a[f]['passed']}/{a[f]['trials']}" for f in ("all", "orders", "calendar")
                ]
                out.append(
                    "| "
                    + " | ".join(
                        [
                            label,
                            *passing,
                            str(a["all"]["retrieved"]),
                            str(a["all"]["exact"]),
                        ]
                    )
                    + " |"
                )
            signs = counts["signs"]
            out.extend(
                [
                    "",
                    "Pair signs "
                    + ", ".join(f"{k} {signs[k]}" for k in ("minus", "zero", "plus", "errored"))
                    + ".",
                    "",
                ]
            )
            for f in ("orders", "calendar"):
                for side in SIDES:
                    a = counts["arms"][side][f]
                    rates.append(f"{a['passed']}/{a['trials']}")
            criteria.append(
                "| "
                + " | ".join(
                    [
                        m["slot"],
                        str(d),
                        *(
                            str(int(decision["verdict"] == v))
                            for v in ("BLOCK", "PASS", "INCONCLUSIVE")
                        ),
                        *rates,
                    ]
                )
                + " |"
            )
    return "\n".join([*out, *criteria, ""])


def assemble(dest: Path, slots: list[Row], *, offline: bool = False) -> None:
    from admission import CLAIMS, finished, registration
    from common import schedule

    claims = ROOT / ".offline-claims" if offline else CLAIMS
    commit = "FIFO stand-in" if offline else registration()
    for run in schedule(slots):
        finished(run, claims, commit)
    dest.mkdir(parents=True, exist_ok=False)
    ids = operator_identifiers()
    for name in inventory(slots):
        data = (
            report(slots, offline=offline).encode()
            if name == "result.md"
            else file(ROOT, name).read_bytes()
        )
        safe_bytes(data, ids)
        target = dest / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)


def pack(path: Path, slots: list[Row], *, offline: bool = False) -> None:
    side = path.with_suffix(path.suffix + ".sha256")
    need(not path.exists() and not side.exists(), "pack destination exists")
    with tempfile.TemporaryDirectory(dir=path.parent) as tmp:
        tree = Path(tmp) / "tree"
        assemble(tree, slots, offline=offline)
        archive = Path(tmp) / "output.zip"
        with zipfile.ZipFile(archive, "x", zipfile.ZIP_DEFLATED) as z:
            for n in inventory(slots):
                z.write(tree / n, n)
        with archive.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        os.link(archive, path)
        with side.open("x") as f:
            f.write(f"{digest}  {path.name}\n")
