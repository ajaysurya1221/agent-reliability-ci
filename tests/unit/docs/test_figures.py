"""The README figures are generated, current and self-contained."""

from __future__ import annotations

import importlib.util
import io
import json
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
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
    "decision-light.svg",
    "decision-dark.svg",
    "gate-light.svg",
    "gate-dark.svg",
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


# ---------------------------------------------------------------------------------------------
# The one README theme (the banner's), held for every figure.
# ---------------------------------------------------------------------------------------------

SVG = "{http://www.w3.org/2000/svg}"
PALETTE = {
    "light": {
        "#F6F8FA",  # ground
        "#FFFFFF",  # panel, text on blue
        "#D0D7DE",  # line, neutral bar
        "#57606A",  # quiet
        "#10161D",  # ink, text on orange
        "#1F6FEB",  # blue
        "#0B57D0",  # blue for small text
        "#E8590C",  # orange
        "#9C3A06",  # orange for small text
    },
    "dark": {
        "#0D1117",  # ground, text on blue and orange
        "#151C26",  # panel
        "#2A3646",  # line, neutral bar
        "#9BA7B4",  # quiet
        "#F2F6FA",  # ink
        "#6CB6FF",  # blue, also for small text
        "#FF9F45",  # orange, also for small text
    },
}
# Shades the banner already had before the theme was applied to every figure.
BANNER_EXTRA = {
    "light": {"#8C959F", "#D14E0A", "#7A838D", "#636C76"},
    "dark": {"#5B6878", "#8B98A7"},
}
SANS = "system-ui, -apple-system, 'Segoe UI', Helvetica, Arial, sans-serif"
MONO = "ui-monospace, 'SF Mono', Menlo, Consolas, 'Liberation Mono', monospace"
PAIRS = sorted({name.rsplit("-", 1)[0] for name in FIGURES})


def _svg(name: str) -> ET.Element:
    return ET.fromstring((REPO / "docs" / "assets" / name).read_text("utf-8"))


def _mode(name: str) -> str:
    return name.removesuffix(".svg").rsplit("-", 1)[1]


@pytest.mark.parametrize("name", FIGURES)
def test_figure_colours_belong_to_the_theme(name: str) -> None:
    text = (REPO / "docs" / "assets" / name).read_text("utf-8")
    allowed = set(PALETTE[_mode(name)])
    if name.startswith("banner-"):
        allowed |= BANNER_EXTRA[_mode(name)]
    used = {colour.upper() for colour in re.findall(r"#[0-9A-Fa-f]{3,8}\b", text)}
    assert used <= allowed, sorted(used - allowed)
    for attribute in ("fill", "stroke"):
        for value in re.findall(rf'\b{attribute}="([^"]*)"', text):
            assert value == "none" or value.upper() in allowed, (attribute, value)
    assert "rgb(" not in text
    assert "Gradient" not in text


def test_generator_palette_is_the_theme() -> None:
    module = _load_generator()
    assert module.palette(module.LIGHT) == PALETTE["light"]
    assert module.palette(module.DARK) == PALETTE["dark"]
    assert not hasattr(module, "SERIF")


@pytest.mark.parametrize("name", FIGURES)
def test_figure_uses_only_the_sans_and_mono_stacks(name: str) -> None:
    text = (REPO / "docs" / "assets" / name).read_text("utf-8")
    families = set(re.findall(r'font-family="([^"]*)"', text))
    assert families <= {SANS, MONO}, families
    assert "Georgia" not in text
    # "serif" appears only as part of the generic family "sans-serif".
    assert re.search(r"(?<!sans-)serif", text) is None
    assert "Times" not in text


def _texts(root: ET.Element) -> list[str]:
    return ["".join(node.itertext()) for node in root.iter(f"{SVG}text")]


@pytest.mark.parametrize("pair", PAIRS)
def test_light_and_dark_say_the_same(pair: str) -> None:
    light, dark = _svg(f"{pair}-light.svg"), _svg(f"{pair}-dark.svg")
    for tag in ("title", "desc"):
        light_node, dark_node = light.find(f"{SVG}{tag}"), dark.find(f"{SVG}{tag}")
        assert light_node is not None and dark_node is not None
        assert light_node.text == dark_node.text
    assert _texts(light) == _texts(dark)
    assert light.get("width") == dark.get("width")
    assert light.get("height") == dark.get("height")


@pytest.mark.parametrize("mode", ("light", "dark"))
def test_hero_shows_one_dot_per_trial(mode: str) -> None:
    root = _svg(f"hero-{mode}.svg")
    blue, orange = ("#1F6FEB", "#E8590C") if mode == "light" else ("#6CB6FF", "#FF9F45")
    circles = list(root.iter(f"{SVG}circle"))
    assert len(circles) == 400
    grid_a, grid_b = circles[:200], circles[200:]
    assert sum(c.get("fill") == blue for c in grid_a) == 192
    assert sum(c.get("fill") == "none" for c in grid_a) == 8
    assert sum(c.get("fill") == orange for c in grid_b) == 132
    assert sum(c.get("fill") == "none" for c in grid_b) == 68
    # Passed trials come first, in reading order, and every hollow ring has a quiet stroke.
    assert [c.get("fill") for c in grid_a] == [blue] * 192 + ["none"] * 8
    assert [c.get("fill") for c in grid_b] == [orange] * 132 + ["none"] * 68
    quiet = "#57606A" if mode == "light" else "#9BA7B4"
    assert all(c.get("stroke") == quiet for c in circles if c.get("fill") == "none")
    # Each grid is 20 columns by 10 rows, and every dot lies inside the card panel.
    for grid in (grid_a, grid_b):
        assert len({c.get("cx") for c in grid}) == 20
        assert len({c.get("cy") for c in grid}) == 10
    card = next(r for r in root.iter(f"{SVG}rect") if r.get("stroke") is not None)
    left, top = float(card.get("x", "0")), float(card.get("y", "0"))
    right = left + float(card.get("width", "0"))
    bottom = top + float(card.get("height", "0"))
    for c in circles:
        cx, cy, r = (float(c.get(key, "0")) for key in ("cx", "cy", "r"))
        assert left < cx - r and cx + r < right, (cx, r)
        assert top < cy - r and cy + r < bottom, (cy, r)
    texts = _texts(root)
    assert "A 192/200" in texts
    assert "B 132/200" in texts


def _readme_cell(pair: str, column: str) -> list[Fraction]:
    readme = (REPO / "README.md").read_text("utf-8")
    header = next(line for line in readme.splitlines() if line.startswith("| baseline -> "))
    row = next(line for line in readme.splitlines() if line.startswith(f"| {pair} |"))
    columns = [cell.strip() for cell in header.strip("|").split("|")]
    cells = [cell.strip() for cell in row.strip("|").split("|")]
    return [Fraction(value) for value in cells[columns.index(column)].split(" / ")]


GATE_BAR_X = 352
GATE_ROWS = (
    ("0.95 -> 0.65", "N=20"),
    ("0.95 -> 0.65", "N=200"),
    ("0.95 -> 0.75", "N=200"),
    ("0.80 -> 0.80", "N=200"),
)


@pytest.mark.parametrize("mode", ("light", "dark"))
def test_gate_bars_are_to_scale(mode: str) -> None:
    root = _svg(f"gate-{mode}.svg")
    palette = PALETTE[mode]
    fills = (
        {"PASS": "#1F6FEB", "BLOCK": "#E8590C", "INCONCLUSIVE": "#D0D7DE"}
        if mode == "light"
        else {"PASS": "#6CB6FF", "BLOCK": "#FF9F45", "INCONCLUSIVE": "#2A3646"}
    )
    assert set(fills.values()) <= palette
    rects = list(root.iter(f"{SVG}rect"))[1:]  # the first rect is the ground
    # The bars run from GATE_BAR_X to the right margin.
    bar_total = float(root.get("width", "0")) - 64 - GATE_BAR_X
    assert bar_total == 1184
    rows: dict[float, list[ET.Element]] = {}
    for rect in rects:
        rows.setdefault(float(rect.get("y", "0")), []).append(rect)
    assert len(rows) == len(GATE_ROWS)
    texts = _texts(root)
    for (pair, column), y in zip(GATE_ROWS, sorted(rows), strict=True):
        probabilities = _readme_cell(pair, column)
        segments = sorted(rows[y], key=lambda rect: float(rect.get("x", "0")))
        widths = [float(rect.get("width", "0")) for rect in segments]
        xs = [float(rect.get("x", "0")) for rect in segments]
        # Every bar shares one scale: the same start, segments end to end, one total width.
        assert xs[0] == GATE_BAR_X, (pair, column, xs)
        for x, previous_x, previous_w in zip(xs[1:], xs, widths, strict=False):
            assert x == previous_x + previous_w, (pair, column, xs, widths)
        total = sum(widths)
        assert total == bar_total, (pair, column, total)
        expected = [
            (verdict, p)
            for verdict, p in zip(("PASS", "BLOCK", "INCONCLUSIVE"), probabilities, strict=True)
            if p
        ]
        assert len(segments) == len(expected)
        for rect, width, (verdict, p) in zip(segments, widths, expected, strict=True):
            assert rect.get("fill") == fills[verdict]
            assert abs(width - float(p) * total) <= 1, (pair, column, verdict, width)
            label = f"{verdict} {float(p * 100):.1f}%"
            if width < 60:  # too narrow for a label: none drawn
                assert label not in texts, label
    for label in (
        "INCONCLUSIVE 99.2%",
        "BLOCK 98.5%",
        "BLOCK 36.5%",
        "INCONCLUSIVE 63.5%",
        "PASS 21.8%",
        "INCONCLUSIVE 78.2%",
    ):
        assert label in texts
    for label in ("BLOCK 0.8%", "INCONCLUSIVE 1.5%"):
        assert label not in texts


@pytest.mark.parametrize("mode", ("light", "dark"))
def test_decision_figure_names_match_the_code(mode: str) -> None:
    texts = " ".join(_texts(_svg(f"decision-{mode}.svg")))
    for needle in (
        "TYPESAFE_BASE_URL",
        "TYPESAFE_API_KEY",
        "decision_low_confidence",
        "decision_unavailable",
        "gate",
        "replay",
        "preflight",
        "report",
        "fixture",
        "http",
    ):
        assert needle in texts, needle
    # The old PNG's footer said Jev was not run; the README says it was (2026-10-03).
    assert "not run" not in texts
    assert "provenance" not in texts.lower()


# Meaning, the same in every figure: the colour of every verdict word, and the tint opacities.
MEANING = {
    "light": {
        "PASS": "#0B57D0",
        "REPRODUCED": "#0B57D0",
        "BLOCK": "#9C3A06",
        "INCONCLUSIVE": "#57606A",
        "ERROR": "#10161D",
    },
    "dark": {
        "PASS": "#6CB6FF",
        "REPRODUCED": "#6CB6FF",
        "BLOCK": "#FF9F45",
        "INCONCLUSIVE": "#9BA7B4",
        "ERROR": "#F2F6FA",
    },
}
# Text on a filled gate bar: on blue, on orange and on the neutral bar.
ON_BAR = {
    "light": {"PASS": "#FFFFFF", "BLOCK": "#10161D", "INCONCLUSIVE": "#10161D"},
    "dark": {"PASS": "#0D1117", "BLOCK": "#0D1117", "INCONCLUSIVE": "#F2F6FA"},
}
TINTS = {
    "light": {"#1F6FEB": "0.1", "#E8590C": "0.12"},
    "dark": {"#6CB6FF": "0.14", "#FF9F45": "0.16"},
}
THEMED = [name for name in FIGURES if not name.startswith("banner-")]
VERDICT_WORD = re.compile(r"\b(PASS|BLOCK|INCONCLUSIVE|ERROR|REPRODUCED)\b")


def _chunks(element: ET.Element, fill: str | None) -> list[tuple[str, str | None]]:
    """(text, effective fill) of every run of text in ``element`` and its tspans."""
    own = element.get("fill", fill)
    chunks = [(element.text or "", own)]
    for child in element:
        chunks += _chunks(child, own)
        chunks.append((child.tail or "", own))
    return chunks


@pytest.mark.parametrize("name", THEMED)
def test_verdict_words_are_coloured_by_meaning(name: str) -> None:
    mode = _mode(name)
    expected = ON_BAR[mode] if name.startswith("gate-") else MEANING[mode]
    seen = 0
    for text in _svg(name).iter(f"{SVG}text"):
        for chunk, fill in _chunks(text, None):
            for word in VERDICT_WORD.findall(chunk):
                assert fill == expected[word], (name, chunk, word, fill)
                seen += 1
    assert seen > 0 or name.startswith("decision-"), name


@pytest.mark.parametrize("name", THEMED)
def test_tints_use_the_theme_opacities(name: str) -> None:
    mode = _mode(name)
    root = _svg(name)
    text = (REPO / "docs" / "assets" / name).read_text("utf-8")
    for attribute in ("opacity", "stroke-opacity"):
        assert f' {attribute}="' not in text, attribute
    for element in root.iter():
        opacity = element.get("fill-opacity")
        if opacity is not None:
            assert TINTS[mode].get(element.get("fill", "")) == opacity, (name, element.attrib)
