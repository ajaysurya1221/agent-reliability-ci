"""Per-tool row construction: union, sorting, start/finish counting, filtering.

From the "Contract" section of R1-tool-outcomes.md.
"""

from __future__ import annotations

from arci.report import tool_outcomes
from arci.schema import Outcome
from tests.unit.tool_outcomes_blind.helpers import finish, start, trial


def test_tools_sorted_by_name_baseline_then_candidate_per_tool() -> None:
    trials = [
        trial("c", arm="candidate", events=[start("c", 0, "a_tool")]),
        trial("b", arm="baseline", events=[start("b", 0, "b_tool")]),
    ]
    out = tool_outcomes(trials)
    assert [(r["tool"], r["arm"]) for r in out["tools"]] == [
        ("a_tool", "baseline"),
        ("a_tool", "candidate"),
        ("b_tool", "baseline"),
        ("b_tool", "candidate"),
    ]


def test_tool_used_by_only_one_arm_still_gets_both_rows() -> None:
    trials = [
        trial("b1", arm="baseline", events=[start("b1", 0, "only_baseline")]),
        trial("b2", arm="baseline"),
        trial("c1", arm="candidate"),
        trial("c2", arm="candidate"),
    ]
    out = tool_outcomes(trials)
    rows = {r["arm"]: r for r in out["tools"] if r["tool"] == "only_baseline"}
    assert set(rows) == {"baseline", "candidate"}
    assert rows["baseline"]["trials"] == 2
    assert rows["baseline"]["trials_started"] == 1
    assert rows["baseline"]["starts"] == 1
    assert rows["candidate"]["trials"] == 2
    assert rows["candidate"]["trials_started"] == 0
    assert rows["candidate"]["trials_not_started"] == 2
    assert rows["candidate"]["starts"] == 0


def test_tool_seen_only_in_successful_finish_with_no_start_gets_no_row() -> None:
    t = trial("t", arm="baseline", events=[finish("t", 0, "clean_tool", ok=True)])
    out = tool_outcomes([t])
    assert out["tools"] == []


def test_tool_seen_only_in_injected_failure_finish_with_no_start_gets_no_row() -> None:
    t = trial(
        "t",
        arm="baseline",
        events=[finish("t", 0, "hurt_tool", ok=False, injected_by="tool_timeout")],
    )
    out = tool_outcomes([t])
    assert out["tools"] == []


def test_non_string_tool_field_is_ignored_entirely() -> None:
    t = trial(
        "t",
        arm="baseline",
        events=[
            start("t", 0, 5),
            finish("t", 1, [], ok=False),
            finish("t", 2, None, ok=False),
        ],
    )
    out = tool_outcomes([t])
    assert out["tools"] == []


def test_non_string_tool_mixed_with_a_valid_tool_only_the_valid_one_gets_a_row() -> None:
    t = trial(
        "t",
        arm="baseline",
        events=[start("t", 0, "real_tool"), start("t", 1, 42)],
    )
    out = tool_outcomes([t])
    assert {r["tool"] for r in out["tools"]} == {"real_tool"}
    row = next(r for r in out["tools"] if r["arm"] == "baseline")
    assert row["starts"] == 1


def test_trials_not_started_is_trials_minus_trials_started() -> None:
    trials = [
        trial("b1", arm="baseline", events=[start("b1", 0, "t")]),
        trial("b2", arm="baseline", events=[start("b2", 0, "t")]),
        trial("b3", arm="baseline"),
    ]
    out = tool_outcomes(trials)
    row = next(r for r in out["tools"] if r["arm"] == "baseline")
    assert row["trials"] == 3
    assert row["trials_started"] == 2
    assert row["trials_not_started"] == 1


def test_starts_counts_events_not_trials() -> None:
    t = trial(
        "t", arm="baseline", events=[start("t", 0, "t"), start("t", 1, "t"), start("t", 2, "t")]
    )
    out = tool_outcomes([t])
    row = next(r for r in out["tools"] if r["arm"] == "baseline")
    assert row["starts"] == 3
    assert row["trials_started"] == 1


def test_decision_tool_names_are_not_filtered() -> None:
    t = trial(
        "t",
        arm="baseline",
        events=[
            start("t", 0, "decision:systemone"),
            finish("t", 1, "decision:systemone", ok=False),
        ],
    )
    out = tool_outcomes([t])
    names = {r["tool"] for r in out["tools"]}
    assert "decision:systemone" in names
    row = next(r for r in out["tools"] if r["arm"] == "baseline")
    assert row["starts"] == 1
    assert row["uninjected_failures"] == 1


def test_incomplete_call_start_without_finish() -> None:
    t = trial("t", arm="baseline", events=[start("t", 0, "fetch")])
    out = tool_outcomes([t])
    row = next(r for r in out["tools"] if r["arm"] == "baseline")
    assert row["starts"] == 1
    assert row["trials_started"] == 1
    assert row["uninjected_failures"] == 0
    assert row["uninjected_failure_trials"] == 0
    assert out["arms"][0]["uninjected_failure_trials"] == 0


def test_per_tool_trials_count_matches_arm_trial_count_regardless_of_usage() -> None:
    # "trials" on a ToolOutcomeRow is the arm's total trial count, not the trials that used it.
    trials = [
        trial("b1", arm="baseline", events=[start("b1", 0, "x")]),
        trial("b2", arm="baseline"),
        trial("b3", arm="baseline"),
    ]
    out = tool_outcomes(trials)
    row = next(r for r in out["tools"] if r["arm"] == "baseline")
    assert row["trials"] == 3 == out["arms"][0]["trials"]


def test_errored_round_or_incomplete_round_trials_are_still_all_counted() -> None:
    # All trials given are counted, complete rounds or not: just a smoke check that mixing
    # outcomes doesn't drop anything.
    trials = [
        trial("b1", arm="baseline", outcome=Outcome.ERROR, events=[finish("b1", 0, "x", ok=False)]),
        trial("b2", arm="baseline", outcome=Outcome.PASS),
    ]
    out = tool_outcomes(trials)
    assert out["arms"][0]["trials"] == 2
    assert out["arms"][0]["uninjected_failure_trials"] == 1
    assert out["arms"][0]["uninjected_then_not_passed"] == 1
