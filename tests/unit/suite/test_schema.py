from __future__ import annotations

import subprocess
import sys
from fractions import Fraction
from typing import Any

import pytest
from pydantic import ValidationError

from arci.suite_schema import (
    SuiteCounts,
    SuiteManifest,
    SuiteTask,
    format_rational,
    parse_rational,
)
from tests.unit.suite.helpers import manifest_fields


@pytest.mark.parametrize(
    "text", ["", "1", "0/1", "-1/2", "1/0", "2/4", "01/2", "1/02", "1/2\n", " 1/2", "1.0/2"]
)
def test_reject_bad_rational(text: str) -> None:
    with pytest.raises(ValueError):
        parse_rational(text)


def test_rational_round_trip() -> None:
    for value in (Fraction(1, 10), Fraction(40), Fraction(7, 3)):
        assert parse_rational(format_rational(value)) == value
    assert format_rational(Fraction(4, 2)) == "2/1"
    for value in (Fraction(0), Fraction(-1)):
        with pytest.raises(ValueError):
            format_rational(value)


@pytest.mark.parametrize(
    "updates",
    [
        {"tasks": ()},
        {"conditions": ()},
        {"tasks": ({"task_id": "a"}, {"task_id": "a"})},
        {"conditions": ({"condition_id": "a"}, {"condition_id": "a"})},
        {"suite_id": "bad:id"},
        {"tasks": ({"task_id": "bad:id"},)},
        {"conditions": ({"condition_id": "bad:id"},)},
        *(
            {"conditions": ({"condition_id": "c", "faults": (fault,)},)}
            for fault in (
                {"name": "f", "bucket": "ceiling"},
                {"name": "decision_unavailable", "bucket": "falsify"},
                {"name": "decision_low_confidence", "bucket": "falsify"},
                {"name": "f", "bucket": "benign", "tool": "decision:anything"},
            )
        ),
        {"candidate": {"label": "c", "command": {"argv": ("agent",)}}},
        {"toolset": None},
        {"mcp_server": {"argv": ("server",), "snapshot": "fixtures:snapshot"}},
        {"alpha": "2/40"},
        {"delta": "2/20"},
        {"stakes": ("2/4",)},
        {"alpha": "1/1000001"},
        {"alpha": "2/3"},
        {"delta": "0/1"},
        {"delta": "1/1"},
        {"stakes": ()},
        {"stakes": tuple(f"1/{n}" for n in range(11, 2, -1))},
        {"stakes": ("0/1",)},
        {"stakes": ("1/1",)},
        {"stakes": ("1/2", "1/4")},
        {"stakes": ("1/4", "1/4")},
        {"max_rounds": 0},
        {"max_rounds": 25001},
        {"max_errored_pairs": -1},
        {"max_errored_pairs": 401},
        {"max_rounds": 1, "max_errored_pairs": 0},
        {"acknowledge_single_round": True},
        {"scenario_seeds": "random"},
        {"seed_derivation": "other"},
        {"schema_version": "arci/0.5"},
        {"unknown": 1},
    ],
)
def test_manifest_validation(updates: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        SuiteManifest(**manifest_fields(**updates))


@pytest.mark.parametrize("field", ["max_rounds", "max_errored_pairs"])
def test_explicit_required_fields(field: str) -> None:
    fields = manifest_fields()
    del fields[field]
    with pytest.raises(ValidationError):
        SuiteManifest(**fields)


def test_seals_defaults_and_structural_only_validation() -> None:
    m = SuiteManifest.create(**manifest_fields(max_rounds=1, acknowledge_single_round=True))
    assert m.n_cells == m.registered_pairs == 4
    assert m.validate_seal()
    assert m.model_copy(update={"created_at": "later"}).validate_seal()
    assert not m.model_copy(update={"delta": "1/5"}).validate_seal()
    assert SuiteManifest.model_validate_json(m.model_dump_json()) == m
    with pytest.raises(ValidationError):
        m.max_rounds = 2
    first, second = SuiteTask(task_id="a"), SuiteTask(task_id="b")
    first.task["value"] = 1
    assert second.task == {}


def test_command_arm_configuration() -> None:
    fields = manifest_fields(
        baseline={"label": "a", "command": {"argv": ("a",)}},
        candidate={"label": "b", "command": {"argv": ("b",)}},
        toolset=None,
        mcp_server={"argv": ("server",), "snapshot": "fixtures:snapshot"},
    )
    assert SuiteManifest(**fields).mcp_server is not None
    for update in ({"mcp_server": None}, {"toolset": "fixtures:tools"}):
        with pytest.raises(ValidationError):
            SuiteManifest.model_validate(fields | update)


@pytest.mark.parametrize("field", ["minus", "zero", "plus", "errored"])
def test_nonnegative_counts(field: str) -> None:
    fields: dict[str, int] = dict.fromkeys(("minus", "zero", "plus", "errored"), 0)
    fields[field] = -1
    with pytest.raises(ValidationError):
        SuiteCounts(**fields)


def test_schema_does_not_import_statistics() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import arci.suite_schema; assert 'arci.suite_stats' not in sys.modules",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
