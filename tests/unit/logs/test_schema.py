"""Closed records, validation and content seals."""

import pytest
from pydantic import ValidationError

from arci.logs.decide import decide_tool
from arci.logs.schema import LogsDecision, seal, verify_seal
from tests.unit.logs.test_measures import sample, table


def decision() -> LogsDecision:
    data = sample()
    return seal(
        {
            "schema_version": "arci-logs/2",
            "arci_version": "2.3.0",
            "example": True,
            "utc_offset_minutes": 0,
            "project_filtered": False,
            "tools": [decide_tool(table(data), data.counters)],
            "exit_code": 0,
        }
    )


def test_seal_roundtrip_and_tampering() -> None:
    actual = decision()
    assert verify_seal(LogsDecision.model_validate_json(actual.model_dump_json()))
    assert not verify_seal(actual.model_copy(update={"example": False}))
    with pytest.raises(ValidationError):
        LogsDecision.model_validate({**actual.model_dump(), "exit_code": 1})


@pytest.mark.parametrize(
    "field,value",
    [
        ("margin", "2/8"),
        ("margin", "1/10"),
        ("worse", "higher"),
        ("median_before", "2/1"),
        ("median_after", None),
        ("p_streak", "0/1"),
        ("p_real", "1/120"),
        ("p_none", "1/1"),
        ("p_none", "-1/1"),
        ("p_streak", "2/1"),
        ("u_none", 51),
        ("u_none", True),
        ("p_real", None),
        ("p_none", None),
        ("finding", "too_few_days"),
        ("id", "CANARY"),
        ("extra", "CANARY"),
    ],
)
def test_measure_rejects_inconsistent_fields(field: str, value: object) -> None:
    from arci.logs.schema import MeasureDecision

    payload = decision().tools[0].measures[0].model_dump()
    payload[field] = value
    with pytest.raises(ValidationError):
        MeasureDecision.model_validate(payload)


@pytest.mark.parametrize(
    "mutation", ["duplicate", "descending", "bad_date", "bad_value", "small_count"]
)
def test_day_validators(mutation: str) -> None:
    from arci.logs.schema import MeasureDecision

    original = decision().tools[0].measures[0]
    days = [d.model_dump() for d in original.before_days]
    if mutation == "duplicate":
        days[1] = days[0]
    elif mutation == "descending":
        days.reverse()
    elif mutation == "bad_date":
        days[0]["day"] = "2026-02-30"
    elif mutation == "bad_value":
        days[0]["value"] = "0/1"
    else:
        days[0]["count"] = 9
    with pytest.raises(ValidationError):
        MeasureDecision.model_validate({**original.model_dump(), "before_days": days})


@pytest.mark.parametrize(
    "field,value",
    [
        ("result", "REAL_DROP"),
        ("reason", "no_logs"),
        ("model", "canary-payroll"),
        ("effort", "other"),
        ("effort", "effort-0"),
        ("model", "model-0"),
        ("before", None),
        ("context", None),
        ("day_table_sha256", "x"),
        ("split_date", "20260501"),
        ("split_date", "2026-05-02"),
        ("other_settings", -1),
        ("after", None),
        ("measures", []),
    ],
)
def test_tool_rejects_inconsistent_fields(field: str, value: object) -> None:
    from arci.logs.schema import ToolDecision

    payload = decision().tools[0].model_dump()
    payload[field] = value
    with pytest.raises(ValidationError):
        ToolDecision.model_validate(payload)


def test_empty_tools_null_rules_and_tool_order() -> None:
    from arci.logs.decide import error_tool
    from arci.logs.records import ReaderCounters
    from arci.logs.schema import ToolDecision

    error = error_tool("codex", "no_logs", ReaderCounters())
    for field in ("model", "effort", "before", "after", "context", "day_table_sha256", "measures"):
        populated = decision().tools[0].model_dump()[field]
        for result, reason in (("ERROR", "no_logs"), ("CANNOT_TELL", "no_usable_setting")):
            payload = {**error.model_dump(), "result": result, "reason": reason, field: populated}
            with pytest.raises(ValidationError):
                ToolDecision.model_validate(payload)
    actual = decision()
    for tools in ([], [actual.tools[0], actual.tools[0]], [error, actual.tools[0]]):
        with pytest.raises(ValidationError):
            LogsDecision.model_validate({**actual.model_dump(), "tools": tools})
    with pytest.raises(ValidationError):
        actual.example = False


def test_every_top_level_field_is_sealed() -> None:
    actual = decision()
    for field in type(actual).model_fields:
        if field != "seal":
            assert not verify_seal(actual.model_copy(update={field: None}))
    assert not verify_seal(actual.model_copy(update={"seal": "0" * 64}))
    changed_tool = actual.tools[0].model_copy(update={"other_settings": 1})
    assert not verify_seal(actual.model_copy(update={"tools": (changed_tool,)}))


def test_json_contains_only_renderable_values() -> None:
    import json
    import re
    from typing import cast

    from arci.logs.records import EFFORTS, render_model

    names = {
        "arci-logs/2",
        "not_read",
        "logs",
        "claude-code",
        "codex",
        "REAL_DROP",
        "NO_DROP",
        "CANNOT_TELL",
        "ERROR",
        "real_drop",
        "no_drop",
        "not_enough_evidence",
        "too_few_days",
        "streaky_days",
        "no_usable_setting",
        "no_logs",
        "read_error",
        "format_not_recognised",
        "lower",
        "higher",
        "reasoning_tokens",
        "no_reasoning_share",
        "edit_failure_share",
        "repeated_value_share",
        "streaky",
        "cannot_tell",
        "2.3.0",
    }

    def walk(value: object) -> None:
        if isinstance(value, dict):
            for child in cast(dict[str, object], value).values():
                walk(child)
        elif isinstance(value, list):
            for child in cast(list[object], value):
                walk(child)
        elif isinstance(value, str):
            assert (
                value in names
                or value in EFFORTS
                or render_model(value) is not None
                or re.fullmatch(
                    r"[0-9]{4}-[0-9]{2}-[0-9]{2}|-?[0-9]+/[1-9][0-9]*|[0-9a-f]{64}|(?:model|effort)-[1-9][0-9]*",
                    value,
                )
            )
        else:
            assert value is None or type(value) in (int, bool)

    walk(json.loads(decision().model_dump_json()))


def test_threshold_values_must_also_match_day_values() -> None:
    from arci.logs.schema import MeasureDecision

    original = decision().tools[0].measures[0].model_dump()
    valid = [
        {"finding": "streaky", "p_streak": "1/10", "p_real": None, "u_none": None, "p_none": None},
        {"finding": "real_drop", "p_real": "1/120", "u_none": None, "p_none": None},
        {"finding": "no_drop", "p_none": "1/40"},
        {"finding": "cannot_tell", "p_none": "1/39"},
    ]
    for changes in valid:
        payload = {**original, **changes}
        with pytest.raises(ValidationError):
            MeasureDecision.model_validate(payload)
        for field in ("p_streak", "p_real", "u_none", "p_none"):
            payload_bad = {
                **payload,
                field: None if payload[field] is not None else (0 if field == "u_none" else "1/1"),
            }
            with pytest.raises(ValidationError):
                MeasureDecision.model_validate(payload_bad)


def test_period_context_and_scalar_validation() -> None:
    from arci.logs.schema import ContextCounts, DayValue, Period

    for day in ("2026-1-01", "2026-02-30", "0000-01-01", "CANARY"):
        with pytest.raises(ValidationError):
            DayValue(day=day, count=20, value="1/1")
    with pytest.raises(ValidationError):
        Period(first_day="2026-05-02", last_day="2026-05-01")
    context = decision().tools[0].context
    assert context is not None
    for field, value in (
        ("client_versions_both", 99),
        ("subagent_share_before", "2/1"),
        ("workdirs_before", -1),
    ):
        with pytest.raises(ValidationError):
            ContextCounts.model_validate({**context.model_dump(), field: value})
    actual = decision()
    for field, value in (
        ("schema_version", "arci-logs/1"),
        ("seal", "CANARY"),
        ("utc_offset_minutes", 1440),
        ("example", 1),
    ):
        with pytest.raises(ValidationError):
            LogsDecision.model_validate({**actual.model_dump(), field: value})
