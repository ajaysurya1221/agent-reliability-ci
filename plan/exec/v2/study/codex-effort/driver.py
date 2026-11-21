"""One start, paired dispatch and round-end verdicts for the Codex effort comparison."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import queue
import re
import subprocess
import sys
import tempfile
import time
from collections import deque
from collections.abc import Sequence
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import asdict
from importlib.metadata import version
from pathlib import Path
from typing import Any, cast

from events import WORKTREES
from grade import AGENT_PYTHON, HERE, PYTHON, REPO, Ticket, blob, bounded, git, outside, tickets
from run_trial import Arm, Executable, Trial, executable_identity, run_trial, utc

from arci.outcomes import load_rule

RULE = HERE / "rule.yaml"
REGISTER = HERE.parent / "PREREGISTRATION-codex-effort.md"
DIGESTS = HERE / "digests.sha256"
PRIVATE_WORK = WORKTREES / "codex-effort-private"
SHARED_MARKER = PRIVATE_WORK.parent / "codex-effort.started"
MARKER = HERE / "codex-effort.started"
OUTPUT = HERE / "runs-codex-effort"
ARMS: tuple[Arm, Arm] = ("baseline", "candidate")
PREFLIGHT_SECONDS = 1800


def save(path: Path, data: object) -> None:
    with path.open("x") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def arm_order(ids: list[str], ticket: str, round_no: int) -> tuple[Arm, Arm]:
    # Randomize the first round of each two-round block; reverse the second.
    odd = round_no - (round_no % 2 == 0)
    ordered = sorted(
        ids, key=lambda name: (hashlib.sha256(f"{name}:{odd}".encode()).digest(), name)
    )
    base_first = ordered.index(ticket) < len(ids) // 2
    if round_no != odd:
        base_first = not base_first
    return ARMS if base_first else ("candidate", "baseline")


def published_tip() -> str:
    # Live start only: a local remote-tracking ref cannot attest to the present remote.
    ref = "refs/heads/v2/phase0"
    lines = git("ls-remote", "--exit-code", "origin", ref).decode().splitlines()
    if len(lines) != 1 or lines[0].split()[1] != ref:
        raise ValueError("origin did not return exactly the registered branch")
    return lines[0].split()[0]


def check_registration(tip: str) -> str:
    registration, manifest = REGISTER, DIGESTS
    if git("rev-parse", "HEAD").decode().strip() != tip:
        raise ValueError("checkout HEAD differs from origin v2/phase0")
    required = {
        p
        for pattern in (
            "*.py",
            "tests/*.py",
            "hidden/*.inc",
            "tickets/*.json",
            "rule.yaml",
            "README.md",
        )
        for p in HERE.glob(pattern)
    }
    lines = manifest.read_text().splitlines()
    seen: set[Path] = set()
    for line in lines:
        match = re.fullmatch(r"([0-9a-f]{64})  ([\w./-]+)", line)
        if match is None:
            raise ValueError("malformed digest entry")
        path = HERE.parent / match[2]
        if path not in required or path in seen or path.resolve() != path:
            raise ValueError(f"unexpected digest path: {match[2]}")
        if hashlib.sha256(path.read_bytes()).hexdigest() != match[1]:
            raise ValueError(f"digest mismatch: {match[2]}")
        seen.add(path)
    if seen != required:
        raise ValueError("registered digest list is incomplete")
    for path in (*seen, registration, manifest):
        rel = str(path.relative_to(REPO))
        if path.is_symlink() or blob(tip, rel) != path.read_bytes():
            raise ValueError(f"published bytes differ: {rel}")
        mode = git("ls-tree", tip, "--", rel).split()[0]
        if mode != (b"100755" if path.stat().st_mode & 0o111 else b"100644"):
            raise ValueError(f"published mode differs: {rel}")
    digest = hashlib.sha256(manifest.read_bytes()).hexdigest()
    text = registration.read_text()
    if re.search(r"\[\[[^\]]+\]\]", text) or digest not in text:
        raise ValueError("registration needs completed fields and the digest-list SHA-256")
    return digest


def append_trial(out: Path, trial: Trial, sequence: int) -> None:
    with (out / "trials.jsonl").open("a") as f:
        f.write(json.dumps({"sequence": sequence, **asdict(trial)}, sort_keys=True) + "\n")
        f.flush()
        os.fsync(f.fileno())


def append_round(out: Path, rows: list[Trial], ids: list[str], round_no: int) -> None:
    if len(rows) != 2 * len(ids) or {(t.ticket, t.arm, t.round) for t in rows} != {
        (name, arm, round_no) for name in ids for arm in ARMS
    }:
        raise ValueError("incomplete or duplicate pair at round end")
    for arm in ARMS:
        path = out / f"{arm}.csv"
        with path.open("a", newline="") as f:
            writer = csv.writer(f, lineterminator="\n")
            if f.tell() == 0:
                writer.writerow(("task_id", "round", "outcome"))
            for t in sorted((t for t in rows if t.arm == arm), key=lambda t: t.ticket):
                writer.writerow((t.ticket, t.round, t.outcome))
            f.flush()
            os.fsync(f.fileno())


def verdict(out: Path, round_no: int, *, replay: bool = False) -> str:
    name = f"round-{round_no:02d}" + ("-replay" if replay else "")
    cmd = [
        str(PYTHON),
        "-I",
        "-B",
        "-m",
        "arci",
        "verdict",
        str(RULE),
        "--baseline",
        "baseline.csv",
        "--candidate",
        "candidate.csv",
        "--json",
        name + ".json",
    ]
    if round_no > 1:
        cmd += ["--previous", f"round-{round_no - 1:02d}.json"]
    proc = bounded(cmd, out, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
    (out / (name + ".log")).write_bytes(proc.stdout + proc.stderr)
    decision = json.loads((out / (name + ".json")).read_bytes())
    value = str(decision["verdict"])
    if proc.returncode != {"PASS": 0, "BLOCK": 1, "INCONCLUSIVE": 2, "ERROR": 3}[value]:
        raise RuntimeError("ARCI decision disagrees with its exit code")
    if value != "ERROR" and decision["last_round_evaluated"] != round_no:
        raise RuntimeError("ARCI evaluated an unexpected round")
    return value


def audit(out: Path, rounds: int, items: list[Ticket], work: Path) -> dict[str, Any]:
    prompts = {t["id"]: hashlib.sha256(t["task"].encode()).hexdigest() for t in items}
    ids = list(prompts)
    next_order: dict[tuple[int, str], int] = {}
    rows_file = out / "trials.jsonl"
    records = (
        [json.loads(s) for s in rows_file.read_text().splitlines()] if rows_file.exists() else []
    )

    def counters() -> dict[str, int]:
        return dict.fromkeys(
            (
                "clean",
                "outside_read",
                "unauditable",
                "denied_attempts",
                "time_limits",
                "deadline_misses",
                "unattributed",
                "pass",
                "fail",
                "error",
            ),
            0,
        )

    by_arm = {arm: counters() for arm in ARMS}
    by_ticket = {ticket: {arm: counters() for arm in ARMS} for ticket in ids}
    affected: set[tuple[int, str]] = set()
    started = {p.parent.name for p in out.glob("r*-*/start.json")}
    finished = {f"r{r['round']:02d}-{r['ticket']}-{r['arm']}" for r in records}
    if started != finished or len(finished) != len(records):
        raise ValueError("every started trial must have exactly one result")
    for seq, row in enumerate(records, 1):
        key = f"r{row['round']:02d}-{row['ticket']}-{row['arm']}"
        receipt = json.loads((out / key / "start.json").read_bytes())
        pair = (row["round"], row["ticket"])
        evidence = row["audit"]
        status = evidence["status"]
        transcript = work / (key + ".transcript")
        actual_digest = None
        if transcript.exists():
            with transcript.open("rb") as stream:
                actual_digest = hashlib.file_digest(stream, "sha256").hexdigest()
        if actual_digest != evidence["sha256"] or (not actual_digest and status != "unauditable"):
            raise ValueError("transcript digest mismatch")
        if status != "clean":
            affected.add(pair)
        for group in (by_arm[row["arm"]], by_ticket[pair[1]][row["arm"]]):
            group[status] += 1
            group[row["outcome"]] += 1
            group["denied_attempts"] += len(evidence["denied_events"])
            group["time_limits"] += int(row["hit_time_limit"])
            group["deadline_misses"] += int(row["service_marker"] == "deadline")
            group["unattributed"] += int(row["service_marker"] == "unattributed")
        position = next_order.get(pair, 1)
        if (
            position > 2
            or row["order"] != position
            or row["arm"] != arm_order(ids, pair[1], pair[0])[position - 1]
            or receipt["task_sha256"] != prompts[pair[1]]
        ):
            raise ValueError("task or arm order differs from the registration")
        next_order[pair] = position + 1
        if any(receipt[k] != row[k] for k in ("ticket", "round", "arm", "order", "start_time")):
            raise ValueError("trial identity differs from its start receipt")
        detail = json.loads((out / key / "grade.json").read_bytes())
        if row != {"sequence": seq, **detail}:
            raise ValueError("per-trial and campaign records disagree")
        patch = out / key / "change.patch"
        if row["diff_sha256"] != (
            hashlib.sha256(patch.read_bytes()).hexdigest() if patch.exists() else None
        ):
            raise ValueError("diff digest mismatch")
    summary = {
        "by_arm": by_arm,
        "by_ticket_and_arm": by_ticket,
        "affected_pairs": len(affected),
        "affected_pair_ids": sorted(affected),
        "eligible": not affected and not any(c["unattributed"] for c in by_arm.values()),
    }
    if rounds == 0:
        return summary
    for arm in ARMS:
        expected = {
            (r["round"], r["ticket"]): r["outcome"]
            for r in records
            if r["round"] <= rounds and r["arm"] == arm
        }
        with (out / f"{arm}.csv").open(newline="") as f:
            rows = list(csv.DictReader(f))
        actual = {(int(r["round"]), r["task_id"]): r["outcome"] for r in rows}
        if actual != expected or len(rows) != len(actual) or len(actual) != rounds * len(ids):
            raise ValueError("CSV does not match trial records")
    if (out / f"round-{rounds:02d}.json").read_bytes() != (
        out / f"round-{rounds:02d}-replay.json"
    ).read_bytes():
        raise ValueError("recomputed ARCI decision differs")
    return summary


def campaign(
    items: list[Ticket],
    work: Path,
    out: Path,
    workers: int,
    *,
    wall_seconds: float = 8 * 3600,
    executable: Executable | None = None,
) -> dict[str, Any]:
    """Workers return one arm at a time. Only this coordinator admits arms and writes rows."""
    rule = load_rule(RULE)
    ids = [t["id"] for t in items]
    if sorted(ids) != list(rule.tasks) or workers < 1 or workers > 4:
        raise ValueError("ticket list or worker count differs from registration")
    deadline = time.monotonic() + wall_seconds
    schedule = [
        {name: arm_order(ids, name, r) for name in ids} for r in range(1, rule.max_rounds + 1)
    ]
    save(out / "schedule.json", schedule)
    counts = {arm: {"pass": 0, "fail": 0, "error": 0} for arm in ARMS}
    timing = {
        arm: {"under_120": 0, "120_to_under_300": 0, "300_to_under_1200": 0, "1200_or_more": 0}
        for arm in ARMS
    }
    sequence = streak = complete = 0
    errors: set[tuple[int, str]] = set()
    decision, reason = "INCONCLUSIVE", ""
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for r, orders in enumerate(schedule, 1):
            ready = deque((t, 1) for t in items)
            finished: queue.Queue[Future[Trial]] = queue.Queue()
            pending: dict[Future[Trial], tuple[Ticket, int]] = {}
            rows: list[Trial] = []
            while pending or (ready and not reason):
                if time.monotonic() >= deadline and not reason:
                    reason = "eight-hour admission limit"
                while ready and not reason and len(pending) < workers and finished.empty():
                    t, position = ready.popleft()
                    future = pool.submit(
                        run_trial,
                        t,
                        orders[t["id"]][position - 1],
                        r,
                        position,
                        work,
                        out,
                        expected_executable=executable,
                    )
                    pending[future] = (t, position)
                    future.add_done_callback(finished.put)
                if not pending:
                    break
                future = finished.get()
                t, position = pending.pop(future)
                row = future.result()
                rows.append(row)
                sequence += 1
                append_trial(out, row, sequence)
                counts[row.arm][row.outcome] += 1
                band = next(
                    (
                        name
                        for threshold, name in (
                            (120, "under_120"),
                            (300, "120_to_under_300"),
                            (1200, "300_to_under_1200"),
                        )
                        if row.seconds < threshold
                    ),
                    "1200_or_more",
                )
                timing[row.arm][band] += 1
                if row.outcome == "error":
                    errors.add((r, t["id"]))
                    streak += 1
                else:
                    streak = 0
                if streak >= 3 and decision != "ERROR":
                    reason, decision = "three consecutive trial errors", "ERROR"
                elif len(errors) > rule.max_errored_pairs and decision != "ERROR":
                    reason, decision = "errored-pair tolerance exceeded", "ERROR"
                if position == 1:
                    ready.appendleft((t, 2))
            if len(rows) == 2 * len(ids):
                append_round(out, rows, ids, r)
                complete = r
                result = verdict(out, r)
                if decision != "ERROR":
                    decision = result
                if result != "INCONCLUSIVE" and not reason:
                    reason = "ARCI round-end " + result
            if reason:
                break
    if complete:
        verdict(out, complete, replay=True)
    checks = audit(out, complete, items, work)
    summary = {
        "status": decision,
        "audit": checks,
        "crossing_eligible_for_review": decision in {"PASS", "BLOCK"} and checks["eligible"],
        "reason": reason or "registered round cap",
        "complete_rounds": complete,
        "trials": sequence,
        "outcomes_by_arm": counts,
        "elapsed_seconds_counts_by_arm": timing,
        "errored_pairs": len(errors),
        "partial_round_trials": sequence - 2 * len(ids) * complete,
        "ended": utc(),
    }
    save(out / "stop.json", summary)
    return summary


def standin_checks(work: Path) -> bytes:
    with tempfile.TemporaryDirectory(dir=work) as tmp:
        env = dict(
            os.environ,
            PYTHONDONTWRITEBYTECODE="1",
            PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
            PYTEST_ADDOPTS="",
            RUN5_CHECK_CONFINEMENT="1",
        )
        cmd = [
            str(PYTHON),
            "-m",
            "pytest",
            "-o",
            "addopts=",
            "-q",
            "-p",
            "no:cacheprovider",
            "--basetemp",
            str(Path(tmp) / "pytest"),
            str(HERE / "tests"),
        ]
        proof = bounded(cmd, HERE, env=env, seconds=PREFLIGHT_SECONDS)
        if proof.returncode:
            raise RuntimeError(
                "stand-in checks failed: " + proof.stdout.decode(errors="replace")[-1500:]
            )
        return proof.stdout + proof.stderr


def live(work_root: Path, workers: int, *, check_only: bool = False) -> None:
    try:
        _live(work_root, workers, check_only=check_only)
    except subprocess.TimeoutExpired as exc:
        print(f"ERROR: infrastructure timeout: {exc}", file=sys.stderr)
        raise SystemExit(3) from exc


def _live(work_root: Path, workers: int, *, check_only: bool) -> None:
    if not 1 <= workers <= 4:
        raise ValueError("choose one through four pairs")
    if any(os.path.lexists(p) for p in (SHARED_MARKER, MARKER, OUTPUT)) or not REGISTER.is_file():
        raise ValueError("prior start/output or missing final registration")
    if work_root.resolve() != PRIVATE_WORK or PRIVATE_WORK.resolve() != PRIVATE_WORK:
        raise ValueError(f"use the fixed campaign work root {PRIVATE_WORK}")
    work = outside(PRIVATE_WORK)
    if work.stat().st_mode & 0o077:
        raise ValueError("private work root requires mode 0700")
    tip = published_tip()
    digest = check_registration(tip)
    if version("agent-reliability-ci") != "2.4.1" or sys.executable != str(PYTHON):
        raise ValueError("use the registered Python environment with ARCI 2.4.1")
    if any(work.iterdir()):
        raise ValueError("supply a fresh, empty work root")
    proof = standin_checks(work)
    if published_tip() != tip or check_registration(tip) != digest:
        raise ValueError("published inputs changed during preflight")
    if any(os.path.lexists(p) for p in (SHARED_MARKER, MARKER, OUTPUT)) or any(work.iterdir()):
        raise ValueError("prior start/output or occupied private work root")
    if check_only:
        print(f"Start check passed for {tip}, digest list {digest}")
        return
    SHARED_MARKER.mkdir(mode=0o700)  # Atomic across every checkout and concurrent start.
    MARKER.mkdir()
    OUTPUT.mkdir()
    (OUTPUT / "preflight.log").write_bytes(proof)
    try:
        executable = executable_identity(dict(os.environ))
        os.environ["CODEX_BIN"] = executable.launcher
        info = bounded([executable.launcher, "--version"], HERE, seconds=30)
        info.check_returncode()
        save(
            OUTPUT / "start.json",
            {
                "start": utc(),
                "published": tip,
                "digest_list": digest,
                "codex": info.stdout.decode().strip(),
                "model": "gpt-6.2-astra",
                "agent_and_grading_python": str(AGENT_PYTHON),
                "shared_marker": str(SHARED_MARKER),
                **asdict(executable),
                "python": sys.version,
                "arci": version("agent-reliability-ci"),
                "workers": workers,
            },
        )
        result = campaign(tickets(), work, OUTPUT, workers, executable=executable)
    except BaseException as exc:
        if not (OUTPUT / "stop.json").exists():
            save(
                OUTPUT / "stop.json",
                {
                    "status": "ERROR",
                    "reason": f"campaign interrupted: {type(exc).__name__}: {exc}",
                    "ended": utc(),
                },
            )
        raise
    print(json.dumps(result))
    if result["status"] in ("PASS", "BLOCK") and not result["crossing_eligible_for_review"]:
        raise SystemExit(3)
    raise SystemExit({"PASS": 0, "BLOCK": 1, "INCONCLUSIVE": 2, "ERROR": 3}[result["status"]])


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-root", default=PRIVATE_WORK, type=Path)
    parser.add_argument("--check-start", action="store_true")
    parser.add_argument("--workers", type=int, default=4, choices=range(1, 5))
    args = parser.parse_args(argv)
    # caffeinate owns the assertion for the entire guarded process, including its preflight.
    script = (
        "from driver import live; from pathlib import Path; import sys; "
        "live(Path(sys.argv[1]), int(sys.argv[2]), check_only=sys.argv[3] == 'check')"
    )
    work = cast(Path, args.work_root).resolve()
    os.chdir(HERE)
    os.execv(
        "/usr/bin/caffeinate",
        [
            "caffeinate",
            "-dims",
            str(PYTHON),
            "-B",
            "-c",
            script,
            str(work),
            str(args.workers),
            "check" if args.check_start else "start",
        ],
    )


if __name__ == "__main__":
    main()
