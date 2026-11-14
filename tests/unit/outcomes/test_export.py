"""Fresh exports must preserve the committed suite decisions and example bytes."""

import csv
from importlib.resources import files
from pathlib import Path

import pytest

from arci.cli import main as verdict_main
from arci.outcome_schema import OutcomeDecision
from arci.outcomes import load_rule
from arci.suite_schema import SuiteDecision
from arci.suite_storage import load_suite_run
from bench.export_outcomes import main

REPO = Path(__file__).resolve().parents[3]
EXAMPLES = REPO / "examples/outcomes/order-desk"
FILENAMES = ("baseline.csv", "candidate.csv", "rule.yaml")


@pytest.mark.parametrize(
    ("run", "verdict", "rounds", "pass_wealth", "block_wealth"),
    [
        ("run-1", "BLOCK", 1, "1.92124e-03", "1.56229e+02"),
        ("run-2", "INCONCLUSIVE", 5, "1.97265e-02", "4.87762e-01"),
    ],
)
def test_export_matches_stored_decision_and_examples(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    run: str,
    verdict: str,
    rounds: int,
    pass_wealth: str,
    block_wealth: str,
) -> None:
    (store,) = (REPO / "docs/results/order-desk-study" / run).iterdir()
    out = tmp_path / run
    assert main([str(store), str(out)]) == 0
    output = capsys.readouterr()
    assert output.err == ""
    assert output.out.splitlines() == [f"wrote {out / name}" for name in FILENAMES]
    for name in FILENAMES:
        assert (out / name).read_bytes() == (EXAMPLES / run / name).read_bytes()
    rule = load_rule(out / "rule.yaml")
    manifest, _ = load_suite_run(store)
    assert rule.suite_id == manifest.suite_id
    assert (rule.alpha, rule.margin, rule.stakes, rule.max_rounds, rule.max_errored_pairs) == (
        manifest.alpha,
        manifest.delta,
        manifest.stakes,
        manifest.max_rounds,
        manifest.max_errored_pairs,
    )
    assert not rule.fixed_before_runs
    for name in FILENAMES[:2]:
        with (out / name).open(newline="", encoding="utf-8") as stream:
            reader = csv.DictReader(stream)
            assert reader.fieldnames == ["task_id", "outcome", "round"]
            rows = list(reader)
        order = [(int(row["round"]), row["task_id"]) for row in rows]
        assert order == sorted(order)
        assert len(rows) == len(rule.tasks) * rounds
        assert set(order) == {(r, task) for r in range(1, rounds + 1) for task in rule.tasks}
    stored = SuiteDecision.model_validate_json((store / "decision.json").read_text())
    json_path = tmp_path / "imported.json"
    assert (
        verdict_main(
            [
                "verdict",
                str(out / "rule.yaml"),
                "--baseline",
                str(out / "baseline.csv"),
                "--candidate",
                str(out / "candidate.csv"),
                "--json",
                str(json_path),
            ]
        )
        == stored.exit_code
    )
    assert capsys.readouterr().err == ""
    imported = OutcomeDecision.model_validate_json(json_path.read_text())
    assert imported.validate_seal()
    assert imported.verdict == stored.verdict == verdict
    assert imported.stopped_at_round == stored.stopped_at_round == rounds
    assert imported.last_round_evaluated == rounds
    for actual, expected in zip(imported.history, stored.history, strict=True):
        assert actual.round == expected.round
        assert actual.pairs == expected.pairs
        assert actual.counts == expected.counts
        assert actual.pass_wealth == expected.pass_wealth
        assert actual.block_wealth == expected.block_wealth
        assert actual.pass_crossed == expected.pass_crossed
        assert actual.block_crossed == expected.block_crossed
        assert actual.verdict == expected.verdict
    assert imported.history[-1].pass_wealth == pass_wealth
    assert imported.history[-1].block_wealth == block_wealth


def test_packaged_files_match_run_one() -> None:
    packaged = files("arci.demo.outcomes").joinpath("order-desk-run-1")
    for name in FILENAMES:
        assert packaged.joinpath(name).read_bytes() == (EXAMPLES / "run-1" / name).read_bytes()


@pytest.mark.parametrize("arguments", [[], ["missing"], ["missing\nstore", "out"]])
def test_export_failure_is_one_line(
    arguments: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(arguments) == 3
    output = capsys.readouterr()
    assert not output.out
    assert len(output.err.splitlines()) == 1
    assert output.err.startswith("error: ")
    assert "Traceback" not in output.err
