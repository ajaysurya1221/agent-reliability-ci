"""v1 parsing goldens and suite projection readability/admission regressions."""

from __future__ import annotations

import json
from fractions import Fraction
from pathlib import Path

import pytest

from arci.cli import main
from arci.planning import render_suite_plan, suite_plan
from arci.suite_stats import operating_characteristics, rule_of
from tests.acceptance.suite_helpers import suite_manifest


@pytest.mark.parametrize(
    "args,message",
    [
        (
            [],
            "the following arguments are required: "
            "--baseline-rate, --candidate-rate, --target-verdict",
        ),
        (
            ["--baseline-rate", "0.9"],
            "the following arguments are required: --candidate-rate, --target-verdict",
        ),
        (
            ["--baseline-rate", "0.9", "--candidate-rate", "0.8"],
            "the following arguments are required: --target-verdict",
        ),
        (
            ["--baseline-rate", "abc", "--candidate-rate", "0.8", "--target-verdict", "PASS"],
            "argument --baseline-rate: invalid float value: 'abc'",
        ),
        (
            ["--baseline-rate", "0.9", "--candidate-rate", "abc", "--target-verdict", "PASS"],
            "argument --candidate-rate: invalid float value: 'abc'",
        ),
        (
            [
                "--baseline-rate",
                "0.9",
                "--candidate-rate",
                "0.8",
                "--target-verdict",
                "PASS",
                "extra",
            ],
            "unrecognized arguments: extra",
        ),
    ],
)
def test_v1_error_goldens(
    args: list[str], message: str, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["plan", *args]) == 3
    output = capsys.readouterr()
    assert output.out == ""
    assert output.err == f"error: CliError: {message}\n"


def test_v1_manifest_positional_is_one_line(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from tests.acceptance.helpers import manifest

    path = tmp_path / "v1.json"
    path.write_text(manifest().model_dump_json())
    assert main(["plan", str(path)]) == 3
    assert (
        capsys.readouterr().err
        == "error: CliError: plan positional input must be a suite descriptor or manifest\n"
    )


@pytest.mark.parametrize("cells", [3, 6, 7, 9])
def test_default_grids_are_projected(cells: int) -> None:
    m = suite_manifest(n_tasks=cells, n_conditions=1, max_rounds=(400 + cells - 1) // cells)
    doc = suite_plan(m, baseline_rate=".875", candidate_rate=".75", agreement=".875")
    expected = operating_characteristics(
        [(Fraction(1, 8), Fraction(7, 8), Fraction(0))] * cells, rule_of(m)
    )
    assert doc["status"] == "exact projection"
    assert doc["projection"] == {
        "PASS": str(expected.p_pass),
        "BLOCK": str(expected.p_block),
        "INCONCLUSIVE": str(expected.p_inconclusive),
        "expected_pairs": str(expected.expected_pairs),
        "expected_sessions": str(2 * expected.expected_pairs),
    }


def test_projection_limits_name_measured_resource() -> None:
    m = suite_manifest(max_rounds=1000)
    doc = suite_plan(m, baseline_rate=".9", candidate_rate=".8", agreement=".7")
    assert doc["projection"] is None and "denominator bits exceeds limit 8192" in str(doc["status"])
    m = suite_manifest(n_tasks=1, n_conditions=1, max_rounds=2000)
    doc = suite_plan(m, baseline_rate=".5", candidate_rate=".5", agreement="0")
    assert doc["projection"] is None and "boundary states" in str(doc["status"])


def test_plan_decimals_stakes_and_model_only_assumptions() -> None:
    m = suite_manifest(max_rounds=4)
    no_model = suite_plan(m)
    text = render_suite_plan(no_model)
    assert "model projections" not in text and no_model["assumptions"] is None
    assert "stakes: 1/4, 1/2\n" in text and "threshold: 40/1\n" in text
    doc = suite_plan(m, baseline_rate=".9", candidate_rate=".8", agreement=".7")
    text = render_suite_plan(doc)
    projection = json.loads(json.dumps(doc))["projection"]
    for key, exact_text in projection.items():
        exact = Fraction(exact_text)
        shown = next(
            line.split(": ", 1)[1] for line in text.splitlines() if line.startswith(key + ": ")
        )
        decimal = Fraction(shown)
        assert decimal <= exact < decimal + Fraction(1, 10**6)
        assert len(shown.split(".")[1]) == 6
    assert "model projections" in text
    doc["projection"] = {"PASS": "1/10000000", "BLOCK": "99999999/100000000"}
    text = render_suite_plan(doc)
    assert "PASS: <0.000001 (positive)" in text and "BLOCK: 0.999999" in text
