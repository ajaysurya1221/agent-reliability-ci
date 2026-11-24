"""All input streams below are fixed by hand. No registered generator calls."""

from __future__ import annotations

import csv
import json
import math
import sys
from fractions import Fraction
from pathlib import Path
from random import Random
from subprocess import run

import pytest
from gates import (
    CAP,
    GATES,
    ROUNDS,
    RULE,
    Counts,
    Decision,
    arci_gate,
    bootstrap_interval,
    classify,
    cs_width,
    decisions,
    mcnemar,
    tango_interval,
)
from simulate import exact_plan, plan_manifest

WIN = Counts(0, 20, 0, 0)
LOSS = Counts(0, 0, 20, 0)
TIE = Counts(0, 0, 0, 20)
MARGIN = Counts(0, 0, 2, 18)


@pytest.mark.parametrize(
    ("stream", "expected"),
    [
        ((WIN,) * ROUNDS, Decision("PASS", 20)),
        ((LOSS,) * ROUNDS, Decision("BLOCK", 20)),
        ((TIE,) * ROUNDS, Decision("PASS", 80)),
        ((MARGIN,) * ROUNDS, Decision("INCONCLUSIVE", 400)),
        ((WIN,) + (LOSS,) * 19, Decision("PASS", 20)),
        ((MARGIN, LOSS) + (WIN,) * 18, Decision("BLOCK", 40)),
    ],
)
def test_in_process_matches_csv_cli(
    tmp_path: Path, stream: tuple[Counts, ...], expected: Decision
) -> None:
    rule = tmp_path / "rule.json"
    rule.write_text(RULE.model_dump_json(exclude_none=True))
    files = [tmp_path / f"{arm}.csv" for arm in ("baseline", "candidate")]
    for arm, path in enumerate(files):
        with path.open("w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["task_id", "round", "outcome"])
            for r, counts in enumerate(stream, 1):
                values = [i for i, count in enumerate(counts) for _ in range(count)]
                for task, cell in zip(RULE.tasks, values, strict=True):
                    passed = cell & (2 if arm == 0 else 1)
                    writer.writerow([task, r, "pass" if passed else "fail"])
    out = tmp_path / "verdict.json"
    cmd = [
        sys.executable,
        "-m",
        "arci",
        "verdict",
        str(rule),
        "--baseline",
        str(files[0]),
        "--candidate",
        str(files[1]),
        "--format",
        "csv",
        "--json",
        str(out),
    ]
    cli = run(cmd, capture_output=True, text=True)
    payload = json.loads(out.read_bytes())
    assert cli.returncode == {"PASS": 0, "BLOCK": 1, "INCONCLUSIVE": 2}[expected.verdict]
    assert Decision(payload["verdict"], payload["history"][-1]["pairs"]) == expected
    assert arci_gate(stream) == expected
    assert payload["stopped_at_round"] == expected.pairs // 20
    assert payload["rule"]["fixed_before_runs"] is True


def test_handmade_exact_cli_projection(tmp_path: Path) -> None:
    path = tmp_path / "manifest.json"
    path.write_text(plan_manifest().model_dump_json())
    # This law has just one possible stream: every candidate wins every pair.
    plan = exact_plan(path, Fraction(0), Fraction(1), "I")
    assert plan["projection"] == {
        "PASS": "1",
        "BLOCK": "0",
        "INCONCLUSIVE": "0",
        "expected_pairs": "20",
        "expected_sessions": "40",
    }
    assert plan["rule"]["stakes"] == list(RULE.stakes)


@pytest.mark.parametrize(("counts", "verdict"), [(WIN, "PASS"), (LOSS, "BLOCK")])
def test_all_gates_unanimous(counts: Counts, verdict: str) -> None:
    rows = decisions((counts,) * ROUNDS, Random(123))
    assert tuple(rows) == GATES
    for gate, result in rows.items():
        assert result == Decision(verdict, 20 if gate in {"arci", "cs_zero", "cs_margin"} else CAP)


def test_different_targets_and_ties() -> None:
    rows = decisions((TIE,) * ROUNDS, Random(78))
    assert [rows[g].verdict for g in GATES] == [
        "PASS",
        "PASS",
        "INCONCLUSIVE",
        "INCONCLUSIVE",
        "INCONCLUSIVE",
        "PASS",
        "PASS",
        "INCONCLUSIVE",
    ]
    assert decisions((Counts(4, 0, 0, 16),) * ROUNDS, Random(1))["threshold"].verdict == "PASS"
    assert decisions((Counts(5, 0, 0, 15),) * ROUNDS, Random(1))["threshold"].verdict == "BLOCK"
    assert classify(Fraction(-1, 10), Fraction(0), Fraction(-1, 10)) == "INCONCLUSIVE"
    assert classify(-0.2, -0.1, -0.1) == "INCONCLUSIVE"
    assert cs_width(20) == pytest.approx(math.sqrt(40 * math.log(800)) / 20)


def test_exact_discordant_test() -> None:
    assert mcnemar(0, 0) == mcnemar(0, 5) == "INCONCLUSIVE"
    assert mcnemar(0, 6) == "BLOCK"
    assert mcnemar(6, 0) == "PASS"


def test_bootstrap_with_both_signs_and_one_sign() -> None:
    # Two pairs (+1,-1). Extremes each have mass 1/4, central mean 0 has mass 1/2.
    assert bootstrap_interval(1, 1, 2, Random(23)) == (-1, 1)
    assert bootstrap_interval(0, 1, 2, Random(23)) == (-1, 0)
    assert bootstrap_interval(1, 0, 2, Random(23)) == (0, 1)


def test_tango_on_agresti_prime_minister_worked_table() -> None:
    # Agresti (1990), p. 350, paired approval (794,150;86,570).
    # Orient earlier minus later. Reference endpoints independently computed by
    # maximizing the constrained trinomial likelihood (README gives the check).
    assert tango_interval(150, 86, 1600) == pytest.approx(
        (0.02136156475478724, 0.05899803330569942), abs=2e-14, rel=0
    )
    assert tango_interval(86, 150, 1600) == pytest.approx(
        (-0.05899803330569942, -0.02136156475478724), abs=2e-14, rel=0
    )


def test_score_extreme_cells() -> None:
    z2 = 1.959963984540054**2
    e = z2 / (400 + z2)
    assert tango_interval(0, 0, 400) == pytest.approx((-e, e))
    assert tango_interval(400, 0, 400) == pytest.approx((1 - 2 * e, 1.0))
    with pytest.raises(ValueError):
        decisions((WIN,), Random(0))


def test_bootstrap_type_seven_percentiles() -> None:
    class FixedResamples(Random):
        values = iter([0] * 50 + [1] * 1900 + [2] * 50)

        def binomialvariate(self, n: int = 1, p: float = 0.5) -> int:
            assert (n, p) == (2, 0.5)
            return next(self.values)

    assert bootstrap_interval(1, 0, 2, FixedResamples(0)) == (Fraction(39, 80), Fraction(41, 80))
