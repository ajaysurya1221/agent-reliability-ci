"""Admit one registered suite, seal its execution inputs and retain the evidence."""

import argparse
import os
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

import count_a
import count_b
from check_evidence import check_run, finish_record, validated_round
from claims import HOST, calendar, claims_dir, locks, prior_claims, schedule
from descriptors import RUNS, SLOTS, Row, encoded, models, read
from freeze import prepare, published, sha, sources, verify, versions
from identity import inspect_model, validate
from preflight import latest_pin, preflight, validate_pin
from records import atomic_json, require, rows

ROOT = Path(__file__).resolve().parent


def timestamp(day: date | None) -> datetime:
    stamp = datetime.now().astimezone()
    return stamp if day is None else stamp.replace(year=day.year, month=day.month, day=day.day)


def guard(claims: Path, run: str, order: tuple[str, ...], start: Row) -> None:
    require(run in order, "unknown run")
    present = prior_claims(claims, order)
    require(run not in present, "permanent claim exists")
    require(order.index(run) == len(present), "unfinished predecessor")
    previous = []
    for r in present:
        directory = claims / r
        require((directory / "finished.json").is_file(), "unfinished predecessor")
        prev = read(directory / "started.json")
        for field in ("mode", "registration", "inputs_sha256", "descriptors_sha256"):
            require(prev[field] == start[field], f"previous {field} differs")
        require(
            read(directory / "finished.json") == finish_record(directory),
            "previous evidence changed",
        )
        previous.append(prev)
    calendar([*previous, start])


def snapshot(root: Path, target: Path, run: str, env: dict[str, str]) -> None:
    inputs = read(root / "prepared/inputs.json")
    pins = read(root / "prepared/descriptors.json")[run + ".yaml"]
    inventory = {
        name: value
        for name, value in inputs.items()
        if name.startswith("agent/") or name in ("execution.py", "processes.py", "records.py")
    }
    inventory.update(
        {
            f"prepared/{run}.yaml": pins["sha256"],
            f"prepared/{run}.assignments.json": pins["assignments"],
        }
    )
    for name, expected in inventory.items():
        data = (root / name).read_bytes()
        require(sha(data) == expected, "snapshot changed during admission")
        path = target / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        path.chmod(0o444)
    # Mirror the released ARCI parent's -I path construction and its worker's -P.
    argv = [
        sys.executable,
        "-IB",
        "-c",
        "from arci.runner import child_pythonpath;print(child_pythonpath())",
    ]
    folder = target / "agent"
    path = subprocess.check_output(
        argv, cwd=folder, env=env, stdin=subprocess.DEVNULL, text=True
    ).strip()
    script = """import agent, tools, check, sys
from pathlib import Path
for module in (agent, tools, check):
    if Path(module.__file__).resolve() != Path.cwd()/(module.__name__+'.py'):
        sys.exit('unexpected worker import: '+module.__name__)
"""
    subprocess.run(
        [sys.executable, "-PB", "-c", script],
        cwd=folder,
        env=env | {"PYTHONPATH": path},
        stdin=subprocess.DEVNULL,
        check=True,
    )
    for directory in (folder, target / "prepared"):
        directory.chmod(0o555)


def run_suite(
    root: Path, run: str, *, rehearsal_day: date | None = None, native: bool = False
) -> None:
    rehearsal = rehearsal_day is not None
    mode = "rehearsal" if rehearsal else "real"
    claims = claims_dir()
    require(run in schedule(rehearsal), "unknown run")
    if rehearsal:
        require(claims != HOST and (root / ".offline").is_file(), "isolated rehearsal required")
    else:
        require(root == ROOT and claims == HOST, "real requires canonical claims and checkout")
    versions()
    with locks(claims, real=not rehearsal) as fds:
        commit = "rehearsal" if rehearsal else published(root)
        verify(root)
        slot, kind = run.split("-")[2:]
        model = models(root)[slot]
        base = {
            "mode": mode,
            "registration": commit,
            "run": run,
            "model": model,
            "inputs_sha256": sha((root / "prepared/inputs.json").read_bytes()),
            "descriptors_sha256": sha((root / "prepared/descriptors.json").read_bytes()),
        }

        def start_record() -> Row:
            stamp = timestamp(rehearsal_day)
            return base | dict(
                started_at=stamp.isoformat(), timezone=stamp.strftime("%z"), date=str(stamp.date())
            )

        guard(claims, run, schedule(rehearsal), start_record())
        synthetic = rehearsal and not native
        before = inspect_model(root, model, synthetic)
        validate(root, model, before)
        pin = latest_pin(claims, slot, commit)
        require(
            validate_pin(root, model, pin, mode, commit) == before,
            "identity differs from preflight",
        )
        work = claims / run
        env = {
            "PATH": os.defpath,
            "LANGSMITH_TRACING": "false",
            "LANGCHAIN_TRACING_V2": "false",
            "PYTHONDONTWRITEBYTECODE": "1",
            "OLLAMA_HOST": "http://127.0.0.1:11434",
            "NO_PROXY": "*",
            "SIZE0_RUN": run,
            "SIZE0_TAG": model["tag"],
            "SIZE0_CONDITION": kind,
            "SIZE0_TRANSPORT": "offline" if synthetic else "live",
            "SIZE0_ASSIGNMENTS": str(work / "snapshot/prepared" / (run + ".assignments.json")),
            "ORDER_DESK_EMPTY_TEXT_AUDIT": str(work / "replacement.jsonl"),
            "ORDER_DESK_FIRST_EXCHANGE_AUDIT": str(work / "receipts"),
            "SIZE0_LOCKS": ",".join(map(str, fds)),
        }
        with TemporaryDirectory(dir=claims) as tmp:
            stage = Path(tmp) / "snapshot"
            snapshot(root, stage, run, env)
            start = start_record()
            guard(claims, run, schedule(rehearsal), start)
            fresh = start_record()
            require(
                (fresh["date"], fresh["timezone"]) == (start["date"], start["timezone"]),
                "local date changed during admission",
            )
            work.mkdir()
            atomic_json(work / "started.json", fresh | {"identity": before})
            stage.rename(work / "snapshot")
            (work / "snapshot").chmod(0o555)
        atomic_json(work / "preflight.json", pin)
        (work / "receipts").mkdir()
        (work / "replacement.jsonl").touch(exist_ok=False)
        code = subprocess.call(
            [
                sys.executable,
                "-IB",
                str(work / "snapshot/execution.py"),
                str(work),
                "run",
                str(work / "snapshot/prepared" / (run + ".yaml")),
                "--out",
                str(work / "store"),
                "--workers",
                "4" if synthetic else "1",
            ],
            cwd=work / "snapshot/agent",
            env=env,
            stdin=subprocess.DEVNULL,
            pass_fds=fds,
            start_new_session=True,
        )
        execution = read(work / "execution.json")
        require(
            execution.get("status") != "interrupted, worker survived",
            "interrupted, worker survived",
        )
        try:
            after = inspect_model(root, model, synthetic)
            atomic_json(work / "identity-after.json", after)
            require(after == before, "identity changed")
        except (OSError, ValueError, KeyError) as exc:
            atomic_json(work / "refused.json", {"reason": "identity changed", "detail": str(exc)})
            raise
        stores = list(work.glob("store/*/decision.json"))
        require(len(stores) == 1, f"interrupted: no unique decision (exit {code})")
        store = stores[0].parent
        decision = read(stores[0])
        require(code == decision["exit_code"], "interrupted: runner exit differs")
        validated_round(
            rows(store / "trials.jsonl"), read(Path(env["SIZE0_ASSIGNMENTS"])), decision
        )
        try:
            with (work / "exchanges.jsonl").open("xb") as stream:
                for receipt in sorted((work / "receipts").glob("*.json")):
                    stream.write(receipt.read_bytes() + b"\n")
            a = count_a.count(store, work / "replacement.jsonl")
            require(a == count_b.count(store, work / "replacement.jsonl"), "counter disagreement")
            atomic_json(work / "counts.json", a)
            result = check_run(root, work, mode, Path(sys.executable))
        except (ValueError, OSError, KeyError, TypeError) as exc:
            atomic_json(work / "refused.json", {"reason": str(exc)})
            raise
        atomic_json(work / "finished.json", finish_record(work))
        print(f"{run}  {result['counts']['pooled']['trials']} trials", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "verb",
        choices=["prepare", "check", "digests", "list", "real", "report", "preflight", "rehearse"],
    )
    parser.add_argument("name", nargs="?")
    parser.add_argument("--rehearsal", action="store_true")
    args = parser.parse_args()
    require(
        bool(args.name) == (args.verb in ("real", "rehearse", "preflight")),
        "unexpected argument count",
    )
    require(args.verb != "real" or not args.rehearsal, "use rehearse for rehearsal mode")
    require(args.verb != "rehearse" or args.rehearsal, "rehearsal flag required")
    root = (
        Path(os.environ.get("SIZE0_REHEARSAL_ROOT", str(ROOT))).resolve()
        if args.rehearsal
        else ROOT
    )
    if args.rehearsal:
        require(
            (root / ".offline").is_file() and claims_dir() != HOST, "isolated rehearsal required"
        )
    if args.verb == "list":
        print("\n".join(RUNS))
        for day in ("d1", "d2"):
            remaining = sum(
                day == r.split("-")[1] and not (claims_dir() / r).exists() for r in RUNS
            )
            # The last suite may finish after midnight. This is a budget estimate,
            # with no allowance for loading, setup, IO or time between starts.
            hours = max(0, remaining - 1) * 160 * (120 + 20) / 3600
            print(
                f"{day}: {remaining} starts remaining; serial budget estimate before last start "
                f"{hours:.1f} h plus setup (160 trials/suite, 120+20 s/trial); "
                "fit starts before local midnight."
            )
    elif args.verb == "digests":
        print(encoded(sources(root)).decode(), end="")
    elif args.verb == "prepare":
        versions()
        prepare(root)
    elif args.verb == "check":
        versions()
        published(root)
        verify(root)
        print("registered inputs and descriptors match")
    elif args.verb == "preflight":
        require(args.name in SLOTS, "unknown slot")
        with locks(claims_dir(), real=not args.rehearsal):
            versions()
            commit = "rehearsal" if args.rehearsal else published(root)
            verify(root)
            preflight(
                root,
                claims_dir(),
                models(root)[args.name],
                "rehearsal" if args.rehearsal else "real",
                commit,
            )
    elif args.verb in ("real", "rehearse"):
        day = date.fromisoformat(os.environ["SIZE0_DATE"]) if args.rehearsal else None
        run_suite(root, args.name, rehearsal_day=day, native=True)
    else:
        from report import report

        print(report(root, rehearsal=args.rehearsal, python=Path(sys.executable)))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError, subprocess.SubprocessError) as exc:
        sys.exit(str(exc))
