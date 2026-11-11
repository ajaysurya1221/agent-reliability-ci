"""Read-only, bounded failure triage; statistical decisions remain authoritative."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

from arci.gate import decide
from arci.hashing import canonical_json
from arci.schedule import build_schedule
from arci.schema import GateDecision, Outcome, TrialEnvelope, Verdict
from arci.storage import load_run
from arci.suite_gate import decide_suite
from arci.suite_schedule import build_suite_schedule
from arci.suite_schema import SUITE_SCHEMA_VERSION, SuiteDecision
from arci.suite_storage import load_suite_run, manifest_schema_version
from arci.trace_check import (
    TraceCheckResult,
    TraceSource,
    TraceStepContext,
    check_traces,
    trace_step_context,
)

_LIMITATIONS = (
    "First difference is not root cause or proof of regression, benignness, "
    "or equality of later behavior.",
    "DRIFT never changes the statistical gate exit; invalid diagnosis exits 3.",
    "No candidate failures means no automatic comparison, not a claim of reliability.",
    "Only selected observed pairs are compared; at most three failure groups are shown.",
    "Names, pointers and hashes can disclose information; this output is not sanitized.",
)


@dataclass(frozen=True)
class FailureGroup:
    condition_id: str
    failure_fingerprint: str | None
    count: int
    hard_violation_trials: int
    is_gating: bool
    condition_verdict: str
    selected_candidate_id: str


@dataclass(frozen=True)
class GroupCounts:
    total: int = 0
    shown: int = 0
    omitted: int = 0


@dataclass(frozen=True)
class DifferenceContext:
    baseline: TraceStepContext
    candidate: TraceStepContext


@dataclass(frozen=True)
class SelectedPair:
    candidate_trial_id: str
    baseline_trial_id: str
    candidate_outcome: str
    baseline_outcome: str
    comparison: TraceCheckResult
    first_difference_context: DifferenceContext | None


@dataclass(frozen=True)
class TriageResult:
    """A gate snapshot and optional diagnostics, with no recorded payload values."""

    status: Literal["OK", "INVALID"]
    reason: str
    gate: GateDecision | SuiteDecision | None = None
    group_counts: GroupCounts = GroupCounts()
    groups: tuple[FailureGroup, ...] = ()
    selected_pairs: tuple[SelectedPair, ...] = ()
    limitations: tuple[str, ...] = _LIMITATIONS
    schema_version: Literal["arci-triage/1"] = "arci-triage/1"

    @property
    def exit_code(self) -> int:
        return 3 if self.status == "INVALID" or self.gate is None else self.gate.exit_code


def _hard(trial: TrialEnvelope) -> bool:
    return trial.contract is not None and any(
        violation.severity == "hard" for violation in trial.contract.violations
    )


def _invalid(reason: str, gate: GateDecision | SuiteDecision | None = None) -> TriageResult:
    return TriageResult("INVALID", reason, gate)


def triage_run(run_dir: Path | str, *, trial_id: str | None = None) -> TriageResult:
    """Derive the complete gate and compare only schedule-selected observed pairs."""
    try:
        try:
            suite = manifest_schema_version(run_dir) == SUITE_SCHEMA_VERSION
        except ValueError:
            # Preserve v1's model-default loading for an omitted schema_version.
            # Only an explicit suite version selects the suite loader.
            suite = False
        if suite:
            manifest, trials = load_suite_run(run_dir)
            gate = decide_suite(manifest, trials)
            schedule = build_suite_schedule(manifest)
        else:
            manifest, trials = load_run(run_dir)
            gate = decide(manifest, trials)
            schedule = build_schedule(manifest)
    except (OSError, ValueError, TypeError, UnicodeError, RecursionError):
        return _invalid("Run store is invalid or unavailable.")
    if gate.verdict is Verdict.ERROR:
        return _invalid("Run statistical gate is ERROR; diagnosis is unavailable.", gate)

    by_id = {trial.trial_id: trial for trial in trials}
    # Pair using schedule identities, without interpreting the trial ID string.
    baseline_ids = {spec.pair_id: spec.trial_id for spec in schedule if spec.arm == "baseline"}
    observed = [by_id[spec.trial_id] for spec in schedule if spec.trial_id in by_id]
    candidates = [trial for trial in observed if trial.arm == "candidate"]
    order = {trial.trial_id: index for index, trial in enumerate(observed)}
    # Suite cells have no individual statistical verdict. Group ranking remains
    # descriptive and cannot present the suite verdict as a condition verdict.
    conditions = (
        {condition.condition_id: (True, "suite mean only") for condition in manifest.conditions}
        if isinstance(gate, SuiteDecision)
        else {
            condition.condition_id: (condition.is_gating, condition.verdict.value)
            for condition in gate.conditions
        }
    )
    grouped: dict[tuple[str, str | None], list[TrialEnvelope]] = {}
    for trial in candidates:
        if trial.outcome is Outcome.FAIL:
            grouped.setdefault((trial.condition_id, trial.failure_fingerprint), []).append(trial)

    def representative(members: list[TrialEnvelope]) -> TrialEnvelope:
        return min(
            members,
            key=lambda t: (
                not _hard(t),
                by_id[baseline_ids[t.pair_id]].outcome is not Outcome.PASS,
                order[t.trial_id],
            ),
        )

    def priority(
        item: tuple[tuple[str, str | None], list[TrialEnvelope]],
    ) -> tuple[int, int, str, bool, str]:
        (condition_id, fingerprint), members = item
        is_gating, verdict = conditions[condition_id]
        tier = (
            0
            if any(_hard(t) for t in members)
            else 1
            if is_gating and verdict == Verdict.BLOCK.value
            else 2
            if is_gating
            else 3
        )
        return tier, -len(members), condition_id, fingerprint is not None, fingerprint or ""

    shown = sorted(grouped.items(), key=priority)[:3]
    groups = tuple(
        FailureGroup(
            condition_id,
            fingerprint,
            len(members),
            sum(_hard(t) for t in members),
            conditions[condition_id][0],
            conditions[condition_id][1],
            representative(members).trial_id,
        )
        for (condition_id, fingerprint), members in shown
    )
    if trial_id is not None:
        selected = [trial for trial in candidates if trial.trial_id == trial_id]
        if len(selected) != 1:
            return _invalid("Candidate trial selection is not unique and available.", gate)
    else:
        selected = [by_id[group.selected_candidate_id] for group in groups]

    pairs: list[SelectedPair] = []
    for candidate in selected:
        baseline = by_id[baseline_ids[candidate.pair_id]]
        comparison = (
            _suite_comparison(run_dir, baseline.trial_id, candidate.trial_id)
            if suite
            else check_traces(run_dir, baseline.trial_id, run_dir, candidate.trial_id)
        )
        # No context is constructed until BOTH loaded snapshots match the initial gate.
        for source, trial in ((comparison.baseline, baseline), (comparison.candidate, candidate)):
            if source is None or (
                source.experiment_id != manifest.experiment_id
                or source.trial_id != trial.trial_id
                or source.trial_outcome != trial.outcome.value
                or source.gate_verdict != gate.verdict.value
                or source.gate_exit_code != gate.exit_code
                or source.manifest_sha256 != manifest.record_sha256
                or source.trial_sha256 != trial.record_sha256
                or source.decision_sha256 != gate.record_sha256
            ):
                return _invalid(
                    "Source snapshot changed or is unavailable; diagnosis discarded.", gate
                )
        if comparison.status == "INVALID":
            return _invalid(
                "Selected paired trace comparison is INVALID; diagnosis discarded.", gate
            )
        difference = comparison.first_difference
        context = None
        if difference is not None:
            context = DifferenceContext(
                trace_step_context(
                    baseline, difference.step, value_present=difference.baseline_sha256 is not None
                ),
                trace_step_context(
                    candidate,
                    difference.step,
                    value_present=difference.candidate_sha256 is not None,
                ),
            )
        pairs.append(
            SelectedPair(
                candidate.trial_id,
                baseline.trial_id,
                candidate.outcome.value,
                baseline.outcome.value,
                comparison,
                context,
            )
        )
    return TriageResult(
        "OK",
        "Selected observed pairs compared."
        if pairs
        else "No candidate failures; no automatic comparison.",
        gate,
        GroupCounts(len(grouped), len(groups), len(grouped) - len(groups)),
        groups,
        tuple(pairs),
    )


def render_triage(result: TriageResult, *, output_format: Literal["text", "json"] = "text") -> str:
    """Render metadata and comparator hashes, without argument/result/failure values."""
    gate = (
        None
        if result.gate is None
        else result.gate.model_dump(mode="json")
        | {
            "decision_sha256": result.gate.record_sha256,
        }
    )
    document = {
        "schema_version": result.schema_version,
        "status": result.status,
        "reason": result.reason,
        "exit_code": result.exit_code,
        "gate": gate,
        "group_counts": asdict(result.group_counts),
        "groups": [asdict(group) for group in result.groups],
        "selected_pairs": [asdict(pair) for pair in result.selected_pairs],
        "limitations": result.limitations,
    }
    if output_format == "json":
        return canonical_json(document).decode("utf-8")
    if output_format != "text":
        raise ValueError("Unsupported triage output format.")
    lines: list[str] = []
    if result.gate is not None:
        decision = result.gate
        lines.append(f"Statistical gate: {decision.verdict.value} (exit {decision.exit_code}).")
        if isinstance(decision, SuiteDecision):
            lines.extend(
                [
                    f"Configuration: alpha {decision.alpha}; delta {decision.delta}; "
                    f"stakes {', '.join(decision.stakes)}; threshold {decision.threshold}.",
                    f"Rounds: {decision.max_rounds}; reached {len(decision.history)}; "
                    f"stopping round {decision.stopped_at_round}.",
                    "Groups are descriptive; a suite-mean PASS can hide a regression in one cell.",
                ]
            )
        else:
            lines.append(
                f"Configuration: alpha {decision.alpha:g}; delta {decision.delta:g}; "
                f"method {decision.interval_method}; planned pairs/arm {decision.n_per_arm}."
            )
            looks = ", ".join(str(look) for look in decision.looks)
            lines.append(
                f"Looks: {looks}; reached {len(decision.history)}; "
                f"stopping look {decision.stopped_at_look}."
            )
            for condition in decision.conditions:
                role = "gating" if condition.is_gating else "descriptive ceiling"
                baseline, candidate = condition.baseline, condition.candidate
                lines.append(
                    f"Condition {_quoted(condition.condition_id)} ({role}): "
                    f"{condition.verdict.value}; baseline {baseline.successes}/{baseline.n} PASS "
                    f"({baseline.errors} ERROR); candidate "
                    f"{candidate.successes}/{candidate.n} PASS "
                    f"({candidate.errors} ERROR); candidate hard violations "
                    f"{condition.candidate_hard_violations}."
                )
        lines.append(f"Manifest SHA-256: {decision.manifest_sha256}")
        lines.append(f"Trials SHA-256: {decision.trials_sha256}")
        lines.append(f"Decision SHA-256: {decision.record_sha256}")
    lines.append(f"{result.status}: {result.reason} Triage exit {result.exit_code}.")
    counts = result.group_counts
    lines.append(
        f"Failure groups: {counts.total} total; {counts.shown} shown; {counts.omitted} omitted."
    )
    for index, group in enumerate(result.groups, 1):
        fingerprint = (
            "<unfingerprinted>"
            if group.failure_fingerprint is None
            else _quoted(group.failure_fingerprint)
        )
        role = "gating" if group.is_gating else "descriptive ceiling"
        lines.append(
            f"Group {index}: condition {_quoted(group.condition_id)}; fingerprint {fingerprint}; "
            f"{group.count} FAIL; {group.hard_violation_trials} hard-violating trials; "
            f"{role} {group.condition_verdict}."
        )
    for index, pair in enumerate(result.selected_pairs, 1):
        comparison = pair.comparison
        lines.append(f"Pair {index}: {comparison.status}. {comparison.reason}")
        lines.append(
            f"  Baseline {_quoted(pair.baseline_trial_id)}: {pair.baseline_outcome}; "
            f"candidate {_quoted(pair.candidate_trial_id)}: {pair.candidate_outcome}."
        )
        if comparison.baseline is not None and comparison.candidate is not None:
            lines.append(f"  Baseline trial SHA-256: {comparison.baseline.trial_sha256}")
            lines.append(f"  Candidate trial SHA-256: {comparison.candidate.trial_sha256}")
        difference = comparison.first_difference
        if difference is not None and pair.first_difference_context is not None:
            lines.append(
                f"  First difference: step {difference.step}, path {_quoted(difference.path)}."
            )
            for label, context, digest in (
                ("Baseline", pair.first_difference_context.baseline, difference.baseline_sha256),
                ("Candidate", pair.first_difference_context.candidate, difference.candidate_sha256),
            ):
                lines.append(f"  {label} context: {_context_text(context)}")
                lines.append(f"    Differing value SHA-256: {digest or '<missing>'}")
    limitations = dict.fromkeys(result.limitations)
    for pair in result.selected_pairs:
        limitations.update(dict.fromkeys(pair.comparison.limitations))
    lines.extend(f"Limitation: {limitation}" for limitation in limitations)
    return "\n".join(lines)


def _quoted(value: str) -> str:
    return json.dumps(value, ensure_ascii=True)


def _context_text(context: TraceStepContext) -> str:
    presence = "present" if context.value_present else "absent"
    if context.location != "event":
        return f"{context.location} record; differing value {presence}."
    parts = [f"event {context.event_kind}", f"seq {context.seq}"]
    if context.tool is not None:
        # Tool is already escaped once by the additive context projection.
        parts.extend((f'tool "{context.tool}"', f"occurrence {context.occurrence}"))
    parts.append(f"differing value {presence}")
    return "; ".join(parts) + "."


def _suite_comparison(run_dir: Path | str, baseline_id: str, candidate_id: str) -> TraceCheckResult:
    """Adapt suite evidence to v1's validated, payload-free trace comparator.

    These internal pure helpers are shared deliberately: trace_check.py is outside
    this work package's ownership and its public suite refusal stays unchanged.
    """
    from arci.trace_check import (
        _first_difference,  # pyright: ignore[reportPrivateUsage]
        _projection,  # pyright: ignore[reportPrivateUsage]
        _valid_events,  # pyright: ignore[reportPrivateUsage]
    )

    try:
        manifest, trials = load_suite_run(run_dir)
        gate = decide_suite(manifest, trials)
        if gate.verdict is Verdict.ERROR:
            return TraceCheckResult("INVALID", "Suite statistical gate is ERROR.")
        by_id = {t.trial_id: t for t in trials}
        baseline, candidate = by_id[baseline_id], by_id[candidate_id]
        sources = tuple(
            TraceSource(
                manifest.experiment_id,
                trial.trial_id,
                manifest.record_sha256,
                trial.record_sha256,
                gate.record_sha256,
                trial.outcome.value,
                gate.verdict.value,
                gate.exit_code,
            )
            for trial in (baseline, candidate)
        )
        if (
            baseline.pair_id != candidate.pair_id
            or baseline.arm != "baseline"
            or candidate.arm != "candidate"
        ):
            return TraceCheckResult(
                "INVALID", "Selected trials are not a scheduled pair.", sources[0], sources[1]
            )
        if not _valid_events(baseline) or not _valid_events(candidate):
            return TraceCheckResult(
                "INVALID", "Selected paired trace is invalid.", sources[0], sources[1]
            )
        difference = _first_difference(_projection(baseline), _projection(candidate))
        return TraceCheckResult(
            "MATCH" if difference is None else "DRIFT",
            "Selected normalized traces match."
            if difference is None
            else "Selected normalized traces differ.",
            sources[0],
            sources[1],
            difference,
            TraceCheckResult("MATCH", "").limitations
            + (
                ("Fixture identities are empty; environment equality is declaration-only.",)
                if not manifest.fixtures_sha256
                else ()
            ),
        )
    except (OSError, ValueError, TypeError, UnicodeError, RecursionError, KeyError):
        return TraceCheckResult("INVALID", "Suite store is invalid or unavailable.")
