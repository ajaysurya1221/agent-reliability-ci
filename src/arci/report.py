"""Deterministic human- and machine-readable experiment reports."""

from __future__ import annotations

import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from collections.abc import Sequence
from typing import TypedDict, cast

from pydantic import JsonValue

from arci.reliability import IID_ASSUMPTION, UNAVAILABLE_SMALL_N, pass_k_report
from arci.schema import (
    DECISION_TOOL,
    ArmStats,
    Condition,
    FaultSpec,
    GateDecision,
    Manifest,
    Outcome,
    TrialEnvelope,
    Verdict,
)


class FaultAccounting(TypedDict):
    condition_id: str
    fault: str
    arm: str
    trials: int
    injections: int
    trials_fired: int
    status: str


class ArmToolSummary(TypedDict):
    arm: str
    trials: int
    uninjected_failure_trials: int
    uninjected_then_passed: int
    uninjected_then_not_passed: int


class ToolOutcomeRow(TypedDict):
    arm: str
    tool: str
    trials: int
    trials_started: int
    trials_not_started: int
    starts: int
    uninjected_failures: int
    uninjected_failure_trials: int


class ToolOutcomes(TypedDict):
    arms: list[ArmToolSummary]
    tools: list[ToolOutcomeRow]


TOOL_OUTCOMES_HEADING = "Tool outcomes (descriptive)"
TOOL_OUTCOMES_INTRO = (
    "Counts of recorded tool attempts. An uninjected failure is a recorded tool_finish "
    "that failed with no injection marker; the record does not show why it failed, and "
    "an earlier injected fault can be the cause. A tool with no recorded start in a trial "
    "may simply not be needed by that task; compare the two arms. Retries by middleware "
    "count as attempts. Counts are descriptive and decide nothing."
)


def tool_outcomes(trials: Sequence[TrialEnvelope]) -> ToolOutcomes:
    """Count recorded attempts literally, without inferring a failure's cause."""
    arms = [
        ArmToolSummary(
            arm=arm,
            trials=0,
            uninjected_failure_trials=0,
            uninjected_then_passed=0,
            uninjected_then_not_passed=0,
        )
        for arm in ("baseline", "candidate")
    ]
    by_arm = {row["arm"]: row for row in arms}
    starts: Counter[tuple[str, str]] = Counter()
    started: Counter[tuple[str, str]] = Counter()
    failures: Counter[tuple[str, str]] = Counter()
    failed: Counter[tuple[str, str]] = Counter()
    tools: set[str] = set()
    for trial in trials:
        summary = by_arm.get(trial.arm)
        if summary is None:
            continue
        summary["trials"] += 1
        trial_started: set[tuple[str, str]] = set()
        trial_failed: set[tuple[str, str]] = set()
        for event in trial.events:
            tool = event.payload.get("tool")
            if not isinstance(tool, str):
                continue
            key = (trial.arm, tool)
            marker = event.payload.get("injected_by")
            if event.kind == "tool_start":
                starts[key] += 1
                trial_started.add(key)
                tools.add(tool)
            elif (
                event.kind == "tool_finish"
                and event.payload.get("ok") is False
                and (marker is None or (isinstance(marker, str) and marker == ""))
            ):
                failures[key] += 1
                trial_failed.add(key)
                tools.add(tool)
        started.update(trial_started)
        failed.update(trial_failed)
        if trial_failed:
            summary["uninjected_failure_trials"] += 1
            if trial.outcome is Outcome.PASS:
                summary["uninjected_then_passed"] += 1
            else:
                summary["uninjected_then_not_passed"] += 1
    rows = [
        ToolOutcomeRow(
            arm=summary["arm"],
            tool=tool,
            trials=summary["trials"],
            trials_started=started[summary["arm"], tool],
            trials_not_started=summary["trials"] - started[summary["arm"], tool],
            starts=starts[summary["arm"], tool],
            uninjected_failures=failures[summary["arm"], tool],
            uninjected_failure_trials=failed[summary["arm"], tool],
        )
        for tool in sorted(tools)
        for summary in arms
    ]
    return ToolOutcomes(arms=arms, tools=rows)


def _tool_outcome_span(tool: str) -> str:
    if not tool:
        return "(empty name)"
    # report._cell stays as v1 has it; a bare CR is a Markdown line ending too.
    value = _cell(tool).replace("\r", "<br>")
    longest = run = 0
    for char in value:
        run = run + 1 if char == "`" else 0
        longest = max(longest, run)
    fence = "`" * (longest + 1)
    # Padding separates a literal backtick from the fence and preserves edge spaces.
    padding = (
        " "
        if longest or (value.startswith(" ") and value.endswith(" ") and value.strip(" "))
        else ""
    )
    return f"{fence}{padding}{value}{padding}{fence}"


def tool_outcomes_markdown(trials: Sequence[TrialEnvelope]) -> list[str]:
    summary = tool_outcomes(trials)
    lines = [
        "",
        f"## {TOOL_OUTCOMES_HEADING}",
        "",
        TOOL_OUTCOMES_INTRO,
        "",
        "| Arm | Trials | Trials with an uninjected failure | Then passed | Then not passed |",
        "|---|---:|---:|---:|---:|",
    ]
    lines.extend(
        f"| {row['arm']} | {row['trials']} | {row['uninjected_failure_trials']} | "
        f"{row['uninjected_then_passed']} | {row['uninjected_then_not_passed']} |"
        for row in summary["arms"]
    )
    lines.append("")
    if not summary["tools"]:
        return [*lines, "No tool starts recorded."]
    lines.extend(
        [
            "| Tool | Arm | Trials | Started in | Not started in | Starts | "
            "Uninjected failures | Trials with one |",
            "|---|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    lines.extend(
        f"| {_tool_outcome_span(row['tool'])} | {row['arm']} | {row['trials']} | "
        f"{row['trials_started']} | {row['trials_not_started']} | {row['starts']} | "
        f"{row['uninjected_failures']} | {row['uninjected_failure_trials']} |"
        for row in summary["tools"]
    )
    return lines


def _fault_name(fault: FaultSpec) -> str | None:
    """Resolve the runner's recorded name without loading user code in this process."""
    from arci.perturb import REGISTRY

    if fault.name in REGISTRY:
        return fault.name
    if ":" not in fault.name:
        return None
    # A broken, noisy, exiting or hanging factory must not prevent a report.
    script = """
import contextlib, json, os, sys
from arci.perturb import build
from arci.schema import FaultSpec
with open(os.devnull, 'w') as sink, contextlib.redirect_stdout(sink):
    name = build(FaultSpec.model_validate_json(sys.stdin.read())).name
print(json.dumps(name))
"""
    try:
        result = subprocess.run(
            [sys.executable, "-c", script],
            input=fault.model_dump_json(),
            capture_output=True,
            text=True,
            timeout=2,
            check=True,
        )
        name: object = json.loads(result.stdout)
        return name if isinstance(name, str) and name else None
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def _fault_scope(fault: FaultSpec, payload: dict[str, JsonValue]) -> bool:
    tool, occurrence = payload.get("tool"), payload.get("occurrence")
    if not isinstance(tool, str) or not isinstance(occurrence, int):
        return True  # Missing scope evidence cannot exclude a declaration.
    at = 0 if fault.at_occurrence is None else fault.at_occurrence
    if fault.name in {"decision_unavailable", "decision_low_confidence"}:
        return tool == DECISION_TOOL and (
            occurrence >= at if fault.name == "decision_unavailable" else occurrence == at
        )
    return (
        not tool.startswith("decision:")
        and (fault.tool is None or tool == fault.tool)
        and occurrence == at
    )


def fault_accounting(
    conditions: Sequence[Condition], trials: Sequence[TrialEnvelope]
) -> list[FaultAccounting]:
    """Attribute each injection once, retaining ambiguous and unknown observations."""
    rows: list[FaultAccounting] = []
    resolved: dict[str, str | None] = {}
    declared = {condition.condition_id for condition in conditions}
    observed_only = tuple(
        Condition(condition_id=name)
        for name in sorted({trial.condition_id for trial in trials} - declared)
    )
    for condition in sorted((*conditions, *observed_only), key=lambda c: c.condition_id):
        declarations = list(enumerate(condition.faults))
        for _, fault in declarations:
            key = fault.model_dump_json()
            if key not in resolved:
                resolved[key] = _fault_name(fault)
        for arm in ("baseline", "candidate"):
            selected = [
                t for t in trials if t.condition_id == condition.condition_id and t.arm == arm
            ]
            injections: Counter[int] = Counter()
            fired: Counter[int] = Counter()
            unknown: Counter[str] = Counter()
            unknown_trials: Counter[str] = Counter()
            ambiguous: set[int] = set()
            for trial in selected:
                starts = {
                    e.payload["call_id"]: e.payload
                    for e in trial.events
                    if e.kind == "tool_start" and isinstance(e.payload.get("call_id"), str)
                }
                seen: set[int] = set()
                unseen: set[str] = set()
                for event in trial.events:
                    name = event.payload.get("injected_by")
                    if event.kind != "tool_finish" or not isinstance(name, str) or not name:
                        continue
                    call_id = event.payload.get("call_id")
                    scope = (
                        starts.get(call_id, event.payload)
                        if isinstance(call_id, str)
                        else event.payload
                    )
                    candidates = [
                        i
                        for i, fault in declarations
                        if resolved[fault.model_dump_json()] in (name, None)
                        and _fault_scope(fault, scope)
                    ]
                    if (
                        len(candidates) == 1
                        and resolved[condition.faults[candidates[0]].model_dump_json()] == name
                    ):
                        injections[candidates[0]] += 1
                        seen.add(candidates[0])
                    else:
                        ambiguous.update(candidates)
                        unknown[name] += 1
                        unseen.add(name)
                fired.update(seen)
                unknown_trials.update(unseen)
            for i, fault in sorted(declarations, key=lambda item: (item[1].name, item[0])):
                label = fault.name
                if sum(f.name == fault.name for f in condition.faults) > 1:
                    label += (
                        f" [declaration {i + 1}; tool={fault.tool or '*'}; "
                        f"occurrence={fault.at_occurrence or 0}]"
                    )
                rows.append(
                    FaultAccounting(
                        condition_id=condition.condition_id,
                        fault=label,
                        arm=arm,
                        trials=len(selected),
                        injections=injections[i],
                        trials_fired=fired[i],
                        status="cannot attribute"
                        if i in ambiguous or resolved[fault.model_dump_json()] is None
                        else "observed"
                        if fired[i]
                        else "declared, never fired",
                    )
                )
            for name in sorted(unknown):
                rows.append(
                    FaultAccounting(
                        condition_id=condition.condition_id,
                        fault=name,
                        arm=arm,
                        trials=len(selected),
                        injections=unknown[name],
                        trials_fired=unknown_trials[name],
                        status="unattributed",
                    )
                )
    # Preserve the established name/arm order for ordinary v1 report rows.
    return sorted(
        rows,
        key=lambda row: (
            row["condition_id"],
            row["status"] == "unattributed",
            row["fault"],
            row["arm"],
        ),
    )


def fault_markdown(conditions: Sequence[Condition], trials: Sequence[TrialEnvelope]) -> list[str]:
    lines = [
        "",
        "## Fault accounting",
        "",
        "Recorded tool_finish injections, grouped by declared fault name; repeated "
        "declarations of the same name are indistinguishable. Counts are descriptive.",
        "",
    ]
    if any(len({f.name for f in c.faults}) != len(c.faults) for c in conditions):
        lines[3] = (
            "Recorded tool_finish injections, attributed by declaration, tool and occurrence; "
            "ambiguous observations are unattributed. Counts are descriptive."
        )
    rows = fault_accounting(conditions, trials)
    if not rows:
        return [*lines, "No faults declared."]
    lines.extend(
        [
            "| Condition | Fault | Arm | Trials | Injections | Trials fired | Status |",
            "|---|---|---|---:|---:|---:|---|",
        ]
    )
    lines.extend(
        f"| `{_cell(row['condition_id'])}` | `{_cell(row['fault'])}` | {row['arm']} | "
        f"{row['trials']} | {row['injections']} | {row['trials_fired']} | {row['status']} |"
        for row in rows
    )
    return lines


USD_PER_MTOK_INPUT = 0.042
_LIST_PRICE_DATE = "2026-09-22"

_VERDICT_MEANINGS: dict[Verdict, str] = {
    Verdict.PASS: (
        "PASS means the candidate is non-inferior to the baseline within the configured delta; "
        "it says nothing about absolute reliability."
    ),
    Verdict.BLOCK: (
        "BLOCK means the candidate is worse than the baseline by more than the configured delta, "
        "or it broke a hard invariant."
    ),
    Verdict.INCONCLUSIVE: (
        "INCONCLUSIVE means there is not enough evidence either way: the confidence interval "
        "stays non-green, and no regression is claimed."
    ),
    Verdict.ERROR: (
        "ERROR means the experiment is invalid or the harness or grader failed, so no reliability "
        "conclusion can be drawn."
    ),
}


def _number(value: float) -> str:
    if abs(value) < 0.00005:
        value = 0.0
    return f"{value:.4f}"


def _interval(low: float, high: float) -> str:
    return f"[{_number(low)}, {_number(high)}]"


def _cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", "<br>")


def _arm_summary(stats: ArmStats) -> tuple[str, str, str, str, str]:
    return (
        str(stats.n),
        str(stats.successes),
        f"{stats.rate:.1%}",
        _interval(stats.wilson_low, stats.wilson_high),
        _interval(stats.cp_low, stats.cp_high),
    )


def _failure_clusters(trials: Sequence[TrialEnvelope]) -> list[tuple[str, int, str]]:
    candidate_failures = [
        trial for trial in trials if trial.arm == "candidate" and trial.outcome is not Outcome.PASS
    ]
    counts = Counter(trial.failure_fingerprint or "unfingerprinted" for trial in candidate_failures)
    examples: dict[str, list[str]] = defaultdict(list)
    for trial in candidate_failures:
        fingerprint = trial.failure_fingerprint or "unfingerprinted"
        if trial.failure_detail:
            examples[fingerprint].append(trial.failure_detail)
    return [
        (fingerprint, count, min(examples[fingerprint], default="No detail recorded."))
        for fingerprint, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]


def _decision_usage(trials: Sequence[TrialEnvelope]) -> tuple[int, int, int]:
    recorded_decisions = 0
    input_tokens = 0
    output_tokens = 0
    for trial in trials:
        for recorded in trial.recording:
            if recorded.tool != DECISION_TOOL:
                continue
            recorded_decisions += 1
            value = recorded.result.value
            if not isinstance(value, dict):
                continue
            body = cast(dict[str, JsonValue], value).get("body")
            if not isinstance(body, dict):
                continue
            usage = cast(dict[str, JsonValue], body).get("usage")
            if not isinstance(usage, dict):
                continue
            raw_input = usage.get("input_tokens", 0)
            raw_output = usage.get("output_tokens", 0)
            if isinstance(raw_input, int) and not isinstance(raw_input, bool):
                input_tokens += raw_input
            if isinstance(raw_output, int) and not isinstance(raw_output, bool):
                output_tokens += raw_output
    return recorded_decisions, input_tokens, output_tokens


def _pass_k_lines(decision: GateDecision, ks: Sequence[int]) -> list[str]:
    report = pass_k_report(decision, ks)
    lines = [
        "",
        "## Descriptive pass^k (not part of the verdict)",
        "",
        (
            "Opt-in and descriptive: it never changes the verdict, a seal or decision.json. "
            "Each arm of each declared condition is its own population, never pooled across "
            "conditions. pass^k = C(successes, k) / C(n, k), the share of k-trial subsets in "
            f"which every trial passed. {IID_ASSUMPTION}"
        ),
        "",
    ]
    if report.unavailable is not None:
        lines.append(f"Unavailable: {report.unavailable}.")
        return lines
    lines.extend(
        [
            "| Condition | Arm | Role | n | Successes | "
            + " | ".join(f"pass^{k}" for k in report.ks)
            + " |",
            "|---|---|---|---:|---:|" + "---:|" * len(report.ks),
        ]
    )
    for row in report.rows:
        role = "Gating" if row.is_gating else "Descriptive (ceiling fault)"
        estimates = " | ".join(
            f"unavailable ({UNAVAILABLE_SMALL_N})" if value is None else f"{value:.4f}"
            for value in row.estimates
        )
        lines.append(
            f"| `{_cell(row.condition_id)}` | {row.arm} | {role} | {row.n} | {row.successes} | "
            f"{estimates} |"
        )
    return lines


def render_markdown(
    manifest: Manifest,
    decision: GateDecision,
    trials: Sequence[TrialEnvelope],
    *,
    pass_k: Sequence[int] = (),
) -> str:
    """Render a deterministic Markdown gate report.

    `pass_k` (opt-in) adds a descriptive pass^k section; without it the report is unchanged.
    """
    lines = [
        f"# Experiment {manifest.experiment_id}",
        "",
        _VERDICT_MEANINGS[decision.verdict],
        "",
        "## Gate configuration",
        "",
        "| Alpha | Delta | K (gating conditions) | Interval method | Per-arm confidence "
        "| n_per_arm |",
        "|---:|---:|---:|---|---:|---:|",
        (
            f"| {_number(decision.alpha)} | {_number(decision.delta)} | "
            f"{decision.k_conditions} | {decision.interval_method} | "
            f"{decision.per_arm_confidence:.4%} | {decision.n_per_arm} |"
        ),
    ]

    if len(decision.looks) > 1:
        lines.extend(
            [
                "",
                "## Looks",
                "",
                f"Stopped at look {decision.stopped_at_look} of {len(decision.looks)}.",
                "",
                "| Look | Cumulative pairs | Verdict | Bounds by condition |",
                "|---:|---:|---|---|",
            ]
        )
        for look in decision.history:
            bounds = "<br>".join(
                f"`{_cell(condition.condition_id)}`: "
                f"{_interval(condition.delta_low, condition.delta_high)}"
                for condition in look.conditions
            )
            lines.append(f"| {look.look} | {look.pairs} | **{look.verdict.value}** | {bounds} |")

    recorded_decisions, input_tokens, output_tokens = _decision_usage(trials)
    if recorded_decisions:
        estimated_cost = input_tokens * USD_PER_MTOK_INPUT / 1_000_000
        lines.extend(
            [
                "",
                "## Decisions",
                "",
                "| Recorded decisions | Input tokens | Output tokens "
                "| Estimated cost at list price |",
                "|---:|---:|---:|---:|",
                (
                    f"| {recorded_decisions} | {input_tokens} | {output_tokens} | "
                    f"USD {estimated_cost:.7f} |"
                ),
                "",
                (
                    f"List price: USD {USD_PER_MTOK_INPUT:.3f} per million input tokens "
                    f"(read {_LIST_PRICE_DATE})."
                ),
                "Fixtures and replays cost nothing; this is an estimate, not billed spend.",
            ]
        )

    for condition in decision.conditions:
        baseline = _arm_summary(condition.baseline)
        candidate = _arm_summary(condition.candidate)
        role = "Gating" if condition.is_gating else "Descriptive (ceiling fault)"
        confidence = f"Clopper-Pearson ({decision.per_arm_confidence:.4%})"
        if decision.interval_method == "newcombe":
            confidence = "Clopper-Pearson (informational; the gate uses Newcombe below)"
        lines.extend(
            [
                "",
                f"## Condition: {condition.condition_id}",
                "",
                "| Measure | Baseline | Candidate / condition |",
                "|---|---:|---:|",
                f"| Role | — | {role} |",
                f"| n | {baseline[0]} | {candidate[0]} |",
                f"| Successes | {baseline[1]} | {candidate[1]} |",
                f"| Success rate | {baseline[2]} | {candidate[2]} |",
                f"| Wilson 95% (display only) | {baseline[3]} | {candidate[3]} |",
                f"| {confidence} | {baseline[4]} | {candidate[4]} |",
                (
                    f"| Bounds on difference, {decision.interval_method} "
                    f"(candidate - baseline) | — | "
                    f"{_interval(condition.delta_low, condition.delta_high)} |"
                ),
                (f"| Candidate hard violations | — | {condition.candidate_hard_violations} |"),
                f"| Condition verdict | — | **{condition.verdict.value}** |",
            ]
        )

    if pass_k:
        lines.extend(_pass_k_lines(decision, pass_k))

    lines.extend(["", "## Candidate failure clusters", ""])
    clusters = _failure_clusters(trials)
    if clusters:
        lines.extend(
            [
                "| Failure fingerprint | Count | Example failure detail |",
                "|---|---:|---|",
            ]
        )
        lines.extend(
            f"| `{_cell(fingerprint)}` | {count} | {_cell(detail)} |"
            for fingerprint, count, detail in clusters
        )
    else:
        lines.append("No candidate failures were recorded.")

    lines.extend(["", "## Earlier runs on this candidate are never hidden", ""])
    if decision.prior_runs:
        lines.extend(f"- `{_cell(run)}`" for run in decision.prior_runs)
    else:
        lines.append("- None recorded.")

    lines.extend(["", "## Reasons", ""])
    if decision.reasons:
        lines.extend(f"- Experiment: {_cell(reason)}" for reason in decision.reasons)
    else:
        lines.append("- Experiment: no global errors.")
    for condition in decision.conditions:
        for reason in condition.reasons:
            lines.append(f"- `{_cell(condition.condition_id)}`: {_cell(reason)}")

    lines.extend(fault_markdown(manifest.conditions, trials))
    lines.extend(["", f"VERDICT: {decision.verdict.value} (exit {decision.exit_code})"])
    return "\n".join(lines) + "\n"


def _trial_message(trial: TrialEnvelope) -> str:
    parts = [trial.failure_fingerprint or "no failure fingerprint"]
    if trial.failure_detail:
        parts.append(trial.failure_detail)
    return ": ".join(parts)


def render_junit(
    manifest: Manifest, decision: GateDecision, trials: Sequence[TrialEnvelope]
) -> str:
    """Render one deterministic JUnit suite per manifest condition."""
    root = ET.Element("testsuites", name=manifest.experiment_id)
    total_tests = 0
    total_failures = 0
    total_errors = 0
    decisions = {condition.condition_id: condition for condition in decision.conditions}

    for manifest_condition in manifest.conditions:
        condition_id = manifest_condition.condition_id
        condition = decisions[condition_id]
        candidates = sorted(
            (
                trial
                for trial in trials
                if trial.condition_id == condition_id and trial.arm == "candidate"
            ),
            key=lambda trial: trial.trial_id,
        )
        failures = sum(trial.outcome is Outcome.FAIL for trial in candidates)
        errors = sum(trial.outcome is Outcome.ERROR for trial in candidates)
        gate_failed = condition.verdict is not Verdict.PASS
        suite = ET.SubElement(
            root,
            "testsuite",
            name=condition_id,
            tests=str(len(candidates) + 1),
            failures=str(failures + int(gate_failed)),
            errors=str(errors),
        )
        for trial in candidates:
            case = ET.SubElement(
                suite,
                "testcase",
                classname=f"{manifest.experiment_id}.{condition_id}.candidate",
                name=trial.trial_id,
            )
            if trial.outcome is Outcome.FAIL:
                failure = ET.SubElement(
                    case,
                    "failure",
                    message=trial.failure_fingerprint or "candidate trial failed",
                    type=trial.termination.value,
                )
                failure.text = _trial_message(trial)
            elif trial.outcome is Outcome.ERROR:
                error = ET.SubElement(
                    case,
                    "error",
                    message=trial.failure_fingerprint or "candidate trial errored",
                    type=trial.termination.value,
                )
                error.text = _trial_message(trial)

        gate_case = ET.SubElement(
            suite,
            "testcase",
            classname=f"{manifest.experiment_id}.{condition_id}",
            name="gate",
        )
        if gate_failed:
            gate_failure = ET.SubElement(
                gate_case,
                "failure",
                message=f"condition verdict is {condition.verdict.value}",
                type="gate",
            )
            gate_failure.text = "; ".join(condition.reasons)

        total_tests += len(candidates) + 1
        total_failures += failures + int(gate_failed)
        total_errors += errors

    root.set("tests", str(total_tests))
    root.set("failures", str(total_failures))
    root.set("errors", str(total_errors))
    ET.indent(root, space="  ")
    return ET.tostring(root, encoding="unicode", xml_declaration=True) + "\n"
