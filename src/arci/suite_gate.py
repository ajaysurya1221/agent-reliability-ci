"""Pure suite gate: normalize evidence, validate the store, then walk balanced rounds."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from arci.hashing import canonical_json, hash_record
from arci.schedule import spec_sha256
from arci.schema import EXIT_CODES, Outcome, TrialEnvelope, TrialSpec, Verdict
from arci.suite_schedule import build_suite_schedule, pair_round, suite_cells, suite_experiment_id
from arci.suite_schema import (
    SuiteCellStats,
    SuiteCounts,
    SuiteDecision,
    SuiteManifest,
    SuiteRoundDecision,
    format_rational,
    parse_rational,
)
from arci.suite_stats import check_suite_plan, crossed, rule_of, scored_wealth, wealth_text


def _is_string(value: object) -> bool:
    return isinstance(value, str)


def _digest(trials: Sequence[TrialEnvelope]) -> str:
    seals = [trial.record_sha256 for trial in trials]
    if any(not _is_string(seal) for seal in seals):
        raise ValueError("trial seals must be strings")
    return hash_record({"trials": sorted(seals)})


def _safe_digest(trials: Sequence[TrialEnvelope]) -> str:
    try:
        return _digest(trials)
    except Exception:
        return ""


def _hard(trial: TrialEnvelope) -> int:
    return (
        sum(v.severity == "hard" for v in trial.contract.violations)
        if trial.arm == "candidate" and trial.contract is not None
        else 0
    )


@dataclass
class _Counts:
    minus: int = 0
    zero: int = 0
    plus: int = 0
    errored: int = 0
    hard: int = 0
    baseline_successes: int = 0
    candidate_successes: int = 0

    def add(self, baseline: TrialEnvelope, candidate: TrialEnvelope) -> None:
        self.hard += _hard(candidate)
        self.baseline_successes += baseline.outcome is Outcome.PASS
        self.candidate_successes += candidate.outcome is Outcome.PASS
        if baseline.outcome is Outcome.ERROR or candidate.outcome is Outcome.ERROR:
            self.errored += 1
        else:
            difference = int(candidate.outcome is Outcome.PASS) - int(
                baseline.outcome is Outcome.PASS
            )
            self.minus += difference == -1
            self.zero += difference == 0
            self.plus += difference == 1

    def model(self) -> SuiteCounts:
        return SuiteCounts(minus=self.minus, zero=self.zero, plus=self.plus, errored=self.errored)


def _round_verdict(
    counts: _Counts, tolerance: int, pass_crossed: bool, block_crossed: bool
) -> tuple[Verdict, tuple[str, ...]]:
    if counts.errored > tolerance:
        return Verdict.ERROR, ("errored pairs exceed max_errored_pairs",)
    if counts.hard:
        return Verdict.BLOCK, ("candidate hard violation",)
    if pass_crossed and block_crossed:
        return Verdict.ERROR, ("both tests crossed",)
    if pass_crossed:
        return Verdict.PASS, ("non-inferiority established",)
    if block_crossed:
        return Verdict.BLOCK, ("regression established",)
    return Verdict.INCONCLUSIVE, ("no test crossed",)


def evaluate_rounds(
    manifest: SuiteManifest, trials: Sequence[TrialEnvelope]
) -> tuple[SuiteRoundDecision, ...]:
    """Walk valid scheduled trials, ignoring an incomplete trailing round."""
    rounds: dict[int, list[TrialEnvelope]] = {}
    for trial in trials:
        rounds.setdefault(pair_round(trial.pair_id), []).append(trial)
    rule = rule_of(manifest)
    counts = _Counts()
    seen: list[TrialEnvelope] = []
    history: list[SuiteRoundDecision] = []
    for r in range(1, manifest.max_rounds + 1):
        current = rounds.get(r, [])
        if len(current) != 2 * manifest.n_cells:
            break
        by_id = {trial.trial_id: trial for trial in current}
        for trial in current:
            if trial.arm == "baseline":
                counts.add(trial, by_id[f"{trial.pair_id}:candidate"])
        seen.extend(current)
        wp, wb = scored_wealth(counts.minus, counts.zero, counts.plus, counts.errored, rule)
        pc, bc = crossed(wp, rule), crossed(wb, rule)
        verdict, reasons = _round_verdict(counts, manifest.max_errored_pairs, pc, bc)
        history.append(
            SuiteRoundDecision(
                round=r,
                pairs=r * manifest.n_cells,
                trials_sha256=_digest(seen),
                counts=counts.model(),
                candidate_hard_violations=counts.hard,
                pass_wealth=wealth_text(wp),
                block_wealth=wealth_text(wb),
                pass_crossed=pc,
                block_crossed=bc,
                verdict=verdict,
                reasons=reasons,
            )
        )
        if verdict is not Verdict.INCONCLUSIVE:
            break
    return tuple(history)


def _cells(manifest: SuiteManifest, trials: Sequence[TrialEnvelope]) -> tuple[SuiteCellStats, ...]:
    counts = {(task.task_id, c.condition_id): _Counts() for task, c in suite_cells(manifest)}
    by_id = {trial.trial_id: trial for trial in trials}
    for trial in trials:
        if trial.arm == "baseline":
            counts[trial.task_id, trial.condition_id].add(
                trial, by_id[f"{trial.pair_id}:candidate"]
            )
    return tuple(
        SuiteCellStats(
            task_id=t,
            condition_id=c,
            pairs=v.minus + v.zero + v.plus + v.errored,
            baseline_successes=v.baseline_successes,
            candidate_successes=v.candidate_successes,
            counts=v.model(),
            candidate_hard_violations=v.hard,
        )
        for (t, c), v in counts.items()
    )


def _matches(trial: TrialEnvelope, spec: TrialSpec) -> bool:
    return (
        trial.experiment_id == spec.experiment_id
        and trial.trial_id == spec.trial_id
        and trial.pair_id == spec.pair_id
        and trial.arm == spec.arm
        and trial.task_id == spec.task_id
        and trial.condition_id == spec.condition.condition_id
        and trial.seed == spec.seed
        and trial.spec_sha256 == spec_sha256(spec)
    )


def _fields(manifest: SuiteManifest | None) -> dict[str, Any]:
    if manifest is None:
        return dict(
            experiment_id="",
            manifest_sha256="",
            alpha="",
            delta="",
            stakes=(),
            threshold="",
            n_cells=0,
            max_rounds=0,
            scenario_seeds="",
            max_errored_pairs=0,
            prior_runs=(),
        )
    return dict(
        experiment_id=manifest.experiment_id,
        manifest_sha256=manifest.record_sha256,
        alpha=manifest.alpha,
        delta=manifest.delta,
        stakes=manifest.stakes,
        threshold=format_rational(2 / parse_rational(manifest.alpha)),
        n_cells=manifest.n_cells,
        max_rounds=manifest.max_rounds,
        scenario_seeds=manifest.scenario_seeds,
        max_errored_pairs=manifest.max_errored_pairs,
        prior_runs=manifest.prior_runs,
    )


def _decision(
    manifest: SuiteManifest | None,
    digest: str,
    reasons: tuple[str, ...],
    verdict: Verdict = Verdict.ERROR,
    history: tuple[SuiteRoundDecision, ...] = (),
    cells: tuple[SuiteCellStats, ...] = (),
    stopped: int = 0,
) -> SuiteDecision:
    try:
        return SuiteDecision.create(
            **_fields(manifest),
            trials_sha256=digest,
            reasons=reasons,
            verdict=verdict,
            exit_code=EXIT_CODES[verdict],
            history=history,
            cells=cells,
            stopped_at_round=0 if verdict is Verdict.ERROR else stopped,
        )
    except Exception:
        return SuiteDecision.create(
            **_fields(None),
            trials_sha256="",
            reasons=("gate computation failed",),
            verdict=Verdict.ERROR,
            exit_code=3,
        )


def decide_suite(manifest: SuiteManifest, trials: Sequence[TrialEnvelope]) -> SuiteDecision:
    """Return a sealed decision, including for unvalidated model copies."""
    normalized: SuiteManifest | None = None
    digest = _safe_digest(trials)
    try:
        reasons: list[str] = []

        def check(reason: str, operation: Callable[[], bool]) -> bool:
            try:
                valid = operation()
            except Exception:
                valid = False
            if not valid:
                reasons.append(reason)
            return valid

        try:
            rebuilt = SuiteManifest.model_validate(manifest.model_dump(mode="python"))
            canonical_json(rebuilt.model_dump(mode="json"))
            normalized = rebuilt
        except Exception:
            return _decision(None, digest, ("manifest values invalid",))

        check("manifest seal invalid", rebuilt.validate_seal)
        check(
            "suite rule digest mismatch",
            lambda: rebuilt.experiment_id == suite_experiment_id(rebuilt),
        )

        def plan() -> bool:
            check_suite_plan(rebuilt)
            return True

        check("suite plan invalid", plan)
        clean: list[TrialEnvelope] = []

        def rebuild_trials() -> bool:
            for trial in trials:
                item = TrialEnvelope.model_validate(trial.model_dump(mode="python"))
                canonical_json(item.model_dump(mode="json"))
                clean.append(item)
            return True

        if check("trial values invalid", rebuild_trials):
            schedule: tuple[TrialSpec, ...] = ()

            def matches_schedule() -> bool:
                nonlocal schedule
                schedule = build_suite_schedule(rebuilt)
                expected = {spec.trial_id: spec for spec in schedule}
                return len({t.trial_id for t in clean}) == len(clean) and all(
                    t.trial_id in expected and _matches(t, expected[t.trial_id]) for t in clean
                )

            schedule_ok = check("trial schedule mismatch", matches_schedule)
            check("trial seal invalid", lambda: all(t.validate_seal() for t in clean))
            if schedule_ok:
                check(
                    "trial set is not a whole number of rounds",
                    lambda: (
                        bool(clean)
                        and len(clean) % (2 * rebuilt.n_cells) == 0
                        and {t.trial_id for t in clean}
                        == {s.trial_id for s in schedule[: len(clean)]}
                    ),
                )
        if reasons:
            return _decision(rebuilt, digest, tuple(reasons))
        history = evaluate_rounds(rebuilt, clean)
        cells = _cells(rebuilt, clean)
        last = history[-1]
        stored_rounds = len(clean) // (2 * rebuilt.n_cells)
        if last.round < stored_rounds:
            return _decision(
                rebuilt,
                digest,
                ("trials stored after the stopping round",),
                history=history,
                cells=cells,
            )
        if last.verdict is Verdict.INCONCLUSIVE and last.round < rebuilt.max_rounds:
            return _decision(
                rebuilt, digest, ("stopped without a decision",), history=history, cells=cells
            )
        return _decision(rebuilt, digest, last.reasons, last.verdict, history, cells, last.round)
    except Exception:
        try:
            return _decision(normalized, digest, ("gate computation failed",))
        except Exception:
            return _decision(None, "", ("gate computation failed",))


def replay_suite_decision(
    decision: SuiteDecision, manifest: SuiteManifest, trials: Sequence[TrialEnvelope]
) -> bool:
    try:
        return decision.validate_seal() and decide_suite(manifest, trials) == decision
    except Exception:
        return False
