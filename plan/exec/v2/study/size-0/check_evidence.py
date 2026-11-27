"""Replay gates and independently verify assignments, receipts, counts and claims."""

import argparse
import hashlib
import ipaddress
import json
import subprocess
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

from claims import calendar, claims_dir, prior_claims, schedule
from descriptors import RUNS, Row, models, read
from identity import validate
from preflight import validate_pin
from records import require, require_receipt_intact, rows

PYTHON = Path(__file__).resolve().parents[6] / ".arci-worktrees/run4-env/bin/python"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def finish_record(work: Path) -> Row:
    names = [
        "started.json",
        "identity-after.json",
        "preflight.json",
        "execution.json",
        "arci.log",
        "counts.json",
        "exchanges.jsonl",
        "replacement.jsonl",
    ]
    (store,) = (work / "store").iterdir()
    files = [work / n for n in names] + [
        store / n for n in ("manifest.json", "decision.json", "trials.jsonl", "events.jsonl")
    ]
    files.extend(
        p
        for folder in ("receipts", "snapshot")
        for p in sorted((work / folder).rglob("*"))
        if p.is_file()
    )
    return {
        "run": work.name,
        "mode": read(work / "started.json")["mode"],
        "files": {str(p.relative_to(work)): digest(p) for p in files},
    }


def observation(t: Row, order: str, completed: bool) -> dict[str, int]:
    require_receipt_intact(t)
    events = [
        (e["kind"], e["payload"])
        for e in t["events"]
        if e["kind"] in ("tool_start", "tool_finish", "model_step")
    ]
    injected = [
        (i, p)
        for i, (k, p) in enumerate(events)
        if k == "tool_finish" and p["injected_by"] is not None
    ]
    clean = t["condition_id"] == "clean"
    require(len(injected) == int(not clean), "unexpected injection ledger")
    recorded = [r for r in t["recording"] if r["result"]["injected_by"] is not None]
    no_worker_result = (
        not t["recording"] and t["final_state"] is None and t["termination"] != "completed"
    )
    if not no_worker_result:
        require(len(recorded) == len(injected), "recorded injection ledger differs")
    if recorded:
        rec = recorded[0]
        require(
            rec["tool"] == "lookup_order"
            and rec["occurrence"] == 0
            and all(
                rec["result"][k] == injected[0][1][k]
                for k in ("tool", "call_id", "injected_by", "ok", "value")
            ),
            "recorded injection differs",
        )
    delivered = False
    retry = right = False
    if injected:
        i, p = injected[0]
        require(
            p["tool"] == "lookup_order"
            and p["injected_by"] == "empty_result"
            and p["value"] is None
            and p["ok"] is True
            and any(
                k == "tool_start"
                and s["call_id"] == p["call_id"]
                and s["tool"] == "lookup_order"
                and s["occurrence"] == 0
                and s["arguments"] == {"order_id": order}
                for k, s in events[:i]
            ),
            "wrong injection",
        )
        delivered = True
        handed = False
        for kind, item in events[i + 1 :]:
            if kind == "model_step":
                handed = True
            if handed and kind == "tool_start" and item["tool"] == "lookup_order":
                retry = True
                right |= item["arguments"].get("order_id") == order
    opening = handoff = False
    if [k for k, _ in events[:4]] == ["tool_start", "tool_finish"] * 2:
        a, b, c, d = [p for _, p in events[:4]]
        opening = (
            a["tool"] == b["tool"] == "check_stock"
            and a["occurrence"] == 0
            and a["arguments"] == {"sku": order}
            and a["call_id"] == b["call_id"]
            and b["injected_by"] is None
            and b["ok"] is False
            and b["error_kind"] == "error"
            and bool(t["recording"])
            and t["recording"][0]["result"]["error_detail"] == "ValueError: unknown SKU"
            and c["tool"] == d["tool"] == "lookup_order"
            and c["occurrence"] == 0
            and c["arguments"] == {"order_id": order}
            and c["call_id"] == d["call_id"]
        )
        handoff = (
            opening
            and len(events) > 4
            and events[4][0] == "model_step"
            and d["ok"] is True
            and (isinstance(d["value"], dict) if clean else injected[0][0] == 3)
        )
    grade = t["contract"]
    passed = grade is not None and grade["grader_error"] is None and grade["success"] is True
    require(not passed or t["final_state"] is not None, "passing grade lacks final state")
    if (
        t["final_state"] is not None
        and t["termination"] == "completed"
        and grade is not None
        and grade["grader_error"] is None
    ):
        state = t["final_state"].get("state")
        correct = (
            isinstance(state, dict)
            and state.get("order_id") == order
            and isinstance(state.get("order"), dict)
            and state["order"].get("refunded_cents") == 0
            and state["order"].get("notes") == [f"stock: {state.get('stock')}"]
        )
        require(correct == passed, "final-state snapshot differs from grade")
    exposed = delivered and completed
    return dict(
        trials=1,
        passed=int(t["outcome"] == "PASS"),
        final_state_passes=int(passed),
        errored=int(t["outcome"] == "ERROR"),
        delivered=int(delivered),
        exposed=int(exposed),
        unexposed=int(delivered and not completed),
        read_again=int(exposed and retry),
        read_again_right_id=int(exposed and right),
        boundary_read_again=int(retry),
        boundary_read_again_right_id=int(right),
        passes_read_again=int(passed and exposed and retry),
        passes_no_read_again=int(passed and exposed and not retry),
        passes_unexposed=int(passed and delivered and not completed),
        scripted_opening_recorded=int(opening),
        model_step_after_opening=int(handoff),
    )


def validated_round(trials: list[Row], assignments: list[Row], decision: Row) -> int:
    n = len(trials)
    require(0 < n <= 160 and n % 16 == 0, "interrupted: incomplete rounds")
    for t, a in zip(trials, assignments[:n], strict=True):
        require(
            all(t[k] == a[k] for k in ("trial_id", "arm", "task_id", "seed")),
            "unexpected scheduled prefix",
        )
    last = n // 16
    hist = decision["history"]
    require(
        [h["round"] for h in hist] == list(range(1, last + 1))
        and all(h["verdict"] == "INCONCLUSIVE" for h in hist[:-1]),
        "interrupted: history differs",
    )
    verdict = decision["verdict"]
    require(
        hist[-1]["verdict"] == verdict
        and (
            (
                verdict == "ERROR"
                and decision["reasons"] == ["errored pairs exceed max_errored_pairs"]
                and hist[-1]["counts"]["errored"] > 4
            )
            or (
                decision["stopped_at_round"] == last
                and (verdict in ("PASS", "BLOCK") or (verdict == "INCONCLUSIVE" and last == 10))
            )
        ),
        "interrupted: invalid stopping reason",
    )
    return last


def receipt_map(receipts: list[Row], assignments: list[Row], tag: str) -> dict[str, bool]:
    key_fields = ("run", "round", "order_id", "arm", "seed", "body_sha256")
    expected = {tuple(a[k] for k in key_fields): a["trial_id"] for a in assignments}
    result: dict[str, bool] = {}
    for r in receipts:
        require(
            type(r["round"]) is int
            and type(r["seed"]) is int
            and type(r["port"]) is int
            and isinstance(r["host"], str),
            "invalid receipt field types",
        )
        k = tuple(r[f] for f in key_fields)
        require(k in expected, "receipt assignment or request body differs")
        tid = expected.pop(k)
        require(
            ipaddress.ip_address(r["host"]).is_loopback
            and r["port"] == 11434
            and r["method"] == "POST"
            and r["path"] == "/api/chat",
            "receipt destination differs",
        )
        done = r["stream_completed"]
        require(
            type(done) is bool
            and r["model_mismatch"] is False
            and (r["response_model"] == tag or (not done and r["response_model"] is None)),
            "receipt response model differs",
        )
        require(
            (r["incomplete_reason"] is None)
            if done
            else isinstance(r["incomplete_reason"], str) and bool(r["incomplete_reason"]),
            "receipt completion reason differs",
        )
        result[tid] = done
    require(not expected, "missing first exchange receipt")
    return result


def compare_counts(expected: object, actual: object, path: str = "counts") -> None:
    if isinstance(expected, dict) and isinstance(actual, dict):
        require(
            expected.keys() == actual.keys(),
            f"{path} fields or group membership differ: {sorted(expected.keys() ^ actual.keys())}",
        )
        for key, value in expected.items():
            compare_counts(value, actual[key], f"{path}/{key}")
    else:
        require(type(expected) is type(actual) and expected == actual, f"{path} differs")


def check_run(root: Path, work: Path, mode: str, python: Path = PYTHON) -> Row:
    run = work.name
    start = read(work / "started.json")
    model = models(root)[run.split("-")[2]]
    require(
        start["mode"] == mode and start["run"] == run and start["model"] == model,
        "claim mode or identity differs",
    )
    for name in ("inputs", "descriptors"):
        require(
            digest(root / "prepared" / (name + ".json")) == start[name + "_sha256"],
            "claim freeze differs",
        )
    before = start["identity"]
    validate(root, model, before)
    require(
        before
        == read(work / "identity-after.json")
        == validate_pin(root, model, read(work / "preflight.json"), mode, start["registration"]),
        "identity changed",
    )
    pin = read(root / "prepared/descriptors.json")[run + ".yaml"]
    path = root / "prepared" / (run + ".assignments.json")
    require(
        digest(path) == pin["assignments"]
        and digest(root / "prepared" / (run + ".yaml")) == pin["sha256"],
        "descriptor differs",
    )
    inventory = read(root / "prepared/inputs.json")
    expected_files = {
        n: v
        for n, v in inventory.items()
        if n.startswith("agent/") or n in ("execution.py", "processes.py", "records.py")
    }
    expected_files.update(
        {
            f"prepared/{run}.yaml": pin["sha256"],
            f"prepared/{run}.assignments.json": pin["assignments"],
        }
    )
    snap = work / "snapshot"
    require(
        {str(p.relative_to(snap)): digest(p) for p in snap.rglob("*") if p.is_file()}
        == expected_files,
        "execution snapshot differs",
    )
    assignments = read(path)
    (store,) = (work / "store").iterdir()
    manifest = read(store / "manifest.json")
    require(
        store.name == manifest["experiment_id"] == pin["experiment"]
        and manifest["suite_id"] == run
        and manifest["record_sha256"] == pin["manifest"],
        "unexpected store identity",
    )
    decision = read(store / "decision.json")
    gate = subprocess.run(
        [str(python), "-IB", "-m", "arci", "gate", str(store)],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
    )
    require(
        gate.returncode == decision["exit_code"]
        and "stored decision: MATCH" in gate.stdout.splitlines(),
        "gate did not match",
    )
    execution = read(work / "execution.json")
    require(
        execution["exit_code"] == gate.returncode
        and datetime.fromisoformat(execution["ended_at"])
        >= datetime.fromisoformat(execution["started_at"]),
        "execution status differs",
    )
    trials = rows(store / "trials.jsonl")
    last = validated_round(trials, assignments, decision)
    files = sorted((work / "receipts").glob("*.json"))
    require(not any((work / "receipts").glob("*.duplicate")), "duplicate receipt writer")
    require(rows(work / "exchanges.jsonl") == [read(f) for f in files], "receipt inventory differs")
    exchanges = rows(work / "exchanges.jsonl")
    receipts = receipt_map(exchanges, assignments[: len(trials)], model["tag"])
    reasons = {(r["arm"], r["seed"]): r["incomplete_reason"] for r in exchanges}
    require((work / "replacement.jsonl").read_bytes() == b"", "replacement audit differs")
    require(
        rows(store / "events.jsonl") == [e for t in trials for e in t["events"]], "events differ"
    )
    ids = {t["task_id"]: t["task"]["order_id"] for t in manifest["tasks"]}
    require(len(ids) == len(set(ids.values())) == 8, "order groups differ")
    totals: Row = {
        arm: {
            "by_order": {oid: Counter() for oid in ids.values()},
            "terminations": Counter(),
            "unexposed_trials": [],
            "unexposed_details": {},
        }
        for arm in ("baseline", "candidate", "pooled")
    }
    for t in trials:
        require(
            all(
                e["trial_id"] == t["trial_id"] and e["seq"] == i for i, e in enumerate(t["events"])
            ),
            "event sequence differs",
        )
        oid = ids[t["task_id"]]
        obs = observation(t, oid, receipts[t["trial_id"]])
        for arm in (t["arm"], "pooled"):
            group = totals[arm]
            group["by_order"][oid].update(obs)
            group["terminations"][t["termination"]] += 1
            if obs["unexposed"]:
                group["unexposed_trials"].append(t["trial_id"])
                group["unexposed_details"][t["trial_id"]] = dict(
                    reason=reasons[t["arm"], t["seed"]], termination=t["termination"]
                )
            for k, v in obs.items():
                group[k] = group.get(k, 0) + v
    compare_counts(totals, read(work / "counts.json"))
    return dict(counts=totals, model=model, round=last, verdict=decision["verdict"])


def inspect_claims(
    root: Path, claims: Path, rehearsal: bool, python: Path = PYTHON
) -> tuple[dict[str, str], dict[str, Row]]:
    mode = "rehearsal" if rehearsal else "real"
    for name, value in read(root / "prepared/inputs.json").items():
        require(
            (root / name).resolve().is_relative_to(root.resolve()) and digest(root / name) == value,
            f"input differs: {name}",
        )
    pins = read(root / "prepared/descriptors.json")
    require(set(pins) == {r + ".yaml" for r in RUNS}, "descriptor inventory differs")
    for run in RUNS:
        pin = pins[run + ".yaml"]
        require(
            digest(root / "prepared" / (run + ".yaml")) == pin["sha256"]
            and digest(root / "prepared" / (run + ".assignments.json")) == pin["assignments"],
            "descriptor differs",
        )
    order = schedule(rehearsal)
    present = prior_claims(claims, order)
    if not rehearsal:
        subprocess.run(
            [
                str(python),
                "-EsB",
                str(Path(__file__).with_name("verify_registration.py")),
                str(root),
                str(claims),
            ],
            stdin=subprocess.DEVNULL,
            check=True,
        )
    first_claim = {day: next(r for r in order if r.split("-")[1] == day) for day in ("d1", "d2")}
    dated: set[str] = set()
    starts = []
    status = dict.fromkeys(RUNS, "not started")
    verified: dict[str, Row] = {}
    for index, run in enumerate(present):
        work = claims / run
        status[run] = "interrupted"
        try:
            if not (work / "started.json").exists():
                if (work / "finished.json").exists():
                    status[run] = "unreadable"
                continue
            start = read(work / "started.json")
            if start["mode"] != mode:
                raise ValueError(f"{run}: evidence mode differs")
            require(start["run"] == run, "claim run differs")
            if not rehearsal:
                require(
                    (claims / "push-receipt.txt").read_text().split()[0] == start["registration"],
                    "registration commit differs",
                )
            calendar([*starts, start])
            starts.append(start)
            day = run.split("-")[1]
            if (work / "finished.json").is_file():
                require(
                    all(
                        (claims / r / "finished.json").is_file()
                        or (r in first_claim.values() and status[r] == "unreadable")
                        for r in present[:index]
                    ),
                    "unfinished predecessor",
                )
                require(not (work / "refused.json").exists(), "conflicting finish and refusal")
                require(
                    read(work / "finished.json") == finish_record(work),
                    "finished inventory differs",
                )
                verified[run] = check_run(root, work, mode, python)
                if run == first_claim[day]:
                    dated.add(day)
                status[run] = "finished" if day in dated and "d1" in dated else "date unverified"
            elif (work / "refused.json").exists():
                status[run] = "refused"
                reason = read(work / "refused.json")["reason"]
                if reason.startswith("receipt lost for "):
                    status[run] = f"refused, {reason}"
                print(f"{run}: refused: {reason}", file=sys.stderr)
            elif (work / "execution.json").exists() and read(work / "execution.json").get(
                "status"
            ) == "interrupted, worker survived":
                status[run] = "interrupted, worker survived"
        except (
            OSError,
            UnicodeError,
            json.JSONDecodeError,
            KeyError,
            IndexError,
            TypeError,
            AttributeError,
        ) as exc:
            status[run] = "unreadable"
            print(f"{run}: unreadable: {exc}", file=sys.stderr)
        except ValueError as exc:
            if str(exc) == f"{run}: evidence mode differs":
                raise
            status[run] = "refused"
            if str(exc).startswith("receipt lost for "):
                status[run] = f"refused, {exc}"
            print(f"{run}: refused: {exc}", file=sys.stderr)
    return status, verified


def check(
    root: Path, python: Path = PYTHON, *, rehearsal: bool = False, claims: Path | None = None
) -> int:
    statuses, verified = inspect_claims(root, claims or claims_dir(), rehearsal, python)
    for run, status in statuses.items():
        print(run, status)
    require(
        all(
            not s.startswith(("refused", "unreadable", "date unverified"))
            for s in statuses.values()
        ),
        "refused evidence",
    )
    require(verified, "no finished runs")
    return len(verified)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    parser.add_argument("--claims", type=Path)
    parser.add_argument("--rehearsal", action="store_true")
    args = parser.parse_args()
    try:
        number = check(args.directory, rehearsal=args.rehearsal, claims=args.claims)
        print(f"{number} finished runs verified")
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        sys.exit(str(exc))
