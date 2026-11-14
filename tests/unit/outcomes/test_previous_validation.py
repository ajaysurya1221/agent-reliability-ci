"""Predecessor validation happens before rejection/comparison, even for ERROR records."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from arci.outcome_schema import OutcomeDecision
from arci.outcomes import decide_outcomes, empty_decision, load_rule
from arci.schema import Verdict


def campaign(tmp_path: Path, *, rounds: int = 1, tolerance: int = 4) -> tuple[Path, Path, Path]:
    rule = tmp_path / "rule.yaml"
    rule.write_text(
        yaml.safe_dump(
            {
                "schema_version": "arci-outcomes/1",
                "suite_id": "previous",
                "tasks": ["a", "b"],
                "fixed_before_runs": False,
                "max_errored_pairs": tolerance,
            }
        )
    )
    baseline, candidate = tmp_path / "a.csv", tmp_path / "b.csv"
    source = "task_id,outcome,round\n" + "".join(
        f"{task},pass,{round_number}\n"
        for round_number in range(1, rounds + 1)
        for task in ("a", "b")
    )
    baseline.write_text(source)
    candidate.write_text(source)
    return rule, baseline, candidate


def reseal(decision: OutcomeDecision, **changes: object) -> OutcomeDecision:
    values: dict[str, Any] = decision.model_dump(exclude={"record_sha256"})
    values.update(changes)
    return OutcomeDecision.create(**values)


def save(tmp_path: Path, decision: OutcomeDecision) -> Path:
    path = tmp_path / "previous.json"
    path.write_text(decision.model_dump_json())
    return path


def test_genuine_inference_error_is_e25(tmp_path: Path) -> None:
    rule, baseline, candidate = campaign(tmp_path, tolerance=0)
    candidate.write_text("task_id,outcome\n")
    original = decide_outcomes(rule, [baseline], [candidate])
    assert original.verdict is Verdict.ERROR and original.last_round_evaluated == 1
    assert original.history[-1].verdict is Verdict.ERROR
    previous = save(tmp_path, original)
    actual = decide_outcomes(rule, [baseline], [candidate], previous=previous)
    assert actual.reasons == (f"the previous decision is an ERROR decision: {previous}",)


@pytest.mark.parametrize("with_rule", [False, True])
def test_genuine_empty_error_is_e25(tmp_path: Path, with_rule: bool) -> None:
    rule, baseline, candidate = campaign(tmp_path)
    original = empty_decision(
        "an earlier input was invalid", load_rule(rule) if with_rule else None
    )
    previous = save(tmp_path, original)
    actual = decide_outcomes(rule, [baseline], [candidate], previous=previous)
    assert actual.reasons == (f"the previous decision is an ERROR decision: {previous}",)


@pytest.mark.parametrize(
    "changes",
    [
        {"rounds_supplied": 1},
        {"rounds_registered": 1},
        {"stopped_at_round": 1},
        {"exit_code": 2},
        {"previous_sha256": "a" * 64},
        {"reasons": ()},
        {"rule_sha256": "a" * 64},
        {"notices": ("not allowed in the empty template",)},
    ],
)
def test_malformed_empty_error_is_e24_before_e25(
    tmp_path: Path,
    changes: dict[str, object],
) -> None:
    rule, baseline, candidate = campaign(tmp_path)
    original = empty_decision("invalid input", load_rule(rule))
    previous = save(tmp_path, reseal(original, **changes))
    actual = decide_outcomes(rule, [baseline], [candidate], previous=previous)
    assert actual.reasons == (
        "the previous decision is not a usable arci-outcomes/1 decision: "
        "empty ERROR template inconsistent",
    )


def test_forged_top_level_error_is_e24_before_e25(tmp_path: Path) -> None:
    rule, baseline, candidate = campaign(tmp_path)
    original = decide_outcomes(rule, [baseline], [candidate])
    assert original.verdict is Verdict.INCONCLUSIVE
    forged = reseal(original, verdict=Verdict.ERROR, exit_code=3, stopped_at_round=0)
    previous = save(tmp_path, forged)
    actual = decide_outcomes(rule, [baseline], [candidate], previous=previous)
    assert actual.reasons == (
        "the previous decision is not a usable arci-outcomes/1 decision: "
        "history verdict inconsistent",
    )


def test_inference_error_missing_digest_is_e24_before_e25(tmp_path: Path) -> None:
    rule, baseline, candidate = campaign(tmp_path, tolerance=0)
    candidate.write_text("task_id,outcome\n")
    original = decide_outcomes(rule, [baseline], [candidate])
    assert original.verdict is Verdict.ERROR
    previous = save(tmp_path, reseal(original, round_digests=()))
    actual = decide_outcomes(rule, [baseline], [candidate], previous=previous)
    assert actual.reasons == (
        "the previous decision is not a usable arci-outcomes/1 decision: "
        "round digests must cover every supplied round",
    )


def test_invalid_seal_of_error_is_e24_before_e25(tmp_path: Path) -> None:
    rule, baseline, candidate = campaign(tmp_path)
    original = empty_decision("invalid input", load_rule(rule))
    previous = save(tmp_path, original.model_copy(update={"record_sha256": "a" * 64}))
    actual = decide_outcomes(rule, [baseline], [candidate], previous=previous)
    assert actual.reasons == (
        "the previous decision is not a usable arci-outcomes/1 decision: seal invalid",
    )


def test_e26_precedes_e27(tmp_path: Path) -> None:
    rule, baseline, candidate = campaign(tmp_path, rounds=2)
    original = decide_outcomes(rule, [baseline], [candidate])
    previous = save(tmp_path, reseal(original, normalisation=2))
    baseline.write_text("task_id,outcome\na,pass\nb,pass\n")
    candidate.write_text(baseline.read_text())
    actual = decide_outcomes(rule, [baseline], [candidate], previous=previous)
    assert actual.reasons == ("the previous decision supplied 2 rounds; this call supplies 1",)


def test_e26_precedes_input_outcome_error(tmp_path: Path) -> None:
    rule, baseline, candidate = campaign(tmp_path, rounds=2)
    previous = save(tmp_path, decide_outcomes(rule, [baseline], [candidate]))
    baseline.write_text("task_id,outcome\na,unreadable\nb,pass\n")
    candidate.write_text("task_id,outcome\na,pass\nb,pass\n")
    actual = decide_outcomes(rule, [baseline], [candidate], previous=previous)
    assert actual.reasons == ("the previous decision supplied 2 rounds; this call supplies 1",)


def test_e27_precedes_input_identity_error(tmp_path: Path) -> None:
    rule, baseline, candidate = campaign(tmp_path)
    original = decide_outcomes(rule, [baseline], [candidate])
    previous = save(tmp_path, reseal(original, normalisation=2))
    baseline.write_text("task_id,outcome\nunknown,pass\n")
    actual = decide_outcomes(rule, [baseline], [candidate], previous=previous)
    assert actual.reasons == ("the previous decision used normalisation 2; this call uses 1",)


def test_e25_precedes_e27(tmp_path: Path) -> None:
    rule, baseline, candidate = campaign(tmp_path)
    original = empty_decision("invalid input", load_rule(rule))
    previous = save(tmp_path, reseal(original, normalisation=2))
    actual = decide_outcomes(rule, [baseline], [candidate], previous=previous)
    assert actual.reasons == (f"the previous decision is an ERROR decision: {previous}",)


def test_huge_inspect_epochs_with_previous_are_bounded(tmp_path: Path) -> None:
    import json

    rule, baseline, candidate = campaign(tmp_path)
    previous = save(tmp_path, decide_outcomes(rule, [baseline], [candidate]))
    path = tmp_path / "input.json"
    path.write_text(
        json.dumps(
            {
                "eval": {
                    "config": {"epochs": 10**12},
                    "dataset": {"sample_ids": ["a", "b"]},
                    "scorers": [{"name": "match"}],
                },
                "samples": [{"id": "a", "epoch": 1, "scores": {"match": {"value": "C"}}}],
            }
        )
    )
    actual = decide_outcomes(rule, [path], [path], previous=previous)
    assert actual.reasons == ("round 201 is outside 1 to 200",)
