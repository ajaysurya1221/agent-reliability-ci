"""Delta debugging for failing trial fault sets."""

from __future__ import annotations

from collections.abc import Sequence

from arci.interfaces import RunTrial
from arci.replay import make_bundle
from arci.runner import run_trial
from arci.schema import (
    Condition,
    Manifest,
    MinimizeResult,
    Outcome,
    ReplayBundle,
    ToolMode,
    TrialEnvelope,
    TrialSpec,
)


def _partitions(items: tuple[int, ...], count: int) -> tuple[tuple[int, ...], ...]:
    """Split items into ``count`` non-empty, similarly sized contiguous chunks."""
    quotient, remainder = divmod(len(items), count)
    chunks: list[tuple[int, ...]] = []
    start = 0
    for index in range(count):
        size = quotient + (1 if index < remainder else 0)
        chunks.append(items[start : start + size])
        start += size
    return tuple(chunks)


def minimize_faults(
    manifest: Manifest,
    trial: TrialEnvelope,
    spec: TrialSpec,
    *,
    run: RunTrial | None = None,
) -> MinimizeResult:
    """Reduce a failing trial's faults while preserving its failure fingerprint."""
    if trial.outcome is not Outcome.FAIL:
        raise ValueError("fault minimization requires a FAIL trial")
    if trial.failure_fingerprint is None:
        raise ValueError("failing trial has no failure fingerprint")

    runner = run_trial if run is None else run
    faults = spec.condition.faults
    original = tuple(range(len(faults)))
    cache: dict[tuple[int, ...], TrialEnvelope] = {original: trial}
    trials_run = 0
    uncertain_single_removal = False

    def candidate_spec(indices: Sequence[int]) -> TrialSpec:
        condition = Condition(
            condition_id=spec.condition.condition_id,
            faults=tuple(faults[index] for index in indices),
        )
        return spec.model_copy(
            update={
                "condition": condition,
                "tool_mode": ToolMode.RECORD,
                "recording": (),
                "replay_final_state": None,
            }
        )

    def evaluate(indices: tuple[int, ...]) -> TrialEnvelope:
        nonlocal trials_run
        cached = cache.get(indices)
        if cached is not None:
            return cached
        observed = runner(candidate_spec(indices), lambda _event: None, manifest.contract)
        cache[indices] = observed
        trials_run += 1
        return observed

    def reproduces(indices: tuple[int, ...], *, removed_from: tuple[int, ...]) -> bool:
        nonlocal uncertain_single_removal
        observed = evaluate(indices)
        if len(indices) == len(removed_from) - 1 and observed.outcome is Outcome.ERROR:
            uncertain_single_removal = True
        return (
            observed.outcome is Outcome.FAIL
            and observed.failure_fingerprint == trial.failure_fingerprint
        )

    current = original
    granularity = 2
    while len(current) >= 2:
        subsets = _partitions(current, min(granularity, len(current)))
        reduced_to: tuple[int, ...] | None = None

        for subset in subsets:
            if reproduces(subset, removed_from=current):
                reduced_to = subset
                break

        if reduced_to is None:
            for subset in subsets:
                members = set(subset)
                complement = tuple(index for index in current if index not in members)
                if reproduces(complement, removed_from=current):
                    reduced_to = complement
                    break

        if reduced_to is not None:
            current = reduced_to
            granularity = max(2, granularity - 1)
        elif granularity >= len(current):
            break
        else:
            granularity = min(len(current), granularity * 2)

    single_removals_lose_failure = True
    for removed_index in current:
        without_one = tuple(index for index in current if index != removed_index)
        if reproduces(without_one, removed_from=current):
            single_removals_lose_failure = False

    was_reduced = current != original
    live_http = spec.decisions is not None and spec.decisions.upstream == "http"
    if live_http or uncertain_single_removal:
        minimality = "reduced"
    elif current and single_removals_lose_failure:
        minimality = "1-minimal"
    elif was_reduced:
        minimality = "reduced"
    else:
        minimality = "original"

    final_trial = evaluate(current)
    final_spec = candidate_spec(current)
    draft_bundle = make_bundle(manifest, final_trial, final_spec)
    bundle_data = draft_bundle.model_dump(exclude={"record_sha256"})
    bundle_data["minimality"] = minimality
    bundle = ReplayBundle.create(**bundle_data)

    kept_indices = set(current)
    return MinimizeResult(
        bundle=bundle,
        kept=tuple(fault.name for index, fault in enumerate(faults) if index in kept_indices),
        removed=tuple(
            fault.name for index, fault in enumerate(faults) if index not in kept_indices
        ),
        minimality=minimality,
        trials_run=trials_run,
    )
