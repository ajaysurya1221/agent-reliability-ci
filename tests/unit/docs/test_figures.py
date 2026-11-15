"""The README figures are generated, current and self-contained."""

from __future__ import annotations

import importlib.util
import io
import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from fractions import Fraction
from pathlib import Path

import pytest

from arci.logs import cli as logs_cli

REPO = Path(__file__).resolve().parents[3]
GENERATOR = REPO / "docs" / "assets" / "src" / "make_figures.py"
FIGURES = (
    "hero-light.svg",
    "hero-dark.svg",
    "where-light.svg",
    "where-dark.svg",
    "banner-light.svg",
    "banner-dark.svg",
)


def _load_generator():
    spec = importlib.util.spec_from_file_location("make_figures", GENERATOR)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # Register before exec: the module's frozen dataclasses resolve `from __future__ import
    # annotations` string annotations via sys.modules[cls.__module__].
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        del sys.modules[spec.name]
    return module


def test_generator_check_passes() -> None:
    completed = subprocess.run(
        [sys.executable, str(GENERATOR), "--check"],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr


@pytest.mark.parametrize("name", FIGURES)
def test_figure_is_text_only_svg(name: str) -> None:
    text = (REPO / "docs" / "assets" / name).read_text("utf-8")
    assert text.startswith('<svg xmlns="http://www.w3.org/2000/svg"')
    assert "<title" in text
    assert "<desc" in text
    for forbidden in ("<style", "<script", "<image", "<foreignObject", "href=", "@import", "url("):
        assert forbidden not in text, forbidden
    assert re.search(r"<text\b", text)


def test_banner_values_match_packaged_example(tmp_path: Path) -> None:
    """The generator's literal dot values are the packaged example's day values."""
    module = _load_generator()
    target = tmp_path / "example.json"
    out, err = io.StringIO(), io.StringIO()
    code = logs_cli.run(
        ["--example", "--tool", "claude-code", "--json", str(target)],
        now=datetime(2026, 11, 15, tzinfo=UTC),
        env={},
        home=tmp_path,
        out=out,
        err=err,
    )
    assert code == 1, err.getvalue()  # the packaged example is REAL_DROP, by design
    data = json.loads(target.read_text("utf-8"))
    tool = data["tools"][0]
    assert tool["tool"] == "claude-code"
    measure = next(m for m in tool["measures"] if m["id"] == "reasoning_tokens")
    before = tuple(Fraction(day["value"]) for day in measure["before_days"])
    after = tuple(Fraction(day["value"]) for day in measure["after_days"])
    assert len(before) == 42
    assert len(after) == 14
    assert before == tuple(Fraction(value) for value in module.BANNER_BEFORE)
    assert after == tuple(Fraction(value) for value in module.BANNER_AFTER)


@pytest.mark.parametrize("name", ("banner-light.svg", "banner-dark.svg"))
def test_banner_shows_dots_and_command(name: str) -> None:
    text = (REPO / "docs" / "assets" / name).read_text("utf-8")
    assert text.count("<circle") == 56
    for needle in ("Real", "noise?", "uvx realornoise", "ARCI"):
        assert needle in text
    assert "%" not in text
    for forbidden in ("REAL DROP", "NO DROP"):
        assert forbidden not in text
