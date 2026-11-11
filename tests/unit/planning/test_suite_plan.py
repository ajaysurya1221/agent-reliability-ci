"""Suite planning uses a stated joint law and the registered exact rule."""

from __future__ import annotations

import json
from fractions import Fraction
from pathlib import Path

import pytest

from arci.cli import main
from arci.suite_stats import operating_characteristics, rule_of
from tests.acceptance.suite_helpers import reference_wealth, suite_manifest


def test_homogeneous_joint_law() -> None:
    from arci.planning import homogeneous_suite_law

    # P(11)=.7, P(10)=.2, P(01)=.1, P(00)=0.
    assert homogeneous_suite_law(".9", ".8", ".7") == (
        Fraction(1, 5),
        Fraction(7, 10),
        Fraction(1, 10),
    )
    for values in [(".9", ".8", ".1"), (".9", ".1", ".9"), ("nan", "0", "0"), ("-1", "0", "0")]:
        with pytest.raises(ValueError):
            homogeneous_suite_law(*values)


def test_plan_floors_and_projection(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    m = suite_manifest(max_rounds=4, max_errored_pairs=0)
    path = tmp_path / "suite.json"
    path.write_text(m.model_dump_json())
    args = [
        "plan",
        str(path),
        "--baseline-rate",
        "0.9",
        "--candidate-rate",
        "0.8",
        "--agreement",
        "0.7",
        "--format",
        "json",
    ]
    assert main(args) == 0
    doc = json.loads(capsys.readouterr().out)
    rule = rule_of(m)
    for name, difference, direction in [
        ("earliest_pass_round", 1, 0),
        ("earliest_block_round", -1, 1),
        ("never_differs_pass_round", 0, 0),
    ]:
        floor = next(
            r
            for r in range(1, 5)
            if reference_wealth(
                20 * r if difference == -1 else 0,
                20 * r if difference == 0 else 0,
                20 * r if difference == 1 else 0,
                rule.alpha,
                rule.delta,
                rule.stakes,
            )[direction]
            >= rule.threshold
        )
        assert doc["floors"][name] == floor
    oc = operating_characteristics([(Fraction(1, 5), Fraction(7, 10), Fraction(1, 10))] * 20, rule)
    projection = doc["projection"]
    assert Fraction(projection["PASS"]) == oc.p_pass
    assert Fraction(projection["BLOCK"]) == oc.p_block
    assert Fraction(projection["INCONCLUSIVE"]) == oc.p_inconclusive
    assert Fraction(projection["expected_sessions"]) == 2 * oc.expected_pairs
    assert "projection under" in doc["model"].lower()
    assert "independent" in doc["assumptions"] and "no errors" in doc["assumptions"]
    assert main(["plan", str(path)]) == 0
    assert "floors only" in capsys.readouterr().out


def test_suite_plan_partial_model_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    m = suite_manifest(max_rounds=4)
    path = tmp_path / "suite.json"
    path.write_text(m.model_dump_json())
    assert main(["plan", str(path), "--baseline-rate", ".9"]) == 3
    assert "all three" in capsys.readouterr().err


def test_large_plan_gives_floors(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "suite.json"
    path.write_text(suite_manifest(max_rounds=1000).model_dump_json())
    assert (
        main(
            [
                "plan",
                str(path),
                "--baseline-rate",
                ".9",
                "--candidate-rate",
                ".8",
                "--agreement",
                ".7",
            ]
        )
        == 0
    )
    assert "too large to enumerate" in capsys.readouterr().out


def test_cell_laws_and_warnings(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    m = suite_manifest(n_tasks=20, max_rounds=1, acknowledge_single_round=True, max_errored_pairs=0)
    path = tmp_path / "suite.json"
    path.write_text(m.model_dump_json())
    laws = [
        {
            "task_id": t.task_id,
            "condition_id": c.condition_id,
            "p00": "0",
            "p01": "0",
            "p10": "0",
            "p11": "1",
        }
        for t in m.tasks
        for c in m.conditions
    ]
    model = tmp_path / "laws.json"
    model.write_text(json.dumps(list(reversed(laws))))
    assert main(["plan", str(path), "--cell-laws", str(model), "--format", "json"]) == 0
    doc = json.loads(capsys.readouterr().out)
    assert doc["projection"] == {
        "PASS": "1",
        "BLOCK": "0",
        "INCONCLUSIVE": "0",
        "expected_pairs": "80",
        "expected_sessions": "160",
    }
    assert doc["warnings"] == ["max_rounds below 3: few looks"]
    model.write_text(json.dumps(laws[:-1]))
    assert main(["plan", str(path), "--cell-laws", str(model)]) == 3
    assert "every registered cell" in capsys.readouterr().err
    model.write_text(json.dumps(laws + laws[:1]))
    assert main(["plan", str(path), "--cell-laws", str(model)]) == 3
    assert "duplicate cell law" in capsys.readouterr().err


def test_suite_descriptor_and_abbreviated_options(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from tests.unit.suite_cli.test_descriptor import TEXT

    path = tmp_path / "suite.yaml"
    path.write_text(TEXT + "rule: {max_rounds: 4, max_errored_pairs: 0}\n")
    assert (
        main(["plan", str(path), "--base", "1", "--cand", "1", "--agree", "1", "--for", "json"])
        == 0
    )
    doc = json.loads(capsys.readouterr().out)
    assert doc["projection"]["expected_sessions"] == "160"


@pytest.mark.parametrize(
    "flag,value",
    [
        ("--alpha", "0.05"),
        ("--del", "0.10"),
        ("--n-grid", "20,50,100,200,400"),
        ("--target-prob", "0.80"),
        ("--conditions", "1"),
        ("--interval", "clopper_pearson"),
    ],
)
def test_suite_rejects_explicit_v1_defaults(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], flag: str, value: str
) -> None:
    path = tmp_path / "suite.json"
    path.write_text(suite_manifest(alpha="1/10", delta="1/5", max_rounds=4).model_dump_json())
    assert main(["plan", str(path), flag, value]) == 3
    assert "registered rule" in capsys.readouterr().err
