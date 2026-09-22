"""Deterministic statistical gate for a completed experiment."""

from __future__ import annotations

import math
from collections.abc import Sequence

from arci.hashing import hash_record
from arci.schedule import build_schedule, spec_sha256
from arci.schema import (
    EXIT_CODES,
    ArmStats,
    Bucket,
    ConditionDecision,
    GateDecision,
    Manifest,
    Outcome,
    TrialEnvelope,
    TrialSpec,
    Verdict,
)
from arci.stats import (
    clopper_pearson_tail,
    difference_bounds,
    newcombe,
    per_arm_confidence,
    wilson,
)


def classify(delta_low: float, delta_high: float, delta: float) -> Verdict:
    """Classify difference bounds using the frozen strict inequalities."""
    if delta_low > -delta:
        return Verdict.PASS
    if delta_high < -delta:
        return Verdict.BLOCK
    return Verdict.INCONCLUSIVE


def _matches_spec(trial: TrialEnvelope, spec: TrialSpec) -> bool:
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


def _arm_stats(trials: Sequence[TrialEnvelope], tail: float) -> tuple[ArmStats, bool]:
    n = len(trials)
    successes = sum(trial.outcome is Outcome.PASS for trial in trials)
    errors = sum(trial.outcome is Outcome.ERROR for trial in trials)
    interval_error = False
    if n == 0 or n > 10_000:
        cp_low, cp_high = 0.0, 1.0
        wilson_low, wilson_high = 0.0, 1.0
    else:
        try:
            cp_low, cp_high = clopper_pearson_tail(successes, n, tail)
            wilson_low, wilson_high = wilson(successes, n)
        except Exception:
            cp_low, cp_high = 0.0, 1.0
            wilson_low, wilson_high = 0.0, 1.0
            interval_error = True
    return (
        ArmStats(
            n=n,
            successes=successes,
            errors=errors,
            rate=successes / n if n else 0.0,
            cp_low=cp_low,
            cp_high=cp_high,
            wilson_low=wilson_low,
            wilson_high=wilson_high,
        ),
        interval_error,
    )


def _hard_violations(trials: Sequence[TrialEnvelope]) -> int:
    return sum(
        1
        for trial in trials
        if trial.contract is not None
        for violation in trial.contract.violations
        if violation.severity == "hard"
    )


def _experiment_verdict(conditions: Sequence[ConditionDecision], has_error: bool) -> Verdict:
    if has_error or any(condition.verdict is Verdict.ERROR for condition in conditions):
        return Verdict.ERROR
    if any(
        condition.candidate_hard_violations > 0
        or (condition.is_gating and condition.verdict is Verdict.BLOCK)
        for condition in conditions
    ):
        return Verdict.BLOCK
    if any(
        condition.is_gating and condition.verdict is Verdict.INCONCLUSIVE
        for condition in conditions
    ):
        return Verdict.INCONCLUSIVE
    return Verdict.PASS


def _safe_float(value: object) -> float:
    try:
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            converted = float(value)
            if math.isfinite(converted):
                return converted
    except BaseException:
        pass
    return 0.0


def _safe_int(value: object) -> int:
    if isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 10_000:
        return value
    return 0


def _safe_text(value: object) -> str:
    if not isinstance(value, str):
        return ""
    try:
        value.encode("utf-8")
    except BaseException:
        return ""
    return value


def _error_decision(
    manifest: Manifest, trials: Sequence[TrialEnvelope], reason: str
) -> GateDecision:
    try:
        gating_count = sum(
            not any(fault.bucket is Bucket.CEILING for fault in condition.faults)
            for condition in manifest.conditions
        )
    except BaseException:
        gating_count = 0
    try:
        trial_hashes = sorted(_safe_text(trial.record_sha256) for trial in trials)
        trials_sha256 = hash_record({"trials": trial_hashes})
    except BaseException:
        trials_sha256 = hash_record({"trials": []})
    alpha = _safe_float(getattr(manifest, "alpha", 0.0))
    delta = _safe_float(getattr(manifest, "delta", 0.0))
    n_per_arm = _safe_int(getattr(manifest, "n_per_arm", 0))
    return GateDecision.create(
        experiment_id=_safe_text(getattr(manifest, "experiment_id", "")),
        manifest_sha256=_safe_text(getattr(manifest, "record_sha256", "")),
        trials_sha256=trials_sha256,
        alpha=alpha,
        delta=delta,
        k_conditions=gating_count,
        per_arm_confidence=0.0,
        n_per_arm=n_per_arm,
        conditions=(),
        verdict=Verdict.ERROR,
        exit_code=EXIT_CODES[Verdict.ERROR],
        reasons=(reason,),
        prior_runs=(),
    )


def _decide(manifest: Manifest, trials: Sequence[TrialEnvelope]) -> GateDecision:
    """Apply the frozen gate rule without executing or mutating anything."""
    try:
        Manifest.model_validate(manifest.model_dump(mode="python"))
    except Exception:
        return _error_decision(manifest, trials, "manifest values invalid")
    gating_count = sum(
        not any(fault.bucket is Bucket.CEILING for fault in condition.faults)
        for condition in manifest.conditions
    )
    adjusted_conditions = max(gating_count, 1)
    tail = manifest.alpha / (4.0 * adjusted_conditions)
    use_newcombe = manifest.interval_method == "newcombe"
    confidence = (
        1.0 - manifest.alpha / adjusted_conditions
        if use_newcombe
        else per_arm_confidence(manifest.alpha, adjusted_conditions)
    )
    if tail < 2.5e-7:
        return _error_decision(manifest, trials, "statistical interval error")

    global_reasons: list[str] = []
    try:
        manifest_valid = manifest.validate_seal()
    except Exception:
        manifest_valid = False
    if not manifest_valid:
        global_reasons.append("manifest seal invalid")

    try:
        expected = build_schedule(manifest)
        expected_by_id = {spec.trial_id: spec for spec in expected}
        expected_ids_unique = len(expected_by_id) == len(expected)
    except Exception:
        expected = ()
        expected_by_id = {}
        expected_ids_unique = False
    observed_by_id: dict[str, TrialEnvelope] = {}
    duplicate_id = False
    for trial in trials:
        if trial.trial_id in observed_by_id:
            duplicate_id = True
        else:
            observed_by_id[trial.trial_id] = trial
    schedule_valid = (
        expected_ids_unique
        and not duplicate_id
        and len(trials) == len(expected)
        and set(observed_by_id) == set(expected_by_id)
    )
    if schedule_valid:
        try:
            schedule_valid = all(
                _matches_spec(trial, expected_by_id[trial_id])
                for trial_id, trial in observed_by_id.items()
            )
        except Exception:
            schedule_valid = False
    if not schedule_valid:
        global_reasons.append("trial schedule mismatch")

    try:
        seals_valid = all(trial.validate_seal() for trial in trials)
    except Exception:
        seals_valid = False
    if not seals_valid:
        global_reasons.append("trial seal invalid")
    try:
        has_trial_error = any(trial.outcome is Outcome.ERROR for trial in trials)
    except Exception:
        has_trial_error = True
    if has_trial_error:
        global_reasons.append("trial outcome ERROR")
    if gating_count == 0:
        global_reasons.append("no gating conditions")

    condition_decisions: list[ConditionDecision] = []
    for condition in manifest.conditions:
        condition_trials = [
            trial for trial in trials if trial.condition_id == condition.condition_id
        ]
        baseline_trials = [trial for trial in condition_trials if trial.arm == "baseline"]
        candidate_trials = [trial for trial in condition_trials if trial.arm == "candidate"]
        baseline, baseline_interval_error = _arm_stats(baseline_trials, tail)
        candidate, candidate_interval_error = _arm_stats(candidate_trials, tail)
        if baseline_interval_error or candidate_interval_error:
            global_reasons.append("statistical interval error")
        if use_newcombe and baseline.n and candidate.n:
            delta_low, delta_high = newcombe(
                baseline.successes, baseline.n, candidate.successes, candidate.n, confidence
            )
        else:
            delta_low, delta_high = difference_bounds(
                baseline=(baseline.cp_low, baseline.cp_high),
                candidate=(candidate.cp_low, candidate.cp_high),
            )
        statistical_verdict = classify(delta_low, delta_high, manifest.delta)
        hard_violations = _hard_violations(candidate_trials)
        is_gating = not any(fault.bucket is Bucket.CEILING for fault in condition.faults)
        condition_reasons: list[str] = []
        if not is_gating:
            condition_reasons.append("ceiling condition is descriptive")
        if baseline.errors or candidate.errors:
            verdict = Verdict.ERROR
            condition_reasons.append("trial outcome ERROR")
        elif hard_violations:
            verdict = Verdict.BLOCK
            condition_reasons.append("candidate hard violation")
        else:
            verdict = statistical_verdict
            condition_reasons.append(
                {
                    Verdict.PASS: "non-inferiority bound passed",
                    Verdict.BLOCK: "regression bound crossed",
                    Verdict.INCONCLUSIVE: "bounds cross the margin",
                    Verdict.ERROR: "invalid statistical verdict",
                }[verdict]
            )
        condition_decisions.append(
            ConditionDecision(
                condition_id=condition.condition_id,
                baseline=baseline,
                candidate=candidate,
                delta_low=delta_low,
                delta_high=delta_high,
                candidate_hard_violations=hard_violations,
                is_gating=is_gating,
                verdict=verdict,
                reasons=tuple(condition_reasons),
            )
        )

    has_error = bool(global_reasons)
    verdict = _experiment_verdict(condition_decisions, has_error)
    try:
        trial_hashes = sorted(trial.record_sha256 for trial in trials)
    except Exception:
        trial_hashes = []
    trials_sha256 = hash_record({"trials": trial_hashes})
    return GateDecision.create(
        experiment_id=manifest.experiment_id,
        manifest_sha256=manifest.record_sha256,
        trials_sha256=trials_sha256,
        alpha=manifest.alpha,
        delta=manifest.delta,
        interval_method=manifest.interval_method,
        k_conditions=gating_count,
        per_arm_confidence=confidence,
        n_per_arm=manifest.n_per_arm,
        conditions=tuple(condition_decisions),
        verdict=verdict,
        exit_code=EXIT_CODES[verdict],
        reasons=tuple(global_reasons),
        prior_runs=manifest.prior_runs,
    )


def decide(manifest: Manifest, trials: Sequence[TrialEnvelope]) -> GateDecision:
    """Apply the frozen gate rule; malformed typed inputs become sealed ERRORs."""
    try:
        return _decide(manifest, trials)
    except BaseException:
        return _error_decision(manifest, trials, "gate computation failed")


def replay_decision(
    decision: GateDecision, manifest: Manifest, trials: Sequence[TrialEnvelope]
) -> bool:
    """Return whether a sealed decision exactly replays from its inputs."""
    try:
        return decision.validate_seal() and decide(manifest, trials) == decision
    except Exception:
        return False
