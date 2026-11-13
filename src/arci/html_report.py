"""Offline, deterministic HTML views of the existing report evidence.

No Markdown is interpreted as HTML. All report text crosses one escaping boundary;
only the small, generated structural vocabulary below becomes markup.
"""

from __future__ import annotations

import math
import unicodedata
from collections import Counter, defaultdict
from collections.abc import Sequence
from fractions import Fraction
from html import escape
from typing import cast

from pydantic import JsonValue

from arci import __version__
from arci.report import (
    TOOL_OUTCOMES_HEADING,
    TOOL_OUTCOMES_INTRO,
    USD_PER_MTOK_INPUT,
    fault_accounting,
    tool_outcomes,
)
from arci.schema import (
    DECISION_TOOL,
    ArmStats,
    Condition,
    GateDecision,
    Manifest,
    Outcome,
    TrialEnvelope,
    Verdict,
)
from arci.suite_report import (
    ASSUMPTIONS,
    CELL_WARNING,
    INTEGRITY_LIMITATION,
    PRIOR_RUNS,
    SEED_LIMITATION,
    WEALTH_DISPLAY,
    guarantee,
)
from arci.suite_schema import SuiteDecision, SuiteManifest

_CSS = """
:root { color-scheme: light dark; --paper: #fff; --ink: #17202a; --line: #677583; }
@media (prefers-color-scheme: dark) {
  :root { --paper: #141a20; --ink: #edf2f7; --line: #9aaaba; }
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--paper); color: var(--ink);
  font: 16px/1.6 system-ui, sans-serif; }
main { max-width: 1100px; margin: auto; padding: clamp(16px, 4vw, 48px); }
h1 { font-size: clamp(24px, 5vw, 38px); line-height: 1.2; }
h2 { margin-top: 2em; font-size: 1.25em; }
.long-value { overflow-wrap: anywhere; }
.verdict { border: 2px solid currentColor; padding: 16px; font-weight: bold; }
.table { overflow-x: auto; margin: 1em 0; }
table { width: 100%; border-collapse: collapse; font-variant-numeric: tabular-nums; }
th, td { border-bottom: 1px solid var(--line); text-align: left; padding: 8px; }
th { vertical-align: bottom; } td { vertical-align: top; min-width: 6ch; }
svg { display: block; width: 100%; height: auto; color: var(--ink); }
pre { white-space: pre-wrap; }
@media print { .table { overflow: visible; } body { font-size: 10pt; } }
"""

_MEANING = {
    Verdict.PASS: "The candidate is non-inferior within the registered margin on the suite mean; "
    "this says nothing about absolute reliability.",
    Verdict.BLOCK: "The suite mean dropped beyond the registered margin, or the candidate broke "
    "a hard invariant.",
    Verdict.INCONCLUSIVE: "There is not enough evidence either way; no regression is claimed.",
    Verdict.ERROR: "The evidence is invalid or errors exceeded tolerance; no reliability "
    "conclusion can be drawn.",
}
LOW_BASELINE = (
    "WARNING: baseline passed fewer than half its trials; "
    "a non-inferiority PASS says little about absolute reliability."
)
# Verbatim sentence from the frozen statistics document. The report also gives
# the standalone qualification from suite_report, so "above" has local context.
PER_ROUND_VERBATIM = (
    "Its error guarantee requires that in every round the suite mean over that "
    "round's scenario instances obey the relevant null, with the independence "
    "conditions above (or their conditional form)."
)


def visible_text(value: object) -> str:
    """Keep stored data on one visible line, including invisible/bidi controls."""
    return "".join(
        f"\\u{ord(char):04x}"
        if unicodedata.category(char) in {"Cc", "Cf", "Zl", "Zp", "Cs"}
        else char
        for char in str(value)
    )


def _text(value: object) -> str:
    return escape(visible_text(value), quote=True)


def _wrap_class(value: object) -> str:
    # Preserve ordinary words' min-content widths, especially the arm names.
    return (
        ' class="long-value"' if any(len(word) > 24 for word in visible_text(value).split()) else ""
    )


def _p(value: object) -> str:
    return f"<p{_wrap_class(value)}>{_text(value)}</p>"


def _heading(value: str) -> str:
    return f"<h2>{_text(value)}</h2>"


def _table(name: str, headers: Sequence[str], rows: Sequence[Sequence[object]]) -> str:
    return (
        f'<div class="table" tabindex="0" role="region" aria-label="{_text(name)}"><table>'
        f"<caption{_wrap_class(name)}>{_text(name)}</caption><thead><tr>"
        + "".join(f'<th scope="col">{_text(h)}</th>' for h in headers)
        + "</tr></thead><tbody>"
        + "".join(
            "<tr>" + "".join(f"<td{_wrap_class(v)}>{_text(v)}</td>" for v in row) + "</tr>"
            for row in rows
        )
        + "</tbody></table></div>"
    )


def _faults(conditions: Sequence[Condition], trials: Sequence[TrialEnvelope]) -> str:
    rows = fault_accounting(conditions, trials)
    return (
        _heading("Fault accounting")
        + _p(
            "Recorded tool_finish injections, attributed by declaration, tool and occurrence; "
            "ambiguous observations are unattributed. Counts are descriptive."
        )
        + (
            _table(
                "Fault accounting",
                ("Condition", "Fault", "Arm", "Trials", "Injections", "Trials fired", "Status"),
                [
                    [
                        r[k]
                        for k in (
                            "condition_id",
                            "fault",
                            "arm",
                            "trials",
                            "injections",
                            "trials_fired",
                            "status",
                        )
                    ]
                    for r in rows
                ],
            )
            if rows
            else _p("No faults declared.")
        )
    )


def _tool_outcomes(trials: Sequence[TrialEnvelope]) -> str:
    summary = tool_outcomes(trials)
    return (
        _heading(TOOL_OUTCOMES_HEADING)
        + _p(TOOL_OUTCOMES_INTRO)
        + _table(
            "Tool outcomes by arm",
            (
                "Arm",
                "Trials",
                "Trials with an uninjected failure",
                "Then passed",
                "Then not passed",
            ),
            [
                [
                    r["arm"],
                    r["trials"],
                    r["uninjected_failure_trials"],
                    r["uninjected_then_passed"],
                    r["uninjected_then_not_passed"],
                ]
                for r in summary["arms"]
            ],
        )
        + (
            _table(
                "Recorded attempts by tool and arm",
                (
                    "Tool",
                    "Arm",
                    "Trials",
                    "Started in",
                    "Not started in",
                    "Starts",
                    "Uninjected failures",
                    "Trials with one",
                ),
                [
                    [
                        r["tool"],
                        r["arm"],
                        r["trials"],
                        r["trials_started"],
                        r["trials_not_started"],
                        r["starts"],
                        r["uninjected_failures"],
                        r["uninjected_failure_trials"],
                    ]
                    for r in summary["tools"]
                ],
            )
            if summary["tools"]
            else _p("No tool starts recorded.")
        )
    )


def _details(trials: Sequence[TrialEnvelope]) -> str:
    counts = Counter(
        (t.task_id, t.condition_id, t.arm, t.failure_detail) for t in trials if t.failure_detail
    )
    return _heading("Failure details (descriptive)") + (
        _table(
            "Failure details by task, condition and arm",
            ("Task", "Condition", "Arm", "Detail", "Count"),
            [(*key, count) for key, count in sorted(counts.items())],
        )
        if counts
        else _p("No failure details recorded.")
    )


def suite_meaning(decision: SuiteDecision, *, mismatch: bool = False) -> str:
    if mismatch:
        return _MEANING[Verdict.ERROR]
    if decision.verdict is Verdict.BLOCK:
        if "candidate hard violation" in decision.reasons:
            return "The candidate broke a hard invariant; this BLOCK is not a statistical finding."
        return (
            "On the suite mean, the candidate's success is lower than the baseline's "
            "by more than the registered margin."
        )
    return _MEANING[decision.verdict]


def render_error_html(error: BaseException) -> str:
    """A readable artifact even when no store objects can be loaded."""
    return _page(Verdict.ERROR, 3, _heading("Report unavailable") + _p(str(error)))


def _page(verdict: Verdict, code: int, body: str) -> str:
    return (
        '<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>ARCI report: {verdict.value}</title><style>{_CSS}</style></head><body><main>\n"
        f'<h1 class="verdict">VERDICT: {verdict.value} (exit {code})</h1>\n'
        + body
        + f"\n<footer><p>ARCI {_text(__version__)}</p></footer></main></body></html>\n"
    )


def _arms(trials: Sequence[TrialEnvelope]) -> tuple[str, bool]:
    rows: list[tuple[str, int, int]] = []
    for arm in ("baseline", "candidate"):
        selected = [t for t in trials if t.arm == arm]
        rows.append((arm, sum(t.outcome is Outcome.PASS for t in selected), len(selected)))
    return _table("Observed arm success", ("Arm", "Successes", "Observed trials"), rows), 2 * rows[
        0
    ][1] < rows[0][2]


def _chart(decision: SuiteDecision) -> str:
    if not decision.history:
        return "<p>No validated complete-round history is available for the chart.</p>"

    # Log scale avoids overflow for legal, very large products. Coordinates are
    # display-only, fixed to three decimals; exact crossing flags remain in the table.
    def log_display(value: str) -> float:
        mantissa, _, exponent = value.lower().partition("e")
        return math.log10(float(mantissa)) + (int(exponent) if exponent else 0)

    threshold = math.log10(float(Fraction(decision.threshold)))
    passes = [log_display(row.pass_wealth) for row in decision.history]
    blocks = [log_display(row.block_wealth) for row in decision.history]
    low, high = min(0.0, *passes, *blocks), max(threshold, *passes, *blocks)

    def y(value: float) -> float:
        return 180 - 150 * (value - low) / (high - low)

    def points(values: list[float]) -> str:
        # Start at wealth one, round zero, so a one-round report still has a line.
        points = [f"50,{y(0):.3f}"]
        for row, value in zip(decision.history, values, strict=True):
            x = 50 + 500 * row.round / decision.history[-1].round
            points.append(f"{x:.3f},{y(value):.3f}")
        return " ".join(points)

    return (
        '<svg viewBox="0 0 600 220" role="img" aria-labelledby="wealth-title wealth-desc">'
        '<title id="wealth-title">Wealth against threshold by round</title>'
        '<desc id="wealth-desc">Logarithmic wealth scale. PASS solid; BLOCK dashed; '
        "threshold dotted. Exact values and crossing flags follow in the table.</desc>"
        f'<path d="M50 20 V180 H550" fill="none" stroke="currentColor"/>'
        f'<path d="M50 {y(threshold):.3f} H550" stroke="currentColor" stroke-dasharray="2 5"/>'
        f'<polyline points="{points(passes)}" fill="none" stroke="currentColor" stroke-width="2"/>'
        f'<polyline points="{points(blocks)}" fill="none" stroke="currentColor" '
        'stroke-width="2" stroke-dasharray="8 5"/>'
        '<text x="50" y="210" fill="currentColor">Round 0</text>'
        f'<text x="480" y="210" fill="currentColor">Round {decision.history[-1].round}</text>'
        "</svg><p>Log wealth: PASS solid · BLOCK dashed · threshold dotted. "
        "The table gives the values and exact crossing flags.</p>"
    )


def render_suite_html(
    manifest: SuiteManifest,
    decision: SuiteDecision,
    trials: Sequence[TrialEnvelope],
    *,
    stored_status: str = "absent",
) -> str:
    """Render the suite evidence without changing the stored or recomputed decision."""
    verdict = Verdict.ERROR if stored_status == "mismatch" else decision.verdict
    code = 3 if stored_status == "mismatch" else decision.exit_code
    arms, low = _arms(trials)
    body = _p(suite_meaning(decision, mismatch=stored_status == "mismatch")) + arms
    body += _heading("Suite") + _p(f"Suite id: {manifest.suite_id}")
    body += _table(
        "Arm labels",
        ("Arm", "Label"),
        [("baseline", manifest.baseline.label), ("candidate", manifest.candidate.label)],
    )
    body += _heading("Reasons") + "".join(_p(r) for r in decision.reasons)
    body += _p(f"Stored decision: {stored_status}")
    if stored_status == "mismatch":
        body += _p(f"Recomputed verdict: {decision.verdict.value}")
    if low:
        body += _p(LOW_BASELINE)
    last = decision.history[-1] if decision.history else None
    body += _heading("Registered rule") + _table(
        "Registered suite rule",
        ("Rule", "Value"),
        [
            ("Alpha", decision.alpha),
            ("Delta", decision.delta),
            ("Stakes", ", ".join(decision.stakes)),
            ("Threshold", decision.threshold),
            ("Cells", decision.n_cells),
            ("Max rounds", decision.max_rounds),
            ("Seed mode", decision.scenario_seeds),
            ("Error tolerance", decision.max_errored_pairs),
            ("Stopping round", decision.stopped_at_round),
            ("Pairs at last evaluated round", last.pairs if last else 0),
            ("Stored trials", len(trials)),
            ("Candidate hard violations", last.candidate_hard_violations if last else 0),
        ],
    )
    body += _p(guarantee(manifest.scenario_seeds)) + _p(ASSUMPTIONS)
    if manifest.scenario_seeds == "per_round":
        body += _p(SEED_LIMITATION) + _p(PER_ROUND_VERBATIM)
    body += _heading("Wealth by round") + _chart(decision) + _p(WEALTH_DISPLAY)
    body += _table(
        "Round history (cumulative)",
        (
            "Round",
            "Pairs",
            "Minus",
            "Zero",
            "Plus",
            "Errored / tolerance",
            "Hard violations",
            "PASS wealth",
            "BLOCK wealth",
            "Threshold",
            "PASS crossed",
            "BLOCK crossed",
            "Verdict",
        ),
        [
            (
                r.round,
                r.pairs,
                r.counts.minus,
                r.counts.zero,
                r.counts.plus,
                f"{r.counts.errored} / {decision.max_errored_pairs}",
                r.candidate_hard_violations,
                r.pass_wealth,
                r.block_wealth,
                decision.threshold,
                str(r.pass_crossed).lower(),
                str(r.block_crossed).lower(),
                r.verdict.value,
            )
            for r in decision.history
        ],
    )
    body += _heading("Per-cell counts (descriptive)") + _p(CELL_WARNING)
    body += _table(
        "Per-cell descriptive counts",
        (
            "Task",
            "Condition",
            "Pairs",
            "Baseline successes",
            "Candidate successes",
            "Minus",
            "Zero",
            "Plus",
            "Errored",
            "Candidate hard violations",
        ),
        [
            (
                c.task_id,
                c.condition_id,
                c.pairs,
                c.baseline_successes,
                c.candidate_successes,
                c.counts.minus,
                c.counts.zero,
                c.counts.plus,
                c.counts.errored,
                c.candidate_hard_violations,
            )
            for c in decision.cells
        ],
    )
    body += _faults(manifest.conditions, trials) + _tool_outcomes(trials) + _details(trials)
    body += _heading(PRIOR_RUNS)
    body += "".join(_p(run) for run in decision.prior_runs) or _p("None recorded.")
    body += _p(INTEGRITY_LIMITATION)
    body += _heading("Record provenance") + _table(
        "Record provenance",
        ("Record", "Value"),
        [
            ("Experiment id", manifest.experiment_id),
            ("Manifest digest", decision.manifest_sha256),
            ("Trials digest", decision.trials_sha256),
            ("Decision digest", decision.record_sha256),
            ("Fixtures digest", manifest.fixtures_sha256 or "none recorded"),
            *((f"Round {r.round} trials digest", r.trials_sha256) for r in decision.history),
        ],
    )
    return _page(verdict, code, body)


# Local presentation helpers preserve v1 formatting without changing its module API.
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


def render_html(manifest: Manifest, decision: GateDecision, trials: Sequence[TrialEnvelope]) -> str:
    """Build the v1 view directly from evidence, never from Markdown syntax."""
    body = _p(_VERDICT_MEANINGS[decision.verdict])
    body += _heading("Experiment") + _p(f"Experiment id: {manifest.experiment_id}")
    body += _table(
        "Arm labels",
        ("Arm", "Label"),
        [("baseline", manifest.baseline.label), ("candidate", manifest.candidate.label)],
    )
    body += _table(
        "Gate configuration",
        (
            "Alpha",
            "Delta",
            "K (gating conditions)",
            "Interval method",
            "Per-arm confidence",
            "n_per_arm",
        ),
        [
            (
                _number(decision.alpha),
                _number(decision.delta),
                decision.k_conditions,
                decision.interval_method,
                f"{decision.per_arm_confidence:.4%}",
                decision.n_per_arm,
            )
        ],
    )
    if len(decision.looks) > 1:
        body += _heading("Looks") + _p(
            f"Stopped at look {decision.stopped_at_look} of {len(decision.looks)}."
        )
        body += _table(
            "Sequential looks by condition",
            ("Look", "Cumulative pairs", "Verdict", "Condition", "Bounds"),
            [
                (
                    look.look,
                    look.pairs,
                    look.verdict.value,
                    c.condition_id,
                    _interval(c.delta_low, c.delta_high),
                )
                for look in decision.history
                for c in look.conditions
            ],
        )
    recorded, inputs, outputs = _decision_usage(trials)
    if recorded:
        body += _heading("Decisions") + _table(
            "Decision usage",
            ("Recorded decisions", "Input tokens", "Output tokens", "Estimated cost at list price"),
            [(recorded, inputs, outputs, f"USD {inputs * USD_PER_MTOK_INPUT / 1_000_000:.7f}")],
        )
        body += _p(
            f"List price: USD {USD_PER_MTOK_INPUT:.3f} per million input tokens "
            f"(read {_LIST_PRICE_DATE})."
        )
        body += _p("Fixtures and replays cost nothing; this is an estimate, not billed spend.")
    for condition in decision.conditions:
        a, b = _arm_summary(condition.baseline), _arm_summary(condition.candidate)
        confidence = (
            "Clopper-Pearson (informational; the gate uses Newcombe below)"
            if decision.interval_method == "newcombe"
            else f"Clopper-Pearson ({decision.per_arm_confidence:.4%})"
        )
        body += _heading("Condition") + _table(
            f"Condition {condition.condition_id} measurements",
            ("Measure", "Baseline", "Candidate / condition"),
            [
                ("Role", "—", "Gating" if condition.is_gating else "Descriptive (ceiling fault)"),
                ("n", a[0], b[0]),
                ("Successes", a[1], b[1]),
                ("Success rate", a[2], b[2]),
                ("Wilson 95% (display only)", a[3], b[3]),
                (confidence, a[4], b[4]),
                (
                    f"Bounds on difference, {decision.interval_method} (candidate - baseline)",
                    "—",
                    _interval(condition.delta_low, condition.delta_high),
                ),
                ("Candidate hard violations", "—", condition.candidate_hard_violations),
                ("Condition verdict", "—", condition.verdict.value),
            ],
        )
    body += _heading("Candidate failure clusters")
    clusters = _failure_clusters(trials)
    body += (
        _table(
            "Candidate failure clusters",
            ("Failure fingerprint", "Count", "Example failure detail"),
            clusters,
        )
        if clusters
        else _p("No candidate failures were recorded.")
    )
    body += _details(trials)
    body += _heading("Earlier runs on this candidate are never hidden")
    body += "".join(_p(run) for run in decision.prior_runs) or _p("None recorded.")
    body += _heading("Reasons")
    body += "".join(_p(f"Experiment: {r}") for r in decision.reasons) or _p(
        "Experiment: no global errors."
    )
    for condition in decision.conditions:
        body += "".join(_p(f"{condition.condition_id}: {r}") for r in condition.reasons)
    body += _faults(manifest.conditions, trials)
    return _page(decision.verdict, decision.exit_code, body)


def render_store_html(run_dir: str) -> tuple[str, int]:
    """Load a store for HTML only; preserve legacy v1 successful-export exit zero."""
    from arci.gate import decide
    from arci.storage import load_run
    from arci.suite_gate import decide_suite
    from arci.suite_storage import load_suite_run, manifest_schema_version

    try:
        if manifest_schema_version(run_dir) == "arci-suite/1":
            manifest, trials = load_suite_run(run_dir)
            decision = decide_suite(manifest, trials)
            status = stored_suite_status(run_dir, manifest, trials)
            return (
                render_suite_html(manifest, decision, trials, stored_status=status),
                3 if status == "mismatch" else decision.exit_code,
            )
        v1, observed = load_run(run_dir)
        return render_html(v1, decide(v1, observed), observed), 0
    except Exception as exc:
        return render_error_html(exc), 3


def stored_suite_status(
    run_dir: str, manifest: SuiteManifest, trials: Sequence[TrialEnvelope]
) -> str:
    from pathlib import Path

    from arci.suite_gate import replay_suite_decision

    stored = Path(run_dir) / "decision.json"
    if not stored.exists() and not stored.is_symlink():
        return "absent"
    try:
        previous = SuiteDecision.model_validate_json(stored.read_text(encoding="utf-8"))
        return "match" if replay_suite_decision(previous, manifest, trials) else "mismatch"
    except (ValueError, OSError):
        return "mismatch"
