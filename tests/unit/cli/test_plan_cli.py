"""`arci plan`: a stable JSON schema, a small Markdown table, explicit refusals."""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from typing import Any, cast

import pytest

from arci.cli import main
from arci.planning import ASSUMPTIONS, plan
from arci.schema import Verdict

BASE = ["plan", "--baseline-rate", "0.95", "--candidate-rate", "0.75", "--target-verdict", "BLOCK"]

TOP_KEYS = {
    "schema",
    "design",
    "target",
    "rows",
    "target_reached",
    "smallest_n_per_arm",
    "conclusion",
    "assumptions",
}
DESIGN_KEYS = {
    "baseline_rate",
    "candidate_rate",
    "alpha",
    "delta",
    "interval_method",
    "conditions",
    "looks",
    "per_arm_tail",
}
TARGET_KEYS = {"verdict", "probability"}
ROW_KEYS = [
    "n_per_arm",
    "total_trials",
    "PASS",
    "BLOCK",
    "INCONCLUSIVE",
    "certain_verdict",
    "meets_target",
]


def _run_json(capsys: pytest.CaptureFixture[str], *extra: str) -> dict[str, Any]:
    assert main([*BASE, "--format", "json", *extra]) == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    return cast(dict[str, Any], json.loads(captured.out))


def test_json_schema_keys_are_stable(capsys: pytest.CaptureFixture[str]) -> None:
    document = _run_json(capsys, "--n-grid", "20,50,100")
    assert set(document) == TOP_KEYS
    assert list(document) == [
        "schema",
        "design",
        "target",
        "rows",
        "target_reached",
        "smallest_n_per_arm",
        "conclusion",
        "assumptions",
    ]
    assert document["schema"] == "arci.plan.v1"
    assert set(document["design"]) == DESIGN_KEYS
    assert set(document["target"]) == TARGET_KEYS
    assert [list(row) for row in document["rows"]] == [ROW_KEYS] * 3
    assert document["design"] == {
        "baseline_rate": 0.95,
        "candidate_rate": 0.75,
        "alpha": 0.05,
        "delta": 0.1,
        "interval_method": "clopper_pearson",
        "conditions": 1,
        "looks": 1,
        "per_arm_tail": 0.0125,
    }
    assert document["target"] == {"verdict": "BLOCK", "probability": 0.8}
    assert document["assumptions"] == list(ASSUMPTIONS)


def test_json_values_are_the_planner_values(capsys: pytest.CaptureFixture[str]) -> None:
    document = _run_json(capsys, "--n-grid", "20,50,100", "--target-probability", "0.01")
    expected = plan(
        baseline_rate=0.95,
        candidate_rate=0.75,
        target_verdict=Verdict.BLOCK,
        target_probability=0.01,
        n_grid=(20, 50, 100),
    )
    assert document["rows"] == [
        {
            "n_per_arm": row.n_per_arm,
            "total_trials": 2 * row.n_per_arm,
            "PASS": row.pass_probability,
            "BLOCK": row.block_probability,
            "INCONCLUSIVE": row.inconclusive_probability,
            "certain_verdict": None,
            "meets_target": row.meets_target,
        }
        for row in expected.rows
    ]
    assert document["target_reached"] is True
    assert document["smallest_n_per_arm"] == 50
    assert document["conclusion"] == expected.conclusion


def test_json_target_not_reached(capsys: pytest.CaptureFixture[str]) -> None:
    document = _run_json(capsys, "--n-grid", "20,50")
    assert document["target_reached"] is False
    assert document["smallest_n_per_arm"] is None
    assert document["conclusion"].startswith("target not reached")
    assert [row["meets_target"] for row in document["rows"]] == [False, False]


def test_json_output_is_deterministic(capsys: pytest.CaptureFixture[str]) -> None:
    first = _run_json(capsys, "--n-grid", "7,30")
    second = _run_json(capsys, "--n-grid", "7,30")
    assert first == second


def test_markdown_is_the_default_with_the_default_grid(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(BASE) == 0
    output = capsys.readouterr().out
    lines = output.splitlines()
    assert lines[0] == "# ARCI plan"
    header = "| N per arm | Total trials | P(PASS) | P(BLOCK) | P(INCONCLUSIVE) | Meets target |"
    assert header in lines
    assert "| 200 | 400 | 0.000 | 0.365 | 0.635 | no |" in lines
    assert "| 400 | 800 | 0.000 | 0.828 | 0.172 | yes |" in lines
    assert (
        "Result: smallest tested N per arm meeting P(BLOCK) >= 0.8: 400 (800 trials in total)."
        in lines
    )
    assumptions = next(line for line in lines if line.startswith("Assumptions: "))
    for phrase in (
        "planning under assumptions, not observed power",
        "Independent binomial arms",
        "No pairing",
        "Fixed sample",
        "Clopper-Pearson per arm with tail alpha/(4K)",
    ):
        assert phrase in assumptions


def test_a_target_of_one_needs_a_certain_verdict(capsys: pytest.CaptureFixture[str]) -> None:
    def run(baseline: str, candidate: str, verdict: str, n: str) -> dict[str, Any]:
        arguments = ["plan", "--baseline-rate", baseline, "--candidate-rate", candidate]
        arguments += ["--target-verdict", verdict, "--target-probability", "1", "--n-grid", n]
        assert main([*arguments, "--format", "json"]) == 0
        return cast(dict[str, Any], json.loads(capsys.readouterr().out))

    certain = run("0.9", "0.9", "INCONCLUSIVE", "1")
    assert certain["rows"][0]["INCONCLUSIVE"] == 1.0
    assert certain["rows"][0]["certain_verdict"] == "INCONCLUSIVE"
    assert certain["smallest_n_per_arm"] == 1
    # P(BLOCK) rounds to the float 1.0 at N=25, but INCONCLUSIVE stays reachable.
    almost = run("0.999", "0.001", "BLOCK", "25")
    assert almost["rows"][0]["BLOCK"] == 1.0
    assert almost["rows"][0]["certain_verdict"] is None
    assert almost["target_reached"] is False


@pytest.mark.parametrize(
    ("extra", "message"),
    [
        (("--n-grid", "20,401"), "unsupported design: N=401 per arm"),
        (("--n-grid", "1000"), "unsupported design: N=1000 per arm"),
        (("--conditions", "2"), "unsupported design: K=2"),
        (("--looks", "50,100,200"), "unsupported design: sequential looks"),
        (("--interval-method", "newcombe"), "unsupported design: interval_method 'newcombe'"),
        (("--n-grid", "20,x"), "--n-grid must be comma-separated integers"),
        (("--looks", "50,x"), "--looks must be comma-separated integers"),
        (("--n-grid", "50,20"), "strictly increasing"),
        (("--alpha", "0.9"), "alpha must be between"),
        (("--target-probability", "nan"), "target probability"),
        (("--target-verdict", "ERROR"), "invalid choice"),
        (("--format", "yaml"), "invalid choice"),
    ],
)
def test_refusals_exit_three_with_a_clear_message(
    capsys: pytest.CaptureFixture[str], extra: tuple[str, ...], message: str
) -> None:
    assert main([*BASE, *extra]) == 3
    captured = capsys.readouterr()
    assert captured.out == ""
    assert message in captured.err
    assert "Traceback" not in captured.err


def test_missing_rates_are_a_usage_error(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["plan", "--target-verdict", "PASS"]) == 3
    assert "--baseline-rate" in capsys.readouterr().err


def test_plan_help_works() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "arci.cli", "plan", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0
    assert completed.stderr == ""
    assert completed.stdout.startswith("usage: arci plan")
    assert "not observed power" in " ".join(completed.stdout.split())


def test_the_cli_never_imports_bench() -> None:
    script = textwrap.dedent(
        """
        import contextlib, io, sys
        from arci.cli import main
        with contextlib.redirect_stdout(io.StringIO()):
            code = main([
                "plan", "--baseline-rate", "0.9", "--candidate-rate", "0.7",
                "--target-verdict", "BLOCK", "--n-grid", "5,10", "--format", "json",
            ])
        assert code == 0, code
        loaded = sorted(m for m in sys.modules if m == "bench" or m.startswith("bench."))
        assert not loaded, loaded
        print("ok")
        """
    )
    completed = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, check=False
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout == "ok\n"
