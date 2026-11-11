"""Builders shared by the suite acceptance tests. FROZEN."""

from __future__ import annotations

from collections.abc import Collection, Sequence
from fractions import Fraction

from arci.schedule import spec_sha256
from arci.schema import (
    ArmSpec,
    Condition,
    ContractResult,
    Outcome,
    Termination,
    TrialEnvelope,
    TrialSpec,
    Violation,
)
from arci.suite_schedule import build_suite_round, create_suite_manifest
from arci.suite_schema import SuiteManifest, SuiteTask
from tests.acceptance.helpers import EMPTY_LOG, MOD, NEVER, TIMEOUT, contract

# One clean condition and three with one built-in fault each (see tests/acceptance/helpers.py).
CONDITIONS: tuple[Condition, ...] = (
    Condition(condition_id="clean", faults=()),
    Condition(condition_id="fetch_timeout", faults=(TIMEOUT,)),
    Condition(condition_id="empty_log", faults=(EMPTY_LOG,)),
    Condition(condition_id="store_error_late", faults=(NEVER,)),
)
HARD = Violation(invariant="forbidden_tools", severity="hard", detail="used rm")


def tasks(n_tasks: int = 5) -> tuple[SuiteTask, ...]:
    """Tasks "t0" .. "t{n-1}", each {"input": ...}."""
    return tuple(
        SuiteTask(task_id=f"t{i}", task={"input": f"store 42 ({i})"}) for i in range(n_tasks)
    )


def suite_manifest(
    *, n_tasks: int = 5, n_conditions: int = 4, **overrides: object
) -> SuiteManifest:
    """A valid sealed suite manifest; 5 tasks x 4 conditions = 20 cells by default.

    `n_conditions` takes the first entries of CONDITIONS (1 to 4). Any keyword in
    `overrides` replaces that manifest field (including `tasks` and `conditions`).
    """
    if not 1 <= n_conditions <= len(CONDITIONS):
        raise ValueError("n_conditions must be between 1 and 4")
    fields: dict[str, object] = {
        "suite_id": "suite-acceptance",
        "tasks": tasks(n_tasks),
        "conditions": CONDITIONS[:n_conditions],
        "toolset": f"{MOD}:make_world",
        "contract": contract(),
        "baseline": ArmSpec(label="A", agent=f"{MOD}:good_agent", candidate_id="a"),
        "candidate": ArmSpec(label="B", agent=f"{MOD}:fragile_agent", candidate_id="b"),
        "max_rounds": 20,
        "max_errored_pairs": 4,
    }
    fields.update(overrides)
    return create_suite_manifest(**fields)


def cell_keys(manifest: SuiteManifest) -> tuple[tuple[str, str], ...]:
    """(task_id, condition_id) of every cell in cell order, computed from contract section 1."""
    return tuple(
        sorted((t.task_id, c.condition_id) for t in manifest.tasks for c in manifest.conditions)
    )


def envelope(
    spec: TrialSpec,
    outcome: Outcome = Outcome.PASS,
    *,
    hard_violation: bool = False,
    **overrides: object,
) -> TrialEnvelope:
    """A sealed ordinary trial envelope for a scheduled spec, with the chosen outcome.

    PASS and FAIL end `completed` with a ContractResult whose `success` is `outcome is PASS`.
    ERROR ends `harness_error` with no contract result, unless `hard_violation` is set, in
    which case it carries a failed ContractResult. `hard_violation` adds one hard Violation
    and never changes the outcome. `overrides` replace envelope fields before sealing.
    """
    violations = (HARD,) if hard_violation else ()
    error = outcome is Outcome.ERROR
    result: ContractResult | None = ContractResult(
        success=outcome is Outcome.PASS, violations=violations
    )
    if error and not hard_violation:
        result = None
    fields: dict[str, object] = {
        "spec_sha256": spec_sha256(spec),
        "experiment_id": spec.experiment_id,
        "trial_id": spec.trial_id,
        "pair_id": spec.pair_id,
        "arm": spec.arm,
        "variant": spec.variant,
        "task_id": spec.task_id,
        "condition_id": spec.condition.condition_id,
        "seed": spec.seed,
        "outcome": outcome,
        "termination": Termination.HARNESS_ERROR if error else Termination.COMPLETED,
        "contract": result,
        "failure_fingerprint": None if outcome is Outcome.PASS else "f" * 64,
    }
    fields.update(overrides)
    return TrialEnvelope.create(**fields)


def round_trials(
    manifest: SuiteManifest,
    round: int,
    differences: Sequence[int],
    *,
    errored: Collection[int] = (),
    hard: Collection[int] = (),
) -> tuple[TrialEnvelope, ...]:
    """The 2 * N envelopes of one round, cells in cell order, baseline then candidate.

    `differences[i]` is the difference of cell i: +1 candidate PASS and baseline FAIL, -1 the
    reverse, 0 both PASS. A cell in `errored` has its candidate trial ERROR (its baseline still
    follows `differences[i]`). A cell in `hard` has a hard violation on its candidate trial;
    the outcomes still follow `differences` and `errored`.
    """
    keys = cell_keys(manifest)
    if len(differences) != len(keys):
        raise ValueError("one difference per cell")
    if any(d not in (-1, 0, 1) for d in differences):
        raise ValueError("differences must be -1, 0 or +1")
    if any(not 0 <= i < len(keys) for i in (*errored, *hard)):
        raise ValueError("cell index out of range")
    specs = {
        (s.task_id, s.condition.condition_id, s.arm): s for s in build_suite_round(manifest, round)
    }
    out: list[TrialEnvelope] = []
    for i, (task_id, condition_id) in enumerate(keys):
        d = differences[i]
        base = specs[(task_id, condition_id, "baseline")]
        cand = specs[(task_id, condition_id, "candidate")]
        base_outcome = Outcome.FAIL if d == 1 else Outcome.PASS
        cand_outcome = Outcome.FAIL if d == -1 else Outcome.PASS
        if i in errored:
            cand_outcome = Outcome.ERROR
        out.append(envelope(base, base_outcome))
        out.append(envelope(cand, cand_outcome, hard_violation=i in hard))
    return tuple(out)


def rounds_trials(
    manifest: SuiteManifest, rows: Sequence[Sequence[int]]
) -> tuple[TrialEnvelope, ...]:
    """Rounds 1 .. len(rows) concatenated; rows[r - 1] holds the differences of round r."""
    out: list[TrialEnvelope] = []
    for r, row in enumerate(rows, start=1):
        out.extend(round_trials(manifest, r, row))
    return tuple(out)


def reference_wealth(
    minus: int,
    zero: int,
    plus: int,
    alpha: Fraction,
    delta: Fraction,
    stakes: Sequence[Fraction],
) -> tuple[Fraction, Fraction]:
    """(PASS wealth, BLOCK wealth) as contract section 4 defines them; the tests' own oracle.

    With x = d + delta, PASS wealth is the mean over stakes q of the product over pairs of
    1 + q / (1 - delta) * x, and BLOCK wealth the mean of the product of 1 - q / (1 + delta) * x.
    Computed from the counts with integer powers. `alpha` sets only the threshold (2 / alpha),
    never the wealth; it is accepted so call sites can pass a whole rule.
    """
    del alpha
    pass_total = Fraction(0)
    block_total = Fraction(0)
    for q in stakes:
        up = q / (1 - delta)
        down = q / (1 + delta)
        pass_total += (
            (1 + up * (-1 + delta)) ** minus
            * (1 + up * delta) ** zero
            * (1 + up * (1 + delta)) ** plus
        )
        block_total += (
            (1 - down * (-1 + delta)) ** minus
            * (1 - down * delta) ** zero
            * (1 - down * (1 + delta)) ** plus
        )
    return pass_total / len(stakes), block_total / len(stakes)
