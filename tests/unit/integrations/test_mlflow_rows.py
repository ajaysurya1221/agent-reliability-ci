"""ADR 0020 C1 on MLflow's saved result_df records."""

import json
from pathlib import Path

import pytest

from arci.cli import main
from arci.outcome_schema import OutcomeDecision
from examples.integrations.mlflow_rows import mlflow_rows, write_jsonl

REAL = Path(__file__).with_name("real") / "mlflow"
SCORER = "contains_word"


def records(mode: str) -> list[dict[str, object]]:
    return json.loads((REAL / f"result_df-{mode}.json").read_bytes())


def word(request: object) -> str:
    assert isinstance(request, dict)
    key = request["word"]
    assert isinstance(key, str)
    return key


def test_c01_real_exports_and_descriptive_verdict(tmp_path: Path) -> None:
    for mode in ("pass", "fail"):
        raw = records(mode)
        expected: list[dict[str, str]] = []
        for record in raw:
            # Regrade the saved response with the fixture's word check.
            key = str(record["word/value"])
            outcome = "pass" if key in str(record["response"]) else "fail"
            if record["state"] != "OK" or record["contains_word/error_message"] is not None:
                outcome = "error"
            expected.append({"task_id": key, "outcome": outcome})
        rows = mlflow_rows(raw, SCORER, word)
        assert rows == expected
        outcomes = {row["task_id"]: row["outcome"] for row in rows}
        assert outcomes["w07"] == "error"
        assert outcomes["w13"] == "error"
        path = tmp_path / f"{mode}.jsonl"
        write_jsonl(path, raw, SCORER, word)
        assert [json.loads(line) for line in path.read_bytes().splitlines()] == expected

    old, new = tmp_path / "pass.jsonl", tmp_path / "fail.jsonl"
    rule, decision = tmp_path / "rule.yaml", tmp_path / "decision.json"
    assert main(["verdict-rule", "--tasks", str(old), "--out", str(rule)]) == 0
    assert (
        main(
            [
                "verdict",
                str(rule),
                "--baseline",
                str(old),
                "--candidate",
                str(new),
                "--json",
                str(decision),
            ]
        )
        == 1
    )
    report = OutcomeDecision.model_validate_json(decision.read_bytes())
    assert report.validate_seal()
    assert report.rule and not report.rule.fixed_before_runs
    assert report.history[0].counts.errored == 2
    assert report.history[0].counts.minus == 18


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (True, "pass"),
        (False, "fail"),
        ("yes", "pass"),
        ("no", "fail"),
        (1, "error"),
        (0, "error"),
        ("True", "error"),
        (None, "error"),
        (0.5, "error"),
    ],
)
def test_c01_exact_scores(value: object, expected: str) -> None:
    record = records("pass")[0]
    record["contains_word/value"] = value
    assert mlflow_rows([record], SCORER, word) == [{"task_id": "w01", "outcome": expected}]


@pytest.mark.parametrize(
    ("fields", "expected"),
    [
        ({}, "pass"),
        ({"metric/error_message": None}, "pass"),
        ({"metric/error_message": float("nan")}, "pass"),
        ({"metric/error_message": ""}, "error"),
        ({"metric/error_message": "broken"}, "error"),
    ],
)
def test_c01_scorer_error_messages(fields: dict[str, object], expected: str) -> None:
    record = {**records("pass")[0], "metric/value": True, **fields}
    assert mlflow_rows([record], "metric", word) == [{"task_id": "w01", "outcome": expected}]


def test_c01_duplicate_task_id(tmp_path: Path) -> None:
    path = tmp_path / "out.jsonl"
    with pytest.raises(ValueError, match="duplicate task id"):
        write_jsonl(path, records("pass"), SCORER, lambda _: "same")
    assert not path.exists()
