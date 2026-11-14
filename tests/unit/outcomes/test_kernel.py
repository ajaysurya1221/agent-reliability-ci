"""Imported rounds must preserve the suite kernel and registered-prefix semantics."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest
import yaml

from arci.demo import suite
from arci.outcome_report import render_terminal, text
from arci.outcome_schema import OutcomeDecision
from arci.outcomes import (
    decide_outcomes,
    load_rule,
    round_outcomes_sha256,
    rule_of,
    rule_sha256,
)
from arci.schema import Verdict
from arci.suite_gate import decide_suite, evaluate_rounds
from arci.suite_schedule import pair_round
from arci.suite_stats import crossed, wealth
from tests.unit.suite.test_walk_rounds import demo_trials


def _write_rule(path: Path, tasks: Sequence[str], **changes: object) -> Path:
    raw: dict[str, object] = {
        "schema_version": "arci-outcomes/1",
        "suite_id": "kernel",
        "fixed_before_runs": True,
        "tasks": list(tasks),
    }
    raw.update(changes)
    path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    return path


def _rows(tasks: Sequence[str], rounds: int, outcome: str = "pass") -> list[dict[str, object]]:
    return [
        {"task_id": task, "outcome": outcome, "round": r}
        for r in range(1, rounds + 1)
        for task in tasks
    ]


def _write_rows(path: Path, rows: Sequence[dict[str, object]]) -> Path:
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    return path


def _campaign(
    directory: Path, *, n: int = 20, supplied: int = 1, **rule_options: object
) -> tuple[Path, Path, Path, list[str]]:
    tasks = [f"task{i:03d}" for i in range(n)]
    rule = _write_rule(directory / "rule.yaml", tasks, **rule_options)
    baseline = _write_rows(directory / "baseline.jsonl", _rows(tasks, supplied))
    candidate = _write_rows(directory / "candidate.jsonl", _rows(tasks, supplied))
    return rule, baseline, candidate, tasks


def _save(path: Path, decision: OutcomeDecision) -> Path:
    path.write_text(decision.model_dump_json(indent=2), encoding="utf-8")
    return path


def _reseal(decision: OutcomeDecision, **changes: object) -> OutcomeDecision:
    values: dict[str, Any] = decision.model_dump(exclude={"record_sha256"})
    values.update(changes)
    return OutcomeDecision.create(**values)


@pytest.mark.parametrize("candidate", ["control", "regression", "uncertain"])
@pytest.mark.parametrize("fixed", [False, True])
def test_packaged_demo_matches_suite_kernel(tmp_path: Path, candidate: str, fixed: bool) -> None:
    manifest = suite.build_manifest(candidate)
    trials = demo_trials(manifest, candidate)
    stop = evaluate_rounds(manifest, trials)[-1].round
    prefix = [trial for trial in trials if pair_round(trial.pair_id) <= stop]
    expected = decide_suite(manifest, prefix)
    assert expected.verdict is not Verdict.ERROR
    tasks = sorted({f"{trial.task_id}::{trial.condition_id}" for trial in prefix})
    rule = _write_rule(
        tmp_path / "rule.yaml",
        tasks,
        fixed_before_runs=fixed,
        alpha=manifest.alpha,
        margin=manifest.delta,
        stakes=list(manifest.stakes),
        max_rounds=manifest.max_rounds,
        max_errored_pairs=manifest.max_errored_pairs,
    )
    arms: dict[str, Path] = {}
    for arm in ("baseline", "candidate"):
        rows: list[dict[str, object]] = [
            {
                "task_id": f"{trial.task_id}::{trial.condition_id}",
                "round": pair_round(trial.pair_id),
                "outcome": trial.outcome.value.lower(),
            }
            for trial in prefix
            if trial.arm == arm
        ]
        arms[arm] = _write_rows(tmp_path / f"{arm}.jsonl", rows)
    actual = decide_outcomes(rule, [arms["baseline"]], [arms["candidate"]])
    assert actual.validate_seal()
    assert actual.verdict is expected.verdict
    assert actual.exit_code == expected.exit_code
    assert actual.stopped_at_round == expected.stopped_at_round
    assert len(actual.history) == len(expected.history)
    for got, want in zip(actual.history, expected.history, strict=True):
        assert (got.round, got.pairs, got.counts) == (want.round, want.pairs, want.counts)
        assert (got.pass_wealth, got.block_wealth) == (want.pass_wealth, want.block_wealth)
        assert (got.pass_crossed, got.block_crossed, got.verdict) == (
            want.pass_crossed,
            want.block_crossed,
            want.verdict,
        )
    cells = {f"{cell.task_id}::{cell.condition_id}": cell for cell in expected.cells}
    for task in actual.tasks:
        cell = cells[task.task_id]
        assert (task.pairs, task.baseline_successes, task.candidate_successes, task.counts) == (
            cell.pairs,
            cell.baseline_successes,
            cell.candidate_successes,
            cell.counts,
        )
    if fixed:
        assert actual.reasons == expected.reasons
        assert text("F5") in actual.statements
    else:
        assert actual.statements[0] == text("F1")
        assert text("F5") not in actual.statements
        if actual.verdict is Verdict.PASS:
            assert actual.reasons == (text("F15"),)
        elif actual.verdict is Verdict.BLOCK:
            assert actual.reasons == (text("F16"),)


def test_later_error_outcomes_are_validated_but_do_not_enter_any_count(tmp_path: Path) -> None:
    rule, baseline, candidate, tasks = _campaign(tmp_path, n=100, supplied=1, max_rounds=4)
    original = decide_outcomes(rule, [baseline], [candidate])
    assert original.verdict is Verdict.PASS
    assert original.last_round_evaluated == 1
    later = [dict(row, round=2) for row in _rows(tasks, 1, "error")]
    _write_rows(baseline, _rows(tasks, 1) + later)
    _write_rows(candidate, _rows(tasks, 1) + later)
    extended = decide_outcomes(rule, [baseline], [candidate])
    assert extended.verdict is Verdict.PASS
    assert extended.rounds_supplied == 2
    assert extended.history == original.history
    assert extended.tasks == original.tasks
    assert extended.last_round_evaluated == 1
    assert extended.round_digests[:1] == original.round_digests
    assert len(extended.round_digests) == 2
    assert text("F10", n=1) in extended.notices
    assert text("F11", k=1) + ": 0" in render_terminal(extended)


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ({"task_id": "unregistered"}, "unknown task id: unregistered"),
        ({"outcome": "PASS"}, "outcome PASS for task000 cannot be read as pass, fail or error"),
        ({"round": 5}, "round 5 is outside 1 to 4"),
    ],
)
def test_faults_after_decisive_round_are_still_errors(
    tmp_path: Path, change: dict[str, object], reason: str
) -> None:
    rule, baseline, candidate, tasks = _campaign(tmp_path, n=100, supplied=2, max_rounds=4)
    rows = _rows(tasks, 2)
    rows[100].update(change)
    _write_rows(candidate, rows)
    decision = decide_outcomes(rule, [baseline], [candidate])
    assert decision.verdict is Verdict.ERROR
    assert decision.reasons == (reason,)
    assert not decision.history and not decision.tasks
    assert decision.last_round_evaluated == decision.stopped_at_round == 0


def test_round_digest_distinguishes_missing_from_explicit_error() -> None:
    missing = round_outcomes_sha256(("a", "b"), {"a": "pass"}, {"a": "pass", "b": "pass"})
    explicit_null = round_outcomes_sha256(
        ("b", "a"), {"a": "pass", "b": None}, {"a": "pass", "b": "pass"}
    )
    error = round_outcomes_sha256(
        ("a", "b"), {"a": "pass", "b": "error"}, {"a": "pass", "b": "pass"}
    )
    assert missing == explicit_null
    assert missing != error


def test_missing_pair_is_errored_and_report_labels_reached_round(tmp_path: Path) -> None:
    rule, baseline, candidate, tasks = _campaign(tmp_path, max_errored_pairs=0)
    _write_rows(candidate, _rows(tasks[1:], 1))
    decision = decide_outcomes(rule, [baseline], [candidate])
    assert decision.verdict is Verdict.ERROR
    assert decision.reasons == ("errored pairs exceed max_errored_pairs",)
    assert decision.last_round_evaluated == 1
    assert decision.stopped_at_round == 0
    assert decision.history[0].counts.errored == 1
    assert decision.history[0].counts.zero == 19
    assert decision.tasks[0].counts.errored == 1
    assert decision.tasks[0].baseline_successes == 1
    assert decision.tasks[0].candidate_successes == 0
    assert text("F11", k=1) + ": 1" in render_terminal(decision)
    assert not any(notice.startswith("if every further pair") for notice in decision.notices)


def test_f8_reports_complete_look_not_arithmetic_pair_threshold(tmp_path: Path) -> None:
    rule_path, baseline, candidate, _ = _campaign(tmp_path, n=50, max_rounds=8)
    decision = decide_outcomes(rule_path, [baseline], [candidate])
    rule = rule_of(load_rule(rule_path))
    arithmetic = next(n for n in range(351) if crossed(wealth(0, 50 + n, 0, rule)[0], rule))
    assert arithmetic == 29
    assert decision.verdict is Verdict.INCONCLUSIVE
    assert text("F7", k=1, N=8) in decision.notices
    assert text("F8", r=1, p=50) in decision.notices
    assert text("F9") not in decision.notices


def test_f9_at_budget_with_no_crossing(tmp_path: Path) -> None:
    rule, baseline, candidate, tasks = _campaign(tmp_path, n=50, supplied=8, max_rounds=8)
    a = _rows(tasks, 8)
    b = _rows(tasks, 8)
    for left, right in zip(a, b, strict=True):
        first_half = str(left["task_id"]) in set(tasks[:25])
        left["outcome"] = "pass" if first_half else "fail"
        right["outcome"] = "fail" if first_half else "pass"
    _write_rows(baseline, a)
    _write_rows(candidate, b)
    decision = decide_outcomes(rule, [baseline], [candidate])
    assert decision.verdict is Verdict.INCONCLUSIVE
    assert decision.last_round_evaluated == 8
    assert text("F9") in decision.notices
    assert text("F7", k=8, N=8) in decision.notices


def test_rule_digest_expands_defaults_but_includes_declaration(tmp_path: Path) -> None:
    tasks = ["z", "a"]
    minimal = _write_rule(tmp_path / "minimal.yaml", tasks)
    expanded = _write_rule(
        tmp_path / "expanded.yaml",
        list(reversed(tasks)),
        alpha="1/20",
        margin="1/10",
        stakes=["1/4", "1/2"],
        max_rounds=200,
        max_errored_pairs=4,
    )
    descriptive = _write_rule(tmp_path / "descriptive.yaml", tasks, fixed_before_runs=False)
    assert rule_sha256(load_rule(minimal)) == rule_sha256(load_rule(expanded))
    assert rule_sha256(load_rule(minimal)) != rule_sha256(load_rule(descriptive))


def test_previous_accepts_unchanged_prefix(tmp_path: Path) -> None:
    rule, baseline, candidate, tasks = _campaign(tmp_path)
    first = decide_outcomes(rule, [baseline], [candidate])
    previous = _save(tmp_path / "previous.json", first)
    _write_rows(baseline, _rows(tasks, 2))
    _write_rows(candidate, _rows(tasks, 2))
    extended = decide_outcomes(rule, [baseline], [candidate], previous=previous)
    assert extended.verdict is Verdict.INCONCLUSIVE
    assert extended.previous_sha256 == first.record_sha256
    assert extended.rounds_supplied == 2
    assert extended.round_digests[:1] == first.round_digests
    assert extended.history[:1] == first.history


def test_e23_previous_rule_comparison(tmp_path: Path) -> None:
    rule, baseline, candidate, tasks = _campaign(tmp_path)
    first = decide_outcomes(rule, [baseline], [candidate])
    previous = _save(tmp_path / "previous.json", first)
    _write_rule(rule, tasks, fixed_before_runs=False)
    decision = decide_outcomes(rule, [baseline], [candidate], previous=previous)
    assert decision.reasons == (
        f"the previous decision was made under another rule: {first.rule_sha256}",
    )
    assert decision.verdict is Verdict.ERROR


def test_e24_previous_invalid_seal(tmp_path: Path) -> None:
    rule, baseline, candidate, _ = _campaign(tmp_path)
    first = decide_outcomes(rule, [baseline], [candidate])
    previous = _save(
        tmp_path / "previous.json", first.model_copy(update={"record_sha256": "f" * 64})
    )
    decision = decide_outcomes(rule, [baseline], [candidate], previous=previous)
    assert decision.reasons == (
        "the previous decision is not a usable arci-outcomes/1 decision: seal invalid",
    )
    assert decision.verdict is Verdict.ERROR


def test_previous_requires_digest_for_every_supplied_round_even_when_resealed(
    tmp_path: Path,
) -> None:
    rule, baseline, candidate, _ = _campaign(tmp_path)
    first = decide_outcomes(rule, [baseline], [candidate])
    previous = _save(tmp_path / "previous.json", _reseal(first, round_digests=()))
    decision = decide_outcomes(rule, [baseline], [candidate], previous=previous)
    assert decision.reasons == (
        "the previous decision is not a usable arci-outcomes/1 decision: "
        "round digests must cover every supplied round",
    )


def test_e25_previous_error_decision(tmp_path: Path) -> None:
    rule, baseline, candidate, tasks = _campaign(tmp_path, max_errored_pairs=0)
    _write_rows(candidate, _rows(tasks[1:], 1))
    first = decide_outcomes(rule, [baseline], [candidate])
    assert first.verdict is Verdict.ERROR
    assert first.reasons == ("errored pairs exceed max_errored_pairs",)
    assert first.validate_seal()
    previous = _save(tmp_path / "previous.json", first)
    decision = decide_outcomes(rule, [baseline], [candidate], previous=previous)
    assert decision.reasons == (f"the previous decision is an ERROR decision: {previous}",)
    assert decision.verdict is Verdict.ERROR


def test_e26_previous_has_more_rounds(tmp_path: Path) -> None:
    rule, baseline, candidate, tasks = _campaign(tmp_path, supplied=2)
    first = decide_outcomes(rule, [baseline], [candidate])
    previous = _save(tmp_path / "previous.json", first)
    _write_rows(baseline, _rows(tasks, 1))
    _write_rows(candidate, _rows(tasks, 1))
    decision = decide_outcomes(rule, [baseline], [candidate], previous=previous)
    assert decision.reasons == ("the previous decision supplied 2 rounds; this call supplies 1",)
    assert decision.verdict is Verdict.ERROR


@pytest.mark.parametrize("version", [0, 2])
def test_e27_previous_normalisation_mismatch(tmp_path: Path, version: int) -> None:
    rule, baseline, candidate, _ = _campaign(tmp_path)
    first = decide_outcomes(rule, [baseline], [candidate])
    previous = _save(tmp_path / "previous.json", _reseal(first, normalisation=version))
    decision = decide_outcomes(rule, [baseline], [candidate], previous=previous)
    assert decision.reasons == (
        f"the previous decision used normalisation {version}; this call uses 1",
    )
    assert decision.verdict is Verdict.ERROR


def test_e28_previous_outcomes_changed(tmp_path: Path) -> None:
    rule, baseline, candidate, tasks = _campaign(tmp_path)
    first = decide_outcomes(rule, [baseline], [candidate])
    previous = _save(tmp_path / "previous.json", first)
    rows = _rows(tasks, 1)
    rows[0]["outcome"] = "fail"
    _write_rows(candidate, rows)
    decision = decide_outcomes(rule, [baseline], [candidate], previous=previous)
    assert decision.reasons == ("round 1 differs from the previous decision",)
    assert decision.verdict is Verdict.ERROR
