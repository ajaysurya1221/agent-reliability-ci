"""Literal event counting, independent of gate validity and failure causality."""

from __future__ import annotations

import json
from collections.abc import Sequence

import pytest
from pydantic import JsonValue

from arci.report import tool_outcomes, tool_outcomes_markdown
from arci.schema import Event, EventKind, Outcome, Termination, TrialEnvelope
from arci.suite_gate import decide_suite
from arci.suite_report import render_suite_json, render_suite_markdown
from tests.unit.suite_report.test_reports import evidence

INTRO = (
    "Counts of recorded tool attempts. An uninjected failure is a recorded tool_finish "
    "that failed with no injection marker; the record does not show why it failed, and "
    "an earlier injected fault can be the cause. A tool with no recorded start in a trial "
    "may simply not be needed by that task; compare the two arms. Retries by middleware "
    "count as attempts. Counts are descriptive and decide nothing."
)


def trial(
    events: Sequence[tuple[EventKind, dict[str, JsonValue]]] = (),
    *,
    arm: str = "baseline",
    outcome: Outcome = Outcome.PASS,
) -> TrialEnvelope:
    return TrialEnvelope.create(
        spec_sha256="0" * 64,
        experiment_id="test",
        trial_id="same-id",
        pair_id="pair",
        arm=arm,
        variant=arm,
        task_id="task",
        condition_id="clean",
        seed=0,
        outcome=outcome,
        termination=Termination.COMPLETED,
        events=tuple(
            Event(trial_id="same-id", seq=i, kind=kind, payload=payload)
            for i, (kind, payload) in enumerate(events)
        ),
    )


def test_empty_has_two_arms_and_no_tools() -> None:
    assert tool_outcomes([]) == {
        "arms": [
            dict(
                arm=arm,
                trials=0,
                uninjected_failure_trials=0,
                uninjected_then_passed=0,
                uninjected_then_not_passed=0,
            )
            for arm in ("baseline", "candidate")
        ],
        "tools": [],
    }
    assert tool_outcomes_markdown([]) == [
        "",
        "## Tool outcomes (descriptive)",
        "",
        INTRO,
        "",
        "| Arm | Trials | Trials with an uninjected failure | Then passed | Then not passed |",
        "|---|---:|---:|---:|---:|",
        "| baseline | 0 | 0 | 0 | 0 |",
        "| candidate | 0 | 0 | 0 | 0 |",
        "",
        "No tool starts recorded.",
    ]


@pytest.mark.parametrize("marker", [None, "", "missing", "empty_result", " ", 0, 1, False, [], {}])
def test_injection_marker_definition(marker: JsonValue) -> None:
    payload: dict[str, JsonValue] = {"tool": "x", "ok": False}
    if marker != "missing":
        payload["injected_by"] = marker
    result = tool_outcomes([trial([("tool_finish", payload)])])
    expected = marker is None or marker == "" or marker == "missing"
    assert result["arms"][0]["uninjected_failure_trials"] == int(expected)
    assert len(result["tools"]) == (2 if expected else 0)


@pytest.mark.parametrize("ok", [False, True, 0, 0.0, "", "false", None, [], {}])
def test_ok_must_be_false_boolean(ok: JsonValue) -> None:
    result = tool_outcomes([trial([("tool_finish", {"tool": "x", "ok": ok})])])
    assert result["arms"][0]["uninjected_failure_trials"] == int(ok is False)


@pytest.mark.parametrize("tool", [None, 7, False, [], {}])
def test_non_string_tool_is_ignored(tool: JsonValue) -> None:
    result = tool_outcomes(
        [
            trial(
                [
                    ("tool_start", {"tool": tool}),
                    ("tool_finish", {"tool": tool, "ok": False}),
                ]
            )
        ]
    )
    assert result["tools"] == []
    assert result["arms"][0]["uninjected_failure_trials"] == 0
    assert result["arms"][0]["trials"] == 1


def test_retries_count_attempts_but_failure_trials_only_once() -> None:
    events: list[tuple[EventKind, dict[str, JsonValue]]] = [
        ("tool_start", {"tool": "lookup"}),
        ("tool_finish", {"tool": "lookup", "ok": False}),
    ] * 2
    # Identical IDs do not deduplicate input envelopes. No event means no attempt.
    trials = [trial(events), trial(outcome=Outcome.FAIL), trial(events, outcome=Outcome.ERROR)]
    before = [t.model_dump_json() for t in trials]
    result = tool_outcomes(trials)
    assert result["arms"][0] == dict(
        arm="baseline",
        trials=3,
        uninjected_failure_trials=2,
        uninjected_then_passed=1,
        uninjected_then_not_passed=1,
    )
    assert result["tools"][0] == dict(
        arm="baseline",
        tool="lookup",
        trials=3,
        trials_started=2,
        trials_not_started=1,
        starts=4,
        uninjected_failures=4,
        uninjected_failure_trials=2,
    )
    assert result == tool_outcomes(list(reversed(trials)))
    assert [t.model_dump_json() for t in trials] == before


@pytest.mark.parametrize("outcome", list(Outcome))
@pytest.mark.parametrize("kind", ["replay_miss", "ValueError", "timeout"])
def test_every_failure_cause_and_non_pass_outcome_is_counted(outcome: Outcome, kind: str) -> None:
    result = tool_outcomes(
        [
            trial(
                [
                    ("tool_finish", {"tool": "x", "ok": False, "error_kind": kind}),
                    ("tool_finish", {"tool": "y", "ok": False}),
                ],
                outcome=outcome,
            )
        ]
    )
    assert result["arms"][0]["uninjected_failure_trials"] == 1
    assert result["arms"][0]["uninjected_then_passed"] == int(outcome is Outcome.PASS)
    assert result["arms"][0]["uninjected_then_not_passed"] == int(outcome is not Outcome.PASS)


def test_union_order_incomplete_calls_and_independent_event_payloads() -> None:
    result = tool_outcomes(
        [
            trial(
                [
                    ("tool_start", {"tool": "z", "call_id": "one"}),
                    ("tool_finish", {"tool": "A", "call_id": "one", "ok": False}),
                    ("tool_start", {"tool": "decision:systemone"}),
                    ("tool_finish", {"tool": "successful-only", "ok": True}),
                    (
                        "tool_finish",
                        {"tool": "injected-only", "ok": False, "injected_by": "empty_result"},
                    ),
                    ("model_step", {"tool": "not-a-tool-event", "ok": False}),
                    ("tool_finish", {"tool": "missing-ok"}),
                ],
                arm="candidate",
            ),
            trial(),
        ]
    )
    assert [(r["tool"], r["arm"]) for r in result["tools"]] == [
        (tool, arm)
        for tool in ("A", "decision:systemone", "z")
        for arm in ("baseline", "candidate")
    ]
    assert result["tools"][1] == dict(
        tool="A",
        arm="candidate",
        trials=1,
        trials_started=0,
        trials_not_started=1,
        starts=0,
        uninjected_failures=1,
        uninjected_failure_trials=1,
    )
    assert result["tools"][5]["starts"] == 1
    assert result["tools"][5]["uninjected_failures"] == 0
    assert all(r["trials_not_started"] == 1 for r in result["tools"][::2])


def test_unknown_arms_ignored_and_pass_uses_enum_identity() -> None:
    t = trial([("tool_finish", {"tool": "x", "ok": False})])
    assert tool_outcomes([t.model_copy(update={"arm": "other"})]) == tool_outcomes([])
    assert (
        tool_outcomes([t.model_copy(update={"outcome": "PASS"})])["arms"][0][
            "uninjected_then_not_passed"
        ]
        == 1
    )


@pytest.mark.parametrize(
    "name,span",
    [
        ("lookup", "`lookup`"),
        ("a|`b", "`` a\\|`b ``"),
        ("`a``b`", "``` `a``b` ```"),
        ("`", "`` ` ``"),
        ("a\nb", "`a<br>b`"),
        (" padded ", "`  padded  `"),
    ],
)
def test_markdown_code_span_escaping(name: str, span: str) -> None:
    lines = tool_outcomes_markdown([trial([("tool_start", {"tool": name})])])
    assert f"| {span} | baseline | 1 | 1 | 0 | 1 | 0 | 0 |" in lines


def test_partial_round_suite_json_and_markdown_keep_counts_descriptive() -> None:
    manifest, original = evidence("BLOCK")
    trials = (
        original[0].model_copy(
            update={
                "events": trial(
                    [
                        ("tool_start", {"tool": "x"}),
                        ("tool_finish", {"tool": "x", "ok": False}),
                    ]
                ).events
            }
        ),
    )
    decision = decide_suite(manifest, trials)
    report = json.loads(render_suite_json(manifest, decision, trials))
    assert report["tool_outcomes"] == tool_outcomes(trials)
    assert "tool_outcomes" not in report["decision"]
    assert report["decision"] == decision.model_dump(mode="json")
    md = render_suite_markdown(manifest, decision, trials)
    assert "\n".join(tool_outcomes_markdown(trials)) in md
    assert (
        md.index("## Fault accounting") < md.index("## Tool outcomes") < md.index("## Prior runs")
    )
    assert "VERDICT: ERROR" in md
