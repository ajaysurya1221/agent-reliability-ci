"""Prepare, claim, run and publish the registered Board-0 schedule."""

from __future__ import annotations

import argparse
import json
import os
import secrets
import shutil
import subprocess
import sys
import time
from datetime import date
from importlib import import_module
from importlib.metadata import version
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import admission
import audit
import count_a
import count_b
import pin
import publication
import suite_process
from agent import atomic_json
from common import (
    NOTE,
    OLLAMA,
    REG,
    ROOT,
    Row,
    descriptor,
    lines,
    models,
    need,
    read,
    schedule,
    sha,
    write,
)
from inputs import descriptors, digests, outputs, sources
from worlds import collisions, rows


def prepare(slots: list[Row], *, offline: bool = False) -> None:
    sys.path.insert(0, str(ROOT / "tasks"))
    doc = import_module("make_tasks").build(ROOT)
    need(doc == read(ROOT / "tasks/tasks.json"), "tasks.json differs from regenerated board")
    findings: list[Row] = []
    index = rows()
    seen: dict[str, set[int]] = {}
    for name in descriptors(slots):
        path = ROOT / name
        task_id = path.parent.name if name.startswith("clean/") else None
        run = path.parents[1].name if task_id else path.parent.name
        slot = run.split("-")[2]
        model = next(m for m in slots if m["slot"] == slot)
        write(path, descriptor(doc, model, run, offline=offline, task_id=task_id))
        m = audit.compiled(path)
        specs = audit.specs(m, getattr(m, "max_rounds", 1))
        seeds = {s.seed for s in specs}
        for s in specs:
            if s.arm == "baseline":
                findings.extend(
                    {"run": run, "task": s.task_id, "seed": s.seed, **hit}
                    for hit in collisions(index[s.task_id], s.seed)
                )
        need(len(seeds) == (1 if task_id else 16 * m.max_rounds), "repeated scenario seed")
        prior = seen.setdefault(slot, set())
        need(prior.isdisjoint(seeds), "day or clean seeds overlap")
        prior.update(seeds)
    write(ROOT / "scenario-collisions.json", {"count": len(findings), "collisions": findings})
    note = digests(descriptors(slots))
    if (ROOT / NOTE).exists():
        need((ROOT / NOTE).read_text() == note, "changed prepared descriptor digest")
    else:
        (ROOT / NOTE).write_text(note)


def jsonl(path: Path, data: list[Row]) -> None:
    with path.open("x") as f:
        for row in data:
            f.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")


def trial_run(
    run: str, model: Row, directory: Path, *, offline: bool, task_id: str | None = None
) -> Row:
    start_ns = time.monotonic_ns()
    target = ROOT / "clean" / run / task_id if task_id else ROOT / "runs" / run
    part = directory / task_id if task_id else directory
    part.mkdir(exist_ok=True)
    m = audit.compiled(target / "descriptor.yaml")
    doc = read(ROOT / "tasks/tasks.json")
    need(
        read(target / "descriptor.yaml")
        == descriptor(doc, model, run, offline=offline, task_id=task_id),
        "descriptor assignment",
    )
    receipts = part / "receipts"
    stores = part / "stores"
    env = {**os.environ, "BOARD0_RECEIPTS": str(receipts)}
    if offline:
        admitted = OLLAMA
        argv = [
            sys.executable,
            "-PB",
            str(ROOT / "harness/fifo.py"),
            str(target / "descriptor.yaml"),
            str(stores),
        ]
    else:
        bindings = [
            admission.binding(s.task, s.arm, s.seed, s.variant, model["tag"], doc["system_prompt"])
            for s in audit.specs(m, getattr(m, "max_rounds", 1))
        ]
        write(part / "bindings.json", bindings)
        admitted = pin.metadata(run, model)["ollama"]
        argv = suite_process.command(
            directory,
            "run",
            ["run", "--workers", "1", "--out", str(stores), str(target / "descriptor.yaml")],
        )
    claim = read(directory / "claim.json")
    admission_record = {
        "run": run,
        "date": claim["date"],
        "claim_ns": claim["claim_ns"],
        "part_ns": start_ns,
        "ollama": admitted,
        "model_digest": model["digest"],
    }
    with (target / "run.log").open("xb") as log:
        log.write(json.dumps(admission_record).encode() + b"\n")
        log.flush()
        status = subprocess.run(
            argv,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            env=env,
            start_new_session=True,
        ).returncode
    store = stores / m.experiment_id
    for name in ("manifest.json", "trials.jsonl", "events.jsonl", "decision.json"):
        shutil.copyfile(store / name, target / name)
    need(status == read(target / "decision.json")["exit_code"], "runner exit code")
    obs, rr, ll, gate = audit.verify(target, receipts, model["tag"])
    with (target / "run.log").open("a") as log:
        log.write(gate)
    jsonl(target / "receipts.jsonl", rr)
    jsonl(target / "ledger.jsonl", ll)
    a = count_a.count(obs)
    b = count_b.count(target, rows(), model["tag"])
    write(target / "count_a.json", a)
    write(target / "count_b.json", b)
    audit.same(a, b, "independent counts")
    decision = read(target / "decision.json")
    if not task_id:
        audit.same(a["signs"], decision["history"][-1]["counts"], "released pair signs")
    if not offline:
        pin.metadata(run, model, loaded=True)
    end_ns = time.monotonic_ns()
    record = {
        "run": run,
        "verified_trials": len(obs),
        "started_local_date": claim["date"],
        "model_digest": model["digest"],
        "counts_agree": True,
        "transport": "FIFO stand-in" if offline else "native Ollama",
        "ollama": admitted,
        "claim_ns": start_ns,
        "export_ns": end_ns,
        "seconds": (end_ns - start_ns) / 1e9,
        "verdict": decision["verdict"],
        "stopping_round": decision.get("stopped_at_round"),
    }
    if task_id:
        write(target / "audit.json", record)
    if not task_id:
        print(
            f"{run} {decision['verdict']} · {len(obs)} trials · gate MATCH · counts agree",
            flush=True,
        )

    return record


def finish_exports(run: str, summary: Path, record: Row, claim_ns: int) -> str:
    name = summary.relative_to(ROOT).as_posix()
    files = outputs(run)
    need(name in files, "missing summary in output inventory")
    verified = digests([n for n in files if n != name])
    end_ns = time.monotonic_ns()
    write(
        summary,
        record | {"claim_ns": claim_ns, "export_ns": end_ns, "seconds": (end_ns - claim_ns) / 1e9},
    )
    return "".join(
        sorted(
            [*verified.splitlines(keepends=True), f"{sha(summary.read_bytes())}  {name}\n"],
            key=lambda line: line.split("  ", 1)[1],
        )
    )


def execute(
    run: str, slots: list[Row], *, offline: bool = False, today: date | None = None
) -> None:
    need(run in schedule(slots), "unknown RUN")
    claims = ROOT / ".offline-claims" if offline else admission.CLAIMS
    need(claims == claims.resolve(), "linked claims root")
    claims.mkdir(mode=0o700, parents=True, exist_ok=True)
    model = next(m for m in slots if m["slot"] in run.split("-"))
    need(offline or today is None, "live clock override")
    with suite_process.locked_file(claims / "suite.lock", 0):
        suite_process.clear(claims)
        day = today or date.today()
        commit = "FIFO stand-in" if offline else admission.registration()
        admission.order_guard(run, slots, claims, day)
        for prior in schedule(slots):
            if (claims / prior / "finished.json").is_file():
                admission.finished(prior, claims, commit)
        directory = claims / run
        claim_ns = time.monotonic_ns()
        directory.mkdir()
        token = secrets.token_hex(32)
        os.environ["BOARD0_TOKEN"] = token
        claim = {
            "run": run,
            "date": day.isoformat(),
            "claim_ns": claim_ns,
            "model": model,
            "registration": commit,
            "registration_sha256": sha((ROOT / REG).read_bytes()),
            "token_sha256": sha(token.encode()),
        }
        if "-pin-" not in run:
            names = [n for n in descriptors(slots) if run in Path(n).parts]
            claim["descriptors"] = {n: sha((ROOT / n).read_bytes()) for n in names}
        write(directory / "claim.json", claim)
        with suite_process.locked_file(directory / "claim.json", 0):
            atomic_json(
                claims / "active-suite.json",
                {"claim": run, "launcher": os.getpid(), "groups": []},
                create=True,
            )
            try:
                if "-pin-" in run:
                    pin.execute(run, model, ROOT / "pins" / (run + ".json"), offline=offline)
                    files = digests(outputs(run))
                elif run.endswith("-clean"):
                    trials = []
                    for tid in rows():
                        trial_run(run, model, directory, offline=offline, task_id=tid)
                        trials.extend(lines(ROOT / "clean" / run / tid / "trials.jsonl"))
                    result = publication.rating(trials, rows())
                    summary = ROOT / "clean" / (run + ".json")
                    result.update(run=run, started_local_date=day.isoformat())
                    files = finish_exports(run, summary, result, claim_ns)
                    print(f"{run} · {len(trials)} clean trials · counts agree", flush=True)
                else:
                    result = trial_run(run, model, directory, offline=offline)
                    files = finish_exports(
                        run, ROOT / "runs" / run / "audit.json", result, claim_ns
                    )
                write(
                    directory / "finished.json",
                    {"run": run, "ok": True, "files": files},
                )
            except Exception:
                if "-pin-" in run:
                    write(directory / "finished.json", {"run": run, "ok": False})
                raise
            finally:
                suite_process.clear(claims, finishing=directory)
                os.environ.pop("BOARD0_TOKEN", None)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "verb",
        choices=("list", "check", "digests", "prepare", "real", "report", "assemble", "pack"),
    )
    parser.add_argument("arg", nargs="?")
    args = parser.parse_args()
    need(bool(args.arg) == (args.verb in ("real", "assemble", "pack")), "wrong argument count")
    need(version("agent-reliability-ci") == "2.4.1", "released ARCI 2.4.1 required")
    slots = models(ROOT / "models.json")
    if args.verb == "list":
        print("\n".join(schedule(slots)))
    elif args.verb == "digests":
        print(digests(sources()), end="")
    elif args.verb == "prepare":
        prepare(slots)
        print(NOTE)
    elif args.verb == "check":
        print(admission.registration())
    elif args.verb == "real":
        execute(args.arg, slots)
    elif args.verb == "report":
        print(publication.report(slots), end="")
    elif args.verb == "assemble":
        publication.assemble(Path(args.arg).resolve(), slots)
    else:
        publication.pack(Path(args.arg).resolve(), slots)


if __name__ == "__main__":
    main()
