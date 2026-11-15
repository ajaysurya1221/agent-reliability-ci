"""Every serialized string belongs to a closed output category."""

import io
import json
import re
from datetime import date
from fractions import Fraction
from pathlib import Path
from typing import get_args

import pytest

from arci import __version__
from arci.logs import schema
from arci.logs.cli import run
from arci.logs.records import EFFORTS, MODEL_WORDS, Tool
from tests.unit.logs.privacy.test_canary import arguments
from tests.unit.logs.synth_logs import generate

CLOSED = frozenset(
    {
        "arci-logs/2",
        "logs",
        "kept",
        "absent",
        "not_read",
        "read",
        "unreadable",
        "lower",
        "higher",
        *EFFORTS,
        *get_args(Tool),
        *get_args(schema.Result),
        *get_args(schema.ReasonCode),
        *get_args(schema.Finding),
        *get_args(schema.MeasureId),
    }
)


def model_name(value: str) -> bool:
    # Independent transcription of record 0016's grammar, not render_model itself.
    if not re.fullmatch(r"[a-z0-9._-]{1,48}", value):
        return False
    parts = re.split(r"[-._]", value)
    dates = sum(bool(re.fullmatch(r"20[0-9]{6}", p)) for p in parts)
    small = sum(bool(re.fullmatch(r"[0-9]{1,2}", p)) for p in parts)
    return (
        len(parts) <= 6
        and dates <= 1
        and small <= 3
        and all(
            p in MODEL_WORDS
            or re.fullmatch(r"[0-9]{1,2}|[a-z][0-9]{1,2}|[0-9]{1,2}[a-z]|20[0-9]{6}", p)
            for p in parts
        )
    )


def allowed(value: str, field: str = "") -> bool:
    if field == "client_versions_after_shown" and re.fullmatch(
        r"[0-9]{1,5}(\.[0-9]{1,5}){1,3}", value
    ):
        return True
    if value in CLOSED or value == __version__ or model_name(value):
        return True
    if re.fullmatch(r"(?:model|effort)-[1-9][0-9]*|[0-9a-f]{64}", value):
        return True
    if re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        return date.fromisoformat(value).isoformat() == value
    if re.fullmatch(r"-?(?:0|[1-9][0-9]*)/[1-9][0-9]*", value):
        fraction = Fraction(value)
        return value == f"{fraction.numerator}/{fraction.denominator}"
    return False


def walk(value: object, field: str = "") -> list[tuple[str, str]]:
    if isinstance(value, str):
        return [(field, value)]
    if isinstance(value, dict):
        return [leaf for key, item in value.items() for leaf in walk(item, key)]
    if isinstance(value, list):
        return [leaf for item in value for leaf in walk(item, field)]
    assert value is None or isinstance(value, bool | int | float)
    return []


@pytest.mark.parametrize("model", [None, "model-1"])
def test_every_json_string_leaf(tmp_path: Path, model: str | None) -> None:
    logs = generate(tmp_path / "input", days=28, sessions_per_day=30, compressed=False)
    target = tmp_path / "output.json"
    argv = [*arguments(logs, "both"), "--json", str(target)]
    if model:
        argv.extend(["--model", model, "--effort", "effort-1"])
    out, err = io.StringIO(), io.StringIO()
    assert run(argv, now=logs.now, env={}, home=tmp_path, out=out, err=err) in (0, 1, 2)
    assert not err.getvalue()
    leaves = walk(json.loads(target.read_text()))
    assert leaves
    for field, leaf in leaves:
        assert allowed(leaf, field), leaf
