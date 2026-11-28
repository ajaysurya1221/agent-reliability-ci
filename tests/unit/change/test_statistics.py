"""Finite offline simulations for ADR 0019. No model or subprocess is involved."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from pathlib import Path
from random import Random
from tempfile import TemporaryDirectory
from typing import NoReturn

import pytest

from arci import change
from arci.change import CapturedResult, LaunchResult, run_rounds
from arci.hashing import hash_bytes
from arci.importers import OutcomeValue
from arci.outcome_schema import OutcomeRule
from arci.outcomes import rule_of, rule_sha256
from arci.schema import Verdict
from arci.stats import clopper_pearson_tail
from arci.suite_schedule import Arm, arm_order


def simulate(
    seed: int, campaigns: int, n: int, baseline: float, candidate: float
) -> Counter[Verdict]:
    registration = OutcomeRule.model_validate(
        {
            "schema_version": "arci-outcomes/1",
            "suite_id": "simulation",
            "fixed_before_runs": True,
            "tasks": [str(i) for i in range(n)],
        }
    )
    rule = rule_of(registration)
    digest = rule_sha256(registration)
    order = [arm_order(digest, 0, r) for r in range(1, rule.max_rounds + 1)]
    counts: Counter[Verdict] = Counter()
    rng = Random(seed)
    # Reuse the fixture directory across independent campaigns. Every reached input
    # and decision is freshly written, and run_rounds starts with no predecessor.
    with TemporaryDirectory() as directory:
        root = Path(directory)
        rule_path = root / "rule.yaml"
        rule_path.write_text(registration.model_dump_json(exclude_none=True))
        for number in range(1, len(order) + 1):
            (root / f"round-{number:03d}").mkdir()

        def launch(arm: Arm, number: int) -> LaunchResult:
            rate = baseline if arm == "baseline" else candidate
            outcomes: dict[str, OutcomeValue | None] = {
                str(i): "pass" if rng.random() < rate else "fail" for i in range(n)
            }
            data = (
                "task_id,outcome\n" + "".join(f"{k},{v}\n" for k, v in outcomes.items())
            ).encode()
            path = root / f"round-{number:03d}" / f"{arm}.csv"
            snapshot = path.with_suffix(".snapshot.csv")
            path.write_bytes(data)
            snapshot.write_bytes(data)
            return CapturedResult(path, snapshot, hash_bytes(data)), outcomes

        def save(number: int, data: bytes) -> None:
            (root / f"round-{number:03d}/decision.json").write_bytes(data)

        for _ in range(campaigns):
            decision, _ = run_rounds(
                order, launch, registration, rule_path, "csv", save, lambda _pairs, _old, _new: None
            )
            counts[decision.verdict] += 1
    return counts


def test_item_16_self_comparison_finite_check_through_bookkeeping_not_proof() -> None:
    """Finite check of the released rule through this command's round bookkeeping, not a proof.

    Inject a seeded in-process launcher in place of programs. The completed paired draws
    go through the command's complete-prefix assessment and sealed predecessor chain.
    """
    total = 0
    for i, rate in enumerate((0.25, 0.5, 0.75, 0.95)):
        counts = simulate(201916 + i, 2500, 100, rate, rate)
        total += counts[Verdict.BLOCK]
        assert sum(counts.values()) == 2500 and counts[Verdict.ERROR] == 0
        assert clopper_pearson_tail(counts[Verdict.BLOCK], 2500, 0.05)[1] <= 0.025
    assert clopper_pearson_tail(total, 10000, 0.05)[1] <= 0.025


def test_item_17_known_difference_finite_check() -> None:
    """Inject an in-process launcher into the command's round bookkeeping, with no subprocesses.

    Both arms draw afresh on 20 tasks. The command evaluates each complete prefix.
    """
    counts = simulate(201917, 1000, 20, 0.95, 0.65)
    assert sum(counts.values()) == 1000 and counts[Verdict.ERROR] == 0
    assert counts[Verdict.BLOCK] >= 950 and counts[Verdict.PASS] == 0


@pytest.mark.parametrize(
    "simulation",
    [
        test_item_16_self_comparison_finite_check_through_bookkeeping_not_proof,
        test_item_17_known_difference_finite_check,
    ],
)
def test_simulations_require_released_assessment(
    monkeypatch: pytest.MonkeyPatch,
    simulation: Callable[[], None],
) -> None:
    def unavailable(*args: object, **kwargs: object) -> NoReturn:
        raise RuntimeError("released assessment called")

    monkeypatch.setattr(change, "decide_outcomes", unavailable)
    with pytest.raises(RuntimeError, match="released assessment called"):
        simulation()
