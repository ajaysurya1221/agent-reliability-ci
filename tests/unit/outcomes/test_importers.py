"""Importer contracts, including expectations independently read from real outputs."""

from __future__ import annotations

import json
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

import pytest

from arci.importers import OutcomeError, loads_json
from arci.importers.inspect_log import read as read_inspect
from arci.importers.junit import read as read_junit

REAL = Path(__file__).parent / "real"


def inspect_log(
    *,
    ids: list[object] | None = None,
    scorers: list[str] | None = None,
    samples: list[dict[str, object]] | None = None,
    epochs: int = 2,
) -> dict[str, Any]:
    return {
        "eval": {
            "config": {"epochs": epochs},
            "dataset": {"sample_ids": ["a"] if ids is None else ids},
            "scorers": [{"name": name} for name in (["match"] if scorers is None else scorers)],
        },
        "samples": (
            [{"id": "a", "epoch": 1, "scores": {"match": {"value": "C"}}}]
            if samples is None
            else samples
        ),
    }


def parse_inspect(
    source: dict[str, Any] | str,
    *,
    tasks: frozenset[str] | None = None,
    score: str | None = None,
    threshold: Fraction | None = None,
) -> Any:
    return read_inspect(
        json.dumps(source) if isinstance(source, dict) else source,
        path="log.json",
        arm="baseline",
        position=1,
        tasks=tasks,
        seen=set(),
        score=score,
        pass_at_least=threshold,
    )


@pytest.mark.parametrize("arm", ["baseline", "candidate"])
@pytest.mark.parametrize("scorer", ["match", "includes"])
def test_real_inspect_independent_expectations(arm: str, scorer: str) -> None:
    path = REAL / "inspect" / f"{arm}.json"
    raw = json.loads(path.read_text())
    expected: dict[tuple[str, int], str | None] = {}
    for sample in raw["samples"]:
        if isinstance(sample.get("error"), dict):
            value = "error"
        elif scorer not in sample["scores"]:
            value = None
        else:
            code = sample["scores"][scorer]["value"]
            assert code in ("C", "I")
            value = "pass" if code == "C" else "fail"
        expected[str(sample["id"]), sample["epoch"]] = value
    task_ids = frozenset(str(value) for value in raw["eval"]["dataset"]["sample_ids"])
    actual = read_inspect(
        path.read_text(),
        path=str(path),
        arm=arm,
        position=7,
        tasks=task_ids,
        seen=set(),
        score=scorer,
    )
    assert {(row.task_id, row.round): row.outcome for row in actual.rows} == expected
    assert tuple(actual.rounds) == tuple(range(1, raw["eval"]["config"]["epochs"] + 1))
    assert len(actual.rows) == 27
    assert sum(row.outcome == "error" for row in actual.rows) == (arm == "candidate")
    assert not actual.assigned
    assert actual.score == scorer


@pytest.mark.parametrize("name,count", [("single.xml", 6), ("repeat.xml", 18)])
def test_real_junit_independent_expectations(name: str, count: int) -> None:
    path = REAL / "pytest" / name
    raw = ElementTree.fromstring(path.read_bytes())
    expected: dict[str, str] = {}
    for case in raw.iter("testcase"):
        key = f"{case.attrib['classname']}::{case.attrib['name']}"
        if case.find("error") is not None or case.find("skipped") is not None:
            expected[key] = "error"
        elif case.find("failure") is not None:
            expected[key] = "fail"
        else:
            expected[key] = "pass"
    actual = read_junit(
        path.read_text(),
        path=str(path),
        arm="candidate",
        position=3,
        tasks=frozenset(expected),
        seen=set(),
    )
    assert {row.task_id: row.outcome for row in actual.rows} == expected
    assert len(actual.rows) == count
    assert tuple(actual.rounds) == (3,)
    assert actual.assigned
    assert all(row.round == 3 for row in actual.rows)
    if name == "repeat.xml":
        assert all(row.task_id.endswith("3]") for row in actual.rows)


def test_junit_recursive_status_priority() -> None:
    source = """<testsuites><testsuite><testsuite>
    <testcase classname="c" name="a"><failure/><error/></testcase>
    <testcase classname="c" name="b"><failure/><skipped/></testcase>
    <testcase classname="c" name="c"><failure/></testcase>
    <testcase classname="c" name="d"/>
    </testsuite></testsuite></testsuites>"""
    actual = read_junit(source, path="a.xml", arm="baseline", position=1, tasks=None, seen=set())
    assert [row.outcome for row in actual.rows] == ["error", "error", "fail", "pass"]


@pytest.mark.parametrize(
    "source,expected",
    [
        (
            '<testsuite><testcase classname="c" name="unknown"><skipped/></testcase></testsuite>',
            "unknown task id: c::unknown",
        ),
        (
            '<testsuite><testcase classname="c" name="a"/>'
            '<testcase classname="c" name="a"/></testsuite>',
            "duplicate outcome for baseline c::a round 1",
        ),
        (
            '<testsuite><testcase classname="c::a" name="b"/>'
            '<testcase classname="c" name="a::b"/></testsuite>',
            "duplicate outcome for baseline c::a::b round 1",
        ),
        (
            '<testsuite><testcase classname="c" name=""/></testsuite>',
            "a test case has an empty classname or name: a.xml",
        ),
        (
            '<testsuite><testcase name="a"/></testsuite>',
            "a test case has an empty classname or name: a.xml",
        ),
        ("<result/>", "unreadable or unsupported input: a.xml"),
        ("<testsuite>", "unreadable or unsupported input: a.xml"),
        (
            '<?xml version="1.0" encoding="utf-16"?><testsuite/>',
            "unreadable or unsupported input: a.xml",
        ),
        (
            '<!DOCTYPE testsuite [<!ENTITY secret "x">]><testsuite/>',
            "unreadable or unsupported input: a.xml",
        ),
        ('<!ENTITY secret "x"><testsuite/>', "unreadable or unsupported input: a.xml"),
    ],
)
def test_junit_fixed_errors(source: str, expected: str) -> None:
    with pytest.raises(OutcomeError) as error:
        read_junit(
            source,
            path="a.xml",
            arm="baseline",
            position=1,
            tasks=frozenset({"c::a", "c::a::b"}),
            seen=set(),
        )
    assert error.value.reason == expected


def test_junit_utf8_bom() -> None:
    actual = read_junit(
        '\ufeff<?xml version="1.0" encoding="UTF-8"?>'
        '<testsuite><testcase classname="c" name="a"/></testsuite>',
        path="a.xml",
        arm="baseline",
        position=4,
        tasks=None,
        seen=set(),
    )
    assert [(row.task_id, row.outcome) for row in actual.rows] == [("c::a", "pass")]
    assert tuple(actual.rounds) == (4,)


def test_junit_without_test_cases_is_e6() -> None:
    with pytest.raises(OutcomeError, match=r"unreadable or unsupported input: a\.xml"):
        read_junit(
            "<testsuites><testsuite/></testsuites>",
            path="a.xml",
            arm="baseline",
            position=1,
            tasks=None,
            seen=set(),
        )


def test_inspect_without_samples_is_e6() -> None:
    with pytest.raises(OutcomeError, match=r"unreadable or unsupported input: log\.json"):
        parse_inspect(inspect_log(samples=[]))


@pytest.mark.parametrize(
    "source,score,expected",
    [
        (inspect_log(ids=["unknown"], samples=[]), None, "unknown task id: unknown"),
        (
            inspect_log(samples=[{"id": "a", "epoch": 1}, {"id": "a", "epoch": 1}]),
            None,
            "duplicate outcome for baseline a round 1",
        ),
        (
            inspect_log(scorers=["match", "includes"]),
            None,
            "log.json reports more than one scorer and the rule sets no score",
        ),
        (inspect_log(), "missing", "the rule's score missing is absent from log.json"),
        (
            inspect_log(samples=[{"id": "a", "epoch": 1, "scores": {"match": {"value": "maybe"}}}]),
            None,
            "outcome maybe for a cannot be read as pass, fail or error",
        ),
        (
            inspect_log(samples=[{"id": "a", "epoch": 1, "scores": {"match": {"value": 1}}}]),
            None,
            "outcome 1 for a cannot be read as pass, fail or error",
        ),
        (
            inspect_log(ids=[7, "7"], samples=[]),
            None,
            "task id 7 appears as both an integer and a string",
        ),
        (
            inspect_log(ids=[7], samples=[{"id": "7", "epoch": 1}]),
            None,
            "task id 7 appears as both an integer and a string",
        ),
    ],
)
def test_inspect_fixed_errors(source: dict[str, Any], score: str | None, expected: str) -> None:
    with pytest.raises(OutcomeError) as error:
        parse_inspect(source, tasks=frozenset({"a", "7"}), score=score)
    assert error.value.reason == expected


@pytest.mark.parametrize(
    "source",
    [
        {},
        {"eval": {"config": {"epochs": 1}, "scorers": [{"name": "match"}]}, "samples": []},
        inspect_log(epochs=0),
        inspect_log(samples=[{"id": "a", "epoch": True}]),
        inspect_log(samples=[{"id": "a", "epoch": 3}]),
        inspect_log(samples=[{"id": "b", "epoch": 1}]),
        inspect_log(samples=[{"id": "a", "epoch": 1, "error": "broken"}]),
        inspect_log(samples=[{"id": "a", "epoch": 1, "scores": None}]),
        inspect_log(samples=[{"id": "a", "epoch": 1, "scores": {"unknown": {"value": "C"}}}]),
        inspect_log(ids=[True], samples=[]),
        inspect_log(ids=["a", "a"], samples=[]),
        inspect_log(scorers=[]),
        inspect_log(scorers=["match", "match"]),
        '{"eval":{},"eval":{}}',
        '{"value":NaN}',
        '{"value":Infinity}',
    ],
)
def test_inspect_bad_structure_is_e6(source: dict[str, Any] | str) -> None:
    with pytest.raises(OutcomeError) as error:
        parse_inspect(source)
    assert error.value.reason == "unreadable or unsupported input: log.json"


def test_inspect_eval_refused_before_content() -> None:
    with pytest.raises(OutcomeError) as error:
        read_inspect(
            "not JSON", path="source.eval", arm="baseline", position=1, tasks=None, seen=set()
        )
    assert error.value.reason == (
        ".eval files are not read: run inspect log dump FILE.eval > FILE.json and pass the JSON"
    )


@pytest.mark.parametrize(
    "value,expected",
    [
        (True, "pass"),
        (False, "fail"),
        ("C", "pass"),
        ("I", "fail"),
        (0.125, "pass"),
        (0.124, "fail"),
        (-1, "fail"),
    ],
)
def test_inspect_outcome_mapping(value: object, expected: str) -> None:
    source = inspect_log(samples=[{"id": "a", "epoch": 1, "scores": {"match": {"value": value}}}])
    actual = parse_inspect(source, threshold=Fraction(1, 8))
    assert actual.rows[0].outcome == expected


def test_inspect_numeric_spelling_is_not_binary_rounded() -> None:
    source = json.dumps(inspect_log()).replace('"C"', "0.100000000000000000000000000001")
    actual = parse_inspect(source, threshold=Fraction("0.1000000000000000000000000000005"))
    assert actual.rows[0].outcome == "pass"
    assert loads_json("0.1") == Decimal("0.1")


def test_inspect_error_precedes_score_and_missing_stays_missing() -> None:
    source = inspect_log(
        samples=[
            {"id": "a", "epoch": 1, "error": {}, "scores": {"match": {"value": "C"}}},
            {"id": "a", "epoch": 2, "scores": {}},
        ]
    )
    actual = parse_inspect(source)
    assert [row.outcome for row in actual.rows] == ["error", None]
    assert tuple(actual.rounds) == (1, 2)


def test_inspect_absent_epoch_keeps_registered_round() -> None:
    actual = parse_inspect(inspect_log(epochs=3))
    assert [(row.task_id, row.round, row.outcome) for row in actual.rows] == [("a", 1, "pass")]
    assert tuple(actual.rounds) == (1, 2, 3)


def test_discovery_retains_skips_and_repeated_ids_are_not_collapsed() -> None:
    actual = read_junit(
        '<testsuite><testcase classname="c" name="a[1-2]"><skipped/></testcase>'
        '<testcase classname="c" name="a[2-2]"/></testsuite>',
        path="a.xml",
        arm="baseline",
        position=1,
        tasks=None,
        seen=set(),
    )
    assert [row.task_id for row in actual.rows] == ["c::a[1-2]", "c::a[2-2]"]


def test_cross_file_duplicate_identity_is_retained() -> None:
    seen: set[tuple[str, int]] = set()
    source = '<testsuite><testcase classname="c" name="a"/></testsuite>'
    read_junit(source, path="a.xml", arm="baseline", position=1, tasks=None, seen=seen)
    with pytest.raises(OutcomeError) as error:
        read_junit(source, path="b.xml", arm="baseline", position=1, tasks=None, seen=seen)
    assert error.value.reason == "duplicate outcome for baseline c::a round 1"


def test_huge_epoch_header_is_a_lazy_range() -> None:
    actual = parse_inspect(inspect_log(epochs=999_999_999))
    assert isinstance(actual.rounds, range)
    assert actual.rounds == range(1, 1_000_000_000)
    assert len(actual.rows) == 1
