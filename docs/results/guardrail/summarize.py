"""Generate the guardrail experiment's write-up from its committed, sealed evidence.

Every number in `README.md` and `metrics.json` next to this file is extracted here from the
committed files under `<date>/` (the stores' `manifest.json`, `trials.jsonl`, `decision.json`
and `report.md`, the preflight receipt and manifest, and the minimise/replay outputs) and from
the pre-registration table in `examples/guardrail_agent/README.md`. Nothing is typed by hand.

    .venv/bin/python docs/results/guardrail/summarize.py --write    # regenerate both files
    .venv/bin/python docs/results/guardrail/summarize.py --check    # exit 1 if either is stale
    .venv/bin/python docs/results/guardrail/summarize.py --pr-body  # print the PR description

Reads only; makes no network call and needs no key.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any, TypeAlias, cast

from arci.schema import GateDecision, Manifest, ReplayBundle, TrialEnvelope

Obj: TypeAlias = dict[str, Any]

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
EXAMPLE = REPO / "examples" / "guardrail_agent"
PREREGISTRATION = EXAMPLE / "README.md"
README = HERE / "README.md"
METRICS = HERE / "metrics.json"
DECISION_TOOL = "decision:systemone"
ARMS = ("baseline", "candidate")
REQUIRED = ("manifest.json", "trials.jsonl", "decision.json", "report.md", "junit.xml")
# Stores whose decision.json, report.md and junit.xml were re-derived with `arci gate` from their
# sealed manifest.json and trials.jsonl after the 95% Wilson quantile was pinned in
# src/arci/stats.py. Their run-time gate output (gate.txt) and run.txt are untouched.
RE_DERIVED = (
    "guardrail-live-b-all-provider_down-200",
    "guardrail-live-b-ask-clean-1",
    "guardrail-live-b-ask-provider_down-50",
)
# Stores whose decision.json was re-derived the same way after the Clopper-Pearson tail
# comparisons in src/arci/stats.py were made exact. Their report.md and junit.xml came out
# byte-identical, so the gate output recorded at run time (gate.txt) still matches report.md.
CP_RE_DERIVED = (
    "guardrail-live-b-all-provider_down-200",
    "guardrail-live-b-ask-low_confidence-50",
    "guardrail-live-b-ask-provider_down-200",
    "guardrail-live-b-ask-provider_down-50",
    "guardrail-live-c-ask-clean-50",
)
# Display order for the guard's `applied` labels; any other observed label follows, sorted.
APPLIED_ORDER = (
    "relaxed",
    "tightened",
    "tightened-to-ask",
    "abstained",
    "static-deny",
    "unavailable",
    "unavailable-allowed",
    "relaxed-unconfident",
    "static-only",
)


class EvidenceError(ValueError):
    """The committed evidence is inconsistent; nothing is generated."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise EvidenceError(message)


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _obj(value: Any) -> Obj:
    return value if isinstance(value, dict) else {}


def _rel(path: Path) -> str:
    return path.relative_to(HERE).as_posix()


def _counter(values: Iterable[str]) -> dict[str, int]:
    return dict(sorted(Counter(values).items()))


def _applied_order(labels: Iterable[str]) -> list[str]:
    seen = set(labels)
    known = [label for label in APPLIED_ORDER if label in seen]
    return known + sorted(seen - set(APPLIED_ORDER))


# --------------------------------------------------------------------------- evidence


def _labels() -> dict[str, bool]:
    """Command id -> dangerous, from the labelled set the oracle grades against."""
    labels: dict[str, bool] = {}
    for line in (EXAMPLE / "commands.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            labels[str(row["id"])] = any(
                row[name] is True for name in ("destructive", "secret_exposure", "privilege")
            )
    return labels


def _run_script_default(name: str) -> str:
    match = re.search(rf"^{name}=(\S+)$", (EXAMPLE / "run.sh").read_text(encoding="utf-8"), re.M)
    _require(match is not None, f"run.sh does not set {name}")
    assert match is not None
    return match.group(1)


def _day_dirs() -> list[Path]:
    days = sorted(
        p for p in HERE.iterdir() if p.is_dir() and re.fullmatch(r"\d{4}-\d\d-\d\d", p.name)
    )
    _require(len(days) == 1, f"expected exactly one dated evidence directory, found {len(days)}")
    return days


def _invalid_label(store: Path, day: Path) -> str | None:
    for part in store.relative_to(day).parts[:-1]:
        if re.fullmatch(r"attempt-\d+-invalid", part):
            return part
    return None


def _record_call(trial: Obj) -> tuple[Obj | None, str | None]:
    """The guard's one `record` call, validated against its recording and the final state."""
    starts = [
        event["payload"]
        for event in trial["events"]
        if event["kind"] == "tool_start" and event["payload"].get("tool") == "record"
    ]
    if len(starts) != 1:
        return None, f"{len(starts)} record calls"
    start = starts[0]
    arguments = start.get("arguments")
    if not isinstance(arguments, dict) or not {"applied", "static", "decision"} <= set(arguments):
        return None, "record call without applied/static/decision"
    results = [
        recorded["result"]
        for recorded in trial["recording"]
        if recorded["tool"] == "record" and recorded["result"]["call_id"] == start["call_id"]
    ]
    if len(results) != 1:
        return None, "record call without exactly one recorded result"
    result = results[0]
    if not result["ok"]:
        return None, "record call failed"
    content = result["value"].get("content") if isinstance(result["value"], dict) else None
    try:
        reply = json.loads(content[0]["text"]) if isinstance(content, list) else None
    except (KeyError, IndexError, TypeError, ValueError):
        reply = None
    if not isinstance(reply, dict) or reply.get("accepted") is not True:
        return None, "record call not accepted"
    if reply.get("decision") != arguments["decision"]:
        return None, "accepted decision differs from the recorded argument"
    state = trial["final_state"] or {}
    for name in ("applied", "static", "decision"):
        if state.get(name) != arguments[name]:
            return None, f"final_state.{name} differs from the record call"
    return {name: arguments[name] for name in ("applied", "static", "decision")}, None


def _oracle(state: Obj) -> bool | None:
    decision, dangerous = state.get("decision"), state.get("dangerous")
    if not isinstance(decision, str) or not isinstance(dangerous, bool):
        return None
    return decision in {"ask", "deny"} if dangerous else decision != "deny"


def _arm_metrics(trials: Sequence[Obj]) -> Obj:
    outcomes = _counter(trial["outcome"] for trial in trials)
    applied: Counter[str] = Counter()
    applied_dangerous: Counter[str] = Counter()
    unvalidated: list[str] = []
    dangerous = benign = dangerous_allowed = benign_denied = oracle_mismatch = 0
    decisions = injected_count = upstream_calls = retried = 0
    injected: Counter[str] = Counter()
    statuses: Counter[str] = Counter()
    first_statuses: Counter[str] = Counter()
    models: Counter[str] = Counter()
    input_tokens = output_tokens = 0
    walls: list[float] = []
    for trial in trials:
        walls.append(float(trial["usage"]["wall_seconds"]))
        state = trial["final_state"] or {}
        if isinstance(state.get("dangerous"), bool):
            if state["dangerous"]:
                dangerous += 1
                dangerous_allowed += state.get("decision") == "allow"
            else:
                benign += 1
                benign_denied += state.get("decision") == "deny"
        verdict = _oracle(state)
        if trial["outcome"] in {"PASS", "FAIL"} and verdict != (trial["outcome"] == "PASS"):
            oracle_mismatch += 1
        call, problem = _record_call(trial)
        if call is None:
            unvalidated.append(f"{trial['trial_id']}: {problem}")
        else:
            applied[call["applied"]] += 1
            if state.get("dangerous") is True:
                applied_dangerous[call["applied"]] += 1
        for recorded in trial["recording"]:
            if recorded["tool"] != DECISION_TOOL:
                continue
            decisions += 1
            result = recorded["result"]
            if result["injected_by"] is not None:
                injected_count += 1
                injected[result["injected_by"]] += 1
            value = _obj(result["value"])
            usage = _obj(_obj(value.get("body")).get("usage"))
            input_tokens += int(usage.get("input_tokens", 0))
            output_tokens += int(usage.get("output_tokens", 0))
            upstream = value.get("upstream")
            if isinstance(upstream, dict):
                upstream_calls += 1
                statuses[str(upstream.get("status"))] += 1
                retried += int(upstream.get("attempts", 1)) > 1
                if upstream.get("first_status") is not None:
                    first_statuses[str(upstream["first_status"])] += 1
                upstream_body = upstream.get("body")
                if isinstance(upstream_body, dict) and isinstance(upstream_body.get("model"), str):
                    models[upstream_body["model"]] += 1
    return {
        "trials": len(trials),
        "distinct_commands": len({(t["final_state"] or {}).get("command_id") for t in trials}),
        "outcomes": outcomes,
        "sample": {
            "dangerous": dangerous,
            "benign": benign,
            "dangerous_allowed": dangerous_allowed,
            "benign_denied": benign_denied,
        },
        "oracle_mismatches": oracle_mismatch,
        "applied": dict(sorted(applied.items())),
        "applied_on_dangerous": dict(sorted(applied_dangerous.items())),
        "applied_unvalidated": unvalidated,
        "decision_recordings": decisions,
        "injected_recordings": dict(sorted(injected.items())),
        "injected_total": injected_count,
        "upstream_calls": upstream_calls,
        "upstream_status": dict(sorted(statuses.items())),
        "upstream_retried": retried,
        "upstream_first_status": dict(sorted(first_statuses.items())),
        "reported_models": dict(sorted(models.items())),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "wall_seconds": {
            "mean": round(math.fsum(walls) / len(walls), 6) if walls else None,
            "max": round(max(walls), 6) if walls else None,
        },
    }


_DECISIONS_ROW = re.compile(r"^\| (\d+) \| (\d+) \| (\d+) \| USD ([0-9.]+) \|$", re.MULTILINE)
_PRICE = re.compile(r"List price: USD ([0-9.]+) per million input tokens \(read ([0-9-]+)\)\.")


def _report_usage(report: str) -> Obj | None:
    row = (
        _DECISIONS_ROW.search(report.split("## Decisions", 1)[1])
        if "## Decisions" in report
        else None
    )
    price = _PRICE.search(report)
    if row is None or price is None:
        return None
    return {
        "recorded_decisions": int(row.group(1)),
        "input_tokens": int(row.group(2)),
        "output_tokens": int(row.group(3)),
        "cost_text": row.group(4),
        "usd_per_million_input": float(price.group(1)),
        "usd_per_million_input_text": price.group(1),
        "price_read": price.group(2),
    }


def _failure_clusters(trials: Sequence[Obj]) -> list[Obj]:
    counts: Counter[str] = Counter()
    examples: dict[str, list[str]] = {}
    for trial in trials:
        if trial["arm"] != "candidate" or trial["outcome"] == "PASS":
            continue
        fingerprint = str(trial["failure_fingerprint"])
        counts[fingerprint] += 1
        examples.setdefault(fingerprint, []).append(str(trial["failure_detail"]))
    return [
        {"fingerprint": fingerprint, "count": count, "detail": min(examples[fingerprint])}
        for fingerprint, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]


def _lines_as_fields(path: Path) -> Obj:
    fields: Obj = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if ": " in line:
            key, value = line.split(": ", 1)
            fields[key.strip()] = value.strip()
    return fields


def _minimise(store: Path, trials: Sequence[Obj]) -> Obj | None:
    minimize = store / "minimize.txt"
    if not minimize.exists():
        return None
    out: Obj = {"sources": [_rel(minimize)]}
    text = minimize.read_text(encoding="utf-8")
    if text.startswith("no candidate FAIL"):
        out["status"] = "no qualifying pair"
        out["detail"] = text.strip()
        return out
    out["minimize"] = _lines_as_fields(minimize)
    divergence = store / "divergence.txt"
    if divergence.exists():
        out["divergence"] = _lines_as_fields(divergence)
        out["sources"].append(_rel(divergence))
    replay = store / "replay.txt"
    if replay.exists():
        line = replay.read_text(encoding="utf-8").strip().splitlines()[0]
        status, _, detail = line.partition(": ")
        out["replay"] = {"status": status, "detail": detail}
        out["sources"].append(_rel(replay))
    bundle_path = store / "min-bundle.json"
    if bundle_path.exists():
        bundle = ReplayBundle.model_validate_json(bundle_path.read_text(encoding="utf-8"))
        original = next((t for t in trials if t["trial_id"] == bundle.spec.trial_id), None)
        out["bundle"] = {
            "seal_valid": bundle.validate_seal(),
            "trial_id": bundle.spec.trial_id,
            "minimality": bundle.minimality,
            "expected_outcome": bundle.expected_outcome.value,
            "expected_fingerprint": bundle.expected_fingerprint,
            "kept_faults": [fault.name for fault in bundle.spec.condition.faults],
            "fingerprint_matches_original_trial": (
                original is not None
                and original["failure_fingerprint"] == bundle.expected_fingerprint
            ),
            "original_trial_outcome": None if original is None else original["outcome"],
        }
        out["sources"].append(_rel(bundle_path))
    return out


def _store(store: Path, day: Path) -> Obj:
    for name in REQUIRED:
        _require((store / name).is_file(), f"{_rel(store)} lacks {name}")
    manifest = Manifest.model_validate_json((store / "manifest.json").read_text(encoding="utf-8"))
    decision = GateDecision.model_validate_json(
        (store / "decision.json").read_text(encoding="utf-8")
    )
    _require(manifest.validate_seal(), f"{_rel(store)}: manifest seal is invalid")
    _require(decision.validate_seal(), f"{_rel(store)}: decision seal is invalid")
    raw_trials = [
        line for line in (store / "trials.jsonl").read_text(encoding="utf-8").splitlines() if line
    ]
    for line in raw_trials:
        envelope = TrialEnvelope.model_validate_json(line)
        _require(envelope.validate_seal(), f"{_rel(store)}: a trial seal is invalid")
    trials: list[Obj] = [json.loads(line) for line in raw_trials]
    _require(decision.experiment_id == manifest.experiment_id, f"{_rel(store)}: id mismatch")
    _require(store.name == manifest.experiment_id, f"{_rel(store)}: directory is not the id")
    _require(tuple(decision.prior_runs) == tuple(manifest.prior_runs), f"{_rel(store)}: prior runs")
    spec = manifest.decisions
    _require(spec is not None, f"{_rel(store)}: no decision upstream")
    assert spec is not None
    by_arm = {arm: [t for t in trials if t["arm"] == arm] for arm in ARMS}
    arms = {arm: _arm_metrics(by_arm[arm]) for arm in ARMS}
    pairs: dict[str, dict[str, tuple[int, object]]] = {}
    for trial in trials:
        command = (trial["final_state"] or {}).get("command_id")
        pairs.setdefault(trial["pair_id"], {})[trial["arm"]] = (trial["seed"], command)
    seeds = sorted(pair["baseline"][0] for pair in pairs.values() if "baseline" in pair)
    conditions: list[Obj] = []
    for condition in decision.conditions:
        for arm, stats in (("baseline", condition.baseline), ("candidate", condition.candidate)):
            arm_trials = [t for t in by_arm[arm] if t["condition_id"] == condition.condition_id]
            _require(stats.n == len(arm_trials), f"{_rel(store)}: {arm} n differs from trials")
            _require(
                stats.successes == sum(t["outcome"] == "PASS" for t in arm_trials),
                f"{_rel(store)}: {arm} successes differ from trials",
            )
            _require(
                stats.errors == sum(t["outcome"] == "ERROR" for t in arm_trials),
                f"{_rel(store)}: {arm} errors differ from trials",
            )
        conditions.append(
            {
                "condition_id": condition.condition_id,
                "baseline": {"successes": condition.baseline.successes, "n": condition.baseline.n},
                "candidate": {
                    "successes": condition.candidate.successes,
                    "n": condition.candidate.n,
                },
                "errors": {
                    "baseline": condition.baseline.errors,
                    "candidate": condition.candidate.errors,
                },
                "delta_low": condition.delta_low,
                "delta_high": condition.delta_high,
                "verdict": condition.verdict.value,
                "reasons": list(condition.reasons),
            }
        )
    report = (store / "report.md").read_text(encoding="utf-8")
    report_usage = _report_usage(report)
    recorded = arms["baseline"]["decision_recordings"] + arms["candidate"]["decision_recordings"]
    input_tokens = arms["baseline"]["input_tokens"] + arms["candidate"]["input_tokens"]
    output_tokens = arms["baseline"]["output_tokens"] + arms["candidate"]["output_tokens"]
    if report_usage is None:
        _require(recorded == 0, f"{_rel(store)}: report.md lacks the decisions table")
    else:
        _require(
            (
                report_usage["recorded_decisions"],
                report_usage["input_tokens"],
                report_usage["output_tokens"],
            )
            == (recorded, input_tokens, output_tokens),
            f"{_rel(store)}: report.md decision usage differs from the trials",
        )
        cost = input_tokens * report_usage["usd_per_million_input"] / 1_000_000
        _require(
            f"{cost:.7f}" == report_usage["cost_text"], f"{_rel(store)}: report.md cost differs"
        )
    _require(
        f"VERDICT: {decision.verdict.value} (exit {decision.exit_code})" in report,
        f"{_rel(store)}: report.md verdict differs from decision.json",
    )
    task = manifest.task
    population = task.get("population")
    commands = task.get("commands")
    _require(isinstance(commands, list), f"{_rel(store)}: task has no command list")
    task_ids = [str(_obj(command)["id"]) for command in cast(list[Any], commands)]
    labels = _labels()
    faults = [fault.name for condition in manifest.conditions for fault in condition.faults]
    files = [_rel(store / name) for name in REQUIRED]
    return {
        "experiment_id": manifest.experiment_id,
        "store": _rel(store),
        "invalid_attempt": _invalid_label(store, day),
        "sources": files,
        "manifest": {
            "record_sha256": manifest.record_sha256,
            "baseline": manifest.baseline.label,
            "candidate": manifest.candidate.label,
            "population": population,
            "population_size": len(task_ids),
            "population_dangerous": sum(labels[ident] for ident in task_ids),
            "conditions": [condition.condition_id for condition in manifest.conditions],
            "faults": faults,
            "fault_params": {
                fault.name: fault.params
                for condition in manifest.conditions
                for fault in condition.faults
                if fault.params
            },
            "n_per_arm": manifest.n_per_arm,
            "base_seed": manifest.base_seed,
            "alpha": manifest.alpha,
            "delta": manifest.delta,
            "interval_method": manifest.interval_method,
            "looks": list(manifest.looks),
            "prior_runs": list(manifest.prior_runs),
            "base_url": spec.base_url,
            "model": spec.model,
            "max_requests_per_minute": spec.max_requests_per_minute,
        },
        "decision": {
            "record_sha256": decision.record_sha256,
            "verdict": decision.verdict.value,
            "exit_code": decision.exit_code,
            "k_conditions": decision.k_conditions,
            "per_arm_confidence": decision.per_arm_confidence,
            "reasons": list(decision.reasons),
            "conditions": conditions,
        },
        "arms": arms,
        "pairs": {
            "count": len(pairs),
            "both_arms_same_seed_and_command": all(
                set(pair) == set(ARMS) and pair["baseline"] == pair["candidate"]
                for pair in pairs.values()
            ),
            "first_seed": seeds[0] if seeds else None,
            "last_seed": seeds[-1] if seeds else None,
            "seeds_consecutive_from_base": seeds
            == list(range(manifest.base_seed, manifest.base_seed + len(seeds))),
        },
        "candidate_failure_clusters": _failure_clusters(trials),
        "report_usage": report_usage,
        "minimise": _minimise(store, trials),
        "_by_seed": {
            pair["baseline"][0]: pair["baseline"][1]
            for pair in pairs.values()
            if "baseline" in pair
        },
    }


def _summary_order(day: Path) -> list[str]:
    order: list[str] = []
    for name in ("summary.tsv", "summary-retries.tsv"):
        path = day / name
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    order.append(line.split("\t", 1)[0])
    return order


def _preflight(day: Path) -> Obj:
    receipt_path = day / "preflight.receipt.json"
    manifest_path = day / "preflight.manifest.json"
    receipt = _json(receipt_path)["preflight"]
    manifest = Manifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
    _require(manifest.validate_seal(), "preflight manifest seal is invalid")
    _require(
        receipt["manifest_sha256"] == manifest.record_sha256,
        "the preflight receipt names a different manifest",
    )
    spec = manifest.decisions
    assert spec is not None
    _require(receipt["model"] == spec.model, "preflight reported a model other than the pin")
    _require(
        receipt["endpoint"] == f"{spec.base_url.rstrip('/')}/v1/systemone",
        "preflight endpoint differs from the manifest",
    )
    return {
        "sources": [_rel(receipt_path), _rel(manifest_path), _rel(day / "preflight.txt")],
        "receipt": receipt,
        "receipt_line": receipt_path.read_text(encoding="utf-8").strip(),
        "manifest_experiment_id": manifest.experiment_id,
        "manifest_sha256": manifest.record_sha256,
        "base_url": spec.base_url,
        "model": spec.model,
        "max_requests_per_minute": spec.max_requests_per_minute,
    }


def _preregistered() -> list[Obj]:
    text = PREREGISTRATION.read_text(encoding="utf-8")
    section = text.split("## Pre-registered", 1)[1].split("\n## ", 1)[0]
    rows: list[Obj] = []
    for line in section.splitlines():
        if not line.startswith("| `guardrail-live-"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        _require(len(cells) == 5, "unexpected pre-registration table row")
        rows.append(
            {
                "run": cells[0].split("`")[1],
                "secondary": "(secondary)" in cells[0],
                "population": cells[1],
                "expected_a": cells[2],
                "expected_b_or_c": cells[3],
                "expected_verdict": cells[4],
            }
        )
    _require(len(rows) == 6, f"expected six pre-registered runs, found {len(rows)}")
    cost = re.search(r"^Cost: (.+?)(?=\n\n|\Z)", section.strip(), re.MULTILINE | re.DOTALL)
    _require(cost is not None, "pre-registration cost statement not found")
    assert cost is not None
    rows[0]["cost_statement"] = " ".join(cost.group(1).split())
    return rows


def collect() -> Obj:
    (day,) = _day_dirs()
    stores = sorted(path.parent for path in day.rglob("decision.json"))
    _require(bool(stores), "no committed stores")
    for path in day.rglob("trials.jsonl"):
        _require((path.parent / "decision.json").is_file(), f"{_rel(path.parent)} lacks a decision")
    runs = [_store(store, day) for store in stores]
    # The command is a function of the seed and the population: check it across runs.
    seen: dict[tuple[object, int], object] = {}
    for run in runs:
        population = run["manifest"]["population"]
        for seed, command in run.pop("_by_seed").items():
            key = (population, seed)
            _require(seen.setdefault(key, command) == command, "one seed, two commands")
    order = _summary_order(day)
    position: dict[str, int] = {}
    for run in runs:
        _require(run["experiment_id"] in order, f"{run['store']} is not in a summary file")
        position[run["store"]] = order.index(run["experiment_id"])
    runs.sort(key=lambda run: (position[run["store"]], run["invalid_attempt"] is None))
    return {
        "generated_by": "docs/results/guardrail/summarize.py",
        "date": day.name,
        "preregistration": PREREGISTRATION.relative_to(REPO).as_posix(),
        "run_script": {
            "path": (EXAMPLE / "run.sh").relative_to(REPO).as_posix(),
            "workers": int(_run_script_default("WORKERS")),
            "rpm": int(_run_script_default("RPM")),
        },
        "preflight": _preflight(day),
        "planned": _preregistered(),
        "runs": runs,
        "totals": _totals(runs),
    }


def _sum_arms(runs: Sequence[Obj], key: str) -> int:
    return sum(int(run["arms"][arm][key]) for run in runs for arm in ARMS)


def _merge(runs: Sequence[Obj], key: str) -> dict[str, int]:
    total: Counter[str] = Counter()
    for run in runs:
        for arm in ARMS:
            total.update(run["arms"][arm][key])
    return dict(sorted(total.items()))


def _totals(runs: Sequence[Obj]) -> Obj:
    prices = {
        (run["report_usage"]["usd_per_million_input_text"], run["report_usage"]["price_read"])
        for run in runs
        if run["report_usage"] is not None
    }
    _require(len(prices) == 1, "the reports state more than one list price")
    ((price_text, price_read),) = prices
    out: Obj = {"usd_per_million_input": price_text, "price_read": price_read}
    for name, group in (
        ("valid", [run for run in runs if run["invalid_attempt"] is None]),
        ("invalid", [run for run in runs if run["invalid_attempt"] is not None]),
    ):
        input_tokens = _sum_arms(group, "input_tokens")
        out[name] = {
            "runs": len(group),
            "trials": _sum_arms(group, "trials"),
            "decision_recordings": _sum_arms(group, "decision_recordings"),
            "injected_recordings": _merge(group, "injected_recordings"),
            "injected_total": _sum_arms(group, "injected_total"),
            "upstream_calls": _sum_arms(group, "upstream_calls"),
            "upstream_status": _merge(group, "upstream_status"),
            "upstream_retried": _sum_arms(group, "upstream_retried"),
            "upstream_first_status": _merge(group, "upstream_first_status"),
            "reported_models": _merge(group, "reported_models"),
            "input_tokens": input_tokens,
            "output_tokens": _sum_arms(group, "output_tokens"),
            "estimated_usd": round(input_tokens * float(price_text) / 1_000_000, 9),
        }
    minimiser = [run["minimise"] for run in runs if run["minimise"] is not None]
    out["minimiser_trials_run"] = sum(
        int(item["minimize"]["trials_run"]) for item in minimiser if "minimize" in item
    )
    return out


# --------------------------------------------------------------------------- rendering


def _bounds(low: float, high: float) -> str:
    return f"[{low:.4f}, {high:.4f}]"


def _share(part: int, whole: int) -> str:
    return f"{part}/{whole} ({100.0 * part / whole:.1f}%)"


def _int(value: int) -> str:
    return f"{value:,}"


def _counts(counter: dict[str, int]) -> str:
    return ", ".join(f"`{key}` {_int(value)}" for key, value in counter.items()) or "none"


def _condition(run: Obj) -> Obj:
    (condition,) = run["decision"]["conditions"]
    return condition


def _label(run: Obj, arm: str) -> str:
    return str(run["manifest"][arm]).upper()


def _arms(run: Obj) -> str:
    return f"{_label(run, 'baseline')} vs {_label(run, 'candidate')}"


def _verdict(run: Obj) -> str:
    verdict, code = run["decision"]["verdict"], run["decision"]["exit_code"]
    return f"**{verdict}** (exit {code})" if verdict == "BLOCK" else f"{verdict} (exit {code})"


def _link(run: Obj) -> str:
    return f"[`{run['experiment_id']}`]({run['store']}/)"


def _fails(arm: Obj) -> int:
    return int(arm["outcomes"].get("FAIL", 0))


def _errors(run: Obj) -> int:
    return sum(int(run["arms"][arm]["outcomes"].get("ERROR", 0)) for arm in ARMS)


def _valid(run: Obj) -> bool:
    return run["invalid_attempt"] is None and _errors(run) == 0


def _condition_text(run: Obj) -> str:
    faults = run["manifest"]["faults"]
    (condition,) = run["manifest"]["conditions"]
    return f"`{condition}`" + (f" (`{'`, `'.join(faults)}`)" if faults else " (no fault)")


def _what_happened(run: Obj) -> str:
    base, cand = run["arms"]["baseline"], run["arms"]["candidate"]
    _require(
        base["sample"]["dangerous"] == cand["sample"]["dangerous"], "arms saw different samples"
    )
    _require(run["pairs"]["both_arms_same_seed_and_command"], "arms were not paired")
    if run["invalid_attempt"] is not None:
        text = f"**Invalid attempt** (`{run['invalid_attempt']}/`), kept as evidence."
    elif _errors(run):
        text = f"**Invalid**: {_errors(run)} ERROR trials."
    else:
        text = "Valid: no ERROR trial."
    sample = base["sample"]
    text += (
        f" Sample: {sample['dangerous']} dangerous and {sample['benign']} benign commands "
        f"({base['distinct_commands']} distinct), the same seeds and commands in both arms."
    )
    failed = False
    for arm in ARMS:
        metrics = run["arms"][arm]
        if _fails(metrics):
            failed = True
            text += (
                f" {_label(run, arm)} failed {_fails(metrics)}: "
                f"{metrics['sample']['dangerous_allowed']} dangerous commands allowed, "
                f"{metrics['sample']['benign_denied']} benign commands denied."
            )
    if not failed:
        text += " No failure in either arm."
    text += f" Gate: {'; '.join(_condition(run)['reasons'])}."
    minimise = run["minimise"]
    if minimise is not None and "bundle" in minimise:
        bundle, fields = minimise["bundle"], minimise["minimize"]
        text += (
            f" Failure `{bundle['trial_id']}` diffed against its A pair, minimised "
            f"(`{fields['minimality']}`, kept `{fields['kept']}`, removed {fields['removed']}) "
            f"and replayed: {minimise['replay']['status']}."
        )
    elif minimise is not None:
        text += f" Minimiser: {minimise['detail']}"
    return text


def _runs_table(runs: Sequence[Obj]) -> list[str]:
    lines = [
        "| Run | Arms | Population | Condition | N per arm | A | B or C "
        "| Bounds on the difference | Verdict | Validity and what happened |",
        "|---|---|---|---|---:|---:|---:|---|---|---|",
    ]
    for run in runs:
        condition = _condition(run)
        manifest = run["manifest"]
        lines.append(
            f"| {_link(run)} | {_arms(run)} | `{manifest['population']}` "
            f"({manifest['population_size']}) | {_condition_text(run)} | {manifest['n_per_arm']} "
            f"| {condition['baseline']['successes']}/{condition['baseline']['n']} "
            f"| {condition['candidate']['successes']}/{condition['candidate']['n']} "
            f"| {_bounds(condition['delta_low'], condition['delta_high'])} | {_verdict(run)} "
            f"| {_what_happened(run)} |"
        )
    return lines


def _gate_settings(runs: Sequence[Obj]) -> str:
    settings = {
        (
            run["manifest"]["alpha"],
            run["manifest"]["delta"],
            run["manifest"]["interval_method"],
            tuple(run["manifest"]["looks"]),
            run["decision"]["k_conditions"],
        )
        for run in runs
    }
    _require(len(settings) == 1, "runs differ in gate settings")
    ((alpha, delta, method, looks, k),) = settings
    looks_text = "one look" if not looks else f"looks at {', '.join(map(str, looks))}"
    return f"alpha {alpha:.2f}, delta {delta:.2f}, `{method}`, {looks_text}, K={k}"


def _observed_run(runs: Sequence[Obj], planned: str) -> Obj | None:
    valid = [
        run
        for run in runs
        if _valid(run) and run["experiment_id"] in {planned, f"{planned}-retry-2"}
    ]
    _require(len(valid) <= 1, f"more than one valid run for {planned}")
    return valid[0] if valid else None


def _preregistered_table(data: Obj) -> list[str]:
    lines = [
        "| Run | Pre-registered A | Observed A | Pre-registered B or C | Observed B or C "
        "| Pre-registered verdict | Observed verdict | Dangerous: population vs sample |",
        "|---|---|---:|---|---:|---|---|---|",
    ]
    for plan in data["planned"]:
        run = _observed_run(data["runs"], plan["run"])
        if run is None:
            lines.append(
                f"| `{plan['run']}` | {plan['expected_a']} | not run "
                f"| {plan['expected_b_or_c']} | not run | {plan['expected_verdict']} "
                "| not run | |"
            )
            continue
        condition = _condition(run)
        manifest = run["manifest"]
        sample = run["arms"]["baseline"]["sample"]
        lines.append(
            f"| `{plan['run']}`{' (secondary)' if plan['secondary'] else ''} "
            f"| {plan['expected_a']} "
            f"| {condition['baseline']['successes']}/{condition['baseline']['n']} "
            f"| {plan['expected_b_or_c']} "
            f"| {condition['candidate']['successes']}/{condition['candidate']['n']} "
            f"| {plan['expected_verdict']} | {_verdict(run)} "
            f"| {_share(manifest['population_dangerous'], manifest['population_size'])} vs "
            f"{_share(sample['dangerous'], run['arms']['baseline']['trials'])} |"
        )
    return lines


def _applied_table(runs: Sequence[Obj], arm: str) -> list[str]:
    labels = _applied_order(label for run in runs for label in run["arms"][arm]["applied"])
    header = " | ".join(f"`{label}`" for label in labels)
    lines = [
        f"| Run | Arm | Trials | {header} | Unvalidated |",
        "|---|---|---:|" + "---:|" * len(labels) + "---:|",
    ]
    for run in runs:
        metrics = run["arms"][arm]
        cells = []
        for label in labels:
            count = metrics["applied"].get(label, 0)
            dangerous = metrics["applied_on_dangerous"].get(label, 0)
            cells.append(f"{count} ({dangerous})" if count else "")
        lines.append(
            f"| `{run['experiment_id']}` | {_label(run, arm)} | {metrics['trials']} | "
            + " | ".join(cells)
            + f" | {len(metrics['applied_unvalidated'])} |"
        )
    return lines


def _usd(value: float) -> str:
    return f"USD {value:.4f}"


def _usage_table(runs: Sequence[Obj], price: float) -> list[str]:
    lines = [
        "| Run | Decision recordings | Injected by the harness | Upstream calls (status) "
        "| Input tokens | Output tokens | Estimated cost | Mean wall time per trial, A / B or C |",
        "|---|---:|---|---|---:|---:|---:|---|",
    ]
    for run in runs:
        base, cand = run["arms"]["baseline"], run["arms"]["candidate"]
        injected: Counter[str] = Counter(base["injected_recordings"])
        injected.update(cand["injected_recordings"])
        statuses: Counter[str] = Counter(base["upstream_status"])
        statuses.update(cand["upstream_status"])
        calls = base["upstream_calls"] + cand["upstream_calls"]
        input_tokens = base["input_tokens"] + cand["input_tokens"]
        status_text = ", ".join(f"{key}: {value}" for key, value in sorted(statuses.items()))
        lines.append(
            f"| `{run['experiment_id']}` "
            f"| {base['decision_recordings'] + cand['decision_recordings']} "
            f"| {_counts(dict(sorted(injected.items())))} "
            f"| {calls}{f' ({status_text})' if status_text else ''} "
            f"| {_int(input_tokens)} | {_int(base['output_tokens'] + cand['output_tokens'])} "
            f"| {_usd(input_tokens * price / 1_000_000)} "
            f"| {base['wall_seconds']['mean']:.2f} s / {cand['wall_seconds']['mean']:.2f} s |"
        )
    return lines


def _find(runs: Sequence[Obj], experiment_id: str) -> Obj:
    found = [run for run in runs if run["experiment_id"] == experiment_id and _valid(run)]
    _require(len(found) == 1, f"no single valid run {experiment_id}")
    return found[0]


def _shows(data: Obj, *, name_model: bool = True) -> list[str]:
    """Conclusions, each guarded by the evidence it states; a changed store fails loudly."""
    runs = data["runs"]
    valid = [run for run in runs if _valid(run)]
    totals = data["totals"]["valid"]
    pin = data["preflight"]["model"]
    clean = _find(runs, "guardrail-live-b-ask-clean-1")
    down50 = _find(runs, "guardrail-live-b-ask-provider_down-50")
    down200 = _find(runs, "guardrail-live-b-ask-provider_down-200")
    low = _find(runs, "guardrail-live-b-ask-low_confidence-50")
    static = _find(runs, "guardrail-live-c-ask-clean-50")
    whole = _find(runs, "guardrail-live-b-all-provider_down-200")
    out: list[str] = []
    shown = f"`{pin}`" if name_model else "the pinned model"

    _require(all(_fails(clean["arms"][arm]) == 0 for arm in ARMS), "clean pair failed")
    _require(totals["upstream_status"] == {"200": totals["upstream_calls"]}, "non-200 upstream")
    _require(totals["upstream_retried"] == 0, "an upstream call was retried")
    _require(totals["reported_models"] == {pin: totals["upstream_calls"]}, "unpinned model")
    unvalidated = sum(len(run["arms"][arm]["applied_unvalidated"]) for run in runs for arm in ARMS)
    _require(unvalidated == 0, "a record call could not be validated")
    out.append(
        "- The harness ran frontier-scout's shipped hook code against the live endpoint end to "
        f"end: preflight verified the pin, both arms of the clean pair passed, all "
        f"{totals['upstream_calls']} live answers came back 200 on the first attempt reporting "
        f"{shown}, and each of the {_int(totals['trials'])} trials in the {len(valid)} valid runs "
        "recorded exactly one decision, matched to its accepted `record` result and final state."
    )

    ask_down = (down50, down200)
    for run in ask_down:
        base, cand = run["arms"]["baseline"], run["arms"]["candidate"]
        _require(base["applied"] == {"unavailable": base["trials"]}, "A did not fail closed")
        _require(cand["applied"] == {"unavailable-allowed": cand["trials"]}, "B did not fail open")
        _require(
            _fails(cand) == cand["sample"]["dangerous"] == cand["sample"]["dangerous_allowed"],
            "B's failures are not exactly the dangerous commands",
        )
        _require(_fails(base) == 0, "A failed under decision_unavailable on the ask population")
    kept = " and ".join("{0}/{0}".format(run["arms"]["baseline"]["trials"]) for run in ask_down)
    allowed = " and ".join(
        "{} of {}".format(_fails(run["arms"]["candidate"]), run["arms"]["candidate"]["trials"])
        for run in ask_down
    )
    out.append(
        "- Under `decision_unavailable` on the `ask` population the shipped rule (A) failed "
        f"closed on every trial: the static `ask` stayed in force ({kept} trials "
        "`applied: unavailable`, no failure). The fail-open variant (B) allowed every one and "
        f"failed on exactly the dangerous commands of its sample ({allowed})."
    )

    big = _condition(down200)
    minimise = down200["minimise"]
    _require(down200["decision"]["verdict"] == "BLOCK", "the N=200 run did not block")
    _require(big["delta_high"] < -float(down200["manifest"]["delta"]), "N=200 bound not cleared")
    _require(minimise is not None and "bundle" in minimise, "no minimised failure")
    assert minimise is not None
    bundle = minimise["bundle"]
    _require(
        bundle["seal_valid"] and bundle["fingerprint_matches_original_trial"],
        "the bundle does not match its failure",
    )
    divergence = minimise["divergence"]
    out.append(
        "- At the pre-registered N=200 the gate blocked the fail-open variant: A "
        f"{big['baseline']['successes']}/{big['baseline']['n']} vs B "
        f"{big['candidate']['successes']}/{big['candidate']['n']}, bounds "
        f"{_bounds(big['delta_low'], big['delta_high'])}, entirely below "
        f"-{down200['manifest']['delta']:.2f}. The first B failure with a passing A pair, "
        f"`{bundle['trial_id']}`, diverges from its A pair after the injected "
        f"`{divergence['after_injection']}`: A records `{divergence['left']}`, B "
        f"`{divergence['right']}`. The first differing boundary event is at trace index "
        f"{divergence['common_prefix']} (zero-based). The minimiser kept "
        f"`{minimise['minimize']['kept']}` (`{minimise['minimize']['minimality']}`, "
        f"{minimise['minimize']['trials_run']} live re-run) and the committed bundle replays "
        f"{minimise['replay']['status']}; replay serves the recorded answers, so it needs no "
        "key."
    )

    small = _condition(down50)
    sample = down50["arms"]["baseline"]["sample"]
    _require(down50["decision"]["verdict"] == "INCONCLUSIVE", "N=50 verdict changed")
    _require(small["delta_high"] > -float(down50["manifest"]["delta"]), "N=50 bound changed")
    manifest = down50["manifest"]
    out.append(
        "- At N=50 the same comparison was INCONCLUSIVE, not the pre-registered BLOCK. B again "
        "failed on every dangerous command it saw, but the 50 seeded commands held "
        f"{_share(sample['dangerous'], down50['arms']['baseline']['trials'])} dangerous ones "
        f"against {_share(manifest['population_dangerous'], manifest['population_size'])} in "
        f"the population the expectation was computed on, so B scored "
        f"{small['candidate']['successes']}/{small['candidate']['n']} and the upper bound, "
        f"{small['delta_high']:.4f}, did not clear -{manifest['delta']:.2f}. The verdict is final "
        "and was not re-run; the expectation was a population share applied to a fixed seeded "
        "sample."
    )

    every = _condition(whole)
    wbase, wcand = whole["arms"]["baseline"], whole["arms"]["candidate"]
    newly = wcand["applied_on_dangerous"].get("unavailable-allowed", 0)
    _require(whole["decision"]["verdict"] == "BLOCK", "secondary verdict changed")
    _require(wbase["applied"] == {"unavailable": wbase["trials"]}, "A did not fail closed")
    _require(_fails(wbase) == wbase["sample"]["dangerous_allowed"], "A's failures changed")
    _require(_fails(wcand) == _fails(wbase) + newly, "B's failures are not A's plus asks")
    out.append(
        "- On the whole labelled set (the secondary run) the gate also blocked: A "
        f"{every['baseline']['successes']}/{every['baseline']['n']} vs B "
        f"{every['candidate']['successes']}/{every['candidate']['n']}, bounds "
        f"{_bounds(every['delta_low'], every['delta_high'])}. A's {_fails(wbase)} failures "
        "are dangerous commands the static policy allows, which no outage handling changes; "
        f"B failed on the same {_fails(wbase)} plus {newly} dangerous `ask`s it allowed."
    )

    lbase, lcand = low["arms"]["baseline"], low["arms"]["candidate"]
    unconfident = lcand["applied"].get("relaxed-unconfident", 0)
    _require(low["decision"]["verdict"] == "PASS", "low-confidence verdict changed")
    _require(lcand["applied_on_dangerous"].get("relaxed-unconfident", 0) == 0, "B relaxed danger")
    _require(_fails(lbase) == _fails(lcand) == 0, "a low-confidence arm failed")
    _require(lbase["applied"].get("relaxed", 0) == 0, "A relaxed at capped confidence")
    cap = low["manifest"]["fault_params"]["decision_low_confidence"]["confidence_max"]
    out.append(
        "- Capped confidence alone did not separate the arms (PASS, "
        f"{lbase['trials']}/{lbase['trials']} each): A never relaxed at confidence {cap}, B "
        f"relaxed {unconfident} of {lcand['trials']} commands on an unconfident read-only or "
        "build/test answer, none of them dangerous, as pre-registered."
    )

    sbase, scand = static["arms"]["baseline"], static["arms"]["candidate"]
    _require(static["decision"]["verdict"] == "PASS", "A-vs-C verdict changed")
    _require(_fails(sbase) == _fails(scand) == 0, "an A-vs-C arm failed")
    applied = ", ".join(
        f"{sbase['applied'][label]} `{label}`" for label in _applied_order(sbase["applied"])
    )
    out.append(
        "- With the endpoint up and nothing injected, A and C both passed "
        f"{sbase['trials']}/{sbase['trials']} (PASS). A acted on the live answers ({applied} "
        f"of {sbase['trials']} trials) without allowing a dangerous command or denying a benign "
        "one."
    )
    return out


def _names(experiment_ids: Sequence[str]) -> str:
    return ", ".join(f"`{name}`" for name in experiment_ids[:-1]) + f" and `{experiment_ids[-1]}`"


def _re_derived(data: Obj) -> str:
    """The post-run normalisations, checked against the gate output recorded at run time."""
    for experiment_id in sorted({*RE_DERIVED, *CP_RE_DERIVED}):
        run = _find(data["runs"], experiment_id)
        store = HERE / run["store"]
        _require(
            (store / "gate.txt").read_bytes() == (store / "report.md").read_bytes(),
            f"{run['store']}: report.md differs from the gate output recorded at run time",
        )
    return (
        "After the 95% Wilson quantile was pinned in `src/arci/stats.py`, the `decision.json`, "
        f"`report.md` and `junit.xml` of {_names(RE_DERIVED)} were re-derived from their sealed "
        "`manifest.json` and `trials.jsonl` with `arci gate` (four Wilson display fields per "
        "affected decision changed by one or two ulps, changing the decision seal; both reports "
        "came out identical and the "
        "verdicts and exit codes are unchanged); `run.txt`, `gate.txt` and the raw `runs/` output "
        "are untouched. After the Clopper-Pearson tail comparisons in `src/arci/stats.py` were "
        "made exact with integer arithmetic (the earlier libm-based evaluation differed in the "
        "last digits between macOS and Linux), the `decision.json` files of "
        f"{_names(CP_RE_DERIVED)} were re-derived the same way: their Clopper-Pearson bounds and "
        "the difference bounds derived from them moved in the last digits, changing the decision "
        "seal, while `report.md`, `junit.xml`, the verdicts and the exit codes came out "
        "identical; `run.txt`, `gate.txt` and the raw `runs/` output are untouched."
    )


def render_readme(data: Obj) -> str:
    runs = data["runs"]
    pre = data["preflight"]
    receipt = pre["receipt"]
    totals = data["totals"]
    valid, invalid = totals["valid"], totals["invalid"]
    price = float(totals["usd_per_million_input"])
    day = data["date"]
    script = data["run_script"]
    planned = data["planned"]
    retries = [run for run in runs if run["experiment_id"].endswith("-retry-2")]
    attempts = [run for run in runs if run["invalid_attempt"] is not None]
    minimisers = [run for run in runs if run["minimise"] is not None]
    clean_c = _find(runs, "guardrail-live-c-ask-clean-50")
    seeds = {run["manifest"]["base_seed"] for run in runs}
    _require(len(seeds) == 1, "runs differ in base seed")
    _require(all(run["pairs"]["seeds_consecutive_from_base"] for run in runs), "seed gaps")
    (base_seed,) = seeds
    replays = [
        f".venv/bin/arci replay docs/results/guardrail/{run['store']}/min-bundle.json"
        for run in minimisers
        if run["minimise"] is not None and "bundle" in run["minimise"]
    ]
    lines = [
        "# Results: frontier-scout's guard under decision faults, live",
        "",
        "<!-- Generated by summarize.py from the committed evidence. Edit summarize.py, then run"
        " it with --write; do not edit this file by hand. -->",
        "",
        "The pre-registered guardrail experiment "
        f"([`{data['preregistration']}`](../../../{data['preregistration']})), run on {day} with "
        f"[`{script['path']}`](../../../{script['path']}) unchanged: endpoint "
        f"`{receipt['endpoint']}`, pinned model `{pre['model']}`, "
        f"{script['rpm']} paced trial starts per minute, {script['workers']} workers. "
        f"{len(runs)} runs: {valid['runs']} valid, {invalid['runs']} invalid attempts, "
        f"{len(retries)} retries. Each run's sealed store (`manifest.json`, `trials.jsonl`, "
        "`decision.json`, `report.md`, `junit.xml`, plus the `arci run` and `arci gate` output "
        f"as `run.txt` and `gate.txt`) is under [`{day}/<experiment_id>/`]({day}/). On macOS "
        "(arm64) and Linux (x86-64), `arci gate` re-derives every committed `decision.json` from "
        "`manifest.json` and `trials.jsonl` byte for byte, and "
        "`tests/unit/examples/test_guardrail_results.py`, which CI runs on Ubuntu and macOS, "
        "repeats that check for every store. "
        f"{_re_derived(data)} "
        "This page and [`metrics.json`](metrics.json) are generated by "
        "[`summarize.py`](summarize.py) from those files and the pre-registration; "
        "`summarize.py --check` fails if either is stale.",
        "",
        "## Preflight",
        "",
        "`arci preflight --allow-unlisted-model` on a manifest built for the purpose "
        f"(`{pre['manifest_experiment_id']}`, never run: "
        f"[`preflight.manifest.json`]({day}/preflight.manifest.json)) verified the endpoint and "
        "the pin with one smoke request before the first trial "
        f"([`preflight.txt`]({day}/preflight.txt), "
        f"[`preflight.receipt.json`]({day}/preflight.receipt.json)):",
        "",
        "```json",
        pre["receipt_line"],
        "```",
        "",
        "| Item | Value |",
        "|---|---|",
        f"| Endpoint | `{receipt['endpoint']}` |",
        f"| Pinned model / reported by the smoke request | `{pre['model']}` / "
        f"`{receipt['model']}` |",
        f"| Receipt `manifest_sha256` = sealed preflight manifest | `{pre['manifest_sha256']}` |",
        f"| Smoke request usage | {receipt['usage']['input_tokens']} input, "
        f"{receipt['usage']['output_tokens']} output tokens |",
        f"| Latency | {receipt['latency_ms']} ms |",
        f"| Request rate in every run's manifest | {pre['max_requests_per_minute']} per minute |",
        "",
        "## The runs",
        "",
        "In execution order. A is the shipped rule, B the fail-open variant, C static only; "
        "the population size is in brackets.",
        "",
        *_runs_table(runs),
        "",
        f"Gate on every run: {_gate_settings(runs)}. Prior runs are listed in each sealed "
        "manifest and in each `report.md`.",
        "",
        "## Pre-registered vs observed",
        "",
        "The pre-registered cells are quoted verbatim from the pre-registration. They were "
        "computed offline over the whole population (`about` marks an approximate "
        "expectation); the observed counts are over the fixed seeded sample of N commands per "
        "arm, whose dangerous share is in the last column.",
        "",
        *_preregistered_table(data),
        "",
        "## A's applied decisions",
        "",
        "What the guard did with each answer, from the argument of its one `record` call "
        '(`events[].kind == "tool_start"`, `payload.tool == "record"`), matched by `call_id` '
        "to an accepted recording and to `final_state`. Each cell is the trial count, with the "
        "dangerous commands among them in brackets; the denominator is the run's trials, not "
        "the pre-registration's 182 commands. Unvalidated: trials whose record call could not "
        "be matched (shown separately, none counted above).",
        "",
        *_applied_table(runs, "baseline"),
        "",
        "The candidate arm (B or C) for comparison:",
        "",
        *_applied_table(runs, "candidate"),
        "",
        "## Totals",
        "",
        "Per run, from the decision recordings in `trials.jsonl` (tool `decision:systemone`). "
        "Recordings, tokens and cost match each run's `report.md` (checked by `summarize.py`). "
        "An injected `decision_unavailable` recording is a 529 from the boundary that never "
        "reached the endpoint (`upstream: null`); a `decision_low_confidence` recording is a "
        "real upstream answer whose confidence the harness capped, so it is both injected and "
        "an upstream call.",
        "",
        *_usage_table(runs, price),
        "",
        "| Totals | Valid runs | Invalid attempts |",
        "|---|---:|---:|",
        f"| Runs | {valid['runs']} | {invalid['runs']} |",
        f"| Trials | {_int(valid['trials'])} | {_int(invalid['trials'])} |",
        f"| Decision recordings | {_int(valid['decision_recordings'])} "
        f"| {_int(invalid['decision_recordings'])} |",
        f"| Injected by the harness | {_counts(valid['injected_recordings'])} "
        f"| {_counts(invalid['injected_recordings'])} |",
        f"| Upstream calls | {_int(valid['upstream_calls'])} | {_int(invalid['upstream_calls'])} |",
        f"| Upstream status | {_counts(valid['upstream_status'])} "
        f"| {_counts(invalid['upstream_status'])} |",
        f"| Upstream calls retried (attempts > 1) | {valid['upstream_retried']} "
        f"| {invalid['upstream_retried']} |",
        f"| Reported model | {_counts(valid['reported_models'])} "
        f"| {_counts(invalid['reported_models'])} |",
        f"| Input tokens | {_int(valid['input_tokens'])} | {_int(invalid['input_tokens'])} |",
        f"| Output tokens | {_int(valid['output_tokens'])} | {_int(invalid['output_tokens'])} |",
        f"| Estimated cost at the list price (USD {totals['usd_per_million_input']} per million "
        f"input tokens, read {totals['price_read']}) | {_usd(valid['estimated_usd'])} "
        f"| {_usd(invalid['estimated_usd'])} |",
        "",
        "Not in the totals above: the preflight smoke request "
        f"({receipt['usage']['input_tokens']} input, {receipt['usage']['output_tokens']} output "
        f"tokens, from its receipt), and the minimiser's {totals['minimiser_trials_run']} live "
        f"re-run{'s' if totals['minimiser_trials_run'] != 1 else ''} with the fault removed, "
        "whose decision usage `arci minimize` does not retain. The estimate is therefore "
        "neither the complete experiment spend nor billed spend. Replay serves recorded answers "
        "and adds no upstream usage. Pre-registered: "
        f'"{planned[0]["cost_statement"]}"',
        "",
        "## What this shows",
        "",
        *_shows(data),
        "",
        "## What this does not show",
        "",
        "- Anything about a shipped regression: B is a constructed fail-open variant, not code "
        "anyone released. The experiment shows what the gate says if someone did.",
        "- The decision model's accuracy beyond this sample. The clean A-vs-C run covered "
        f"{clean_c['arms']['baseline']['distinct_commands']} distinct commands in "
        f"{clean_c['arms']['baseline']['trials']} trials; A's correct outcomes there are a "
        "small, sampled observation, and the oracle grades only allow/ask/deny against three "
        "yes/no labels.",
        "- Provider behaviour under load or failure: no upstream 429 or 529 was seen at "
        f"{pre['max_requests_per_minute']} paced trial starts per minute, and every outage "
        "here is injected by the harness.",
        "- Billed spend, or the minimiser's spend (see Totals).",
        "",
        "## Limits",
        "",
        "- Every run uses the manifests' fixed seeds, consecutive from "
        f"{base_seed}, with each A trial paired to the B or C trial on the same seed and "
        "command (checked), and one seed always draws the same command from one population "
        "(checked across runs). So the N=50 `ask` runs share one sample of 50 commands, the "
        "`ask` N=200 run starts with it, and the secondary run draws from the whole set; "
        "another seed set would give different counts.",
        "- Live answers are sampled. The minimised bundle is `reduced`, never `1-minimal`, and "
        "the replay serves the recorded answer rather than asking the model again.",
        "- One labelled set written by the maintainer, one model version, one static policy "
        "(frontier-scout's own) defining the `ask` population. The hook ran through the "
        "boundary on loopback, not inside a coding-agent session, so its own receipts are not "
        "written here.",
        "",
        "## Re-check",
        "",
        "```bash",
        'export PYTHONPATH="$PWD"',
        ".venv/bin/pytest tests/unit/examples/test_guardrail_results.py",
        ".venv/bin/python docs/results/guardrail/summarize.py --check",
        *replays,
        "```",
        "",
        "The test copies each store's `manifest.json` and `trials.jsonl` to a temporary "
        "directory, runs `arci gate` there and compares the new `decision.json` with the "
        "committed bytes; none of these commands needs a key or makes a network call."
        + (
            " Replay was verified on the originating checkout; it requires the sealed "
            "interpreter path and example modules. Gate re-derivation does not execute that "
            "interpreter."
            if replays
            else ""
        ),
    ]
    if attempts:
        lines.insert(
            lines.index("## Pre-registered vs observed"),
            f"Invalid attempts are kept under `{day}/attempt-*-invalid/`.\n",
        )
    return "\n".join(lines) + "\n"


def render_pr_body(data: Obj) -> str:
    runs = data["runs"]
    totals = data["totals"]
    valid = totals["valid"]
    receipt = data["preflight"]["receipt"]
    lines = [
        "## Summary",
        "",
        "Publishes the pre-registered guardrail experiment (`examples/guardrail_agent/`), run "
        f"once against the live decision endpoint on {data['date']} with `run.sh` unchanged: "
        "sealed stores, the preflight receipt, per-run gate reports, the minimised and replayed "
        "failure, a generated write-up (`docs/results/guardrail/README.md`, every number "
        "extracted by `docs/results/guardrail/summarize.py`), and an offline test that "
        "re-derives every committed `decision.json` byte for byte with `arci gate`.",
        "",
        "## Results",
        "",
        "| Run | Arms | Population | N per arm | A | B or C | Bounds on the difference | Verdict |",
        "|---|---|---|---:|---:|---:|---|---|",
    ]
    for run in runs:
        condition = _condition(run)
        lines.append(
            f"| `{run['experiment_id']}` | {_arms(run)} | `{run['manifest']['population']}` "
            f"| {run['manifest']['n_per_arm']} "
            f"| {condition['baseline']['successes']}/{condition['baseline']['n']} "
            f"| {condition['candidate']['successes']}/{condition['candidate']['n']} "
            f"| {_bounds(condition['delta_low'], condition['delta_high'])} | {_verdict(run)} |"
        )
    lines += ["", *_shows(data, name_model=False)]
    lines += [
        "",
        f"- Invalid attempts: {totals['invalid']['runs']}; retries: "
        f"{sum(run['experiment_id'].endswith('-retry-2') for run in runs)}.",
        f"- Usage: {valid['upstream_calls']} live decision requests (status "
        f"{_counts(valid['upstream_status'])}, none retried), {_int(valid['input_tokens'])} "
        f"input and {_int(valid['output_tokens'])} output tokens, about "
        f"{_usd(valid['estimated_usd'])} at the list price read {totals['price_read']}; plus "
        f"one preflight request ({receipt['usage']['input_tokens']} input tokens) and "
        f"{totals['minimiser_trials_run']} minimiser re-run whose usage is not retained. "
        "Not billed spend.",
        "",
        "## Files",
        "",
        f"- `docs/results/guardrail/{data['date']}/`: the stores, preflight files and summary.",
        "- `docs/results/guardrail/README.md`, `metrics.json`, `summarize.py`: the generated "
        "write-up and its extractor.",
        "- `tests/unit/examples/test_guardrail_results.py`: offline byte-for-byte re-derivation "
        "of every committed guardrail decision.",
        "- `docs/results/README.md` (pointer) and `CHANGELOG.md` (Unreleased entry).",
        "",
        "## Re-check",
        "",
        "```bash",
        'export PYTHONPATH="$PWD"',
        ".venv/bin/pytest tests/unit/examples/test_guardrail_results.py",
        ".venv/bin/python docs/results/guardrail/summarize.py --check",
        "```",
    ]
    return "\n".join(lines) + "\n"


def render_metrics(data: Obj) -> str:
    return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0] if __doc__ else None)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true", help="regenerate README.md and metrics.json")
    mode.add_argument("--check", action="store_true", help="fail if either file is stale")
    mode.add_argument("--pr-body", action="store_true", help="print the PR description")
    args = parser.parse_args(argv)
    try:
        data = collect()
        outputs = {README: render_readme(data), METRICS: render_metrics(data)}
        pr_body = render_pr_body(data)
    except EvidenceError as exc:
        print(f"evidence check failed: {exc}", file=sys.stderr)
        return 2
    if args.pr_body:
        sys.stdout.write(pr_body)
        return 0
    if args.write:
        for path, text in outputs.items():
            path.write_text(text, encoding="utf-8")
            print(f"wrote {_rel(path)}")
        return 0
    stale = [
        _rel(path)
        for path, text in outputs.items()
        if not path.exists() or path.read_text(encoding="utf-8") != text
    ]
    if stale:
        print(f"stale: {', '.join(stale)}; run summarize.py --write", file=sys.stderr)
        return 1
    print("README.md and metrics.json match the committed evidence")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
