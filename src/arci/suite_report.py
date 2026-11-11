"""Deterministic descriptive reports for the sealed suite rule."""

from __future__ import annotations

import json
from collections.abc import Sequence

from arci.report import fault_accounting, fault_markdown
from arci.schema import TrialEnvelope
from arci.suite_schema import SuiteDecision, SuiteManifest

# Verbatim sentences from docs/STATISTICS_SUITE.md, with source line wraps removed.
FIXED_GUARANTEE = "The claim is for the registered scenarios over outcome randomness."
PER_ROUND_GUARANTEE = (
    "Its error guarantee requires that in every round the suite mean "
    "over that round's scenario instances obey the relevant null, with the "
    "independence conditions above (or their conditional form)."
)
CELL_WARNING = "A suite-mean PASS can hide a regression in one cell."
ASSUMPTIONS = (
    "Statistical directional error bounds are alpha/2 under joint independence across "
    "distinct (round, cell) pairs and stationary per-cell laws (including no execution-order "
    "effect), or the per-round conditional null and conditional independence. "
    "The false-BLOCK bound covers statistical BLOCK only, not candidate hard violations. "
    "ARCI does not certify these assumptions."
)


def _cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", "<br>").replace("\r", "<br>")


def guarantee(seed_mode: str) -> str:
    return FIXED_GUARANTEE if seed_mode == "fixed" else PER_ROUND_GUARANTEE


def render_suite_json(
    manifest: SuiteManifest, decision: SuiteDecision, trials: Sequence[TrialEnvelope]
) -> str:
    return (
        json.dumps(
            {
                "decision": decision.model_dump(mode="json"),
                "guarantee": guarantee(manifest.scenario_seeds),
                "assumptions": ASSUMPTIONS,
                "cell_warning": CELL_WARNING,
                "cells_role": "descriptive; no per-cell statistical verdict",
                "observed_trials": len(trials),
                "fault_accounting": fault_accounting(manifest.conditions, trials),
            },
            sort_keys=True,
            indent=2,
        )
        + "\n"
    )


def render_suite_markdown(
    manifest: SuiteManifest, decision: SuiteDecision, trials: Sequence[TrialEnvelope]
) -> str:
    last = decision.history[-1] if decision.history else None
    lines = [
        f"# Suite {_cell(manifest.suite_id)}",
        "",
        f"VERDICT: {decision.verdict.value} (exit {decision.exit_code})",
        "",
        "Reasons: " + "; ".join(_cell(reason) for reason in decision.reasons),
        "",
        "## Registered rule",
        "",
        f"Alpha: {decision.alpha}; delta: {decision.delta}; stakes: {', '.join(decision.stakes)}; "
        f"threshold: {decision.threshold}.",
        f"Cells: {decision.n_cells}; max rounds: {decision.max_rounds}; "
        f"seed mode: {decision.scenario_seeds}; error tolerance: {decision.max_errored_pairs}.",
        f"Stopping round: {decision.stopped_at_round}; "
        f"pairs at last evaluated round: {last.pairs if last else 0}; "
        f"stored trials: {len(trials)}.",
        "",
        guarantee(manifest.scenario_seeds),
        "",
        ASSUMPTIONS,
    ]
    if manifest.scenario_seeds == "per_round":
        lines.extend(
            [
                "",
                "There is no guarantee averaged over seeds: a deterministic hash of "
                "registered content is not a sampling distribution.",
            ]
        )
    lines.extend(
        [
            "",
            "## Round history (cumulative)",
            "",
            "Wealth displays are truncated; exact crossing flags decide against the threshold.",
            "",
            "| Round | Pairs | Minus | Zero | Plus | Errored / tolerance | Hard violations | "
            "PASS wealth | BLOCK wealth | Threshold | PASS crossed | BLOCK crossed | Verdict |",
            "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---|",
        ]
    )
    for row in decision.history:
        c = row.counts
        lines.append(
            f"| {row.round} | {row.pairs} | {c.minus} | {c.zero} | {c.plus} | "
            f"{c.errored} / {decision.max_errored_pairs} | {row.candidate_hard_violations} | "
            f"{row.pass_wealth} | {row.block_wealth} | {decision.threshold} | "
            f"{str(row.pass_crossed).lower()} | {str(row.block_crossed).lower()} | "
            f"{row.verdict.value} |"
        )
    if not decision.history:
        lines.extend(["", "No validated complete-round history is available."])
    lines.extend(
        [
            "",
            "## Per-cell counts (descriptive)",
            "",
            CELL_WARNING,
            "",
            "| Task | Condition | Pairs | Baseline successes | Candidate successes | "
            "Minus | Zero | Plus | Errored | Candidate hard violations |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for cell in decision.cells:
        c = cell.counts
        lines.append(
            f"| {_cell(cell.task_id)} | {_cell(cell.condition_id)} | {cell.pairs} | "
            f"{cell.baseline_successes} | {cell.candidate_successes} | {c.minus} | {c.zero} | "
            f"{c.plus} | {c.errored} | {cell.candidate_hard_violations} |"
        )
    lines.extend(fault_markdown(manifest.conditions, trials))
    lines.extend(["", "## Earlier runs on this candidate are never hidden", ""])
    lines.extend(f"- `{_cell(run)}`" for run in decision.prior_runs)
    if not decision.prior_runs:
        lines.append("- None recorded.")
    lines.extend(
        [
            "",
            "A new campaign does not reset the error budget. Integrity seals do not "
            "authenticate execution.",
            "",
            f"VERDICT: {decision.verdict.value} (exit {decision.exit_code})",
        ]
    )
    return "\n".join(lines) + "\n"
