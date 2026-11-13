"""arms rows, the uninjected-failure definition, passed/not-passed, and retries.

From the "Contract" section of R1-tool-outcomes.md.
"""

from __future__ import annotations

import pytest
from pydantic import JsonValue

from arci.report import tool_outcomes
from arci.schema import Outcome
from tests.unit.tool_outcomes_blind.helpers import finish, start, trial


def test_arms_always_two_rows_zero_trials() -> None:
    out = tool_outcomes([])
    assert out["arms"] == [
        {
            "arm": "baseline",
            "trials": 0,
            "uninjected_failure_trials": 0,
            "uninjected_then_passed": 0,
            "uninjected_then_not_passed": 0,
        },
        {
            "arm": "candidate",
            "trials": 0,
            "uninjected_failure_trials": 0,
            "uninjected_then_passed": 0,
            "uninjected_then_not_passed": 0,
        },
    ]
    assert out["tools"] == []


def test_arms_order_is_baseline_then_candidate_with_nonzero_counts() -> None:
    trials = [
        trial(arm="baseline"),
        trial(arm="baseline"),
        trial(arm="candidate"),
    ]
    out = tool_outcomes(trials)
    assert [row["arm"] for row in out["arms"]] == ["baseline", "candidate"]
    assert out["arms"][0]["trials"] == 2
    assert out["arms"][1]["trials"] == 1


# --- the uninjected-failure definition, one clause at a time ----------------------------


def _single_finish_arm_failure_count(ok: JsonValue, injected_by: JsonValue, present: bool) -> int:
    t = trial(
        "t",
        arm="baseline",
        events=[
            finish("t", 0, "tool_a", ok=ok, injected_by=injected_by if present else "__absent__")
        ],
    )
    out = tool_outcomes([t])
    return out["arms"][0]["uninjected_failure_trials"]


def test_ok_false_injected_by_missing_is_counted() -> None:
    assert _single_finish_arm_failure_count(False, None, present=False) == 1


def test_ok_false_injected_by_none_is_counted() -> None:
    assert _single_finish_arm_failure_count(False, None, present=True) == 1


def test_ok_false_injected_by_empty_string_is_counted() -> None:
    assert _single_finish_arm_failure_count(False, "", present=True) == 1


def test_ok_false_injected_by_nonempty_string_excluded() -> None:
    assert _single_finish_arm_failure_count(False, "tool_timeout", present=True) == 0


def test_ok_false_injected_by_int_marker_excluded_as_malformed() -> None:
    assert _single_finish_arm_failure_count(False, 7, present=True) == 0


def test_ok_false_injected_by_list_marker_excluded_as_malformed() -> None:
    assert _single_finish_arm_failure_count(False, [], present=True) == 0


def test_ok_false_injected_by_empty_result_excluded() -> None:
    # empty_result only replaces the value and sets the marker; ok can still be False, but
    # the finish is still marked, so it is excluded here.
    assert _single_finish_arm_failure_count(False, "empty_result", present=True) == 0


def test_ok_zero_int_not_counted() -> None:
    # ok must be exactly the bool False, not merely falsy.
    assert _single_finish_arm_failure_count(0, None, present=False) == 0


def test_ok_none_not_counted() -> None:
    assert _single_finish_arm_failure_count(None, None, present=False) == 0


@pytest.mark.parametrize(
    "ok,injected_by,present",
    [
        (False, None, False),
        (False, None, True),
        (False, "", True),
    ],
)
def test_counted_uninjected_failure_gives_no_tool_row_without_a_start(
    ok: JsonValue, injected_by: JsonValue, present: bool
) -> None:
    # A tool seen only through a finish event (uninjected failure or not) with no start still
    # gets rows in `tools` per the contract ("a tool seen only in an uninjected failed finish
    # with no start gets rows"). trials_started is 0 because there was no tool_start.
    marker = injected_by if present else "__absent__"
    t = trial(
        "t",
        arm="baseline",
        events=[finish("t", 0, "tool_a", ok=ok, injected_by=marker)],
    )
    out = tool_outcomes([t])
    rows = {(r["tool"], r["arm"]): r for r in out["tools"]}
    assert set(rows) == {("tool_a", "baseline"), ("tool_a", "candidate")}
    base = rows[("tool_a", "baseline")]
    assert base["trials"] == 1
    assert base["trials_started"] == 0
    assert base["trials_not_started"] == 1
    assert base["starts"] == 0
    assert base["uninjected_failures"] == 1
    assert base["uninjected_failure_trials"] == 1


@pytest.mark.parametrize(
    "ok,injected_by,present",
    [
        (False, "tool_timeout", True),
        (False, 7, True),
        (False, [], True),
        (0, None, False),
        (None, None, False),
    ],
)
def test_excluded_finish_with_no_start_gives_no_tool_row(
    ok: JsonValue, injected_by: JsonValue, present: bool
) -> None:
    marker = injected_by if present else "__absent__"
    t = trial(
        "t",
        arm="baseline",
        events=[finish("t", 0, "tool_a", ok=ok, injected_by=marker)],
    )
    out = tool_outcomes([t])
    assert out["tools"] == []
    assert out["arms"][0]["uninjected_failure_trials"] == 0


# --- passed vs. not-passed ---------------------------------------------------------------


def test_uninjected_failure_then_pass_counts_as_passed() -> None:
    t = trial("t", arm="candidate", outcome=Outcome.PASS, events=[finish("t", 0, "x", ok=False)])
    out = tool_outcomes([t])
    row = out["arms"][1]
    assert row["uninjected_failure_trials"] == 1
    assert row["uninjected_then_passed"] == 1
    assert row["uninjected_then_not_passed"] == 0


def test_uninjected_failure_then_fail_counts_as_not_passed() -> None:
    t = trial("t", arm="candidate", outcome=Outcome.FAIL, events=[finish("t", 0, "x", ok=False)])
    out = tool_outcomes([t])
    row = out["arms"][1]
    assert row["uninjected_then_passed"] == 0
    assert row["uninjected_then_not_passed"] == 1


def test_uninjected_failure_then_error_counts_as_not_passed() -> None:
    t = trial("t", arm="candidate", outcome=Outcome.ERROR, events=[finish("t", 0, "x", ok=False)])
    out = tool_outcomes([t])
    row = out["arms"][1]
    assert row["uninjected_then_passed"] == 0
    assert row["uninjected_then_not_passed"] == 1


# --- a retry: two failed finishes in one trial ----------------------------------------


def test_retry_two_failed_finishes_count_two_failures_one_trial() -> None:
    t = trial(
        "t",
        arm="baseline",
        events=[
            start("t", 0, "fetch"),
            finish("t", 1, "fetch", ok=False),
            start("t", 2, "fetch"),
            finish("t", 3, "fetch", ok=False),
        ],
    )
    out = tool_outcomes([t])
    assert out["arms"][0]["trials"] == 1
    assert out["arms"][0]["uninjected_failure_trials"] == 1
    row = next(r for r in out["tools"] if r["arm"] == "baseline")
    assert row["starts"] == 2
    assert row["trials_started"] == 1
    assert row["uninjected_failures"] == 2
    assert row["uninjected_failure_trials"] == 1
