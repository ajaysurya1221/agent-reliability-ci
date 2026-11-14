"""Record shapes and verbatim reporting, checked against the design record."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from arci.outcome_report import FIXED_TEXT, render_markdown, render_terminal, text
from arci.outcome_schema import (
    NORMALISATION,
    OUTCOMES_SCHEMA_VERSION,
    OutcomeDecision,
    OutcomeInput,
    OutcomeRoundDigest,
    OutcomeRoundLook,
    OutcomeRule,
    OutcomeTaskCounts,
)
from arci.outcomes import empty_decision
from arci.schema import Verdict
from arci.suite_schema import SuiteCounts


def _rule(**changes: object) -> OutcomeRule:
    fields: dict[str, object] = {
        "schema_version": OUTCOMES_SCHEMA_VERSION,
        "suite_id": "sample",
        "tasks": ["b", "a"],
        "fixed_before_runs": True,
        "max_rounds": 200,
        "max_errored_pairs": 4,
    }
    fields.update(changes)
    return OutcomeRule.model_validate(fields)


def test_model_defaults_expand_from_inventory_without_treating_null_as_omitted() -> None:
    fields: dict[str, object] = {
        "schema_version": OUTCOMES_SCHEMA_VERSION,
        "suite_id": "defaults",
        "tasks": ["b", "a"],
        "fixed_before_runs": False,
    }
    rule = OutcomeRule.model_validate(fields)
    assert (rule.max_rounds, rule.max_errored_pairs, rule.tasks) == (200, 4, ("a", "b"))
    bounded = OutcomeRule.model_validate(fields | {"max_rounds": 300})
    assert bounded.max_errored_pairs == 6
    for field in ("max_rounds", "max_errored_pairs"):
        with pytest.raises(ValidationError):
            OutcomeRule.model_validate(fields | {field: None})


def _decision(*, fixed: bool) -> OutcomeDecision:
    counts = SuiteCounts(minus=0, zero=2, plus=0, errored=0)
    look = OutcomeRoundLook(
        round=1,
        pairs=2,
        counts=counts,
        pass_wealth="1.08429e+00",
        block_wealth="9.32851e-01",
        pass_crossed=False,
        block_crossed=False,
        verdict=Verdict.INCONCLUSIVE,
        reasons=("no test crossed",),
    )
    statements = ([text("F1")] if not fixed else []) + [text("F2"), text("F3"), text("F4", k=1)]
    if fixed:
        statements.extend((text("F5"), text("F6", alpha="1/20", bound="1/40")))
    return OutcomeDecision.create(
        rule=_rule(fixed_before_runs=fixed),
        rule_sha256="a" * 64,
        inputs=(
            OutcomeInput(path="a.csv", sha256="b" * 64, arm="baseline", format="csv", rounds=(1,)),
        ),
        rounds_registered=200,
        rounds_supplied=1,
        last_round_evaluated=1,
        round_digests=(OutcomeRoundDigest(round=1, outcomes_sha256="c" * 64),),
        history=(look,),
        tasks=(
            OutcomeTaskCounts(
                task_id="a",
                pairs=1,
                baseline_successes=1,
                candidate_successes=1,
                counts=SuiteCounts(minus=0, zero=1, plus=0, errored=0),
            ),
        ),
        stopped_at_round=1,
        verdict=Verdict.INCONCLUSIVE,
        exit_code=2,
        reasons=("no test crossed",),
        statements=tuple(statements),
        notices=(text("F7", k=1, N=200), text("F8", r=39, p=78)),
    )


def test_every_fixed_string_matches_design_record() -> None:
    record = Path("docs/design/0015-imported-outcomes.md").read_text(encoding="utf-8")
    section = record.split("## Fixed text\n", 1)[1].split("## Kernel extraction\n", 1)[0]
    expected = {
        tag: " ".join(body.split())
        for tag, body in re.findall(r"\*\*([FE]\d+)\*\*\s+`([^`]+)`", section)
    }
    warning = re.search(r"Warning \*\*W1\*\*: `([^`]+)`", section)
    assert warning is not None
    expected["W1"] = " ".join(warning.group(1).split())
    assert len(expected) == 46
    assert {tag: " ".join(body.split()) for tag, body in FIXED_TEXT.items()} == expected


def test_repeated_round_placeholder() -> None:
    assert text("E5", baseline=[1, 2], candidate=[1]) == (
        "arms supply different rounds: baseline [1, 2], candidate [1]"
    )


def test_placeholder_like_outcome_is_inserted_as_opaque_text() -> None:
    assert text("E10", value="<id>", id="task") == (
        "outcome <id> for task cannot be read as pass, fail or error"
    )


def test_placeholder_like_task_id_does_not_expand_as_round() -> None:
    assert text("E2", arm="candidate", id="<n>", n=4) == (
        "duplicate outcome for candidate <n> round 4"
    )


def test_rule_canonical_tasks_and_exact_rationals() -> None:
    rule = _rule(pass_at_least="-3/2")
    assert rule.tasks == ("a", "b")
    assert rule.alpha == "1/20"
    assert rule.margin == "1/10"
    assert rule.stakes == ("1/4", "1/2")
    assert rule.pass_at_least == "-3/2"
    assert _rule(pass_at_least="0/1").pass_at_least == "0/1"


@pytest.mark.parametrize(
    "changes",
    [
        {"schema_version": "arci-suite/1"},
        {"suite_id": "a/b"},
        {"tasks": []},
        {"tasks": ["a", "a"]},
        {"tasks": [""]},
        {"tasks": [1]},
        {"fixed_before_runs": "false"},
        {"fixed_before_runs": 1},
        {"alpha": "2/40"},
        {"alpha": "3/4"},
        {"margin": "1/1"},
        {"stakes": ["1/2", "1/4"]},
        {"stakes": []},
        {"max_rounds": True},
        {"max_rounds": 1.0},
        {"max_rounds": 50_001},
        {"max_errored_pairs": 401},
        {"score": ""},
        {"pass_at_least": "nan"},
        {"pass_at_least": "-2/4"},
        {"pass_at_least": "-0/1"},
        {"unexpected": 1},
    ],
)
def test_rule_rejects_invalid_fields(changes: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        _rule(**changes)


def test_records_seal_and_json_round_trip() -> None:
    decision = _decision(fixed=True)
    assert decision.validate_seal()
    assert decision.normalisation == NORMALISATION
    recovered = OutcomeDecision.model_validate_json(decision.model_dump_json())
    assert recovered == decision
    assert recovered.validate_seal()
    assert not decision.model_copy(update={"notices": ()}).validate_seal()
    with pytest.raises(ValidationError):
        OutcomeDecision.model_validate({**decision.model_dump(), "unexpected": True})


@pytest.mark.parametrize("fixed", [False, True])
def test_reports_have_all_verbatim_qualifications_and_counts(fixed: bool) -> None:
    decision = _decision(fixed=fixed)
    for report in (render_terminal(decision), render_markdown(decision)):
        lines = [line for line in report.splitlines() if line]
        if fixed:
            assert lines[0] == "VERDICT: INCONCLUSIVE (exit 2)"
            assert text("F1") not in report
        else:
            assert lines[:2] == [text("F1"), "VERDICT: INCONCLUSIVE (exit 2)"]
            assert report.count(text("F1")) == 1
            assert text("F5") not in report
        for fixed_text in (*decision.statements, *decision.notices):
            assert fixed_text in report.splitlines()
        assert "a" * 64 in report
        assert "1 | 2 | 0 | 2 | 0 | 0 | 1.08429e+00" in report
        assert text("F11", k=1) + ": 0" in report
    assert "a | 1 | 1 | 1 | 0 | 1 | 0 | 0" in render_markdown(decision)
    assert "a | 1 | 1 | 1 | 0 | 1 | 0 | 0" not in render_terminal(decision)


@pytest.mark.parametrize("fixed", [False, True])
@pytest.mark.parametrize("validated_rounds", [None, 1, 10])
def test_empty_template_statements_are_f2_alone(fixed: bool, validated_rounds: int | None) -> None:
    decision = empty_decision(
        "invalid input", _rule(fixed_before_runs=fixed), validated_rounds=validated_rounds
    )
    assert decision.statements == (text("F2"),)
    assert decision.rounds_registered == 0
    assert decision.validate_seal()


@pytest.mark.parametrize("fixed", [False, True])
@pytest.mark.parametrize("projection", ["F8", "F9"])
def test_terminal_section_order(fixed: bool, projection: str) -> None:
    notices = (
        text("W1"),
        text("F12"),
        text("F7", k=1, N=200),
        text(projection, r=39, p=78),
        text("F10", n=2),
        text("F14"),
    )
    decision = _decision(fixed=fixed).model_copy(update={"notices": notices})
    report = render_terminal(decision)
    sections = ([text("F1")] if not fixed else []) + [
        "VERDICT: INCONCLUSIVE (exit 2)",
        "no test crossed",
        *notices,
        "Rule SHA-256:",
        "Round | Pairs |",
        "errored pairs through round 1: 0",
        "Tasks where the candidate did worse or a pair errored, through round 1\nnone",
        *(statement for statement in decision.statements if statement != text("F1")),
    ]
    positions = [report.index(section) for section in sections]
    assert positions == sorted(positions)


def test_terminal_tasks_filter_sort_and_cap_without_truncating_artifacts() -> None:
    # Input order deliberately disagrees with every terminal ordering key.
    metrics = [(f"task-{n:02}", 1, 0) for n in reversed(range(10))] + [
        ("errors-only", 0, 4),
        ("more-errors", 1, 2),
        ("most-minus", 2, 0),
        ("ties-only", 0, 0),
        ("improved", 0, 0),
    ]
    tasks = tuple(
        OutcomeTaskCounts(
            task_id=task_id,
            pairs=4,
            baseline_successes=minus,
            candidate_successes=int(task_id == "improved"),
            counts=SuiteCounts(
                minus=minus,
                zero=4 - minus - errored - int(task_id == "improved"),
                plus=int(task_id == "improved"),
                errored=errored,
            ),
        )
        for task_id, minus, errored in metrics
    )
    decision = _decision(fixed=True).model_copy(update={"tasks": tasks})
    before = decision.model_dump_json()
    report = render_terminal(decision)
    rows = [
        line.split(" | ")[0].removeprefix("| ") for line in report.splitlines() if " | " in line
    ]
    assert rows[3:] == ["most-minus", "more-errors", *(f"task-{n:02}" for n in range(8))]
    overflow = "3 more such tasks: add --markdown PATH or --json PATH for the full table"
    assert report.splitlines()[report.splitlines().index(overflow) - 1].startswith("| task-07 | ")
    # No line of the terminal report begins with text taken from a task id.
    assert all(
        not line.startswith(tuple(task.task_id for task in tasks)) for line in report.splitlines()
    )
    assert all(
        task.task_id.replace("-", "\\-") + " | " in render_markdown(decision) for task in tasks
    )
    assert decision.model_dump_json() == before
    assert len(OutcomeDecision.model_validate_json(before).tasks) == 15
    assert overflow not in decision.statements + decision.notices


def test_terminal_includes_tasks_with_only_errored_pairs() -> None:
    decision = _decision(fixed=True)
    task = decision.tasks[0].model_copy(
        update={"counts": SuiteCounts(minus=0, zero=0, plus=0, errored=1)}
    )
    report = render_terminal(decision.model_copy(update={"tasks": (task,)}))
    assert "a | 1 | 1 | 1 | 0 | 0 | 0 | 1" in report
    assert "more such tasks" not in report


@pytest.mark.parametrize(
    ("reason", "tag"),
    [("non-inferiority established", "F15"), ("regression established", "F16")],
)
def test_descriptive_rendering_uses_threshold_reason(reason: str, tag: str) -> None:
    decision = _decision(fixed=False).model_copy(update={"reasons": (reason,)})
    assert text(tag) in render_terminal(decision).splitlines()
    assert reason not in render_terminal(decision)


def test_empty_error_report_makes_no_digest_promise() -> None:
    decision = OutcomeDecision.create(
        verdict=Verdict.ERROR,
        exit_code=3,
        reasons=(text("E15", reason="schema_version"),),
        statements=(text("F2"),),
    )
    report = render_terminal(decision)
    assert report.splitlines()[0] == "VERDICT: ERROR (exit 3)"
    assert "SHA-256" not in report
    assert text("F2") in report.splitlines()
