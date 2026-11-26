"""Prepare, claim, run and publish the registered Board-0 schedule."""

from __future__ import annotations

import argparse
import json
import os
import secrets
import shutil
import subprocess
import sys
import tempfile
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
    dump,
    lines,
    models,
    need,
    pin_name,
    read,
    registry,
    schedule,
    sha,
    write,
)
from inputs import descriptors, digests, file, outputs, sources
from worlds import collisions, rows


def replace_bytes(path: Path, data: bytes) -> None:
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        tmp = Path(stream.name)
        try:
            stream.write(data)
            stream.flush()
            os.replace(tmp, path)
        finally:
            tmp.unlink(missing_ok=True)


def prepare_descriptors(slots: list[Row], doc: Row, *, offline: bool) -> list[str]:
    names = descriptors(slots)
    note = ROOT / NOTE
    claims = ROOT / ".offline-claims" if offline else admission.CLAIMS
    if (
        any(m.get("vacant") or m["pin"] != pin_name(m["slot"]) for m in slots)
        or (claims / pin_name("M1") / "finished.json").exists()
    ):
        need(note.is_file(), "missing frozen descriptor list")
        need(slots == admission.final_slots(slots, claims), "prepare requires final roster")
    frozen = {}
    if note.exists():
        for line in file(ROOT, NOTE).read_text().splitlines():
            digest, name = line.split("  ", 1)
            need(name not in frozen, "duplicate frozen descriptor")
            frozen[name] = digest
        need(set(frozen) == set(names), "descriptor inventory differs")
    models_by_slot = {m["slot"]: m for m in slots}
    pending: dict[Path, bytes] = {}
    for name in names:
        path = ROOT / name
        need(path.resolve() == path, f"linked descriptor {name}")
        task_id = path.parent.name if name.startswith("clean/") else None
        run = path.parents[1].name if task_id else path.parent.name
        model = models_by_slot[run.split("-")[2]]
        desired = dump(descriptor(doc, model, run, offline=offline, task_id=task_id))
        existing = file(ROOT, name).read_bytes() if frozen or path.exists() else None
        if frozen and frozen[name] != sha(desired):
            need(
                not model.get("vacant") and model["pin"] != pin_name(model["slot"]),
                f"changed prepared descriptor {name}",
            )
            original, passed = admission.pin_record(claims, model["slot"])
            before = dump(descriptor(doc, original, run, offline=offline, task_id=task_id))
            need(
                not passed and sha(before) == frozen[name] and existing in (before, desired),
                f"changed prepared descriptor {name}",
            )
        else:
            need(existing is None or existing == desired, f"conflicting descriptor {name}")
        if existing != desired:
            pending[path] = desired
    # Check the entire board before replacing even the first descriptor.
    for path, data in pending.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        replace_bytes(path, data)
    return names


def prepare(slots: list[Row], *, offline: bool = False) -> None:
    sys.path.insert(0, str(ROOT / "tasks"))
    doc = import_module("make_tasks").build(ROOT)
    need(doc == read(ROOT / "tasks/tasks.json"), "tasks.json differs from regenerated board")
    findings: list[Row] = []
    index = rows()
    seen: dict[str, set[int]] = {}
    for name in prepare_descriptors(slots, doc, offline=offline):
        path = ROOT / name
        task_id = path.parent.name if name.startswith("clean/") else None
        run = path.parents[1].name if task_id else path.parent.name
        slot = run.split("-")[2]
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
    report = ROOT / "scenario-collisions.json"
    collision_report = {"count": len(findings), "collisions": findings}
    if report.exists() and report.read_bytes() != dump(collision_report):
        previous = read(file(ROOT, report.name))
        changed_runs = {
            f"board0-d{day}-{m['slot']}-E"
            for day in (1, 2)
            for m in slots
            if not m.get("vacant") and m["pin"] != pin_name(m["slot"])
        }
        need(
            changed_runs
            and previous["count"] == len(previous["collisions"])
            and [r for r in previous["collisions"] if r["run"] not in changed_runs]
            == [r for r in findings if r["run"] not in changed_runs],
            "changed collisions outside substituted measured suites",
        )
        replace_bytes(report, dump(collision_report))
    else:
        write(report, collision_report)
    if not (ROOT / NOTE).exists():
        (ROOT / NOTE).write_text(digests(descriptors(slots)))


def roster(*, offline: bool = False) -> list[Row]:
    path = ROOT / "models.json"
    claims = ROOT / ".offline-claims" if offline else admission.CLAIMS
    need(claims.is_dir(), "unfinished corrected pins")
    with suite_process.locked_file(claims / "suite.lock", 0):
        config = registry(path, offline=offline)
        final = admission.final_slots(config["slots"], claims)
        commit = read(file(claims, pin_name("M1") + "/claim.json"))["registration"]
        for run in schedule(final):
            if "-pin2-" in run and (claims / run).exists():
                admission.finished(run, claims, commit)
        for model in final:
            if model["pin"] != pin_name(model["slot"]):
                need(
                    any(model == s | {"slot": model["slot"]} for s in config["spares"]),
                    "substitute differs from registry",
                )
        data = dump(config | {"slots": final})
        if path.read_bytes() != data:
            replace_bytes(path, data)
        return final


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
    need(offline or today is None, "live clock override")
    with suite_process.locked_file(claims / "suite.lock", 0):
        config = registry(ROOT / "models.json", offline=offline)
        need(config["slots"] == slots, "registry changed")
        model = next(m for m in slots + config["spares"] if m["slot"] == run.split("-")[2])
        if "-pin2-" in run:
            need(model["pin"] == run and not model.get("vacant"), "pin requires original model")
        suite_process.clear(claims)
        day = today or date.today()
        commit = "FIFO stand-in" if offline else admission.registration()
        admission.order_guard(run, slots, claims, day)
        for prior in schedule(slots):
            if (claims / prior / "finished.json").is_file():
                admission.finished(prior, claims, commit, board="-pin2-" not in run)
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
        if "-pin2-" not in run:
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
                if "-pin2-" in run:
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
            except pin.PinFailed:
                write(
                    directory / "finished.json",
                    {"run": run, "ok": False, "files": digests(outputs(run))},
                )
                raise
            finally:
                suite_process.clear(claims, finishing=directory)
                os.environ.pop("BOARD0_TOKEN", None)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "verb",
        choices=(
            "list",
            "check",
            "digests",
            "descriptor-digests",
            "roster",
            "prepare",
            "real",
            "report",
            "assemble",
            "pack",
        ),
    )
    parser.add_argument("arg", nargs="?")
    args = parser.parse_args()
    need(bool(args.arg) == (args.verb in ("real", "assemble", "pack")), "wrong argument count")
    need(version("agent-reliability-ci") == "2.4.1", "released ARCI 2.4.1 required")
    slots = models(ROOT / "models.json")
    if args.verb == "list":
        print("\n".join(schedule(slots)))
    elif args.verb == "roster":
        print(json.dumps(roster(), indent=2))
    elif args.verb == "descriptor-digests":
        print(digests(descriptors(slots)), end="")
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
