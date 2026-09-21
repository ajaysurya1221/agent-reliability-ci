"""Deterministic human- and machine-readable experiment reports."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from collections.abc import Sequence

from arci.schema import (
    ArmStats,
    GateDecision,
    Manifest,
    Outcome,
    TrialEnvelope,
    Verdict,
)

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


def render_markdown(
    manifest: Manifest, decision: GateDecision, trials: Sequence[TrialEnvelope]
) -> str:
    """Render a deterministic Markdown gate report."""
    lines = [
        f"# Experiment {manifest.experiment_id}",
        "",
        _VERDICT_MEANINGS[decision.verdict],
        "",
        "## Gate configuration",
        "",
        "| Alpha | Delta | K (gating conditions) | Per-arm confidence | n_per_arm |",
        "|---:|---:|---:|---:|---:|",
        (
            f"| {_number(decision.alpha)} | {_number(decision.delta)} | "
            f"{decision.k_conditions} | {decision.per_arm_confidence:.4%} | "
            f"{decision.n_per_arm} |"
        ),
    ]

    for condition in decision.conditions:
        baseline = _arm_summary(condition.baseline)
        candidate = _arm_summary(condition.candidate)
        role = "Gating" if condition.is_gating else "Descriptive (ceiling fault)"
        confidence = f"Clopper-Pearson ({decision.per_arm_confidence:.4%})"
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
                    "| Bounds on difference (candidate - baseline) | — | "
                    f"{_interval(condition.delta_low, condition.delta_high)} |"
                ),
                (f"| Candidate hard violations | — | {condition.candidate_hard_violations} |"),
                f"| Condition verdict | — | **{condition.verdict.value}** |",
            ]
        )

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
