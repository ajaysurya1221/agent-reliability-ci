"""The README figures are generated, current and self-contained."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
GENERATOR = REPO / "docs" / "assets" / "src" / "make_figures.py"
FIGURES = ("hero-light.svg", "hero-dark.svg", "where-light.svg", "where-dark.svg")


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
