"""ADR 0020 C2 on the items and evaluations returned by run_experiment."""

import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TypedDict

import pytest

from examples.integrations.langfuse_rows import langfuse_rows, write_jsonl

REAL = Path(__file__).with_name("real") / "langfuse"
EXPECTED_IDS = [f"task-w{n:02d}" for n in range(1, 21)]


class Item(TypedDict):
    metadata: dict[str, str]
    expected_output: str


@dataclass
class Evaluation:
    name: str
    value: object


@dataclass
class Result:
    item: Item
    evaluations: list[Evaluation]


class RawResult(TypedDict):
    item: Item
    evaluations: list[dict[str, object]]
    output: str


def raw_items(mode: str) -> list[RawResult]:
    return json.loads((REAL / f"item_results-{mode}.json").read_bytes())["items"]


def result_objects(items: list[RawResult]) -> list[Result]:
    return [
        Result(r["item"], [Evaluation(str(e["name"]), e["value"]) for e in r["evaluations"]])
        for r in items
    ]


def task_id(item: Item) -> str:
    return item["metadata"]["task_id"]


@pytest.mark.parametrize("mode", ["pass", "fail"])
def test_c02_real_results_and_missing_items(mode: str, tmp_path: Path) -> None:
    raw = raw_items(mode)
    outcomes = dict.fromkeys(EXPECTED_IDS, "error")
    for record in raw:
        item = record["item"]
        if any(e["name"] == "contains_word" for e in record["evaluations"]):
            outcomes[item["metadata"]["task_id"]] = (
                "pass" if item["expected_output"] in record["output"] else "fail"
            )
    expected = [{"task_id": key, "outcome": value} for key, value in outcomes.items()]
    results = result_objects(raw)
    rows = langfuse_rows(EXPECTED_IDS, reversed(results), "contains_word", task_id)
    assert rows == expected
    assert len(rows) == 20
    by_id = {row["task_id"]: row["outcome"] for row in rows}
    assert by_id["task-w07"] == "error"
    assert by_id["task-w13"] == "error"
    path = tmp_path / "out.jsonl"
    write_jsonl(path, EXPECTED_IDS, results, "contains_word", task_id)
    assert [json.loads(line) for line in path.read_bytes().splitlines()] == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (True, "pass"),
        (1, "pass"),
        (1.0, "pass"),
        (False, "fail"),
        (0, "fail"),
        (0.0, "fail"),
        ("yes", "error"),
        ("1", "error"),
        (0.5, "error"),
        (None, "error"),
    ],
)
def test_c02_named_binary_score(value: object, expected: str) -> None:
    item = result_objects(raw_items("pass"))[0]
    item.evaluations.append(Evaluation("another", value))
    rows = langfuse_rows(["task-w01"], [item], "another", task_id)
    assert rows == [{"task_id": "task-w01", "outcome": expected}]


def test_c02_missing_named_evaluation() -> None:
    item = result_objects(raw_items("pass"))[0]
    rows = langfuse_rows(["task-w01"], [item], "absent", task_id)
    assert rows == [{"task_id": "task-w01", "outcome": "error"}]


def test_c02_duplicate_result_id() -> None:
    item = result_objects(raw_items("pass"))[0]
    with pytest.raises(ValueError, match="duplicate task id"):
        langfuse_rows(EXPECTED_IDS, [item, item], "contains_word", task_id)


def test_c02_duplicate_expected_id() -> None:
    with pytest.raises(ValueError, match="duplicate expected task id"):
        langfuse_rows(
            [*EXPECTED_IDS, EXPECTED_IDS[0]],
            result_objects(raw_items("pass")),
            "contains_word",
            task_id,
        )


def test_c02_unexpected_result_id() -> None:
    with pytest.raises(ValueError, match="unexpected task id"):
        langfuse_rows(EXPECTED_IDS[1:], result_objects(raw_items("pass")), "contains_word", task_id)


def test_c02_duplicate_named_evaluation(tmp_path: Path) -> None:
    item = result_objects(raw_items("pass"))[0]
    path = tmp_path / "out.jsonl"
    with pytest.raises(ValueError, match="duplicate evaluation"):
        write_jsonl(
            path,
            EXPECTED_IDS,
            [replace(item, evaluations=item.evaluations * 2)],
            "contains_word",
            task_id,
        )
    assert not path.exists()
