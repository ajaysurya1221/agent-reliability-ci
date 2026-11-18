"""Generate the README figures in ``docs/assets/``, each in a light and a dark file.

Standard library only, deterministic, no network. ``--write`` regenerates the ten files;
``--check`` regenerates them in memory and exits 1 if a committed file is missing or differs.

- ``banner-{light,dark}.svg``: the first picture, the realornoise banner.
- ``hero-{light,dark}.svg``: the thesis and the evidence card of the seeded retry demo, with one
  dot per trial.
- ``where-{light,dark}.svg``: where arci sits in a CI pipeline.
- ``decision-{light,dark}.svg``: agents that use a decision model (the harness-owned boundary).
- ``gate-{light,dark}.svg``: the gate's verdict probabilities, measured against itself.

All of them share one theme, the banner's: a neutral ground, blue for the reference or the good
outcome (baseline, agent A, PASS, REPRODUCED), orange for the thing in question or the bad outcome
(candidate, agent B, BLOCK, injected faults), a neutral bar or quiet outline for INCONCLUSIVE and
ink for ERROR; one system sans-serif stack for titles and text and one monospace stack for labels.

The SVGs are plain ``<text>``, ``<rect>``, ``<circle>``, ``<line>`` and ``<path>`` elements: no
``<style>`` blocks, no scripts, no raster images, no external fonts. Text uses system font stacks so
GitHub renders it without web fonts. Every line of text is measured (``text_width``) and the
generator refuses to write a figure in which a line does not fit its box with ``SPARE`` pixels to
spare, which leaves room for font-metric differences between platforms. ``<title>`` and ``<desc>``
carry the full text of each figure.

Every number and every name shown traces to a committed file, and both modes first confirm that the
exact strings below are still present in those files (``SOURCES``), so the figures cannot drift
from the evidence silently:

- ``docs/results/retry-demo-n200.md``: 200 trials per arm (``n_per_arm`` 200), A 192/200,
  B 132/200, bounds on the difference [-0.405, -0.183], margin (``delta``) 0.10,
  BLOCK with exit 1.
- ``docs/reports/ci-gate-2026-10-06/logs/hero-demo-2026-10-05.txt`` (the unedited demo log):
  BLOCK (exit 1) for A vs B, the condition shrunk from 3 injected faults to ``tool_timeout``,
  ``1-minimal``, and the offline replay ``REPRODUCED``.
- ``examples/retry_agent/experiment.py``: the timeout is injected on the first ``reserve``
  call (``tool="reserve"``, ``at_occurrence=0``).
- ``src/arci/schema.py`` (frozen): the four verdicts and their exit codes 0, 1, 2 and 3, and the
  two decision upstreams ``fixture`` and ``http``.
- ``src/arci/runner.py``: the two environment variables the harness sets for the agent,
  ``TYPESAFE_BASE_URL`` (a loopback port) and ``TYPESAFE_API_KEY`` (the per-trial token).
- ``src/arci/perturb.py``: the two decision faults ``decision_low_confidence`` and
  ``decision_unavailable``.
- ``src/arci/cli.py``: the commands ``gate``, ``replay``, ``preflight`` and ``report``.
- ``README.md``: what ``arci preflight`` and ``arci report`` check and show, that the official SDKs
  run unchanged, the gate figure's settings (``alpha`` 0.05, ``delta`` 0.10, one condition) and
  the rows of the table under "The gate, measured against itself" that the gate figure draws
  (``GATE_TABLE``); the bar widths and the percentages are both computed from those row strings.

The pipeline figure contains no measured numbers.

The banner figure's 56 dot values are the daily values of the ``reasoning_tokens`` measure for
the Claude Code tool in the packaged example (what ``arci logs --example --json`` writes under
``tools[0].measures[0].before_days[*].value`` and ``.after_days[*].value``). They are literal
tuples below, not read from a file; ``tests/unit/docs/test_figures.py`` checks them against the
packaged example directly.
"""

from __future__ import annotations

import argparse
import math
import re
import statistics
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from fractions import Fraction
from html import escape
from pathlib import Path

ASSETS = Path(__file__).resolve().parent.parent
REPO = ASSETS.parent.parent

GATE_TABLE_HEADER = "| baseline -> candidate | N=20 | N=100 | N=200 | N=400 |"
GATE_TABLE: dict[str, str] = {
    "0.95 -> 0.75": (
        "| 0.95 -> 0.75 | .000 / .000 / 1.000 | .000 / .093 / .907 | .000 / .365 / .635"
        " | .000 / .828 / .172 |"
    ),
    "0.95 -> 0.65": (
        "| 0.95 -> 0.65 | .000 / .008 / .992 | .000 / .685 / .315 | .000 / .985 / .015"
        " | .000 / 1.000 / .000 |"
    ),
    "0.80 -> 0.80": (
        "| 0.80 -> 0.80 | .003 / .000 / .997 | .059 / .000 / .941 | .218 / .000 / .782"
        " | .615 / .000 / .385 |"
    ),
}

SOURCES: tuple[tuple[str, str], ...] = (
    (
        "docs/results/retry-demo-n200.md",
        "| B (retry removed) | 192/200 | 132/200 | [-0.405, -0.183] | BLOCK | 1 |",
    ),
    (
        "docs/results/retry-demo-n200.md",
        "| 0.0500 | 0.1000 | 1 | clopper_pearson | 97.5000% | 200 |",
    ),
    (
        "docs/reports/ci-gate-2026-10-06/logs/hero-demo-2026-10-05.txt",
        "VERDICT: BLOCK (exit 1)   [A vs agent_b]",
    ),
    (
        "docs/reports/ci-gate-2026-10-06/logs/hero-demo-2026-10-05.txt",
        "=== 4. Shrink the failing condition (3 injected faults)",
    ),
    ("docs/reports/ci-gate-2026-10-06/logs/hero-demo-2026-10-05.txt", "  kept: tool_timeout\n"),
    ("docs/reports/ci-gate-2026-10-06/logs/hero-demo-2026-10-05.txt", "minimality: 1-minimal"),
    (
        "docs/reports/ci-gate-2026-10-06/logs/hero-demo-2026-10-05.txt",
        "REPRODUCED: failure reproduced",
    ),
    ("examples/retry_agent/experiment.py", 'tool="reserve",\n                at_occurrence=0,'),
    (
        "src/arci/schema.py",
        "    Verdict.PASS: 0,\n    Verdict.BLOCK: 1,\n    Verdict.INCONCLUSIVE: 2,\n"
        "    Verdict.ERROR: 3,",
    ),
    # The decision figure.
    ("src/arci/schema.py", 'upstream: Literal["fixture", "http"]'),
    (
        "src/arci/runner.py",
        'command_env["TYPESAFE_BASE_URL"] = f"http://127.0.0.1:{decision_port}"\n'
        '                command_env["TYPESAFE_API_KEY"] = decision_token',
    ),
    ("src/arci/perturb.py", '"decision_low_confidence": _decision_low_confidence,'),
    ("src/arci/perturb.py", '"decision_unavailable": _decision_unavailable,'),
    ("src/arci/cli.py", 'commands.add_parser("gate", '),
    ("src/arci/cli.py", 'commands.add_parser("replay", '),
    ("src/arci/cli.py", 'commands.add_parser("preflight", '),
    ("src/arci/cli.py", 'commands.add_parser("report", '),
    (
        "README.md",
        "the official Python and JavaScript SDKs are exercised\nunchanged by the acceptance tests.",
    ),
    ("README.md", "`arci preflight` checks key, endpoint, pinned model and one\nsmoke decision"),
    ("README.md", "# gate, failure clusters, tokens, estimated cost"),
    # The gate figure.
    ("README.md", "by exact enumeration (`alpha` 0.05, `delta` 0.10, one condition)"),
    (
        "README.md",
        "- False PASS at the margin and false BLOCK under no change are both far below `alpha`",
    ),
    ("README.md", "- **Twenty runs decide almost nothing.**"),
    ("README.md", GATE_TABLE_HEADER),
    *(("README.md", row) for row in GATE_TABLE.values()),
)

MONO = "ui-monospace, 'SF Mono', Menlo, Consolas, 'Liberation Mono', monospace"
SANS = "system-ui, -apple-system, 'Segoe UI', Helvetica, Arial, sans-serif"
MONO_ADVANCE = 0.6  # em; ui-monospace, SF Mono, Menlo, Liberation Mono and DejaVu all use ~0.6

MINUS = chr(0x2212)  # typographic minus
ARROW = chr(0x2192)
DOT = chr(0x00B7)  # middle dot

MARGIN = 64  # outer margin of every figure except the banner
SPARE = 24  # px every line of text leaves free in its box, for font-metric differences
ARROW_TAIL, ARROW_TIP = 4, 6  # px an arrow leaves free from the box it leaves and the box it enters

# Advance widths of a Helvetica/Arial-like sans in 1/1000 em. system-ui (SF Pro, Segoe UI,
# Roboto) runs a few per cent wider, hence SANS_SAFETY; weight 600 adds SANS_BOLD.
_SANS_GROUPS: tuple[tuple[int, str], ...] = (
    (191, "'"),
    (222, "ijl"),
    (260, "|"),
    (278, " !,./:;I[]\\ft" + DOT),
    (333, "()-r`{}"),
    (355, '"'),
    (389, "*"),
    (500, "Jckvxyzs"),
    (556, "0123456789abdeghnopqu_$#?L" + chr(0x2013)),
    (584, "+<=>~" + MINUS),
    (611, "FTZ"),
    (667, "ABEKPSVXY&"),
    (722, "CDHNRUw"),
    (778, "GOQ"),
    (833, "mM"),
    (889, "%"),
    (944, "W"),
    (1000, ARROW),
    (1015, "@"),
)
SANS_WIDTHS: dict[str, int] = {ch: width for width, chars in _SANS_GROUPS for ch in chars}
SANS_SAFETY = 1.05
SANS_BOLD = 1.07


def text_width(
    text: str, size: float, family: str, *, weight: int = 400, spacing: float = 0.0
) -> float:
    """Estimated rendered width of one line of text, in px."""
    if family == MONO:
        return len(text) * (size * MONO_ADVANCE + spacing)
    units = sum(SANS_WIDTHS.get(ch, 600) for ch in text)
    scale = SANS_SAFETY * (SANS_BOLD if weight >= 600 else 1.0)
    return units / 1000 * size * scale + len(text) * spacing


def require_fit(
    text: str,
    size: float,
    family: str,
    room: float,
    *,
    weight: int = 400,
    spacing: float = 0.0,
) -> None:
    """Refuse a layout in which ``text`` does not fit ``room`` with SPARE px to spare."""
    need = text_width(text, size, family, weight=weight, spacing=spacing) + SPARE
    if need > room:
        raise ValueError(f"layout: {text!r} needs {need:.0f}px, has {room:.0f}px")


def wrap(
    text: str,
    room: float,
    size: float,
    family: str,
    *,
    weight: int = 400,
    first_room: float | None = None,
) -> list[str]:
    """Greedy word wrap so that every line fits ``room`` (the first line ``first_room``)."""
    lines: list[str] = []
    current = ""
    for word in text.split(" "):
        candidate = f"{current} {word}" if current else word
        limit = (first_room if first_room is not None and not lines else room) - SPARE
        if current and text_width(candidate, size, family, weight=weight) > limit:
            lines.append(current)
            current = word
        else:
            current = candidate
    lines.append(current)
    for index, line in enumerate(lines):
        limit = first_room if first_room is not None and index == 0 else room
        require_fit(line, size, family, limit, weight=weight)
    return lines


@dataclass(frozen=True)
class Theme:
    """The README theme (the banner's), one instance per colour scheme."""

    name: str
    ground: str
    panel: str
    line: str
    quiet: str
    ink: str
    blue: str  # marks: dots, bars, borders
    blue_text: str  # text in blue, at least 4.5:1 on ground and panel
    orange: str
    orange_text: str
    neutral: str  # the INCONCLUSIVE bar
    blue_tint: float  # fill-opacity of a blue tint
    orange_tint: float
    on_blue: str  # text on a filled blue bar
    on_orange: str


LIGHT = Theme(
    name="light",
    ground="#F6F8FA",
    panel="#FFFFFF",
    line="#D0D7DE",
    quiet="#57606A",
    ink="#10161D",
    blue="#1F6FEB",
    blue_text="#0B57D0",
    orange="#E8590C",
    orange_text="#9C3A06",
    neutral="#D0D7DE",
    blue_tint=0.10,
    orange_tint=0.12,
    on_blue="#FFFFFF",
    on_orange="#10161D",
)

DARK = Theme(
    name="dark",
    ground="#0D1117",
    panel="#151C26",
    line="#2A3646",
    quiet="#9BA7B4",
    ink="#F2F6FA",
    blue="#6CB6FF",
    blue_text="#6CB6FF",
    orange="#FF9F45",
    orange_text="#FF9F45",
    neutral="#2A3646",
    blue_tint=0.14,
    orange_tint=0.16,
    on_blue="#0D1117",
    on_orange="#0D1117",
)


def palette(theme: Theme) -> frozenset[str]:
    """Every colour literal a non-banner figure in this theme may use."""
    return frozenset(
        {
            theme.ground,
            theme.panel,
            theme.line,
            theme.quiet,
            theme.ink,
            theme.blue,
            theme.blue_text,
            theme.orange,
            theme.orange_text,
            theme.neutral,
            theme.on_blue,
            theme.on_orange,
        }
    )


_VERDICT_WORDS = re.compile(r"(PASS|BLOCK|INCONCLUSIVE|ERROR|REPRODUCED)")


def verdict_fill(word: str, theme: Theme) -> str:
    """The text colour of a verdict word: the same meaning in every figure."""
    if word in ("PASS", "REPRODUCED"):
        return theme.blue_text
    if word == "BLOCK":
        return theme.orange_text
    if word == "INCONCLUSIVE":
        return theme.quiet
    return theme.ink  # ERROR


@dataclass(frozen=True)
class Span:
    text: str
    fill: str | None = None
    weight: int | None = None
    x: int | None = None
    family: str | None = None


def verdict_spans(line: str, theme: Theme, weight: int | None = 600) -> list[Span]:
    """``line`` with every verdict word coloured by its meaning."""
    spans: list[Span] = []
    for part in _VERDICT_WORDS.split(line):
        if not part:
            continue
        if _VERDICT_WORDS.fullmatch(part):
            spans.append(Span(part, fill=verdict_fill(part, theme), weight=weight))
        else:
            spans.append(Span(part))
    return spans


class Canvas:
    def __init__(self, width: int, height: int, title: str, desc: str) -> None:
        self.width = width
        self.height = height
        self.title = title
        self.desc = desc
        self.body: list[str] = []

    def rect(
        self,
        x: float,
        y: float,
        w: float,
        h: float,
        fill: str,
        rx: int = 0,
        stroke: str | None = None,
        stroke_width: int = 1,
        fill_opacity: float | None = None,
    ) -> None:
        extra = f' stroke="{stroke}" stroke-width="{stroke_width}"' if stroke else ""
        radius = f' rx="{rx}"' if rx else ""
        opacity = f' fill-opacity="{fill_opacity}"' if fill_opacity is not None else ""
        self.body.append(
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}"{radius} fill="{fill}"'
            f"{extra}{opacity}/>"
        )

    def panel(self, x: float, y: float, w: float, h: float, theme: Theme) -> None:
        """A panel: panel fill, 1px line border, small corner radius."""
        # Half-pixel offsets keep the 1px border crisp.
        self.rect(x + 0.5, y + 0.5, w - 1, h - 1, theme.panel, rx=4, stroke=theme.line)

    def circle(self, cx: float, cy: float, r: float, fill: str) -> None:
        self.body.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{fill}"/>')

    def ring(self, cx: float, cy: float, r: float, stroke: str, width: float = 1.5) -> None:
        self.body.append(
            f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{stroke}"'
            f' stroke-width="{width}"/>'
        )

    def line(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        color: str,
        *,
        width: float = 1.5,
        dasharray: str | None = None,
        linecap: str | None = None,
        opacity: float | None = None,
    ) -> None:
        extra = ""
        if dasharray is not None:
            extra += f' stroke-dasharray="{dasharray}"'
        if linecap is not None:
            extra += f' stroke-linecap="{linecap}"'
        if opacity is not None:
            extra += f' stroke-opacity="{opacity}"'
        self.body.append(
            f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}"'
            f' stroke-width="{width}"{extra}/>'
        )

    def text(
        self,
        x: int,
        y: int,
        spans: Sequence[Span] | str,
        *,
        size: int,
        family: str,
        fill: str,
        weight: int = 400,
        anchor: str = "start",
        spacing: str | None = None,
    ) -> None:
        items = [Span(spans)] if isinstance(spans, str) else list(spans)
        attrs = [
            f'x="{x}"',
            f'y="{y}"',
            f'font-family="{family}"',
            f'font-size="{size}"',
            f'fill="{fill}"',
        ]
        if weight != 400:
            attrs.append(f'font-weight="{weight}"')
        if anchor != "start":
            attrs.append(f'text-anchor="{anchor}"')
        if spacing is not None:
            attrs.append(f'letter-spacing="{spacing}"')
        inner: list[str] = []
        for span in items:
            span_attrs: list[str] = []
            if span.x is not None:
                span_attrs.append(f'x="{span.x}"')
            if span.family is not None:
                span_attrs.append(f'font-family="{span.family}"')
            if span.fill is not None:
                span_attrs.append(f'fill="{span.fill}"')
            if span.weight is not None:
                span_attrs.append(f'font-weight="{span.weight}"')
            content = escape(span.text, quote=False)
            if span_attrs:
                inner.append(f"<tspan {' '.join(span_attrs)}>{content}</tspan>")
            else:
                inner.append(content)
        self.body.append(f"<text {' '.join(attrs)}>{''.join(inner)}</text>")

    def arrow(self, points: Sequence[tuple[int, int]], color: str, width: int = 2) -> None:
        """A polyline with a filled triangular head at its last point."""
        path = " ".join(
            f"{'M' if index == 0 else 'L'} {x} {y}" for index, (x, y) in enumerate(points)
        )
        self.body.append(
            f'<path d="{path}" fill="none" stroke="{color}" stroke-width="{width}"'
            ' stroke-linecap="round" stroke-linejoin="round"/>'
        )
        (x0, y0), (x1, y1) = points[-2], points[-1]
        dx = (x1 > x0) - (x1 < x0)
        dy = (y1 > y0) - (y1 < y0)
        size = 9
        # Head: tip at (x1, y1), base `size` back along the segment, half-width size * 0.6.
        bx, by = x1 - dx * size, y1 - dy * size
        half = round(size * 0.6)
        px, py = -dy * half, dx * half
        self.body.append(
            f'<path d="M {x1} {y1} L {bx + px} {by + py} L {bx - px} {by - py} Z" fill="{color}"/>'
        )

    def render(self) -> str:
        head = (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.width}"'
            f' height="{self.height}" viewBox="0 0 {self.width} {self.height}"'
            ' role="img" aria-labelledby="title desc">'
        )
        lines = [
            head,
            f'<title id="title">{escape(self.title, quote=False)}</title>',
            f'<desc id="desc">{escape(self.desc, quote=False)}</desc>',
            *self.body,
            "</svg>",
        ]
        return "\n".join(lines) + "\n"


def baseline(top: int, line_height: int, size: int) -> int:
    """Baseline of a single text line centred in a line box (cap height about 0.7 em)."""
    return round(top + line_height / 2 + size * 0.35)


# Shared type scale of the diagram figures (where, decision, gate).
TITLE_SIZE, TITLE_LH = 36, 48
SUB_SIZE, SUB_LH = 22, 32
LABEL_SIZE, LABEL_SPACING = 18, 1.8  # small capitals, monospace
BODY_SIZE, BODY_LH = 20, 30


def header(canvas: Canvas, theme: Theme, title: str, sub: Sequence[str]) -> int:
    """Title and sub-lines at the top-left margin; returns the y where content starts."""
    room = canvas.width - 2 * MARGIN
    require_fit(title, TITLE_SIZE, SANS, room, weight=600)
    canvas.text(
        MARGIN,
        baseline(MARGIN, TITLE_LH, TITLE_SIZE),
        title,
        size=TITLE_SIZE,
        family=SANS,
        fill=theme.ink,
        weight=600,
    )
    top = MARGIN + TITLE_LH + 4
    for index, line in enumerate(sub):
        require_fit(line, SUB_SIZE, SANS, room)
        canvas.text(
            MARGIN,
            baseline(top + index * SUB_LH, SUB_LH, SUB_SIZE),
            line,
            size=SUB_SIZE,
            family=SANS,
            fill=theme.quiet,
        )
    return top + len(sub) * SUB_LH + 32


def small_caps(canvas: Canvas, x: int, y: int, label: str, theme: Theme, room: float) -> None:
    """A monospace small-capitals label (lane and panel headings)."""
    require_fit(label, LABEL_SIZE, MONO, room, spacing=LABEL_SPACING)
    canvas.text(
        x,
        y,
        label,
        size=LABEL_SIZE,
        family=MONO,
        fill=theme.quiet,
        spacing=f"{LABEL_SPACING}",
    )


# ---------------------------------------------------------------------------------------------
# Hero, 1600 x 520
# ---------------------------------------------------------------------------------------------

HERO_W, HERO_H = 1600, 520
EYEBROW = ("arci", "agent-reliability-ci", "regression gate for stochastic agents")
THESIS = ("Did this change make", "the agent less reliable,", "and what broke?")
SUBLINE = (
    "A frozen experiment, an exact verdict with its",
    "uncertainty, and a failure case you can replay offline.",
)
CARD_LABEL = (
    f"SEEDED RETRY DEMO {DOT} 200 TRIALS PER ARM",
    "TIMEOUT ON THE FIRST reserve CALL",
)
CARD_N = 200
CARD_PASSED = (192, 132)  # trials passed by A and by B, out of CARD_N
CARD_A, CARD_B = f"{CARD_PASSED[0]}/{CARD_N}", f"{CARD_PASSED[1]}/{CARD_N}"
CARD_BOUNDS = f"[{MINUS}0.405, {MINUS}0.183]"
CARD_MARGIN = f" {DOT} margin {MINUS}0.10"
CARD_VERDICT = "VERDICT: BLOCK (exit 1)"
CARD_CHAIN = (f"3 faults {ARROW} 1-minimal", f"{ARROW} replay ")
CARD_REPLAY = "REPRODUCED"
CARD_FOOT = ("B is A with one retry removed", "docs/results/retry-demo-n200.md")
GRID_COLS, GRID_ROWS = 20, 10  # one dot per trial, filled in reading order
GRID_PITCH, GRID_R = 10, 3.5


def hero(theme: Theme) -> str:
    desc = " ".join(
        [
            f"{EYEBROW[0]}: {EYEBROW[1]}, {EYEBROW[2]}.",
            " ".join(THESIS),
            " ".join(SUBLINE),
            "Evidence card:",
            "Seeded retry demo, 200 trials per arm, timeout on the first reserve call.",
            f"A {CARD_A}, B {CARD_B}.",
            f"Two grids of {CARD_N} dots, one dot per trial: {CARD_PASSED[0]} filled for A and"
            f" {CARD_PASSED[1]} filled for B; a hollow dot is a failed trial.",
            f"Bounds on the difference {CARD_BOUNDS}, margin {MINUS}0.10.",
            f"{CARD_VERDICT}; 3 injected faults reduced to 1, 1-minimal; offline replay"
            f" {CARD_REPLAY}.",
            f"{CARD_FOOT[0]}. Source: {CARD_FOOT[1]}.",
        ]
    )
    canvas = Canvas(HERO_W, HERO_H, " ".join(THESIS), desc)
    canvas.rect(0, 0, HERO_W, HERO_H, theme.ground)

    card_w, col_gap = 720, 48
    card_x = HERO_W - MARGIN - card_w
    card_y, card_h = MARGIN, HERO_H - 2 * MARGIN
    col_x = MARGIN
    col_room = card_x - col_gap - col_x

    # Left column: eyebrow (2 lines), thesis (3 lines), subline (2 lines), vertically centred.
    eyebrow_size, eyebrow_lh, eyebrow_spacing = 22, 30, 0.44
    thesis_size, thesis_lh, sub_size, sub_lh, block_gap = 56, 62, 26, 36, 22
    total = 2 * eyebrow_lh + block_gap + 3 * thesis_lh + block_gap + 2 * sub_lh
    top = card_y + (card_h - total) // 2
    first_w = round(len(EYEBROW[0]) * eyebrow_size * MONO_ADVANCE) + 14
    require_fit(EYEBROW[1], eyebrow_size, MONO, col_room - first_w, spacing=eyebrow_spacing)
    require_fit(EYEBROW[2], eyebrow_size, MONO, col_room, spacing=eyebrow_spacing)
    canvas.text(
        col_x,
        baseline(top, eyebrow_lh, eyebrow_size),
        [
            Span(EYEBROW[0], fill=theme.blue_text, weight=600),
            Span(EYEBROW[1], x=col_x + first_w),
        ],
        size=eyebrow_size,
        family=MONO,
        fill=theme.quiet,
        spacing=f"{eyebrow_spacing}",
    )
    canvas.text(
        col_x,
        baseline(top + eyebrow_lh, eyebrow_lh, eyebrow_size),
        EYEBROW[2],
        size=eyebrow_size,
        family=MONO,
        fill=theme.quiet,
        spacing=f"{eyebrow_spacing}",
    )
    top += 2 * eyebrow_lh + block_gap
    for index, line in enumerate(THESIS):
        require_fit(line, thesis_size, SANS, col_room, weight=600)
        canvas.text(
            col_x,
            baseline(top + index * thesis_lh, thesis_lh, thesis_size),
            line,
            size=thesis_size,
            family=SANS,
            fill=theme.ink,
            weight=600,
        )
    top += 3 * thesis_lh + block_gap
    for index, line in enumerate(SUBLINE):
        require_fit(line, sub_size, SANS, col_room)
        canvas.text(
            col_x,
            baseline(top + index * sub_lh, sub_lh, sub_size),
            line,
            size=sub_size,
            family=SANS,
            fill=theme.quiet,
        )

    # Evidence card: a panel with the label on top, a dot grid per agent on the left and the
    # verdict text on the right.
    canvas.panel(card_x, card_y, card_w, card_h, theme)
    pad = 32
    inner_x = card_x + pad
    inner_right = card_x + card_w - pad
    label_size, label_lh, label_spacing = 18, 24, 1.0
    y = card_y + 20
    for index, line in enumerate(CARD_LABEL):
        require_fit(line, label_size, MONO, inner_right - inner_x, spacing=label_spacing)
        canvas.text(
            inner_x,
            baseline(y + index * label_lh, label_lh, label_size),
            line,
            size=label_size,
            family=MONO,
            fill=theme.quiet,
            spacing=f"{label_spacing}",
        )
    zone_top = y + 2 * label_lh + 12

    grid_w = (GRID_COLS - 1) * GRID_PITCH + 2 * GRID_R
    grid_h = (GRID_ROWS - 1) * GRID_PITCH + 2 * GRID_R
    count_size, count_lh, grid_gap, block_gap_y = 26, 34, 4, 14
    agents = (
        ("A", CARD_A, CARD_PASSED[0], theme.blue, theme.blue_text),
        ("B", CARD_B, CARD_PASSED[1], theme.orange, theme.orange_text),
    )
    block_h = count_lh + grid_gap + grid_h
    for index, (name, score, passed, mark, text_fill) in enumerate(agents):
        block_top = zone_top + index * (block_h + block_gap_y)
        require_fit(f"{name} {score}", count_size, MONO, grid_w + SPARE, weight=600)
        canvas.text(
            inner_x,
            baseline(block_top, count_lh, count_size),
            f"{name} {score}",
            size=count_size,
            family=MONO,
            fill=text_fill,
            weight=600,
        )
        grid_top = block_top + count_lh + grid_gap
        for trial in range(CARD_N):
            row, col = divmod(trial, GRID_COLS)
            cx = inner_x + GRID_R + col * GRID_PITCH
            cy = grid_top + GRID_R + row * GRID_PITCH
            if trial < passed:
                canvas.circle(cx, cy, GRID_R, mark)
            else:
                canvas.ring(cx, cy, GRID_R - 0.5, theme.quiet, width=1)
    zone_h = 2 * block_h + block_gap_y
    if zone_top + zone_h > card_y + card_h - 16:
        raise ValueError("layout: the hero grids overflow the card")

    size, lh, foot_size, foot_lh, gap = 20, 28, 18, 24, 12
    lines = (
        "bounds on the difference",
        CARD_BOUNDS + CARD_MARGIN,
        CARD_VERDICT,
        CARD_CHAIN[0],
        CARD_CHAIN[1] + CARD_REPLAY,
    )
    # The text column ends SPARE px inside the card's padding, so its right edge is as close to
    # the card's padding as its left edge (the grids) is, with room for font differences.
    widest = max(
        *(text_width(line, size, MONO, weight=600) for line in lines),
        *(text_width(line, foot_size, MONO) for line in CARD_FOOT),
    )
    text_x = round(inner_right - SPARE - widest)
    if text_x < inner_x + grid_w + 40:
        raise ValueError("layout: the hero card text column overlaps the grids")
    text_room = inner_right - text_x
    for line in lines:
        require_fit(line, size, MONO, text_room, weight=600)
    for line in CARD_FOOT:
        require_fit(line, foot_size, MONO, text_room)
    text_h = 5 * lh + 2 * gap + 2 * foot_lh
    ty = zone_top + (zone_h - text_h) // 2
    canvas.text(text_x, baseline(ty, lh, size), lines[0], size=size, family=MONO, fill=theme.ink)
    canvas.text(
        text_x,
        baseline(ty + lh, lh, size),
        [Span(CARD_BOUNDS, fill=theme.orange_text), Span(CARD_MARGIN)],
        size=size,
        family=MONO,
        fill=theme.ink,
    )
    ty += 2 * lh + gap
    canvas.text(
        text_x,
        baseline(ty, lh, size),
        CARD_VERDICT,
        size=size,
        family=MONO,
        fill=theme.orange_text,
        weight=600,
    )
    canvas.text(
        text_x, baseline(ty + lh, lh, size), lines[3], size=size, family=MONO, fill=theme.ink
    )
    canvas.text(
        text_x,
        baseline(ty + 2 * lh, lh, size),
        [Span(CARD_CHAIN[1]), Span(CARD_REPLAY, fill=theme.blue_text, weight=600)],
        size=size,
        family=MONO,
        fill=theme.ink,
    )
    ty += 3 * lh + gap
    for index, line in enumerate(CARD_FOOT):
        canvas.text(
            text_x,
            baseline(ty + index * foot_lh, foot_lh, foot_size),
            line,
            size=foot_size,
            family=MONO,
            fill=theme.quiet,
        )
    return canvas.render()


# ---------------------------------------------------------------------------------------------
# Where arci sits, 1600 wide
# ---------------------------------------------------------------------------------------------

WHERE_W = 1600
WHERE_TITLE = "Where arci sits"
WHERE_SUB = (
    "Between an agent change and the merge decision: a frozen, repeated experiment,"
    " and diagnosis from the same records."
)
VERDICTS = f"PASS {DOT} BLOCK {DOT} INCONCLUSIVE {DOT} ERROR"
EXITS = f"exit 0 {DOT} 1 {DOT} 2 {DOT} 3"
WHERE_NOTE = (
    "Diagnosis does not need a BLOCK: it compares any passing and failing trial in the records.",
    "Replay re-serves the recorded boundary calls; it does not repeat model inference.",
)


@dataclass(frozen=True)
class Node:
    title: str
    lines: tuple[str, ...]


MANIFEST = Node(
    "Frozen manifest",
    ("baseline and", "candidate, oracle,", "faults, seeds, N", "and the decision rule"),
)
TRIALS = Node(
    "Recorded trials",
    ("seeded trials per arm,", "injected tool faults,", "sealed boundary", "records"),
)
GATE = Node("arci gate", ("exact Clopper-Pearson bounds", "on the difference, frozen margin"))
MERGE = Node(
    "Merge",
    ("on PASS (exit 0)", "BLOCK and ERROR fail", "the job; INCONCLUSIVE", "fails by default"),
)
DIFF = Node("Trace comparison", ("first divergent step,", "passing vs failing trial"))
SHRINK = Node("Fault reduction", ("ddmin over", "injected faults,", "same fingerprint"))
REPLAY = Node("Offline replay", ("recorded boundary", "calls, not fresh", "model inference"))

NODE_TITLE_SIZE, NODE_TITLE_LH = 20, 28
NODE_SIZE, NODE_LH = 18, 24
NODE_PAD_X, NODE_PAD_Y = 20, 16


def _node_width(node: Node) -> int:
    widths = [text_width(node.title, NODE_TITLE_SIZE, SANS, weight=600)]
    widths += [text_width(line, NODE_SIZE, SANS) for line in node.lines]
    return 2 * NODE_PAD_X + SPARE + round(max(widths))


def _node_height(node: Node) -> int:
    return 2 * NODE_PAD_Y + NODE_TITLE_LH + NODE_LH * len(node.lines)


def _node(canvas: Canvas, node: Node, x: int, y: int, w: int, h: int, theme: Theme) -> None:
    canvas.panel(x, y, w, h, theme)
    total = NODE_TITLE_LH + NODE_LH * len(node.lines)
    top = y + (h - total) // 2
    cx = x + w // 2
    require_fit(node.title, NODE_TITLE_SIZE, SANS, w - 2 * NODE_PAD_X + SPARE, weight=600)
    canvas.text(
        cx,
        baseline(top, NODE_TITLE_LH, NODE_TITLE_SIZE),
        node.title,
        size=NODE_TITLE_SIZE,
        family=SANS,
        fill=theme.ink,
        weight=600,
        anchor="middle",
    )
    for index, line in enumerate(node.lines):
        require_fit(line, NODE_SIZE, SANS, w - 2 * NODE_PAD_X + SPARE)
        canvas.text(
            cx,
            baseline(top + NODE_TITLE_LH + index * NODE_LH, NODE_LH, NODE_SIZE),
            verdict_spans(line, theme),
            size=NODE_SIZE,
            family=SANS,
            fill=theme.quiet,
            anchor="middle",
        )


def _describe(node: Node) -> str:
    return f"{node.title} ({' '.join(node.lines)})"


def where(theme: Theme) -> str:
    desc_parts = [
        f"{WHERE_TITLE}. {WHERE_SUB}",
        "Before the run: " + _describe(MANIFEST) + ".",
        "In CI: " + _describe(TRIALS) + ", then " + _describe(GATE) + f", verdict {VERDICTS},"
        f" {EXITS}.",
        "Merge decision: merge on PASS (exit 0); BLOCK and ERROR fail the job;"
        " INCONCLUSIVE fails by default.",
        "A separate branch from the recorded trials: "
        + "; then ".join(_describe(node) for node in (DIFF, SHRINK, REPLAY))
        + ".",
        " ".join(WHERE_NOTE),
    ]

    # Horizontal layout, measured: three lanes, nodes in two rows inside the CI lane. The
    # side lanes take what their node needs; the CI lane takes the rest.
    lane_pad, lane_gap, arrow_gap = 20, 24, 32
    verdict_size = 18
    gate_w = max(
        _node_width(GATE),
        2 * NODE_PAD_X + SPARE + round(text_width(VERDICTS, verdict_size, MONO, weight=600)),
    )
    manifest_w = _node_width(MANIFEST)
    trials_w = _node_width(TRIALS)
    merge_w = _node_width(MERGE)
    bottom = (DIFF, SHRINK, REPLAY)
    bottom_w = [_node_width(node) for node in bottom]

    before_x = MARGIN
    manifest_x = before_x + lane_pad
    ci_x = manifest_x + manifest_w + lane_pad + lane_gap
    merge_lane_w = merge_w + 2 * lane_pad
    merge_lane_x = WHERE_W - MARGIN - merge_lane_w
    merge_x = merge_lane_x + lane_pad
    ci_end = merge_lane_x - lane_gap
    trials_x = ci_x + lane_pad
    gate_x = trials_x + trials_w + arrow_gap
    if gate_x + gate_w > ci_end - lane_pad:
        raise ValueError("layout: the top row overflows the CI lane")
    spread = ci_end - lane_pad - trials_x - sum(bottom_w)
    if spread < 2 * arrow_gap:
        raise ValueError("layout: the diagnosis row overflows the CI lane")
    bottom_x = [trials_x]
    for width in bottom_w[:-1]:
        bottom_x.append(bottom_x[-1] + width + spread // 2)

    content_top = MARGIN + TITLE_LH + 4 + SUB_LH + 32
    lane_y = content_top - 8
    label_y = baseline(lane_y + 8, 32, LABEL_SIZE)
    top_y = lane_y + 48
    top_h = max(
        2 * NODE_PAD_Y + NODE_TITLE_LH + NODE_LH * 4,  # the gate: two lines, verdicts, exits
        *(_node_height(node) for node in (MANIFEST, TRIALS, MERGE)),
    )
    mid = top_y + top_h // 2
    row_y = top_y + top_h + 64
    row_h = max(_node_height(node) for node in bottom)
    lane_h = row_y + row_h + lane_pad - lane_y
    note_top = lane_y + lane_h + 16
    note_lh = 26
    canvas_h = note_top + len(WHERE_NOTE) * note_lh + MARGIN - 8

    canvas = Canvas(WHERE_W, canvas_h, "Where arci sits in a CI pipeline", " ".join(desc_parts))
    canvas.rect(0, 0, WHERE_W, canvas_h, theme.ground)
    top = header(canvas, theme, WHERE_TITLE, (WHERE_SUB,))
    assert top == content_top

    # Lanes are the lightest tint, without a border, so that the arrow labels between lanes
    # never cross a line.
    lanes = (
        (before_x, manifest_w + 2 * lane_pad, "BEFORE THE RUN"),
        (ci_x, ci_end - ci_x, "CI"),
        (merge_lane_x, merge_lane_w, "MERGE DECISION"),
    )
    for x, w, label in lanes:
        canvas.rect(x, lane_y, w, lane_h, theme.blue, rx=4, fill_opacity=theme.blue_tint)
        small_caps(canvas, x + lane_pad, label_y, label, theme, w - 2 * lane_pad + SPARE)

    _node(canvas, MANIFEST, manifest_x, top_y, manifest_w, top_h, theme)
    _node(canvas, TRIALS, trials_x, top_y, trials_w, top_h, theme)
    _node(canvas, MERGE, merge_x, top_y, merge_w, top_h, theme)
    for node, x, w in zip(bottom, bottom_x, bottom_w, strict=True):
        _node(canvas, node, x, row_y, w, row_h, theme)

    # The gate: a panel with a blue title, the verdicts coloured by meaning and the exit codes.
    canvas.panel(gate_x, top_y, gate_w, top_h, theme)
    gx = gate_x + gate_w // 2
    gtop = top_y + (top_h - NODE_TITLE_LH - 4 * NODE_LH) // 2
    canvas.text(
        gx,
        baseline(gtop, NODE_TITLE_LH, NODE_TITLE_SIZE),
        GATE.title,
        size=NODE_TITLE_SIZE,
        family=MONO,
        fill=theme.blue_text,
        weight=600,
        anchor="middle",
    )
    for index, line in enumerate(GATE.lines):
        canvas.text(
            gx,
            baseline(gtop + NODE_TITLE_LH + index * NODE_LH, NODE_LH, NODE_SIZE),
            line,
            size=NODE_SIZE,
            family=SANS,
            fill=theme.quiet,
            anchor="middle",
        )
    canvas.text(
        gx,
        baseline(gtop + NODE_TITLE_LH + 2 * NODE_LH, NODE_LH, verdict_size),
        verdict_spans(VERDICTS, theme),
        size=verdict_size,
        family=MONO,
        fill=theme.quiet,
        anchor="middle",
    )
    canvas.text(
        gx,
        baseline(gtop + NODE_TITLE_LH + 3 * NODE_LH, NODE_LH, verdict_size),
        EXITS,
        size=verdict_size,
        family=MONO,
        fill=theme.quiet,
        anchor="middle",
    )

    for (x0, w0), x1 in (
        ((manifest_x, manifest_w), trials_x),
        ((trials_x, trials_w), gate_x),
        ((gate_x, gate_w), merge_x),
    ):
        canvas.arrow(((x0 + w0 + ARROW_TAIL, mid), (x1 - ARROW_TIP, mid)), theme.quiet)
    # The arrow label sits wholly inside the CI lane, between the gate and the lane's edge, so
    # that it never crosses the edge of a lane tint.
    verdict_label = "verdict"
    label_gap = 8
    verdict_w = text_width(verdict_label, verdict_size, MONO)
    if gate_x + gate_w + label_gap + verdict_w + label_gap > ci_end:
        raise ValueError("layout: the verdict label does not fit between the gate and the lane")
    canvas.text(
        (gate_x + gate_w + ci_end) // 2,
        mid - 14,
        verdict_label,
        size=verdict_size,
        family=MONO,
        fill=theme.quiet,
        anchor="middle",
    )
    branch_x = trials_x + 48
    canvas.arrow(
        ((branch_x, top_y + top_h + ARROW_TAIL), (branch_x, row_y - ARROW_TIP)), theme.quiet
    )
    branch_label = "from the records, any verdict"
    require_fit(branch_label, verdict_size, MONO, ci_end - lane_pad - branch_x - 16)
    canvas.text(
        branch_x + 16,
        baseline(top_y + top_h, row_y - top_y - top_h, verdict_size),
        branch_label,
        size=verdict_size,
        family=MONO,
        fill=theme.quiet,
    )
    row_mid = row_y + row_h // 2
    for (x0, w0), x1 in zip(
        zip(bottom_x[:-1], bottom_w[:-1], strict=True), bottom_x[1:], strict=True
    ):
        canvas.arrow(((x0 + w0 + ARROW_TAIL, row_mid), (x1 - ARROW_TIP, row_mid)), theme.quiet)

    for index, line in enumerate(WHERE_NOTE):
        require_fit(line, NODE_SIZE, SANS, WHERE_W - 2 * MARGIN, weight=600)
        canvas.text(
            MARGIN,
            baseline(note_top + index * note_lh, note_lh, NODE_SIZE),
            verdict_spans(line, theme),
            size=NODE_SIZE,
            family=SANS,
            fill=theme.quiet,
        )
    return canvas.render()


# ---------------------------------------------------------------------------------------------
# Agents that use a decision model, 1600 wide
# ---------------------------------------------------------------------------------------------

DECISION_W = 1600
DECISION_TITLE = "Agents that use a decision model"
DECISION_SUB = (
    "TypeSafe's Jev answers typed questions with calibrated probabilities.",
    "arci tests what the agent does with those answers, with zero agent changes.",
)
AGENT_HEAD = "AGENT PROCESS"
AGENT_TEXT = (
    "Any SDK, unchanged. It reads two environment variables the harness sets: the endpoint is a"
    " loopback port, the key is a per-trial token."
)
AGENT_ENV = ("TYPESAFE_BASE_URL", "TYPESAFE_API_KEY")
BOUNDARY_HEAD = "HARNESS-OWNED BOUNDARY"
BOUNDARY_TEXT = (
    "Serves the MCP tools and the decision endpoint. Every request and answer is recorded as a"
    " tool call, budgeted, and perturbed on schedule."
)
BOUNDARY_FAULTS = ("decision_low_confidence", "decision_unavailable")
UPSTREAM_HEAD = "UPSTREAM"
UPSTREAM_TEXT = (
    ("fixture", ": seeded answers, offline, runs in CI."),
    (
        "http",
        ": the real API or a gateway, key held by the harness, model pinned, trial starts paced.",
    ),
)
RECORDS_HEAD = "SEALED RECORDS"
RECORDS_TEXT = "The answer the agent saw and the raw upstream answer, side by side. Never the key."
COMMANDS = (
    ("gate", "the same exact intervals; a model's confidence never enters a verdict"),
    ("replay", "serves the recording; no provider needed"),
    ("preflight", "key, endpoint, pinned model, one smoke request"),
    ("report", "recorded decisions, tokens, estimated cost"),
)


def _lead_lines(
    lead: str, rest: str, room: float, lead_family: str, lead_weight: int
) -> tuple[list[str], float]:
    """Wrap ``lead`` + ``rest`` where the lead word is set in another face; returns the lines of
    ``rest`` (the first one follows the lead) and the x offset of the first line."""
    space = 0.0 if rest.startswith(":") else text_width(" ", BODY_SIZE, SANS)
    offset = text_width(lead, BODY_SIZE, lead_family, weight=lead_weight) + space
    lines = wrap(rest.lstrip(" "), room, BODY_SIZE, SANS, first_room=room - offset)
    return lines, offset


def decision(theme: Theme) -> str:
    inner_pad, head_lh, head_gap = 24, 28, 12
    arrow_gap = 56
    row_gap = 24
    room_w = DECISION_W - 2 * MARGIN
    side_w = 400
    mid_w = room_w - 2 * side_w - 2 * arrow_gap
    xs = (MARGIN, MARGIN + side_w + arrow_gap, MARGIN + side_w + arrow_gap + mid_w + arrow_gap)
    ws = (side_w, mid_w, side_w)

    def text_room(width: int) -> int:
        return width - 2 * inner_pad

    agent_lines = wrap(AGENT_TEXT, text_room(ws[0]), BODY_SIZE, SANS)
    boundary_lines = wrap(BOUNDARY_TEXT, text_room(ws[1]), BODY_SIZE, SANS)
    upstream = [
        _lead_lines(lead, rest, text_room(ws[2]), SANS, 600) for lead, rest in UPSTREAM_TEXT
    ]
    env_size, env_lh = 18, 28
    chip_size, chip_h, chip_gap, chip_pad = 18, 34, 10, 12
    for name in AGENT_ENV:
        require_fit(name, env_size, MONO, text_room(ws[0]))
    for name in BOUNDARY_FAULTS:
        require_fit(name, chip_size, MONO, text_room(ws[1]) - 2 * chip_pad - SPARE)

    head_h = head_lh + head_gap
    agent_h = head_h + len(agent_lines) * BODY_LH + 12 + len(AGENT_ENV) * env_lh
    boundary_h = head_h + len(boundary_lines) * BODY_LH + 14
    boundary_h += len(BOUNDARY_FAULTS) * chip_h + (len(BOUNDARY_FAULTS) - 1) * chip_gap
    upstream_h = head_h + sum(len(lines) for lines, _ in upstream) * BODY_LH + 10
    row1_h = max(agent_h, boundary_h, upstream_h) + 2 * inner_pad

    # Row 2: sealed records under the agent, the commands panel to its right.
    records_lines = wrap(RECORDS_TEXT, text_room(side_w), BODY_SIZE, SANS)
    cmd_x = MARGIN + side_w + arrow_gap
    cmd_w = DECISION_W - MARGIN - cmd_x
    col_gap = 48
    col_w = (cmd_w - 2 * inner_pad - col_gap) // 2
    cmd_lines = [_lead_lines(word, text, col_w, MONO, 400) for word, text in COMMANDS]
    entry_gap = 18
    first_h = max(len(cmd_lines[0][0]), len(cmd_lines[1][0])) * BODY_LH
    second_h = max(len(cmd_lines[2][0]), len(cmd_lines[3][0])) * BODY_LH
    cmd_h = first_h + entry_gap + second_h
    records_h = head_h + len(records_lines) * BODY_LH
    row2_h = max(cmd_h, records_h) + 2 * inner_pad

    desc = " ".join(
        [
            f"{DECISION_TITLE}. {' '.join(DECISION_SUB)}",
            f"Agent process: {AGENT_TEXT} The two variables are {AGENT_ENV[0]} and {AGENT_ENV[1]}.",
            f"An arrow to the harness-owned boundary: {BOUNDARY_TEXT} Injected decision faults:"
            f" {BOUNDARY_FAULTS[0]} and {BOUNDARY_FAULTS[1]}.",
            "An arrow to the upstream: " + " ".join(lead + rest for lead, rest in UPSTREAM_TEXT),
            f"Sealed records: {RECORDS_TEXT} An arrow to the same commands:",
            "; ".join(f"{word}: {text}" for word, text in COMMANDS) + ".",
        ]
    )
    content_top = MARGIN + TITLE_LH + 4 + len(DECISION_SUB) * SUB_LH + 32
    row1_y = content_top
    row2_y = row1_y + row1_h + row_gap
    canvas_h = row2_y + row2_h + MARGIN
    canvas = Canvas(DECISION_W, canvas_h, DECISION_TITLE, desc)
    canvas.rect(0, 0, DECISION_W, canvas_h, theme.ground)
    top = header(canvas, theme, DECISION_TITLE, DECISION_SUB)
    assert top == content_top

    for x, w in zip(xs, ws, strict=True):
        canvas.panel(x, row1_y, w, row1_h, theme)
    heads = (AGENT_HEAD, BOUNDARY_HEAD, UPSTREAM_HEAD)
    for x, w, head in zip(xs, ws, heads, strict=True):
        small_caps(
            canvas,
            x + inner_pad,
            baseline(row1_y + inner_pad, head_lh, LABEL_SIZE),
            head,
            theme,
            text_room(w),
        )
    body_top = row1_y + inner_pad + head_h

    def body(x: int, top: int, lines: Sequence[str]) -> int:
        for index, line in enumerate(lines):
            canvas.text(
                x,
                baseline(top + index * BODY_LH, BODY_LH, BODY_SIZE),
                line,
                size=BODY_SIZE,
                family=SANS,
                fill=theme.ink,
            )
        return top + len(lines) * BODY_LH

    # Agent process.
    ax = xs[0] + inner_pad
    y = body(ax, body_top, agent_lines) + 12
    for index, name in enumerate(AGENT_ENV):
        canvas.text(
            ax,
            baseline(y + index * env_lh, env_lh, env_size),
            name,
            size=env_size,
            family=MONO,
            fill=theme.ink,
        )

    # Harness-owned boundary, with the two decision faults as orange-tinted chips.
    bx = xs[1] + inner_pad
    y = body(bx, body_top, boundary_lines) + 14
    for index, name in enumerate(BOUNDARY_FAULTS):
        chip_y = y + index * (chip_h + chip_gap)
        # The chip leaves SPARE px beyond its padding, and the name is centred in it.
        chip_w = math.ceil(text_width(name, chip_size, MONO)) + 2 * chip_pad + SPARE
        require_fit(name, chip_size, MONO, chip_w - 2 * chip_pad)
        canvas.rect(bx, chip_y, chip_w, chip_h, theme.orange, rx=3, fill_opacity=theme.orange_tint)
        canvas.text(
            bx + chip_w // 2,
            baseline(chip_y, chip_h, chip_size),
            name,
            size=chip_size,
            family=MONO,
            fill=theme.orange_text,
            anchor="middle",
        )

    # Upstream: two modes, the mode name in bold.
    ux = xs[2] + inner_pad
    y = body_top
    for (lead, _), (lines, _offset) in zip(UPSTREAM_TEXT, upstream, strict=True):
        for index, line in enumerate(lines):
            spans = [Span(line)]
            if index == 0:
                gap = "" if line.startswith(":") else " "
                spans = [Span(lead, weight=600), Span(gap + line)]
            canvas.text(
                ux,
                baseline(y + index * BODY_LH, BODY_LH, BODY_SIZE),
                spans,
                size=BODY_SIZE,
                family=SANS,
                fill=theme.ink,
            )
        y += len(lines) * BODY_LH + 10

    mid1 = row1_y + row1_h // 2
    for index in range(2):
        start = xs[index] + ws[index] + ARROW_TAIL
        canvas.arrow(((start, mid1), (xs[index + 1] - ARROW_TIP, mid1)), theme.quiet)

    # Row 2.
    canvas.panel(MARGIN, row2_y, side_w, row2_h, theme)
    small_caps(
        canvas,
        MARGIN + inner_pad,
        baseline(row2_y + inner_pad, head_lh, LABEL_SIZE),
        RECORDS_HEAD,
        theme,
        text_room(side_w),
    )
    body(MARGIN + inner_pad, row2_y + inner_pad + head_h, records_lines)

    canvas.panel(cmd_x, row2_y, cmd_w, row2_h, theme)
    cmd_top = row2_y + (row2_h - cmd_h) // 2
    for index, ((word, _), (lines, offset)) in enumerate(zip(COMMANDS, cmd_lines, strict=True)):
        col, row = index % 2, index // 2
        x = cmd_x + inner_pad + col * (col_w + col_gap)
        top = cmd_top + row * (first_h + entry_gap)
        for line_index, line in enumerate(lines):
            if line_index == 0:
                spans = [
                    Span(word, fill=theme.blue_text, family=MONO),
                    Span(line, x=round(x + offset)),
                ]
            else:
                spans = [Span(line)]
            canvas.text(
                x,
                baseline(top + line_index * BODY_LH, BODY_LH, BODY_SIZE),
                spans,
                size=BODY_SIZE,
                family=SANS,
                fill=theme.ink,
            )
    mid2 = row2_y + row2_h // 2
    canvas.arrow(((MARGIN + side_w + ARROW_TAIL, mid2), (cmd_x - ARROW_TIP, mid2)), theme.quiet)
    return canvas.render()


# ---------------------------------------------------------------------------------------------
# The gate, measured against itself, 1600 wide
# ---------------------------------------------------------------------------------------------

GATE_W = 1600
GATE_TITLE = "200 trials still do not guarantee a decision"
GATE_SUB = (
    "Probability of each verdict, by exact enumeration.",
    f"Default Clopper-Pearson {DOT} alpha 0.05 {DOT} delta 0.10 {DOT} K=1 {DOT} N per arm"
    f" {DOT} independent arms.",
)
GATE_BARS: tuple[tuple[str, int], ...] = (
    ("0.95 -> 0.65", 20),
    ("0.95 -> 0.65", 200),
    ("0.95 -> 0.75", 200),
    ("0.80 -> 0.80", 200),
)
GATE_VERDICTS = ("PASS", "BLOCK", "INCONCLUSIVE")  # the table's column order
GATE_BAR_X = 352
GATE_BAR_W = GATE_W - MARGIN - GATE_BAR_X


def gate_probabilities(pair: str, n: int) -> tuple[Fraction, Fraction, Fraction]:
    """PASS / BLOCK / INCONCLUSIVE for one cell of the README table, from its row string."""
    header_cells = [cell.strip() for cell in GATE_TABLE_HEADER.strip("|").split("|")]
    cells = [cell.strip() for cell in GATE_TABLE[pair].strip("|").split("|")]
    if cells[0] != pair:
        raise ValueError(f"table row for {pair!r} starts with {cells[0]!r}")
    values = [Fraction(value) for value in cells[header_cells.index(f"N={n}")].split(" / ")]
    if len(values) != 3:
        raise ValueError(f"cell {pair} N={n} is not PASS / BLOCK / INCONCLUSIVE")
    return values[0], values[1], values[2]


def gate_segments(pair: str, n: int) -> list[tuple[str, Fraction, int, int]]:
    """(verdict, probability, x, width) of each non-empty segment, widths to scale."""
    probabilities = gate_probabilities(pair, n)
    segments: list[tuple[str, Fraction, int, int]] = []
    cumulative = Fraction(0)
    for verdict, probability in zip(GATE_VERDICTS, probabilities, strict=True):
        start = round(cumulative * GATE_BAR_W)
        cumulative += probability
        end = round(cumulative * GATE_BAR_W)
        if probability:
            segments.append((verdict, probability, GATE_BAR_X + start, end - start))
    return segments


def _percent(probability: Fraction) -> str:
    return f"{float(probability * 100):.1f}%"


def _bar_label(pair: str, n: int) -> str:
    before, after = (round(Fraction(side) * 100) for side in pair.split(" -> "))
    return f"{before}% {ARROW} {after}%, N={n}"


def gate(theme: Theme) -> str:
    desc_rows = []
    for pair, n in GATE_BARS:
        values = ", ".join(
            f"{verdict} {_percent(p)}"
            for verdict, p in zip(GATE_VERDICTS, gate_probabilities(pair, n), strict=True)
        )
        desc_rows.append(f"{_bar_label(pair, n)}: {values}.")
    desc = " ".join(
        [
            f"{GATE_TITLE}. {' '.join(GATE_SUB)}",
            "One bar per case, drawn to scale:",
            *desc_rows,
            "Twenty runs decide almost nothing. False PASS at the margin and false BLOCK under no"
            " change are both far below alpha; the price is conservatism.",
            'Source: the table under "The gate, measured against itself" in the README.',
        ]
    )
    bar_h, bar_gap, label_size, seg_size, seg_pad = 56, 20, 20, 20, 16
    content_top = MARGIN + TITLE_LH + 4 + len(GATE_SUB) * SUB_LH + 32
    canvas_h = content_top + len(GATE_BARS) * bar_h + (len(GATE_BARS) - 1) * bar_gap + MARGIN
    canvas = Canvas(GATE_W, canvas_h, GATE_TITLE, desc)
    canvas.rect(0, 0, GATE_W, canvas_h, theme.ground)
    top = header(canvas, theme, GATE_TITLE, GATE_SUB)
    assert top == content_top

    fills = {
        "PASS": (theme.blue, theme.on_blue),
        "BLOCK": (theme.orange, theme.on_orange),
        "INCONCLUSIVE": (theme.neutral, theme.ink),
    }
    for index, (pair, n) in enumerate(GATE_BARS):
        y = top + index * (bar_h + bar_gap)
        label = _bar_label(pair, n)
        require_fit(label, label_size, MONO, GATE_BAR_X - MARGIN)
        canvas.text(
            MARGIN,
            baseline(y, bar_h, label_size),
            label,
            size=label_size,
            family=MONO,
            fill=theme.ink,
        )
        for verdict, probability, x, width in gate_segments(pair, n):
            fill, text_fill = fills[verdict]
            canvas.rect(x, y, width, bar_h, fill)
            text = f"{verdict} {_percent(probability)}"
            if text_width(text, seg_size, MONO) + 2 * seg_pad + SPARE <= width:
                canvas.text(
                    x + seg_pad,
                    baseline(y, bar_h, seg_size),
                    text,
                    size=seg_size,
                    family=MONO,
                    fill=text_fill,
                )
    return canvas.render()


# ---------------------------------------------------------------------------------------------
# Banner, 1280 x 640
# ---------------------------------------------------------------------------------------------

BANNER_W, BANNER_H = 1280, 640
BANNER_TITLE = "Real or noise?"
BANNER_MARK = "ARCI"
PILL_TEXT = "$ uvx realornoise"

# The daily values of the `reasoning_tokens` measure for the Claude Code tool in the packaged
# example: what `arci logs --example --json FILE` writes under
# `tools[0].measures[0].before_days[*].value` (earlier) and `.after_days[*].value` (recent).
# `tests/unit/docs/test_figures.py` checks these two tuples against the packaged example.
BANNER_BEFORE: tuple[int, ...] = (
    972, 925, 1060, 1047, 1097, 911, 1022, 913, 985, 931,
    919, 944, 970, 1049, 1054, 987, 905, 980, 1015, 1101,
    983, 964, 897, 935, 1097, 980, 969, 1060, 1115, 1088,
    910, 1058, 967, 1054, 1074, 911, 1111, 999, 1006, 1001,
    993, 914,
)  # fmt: skip
BANNER_AFTER: tuple[int, ...] = (
    535, 500, 491, 543, 518, 552, 497, 595, 534, 530, 527, 521, 559, 495,
)  # fmt: skip
BANNER_VALUES: tuple[int, ...] = BANNER_BEFORE + BANNER_AFTER
BANNER_MEDIAN_BEFORE = statistics.median(BANNER_BEFORE)
BANNER_MEDIAN_AFTER = statistics.median(BANNER_AFTER)


@dataclass(frozen=True)
class BannerTheme:
    name: str
    ground: str
    band_opacity: float
    split: str
    median_before_opacity: float
    median_after_opacity: float
    mark: str
    dot_blue: str
    dot_orange: str
    headline_blue: str
    headline_orange: str
    headline_muted: str
    pill_fill: str
    pill_border: str
    pill_dollar: str
    pill_ink: str


BANNER_LIGHT = BannerTheme(
    name="light",
    ground="#F6F8FA",
    band_opacity=0.08,
    split="#8C959F",
    median_before_opacity=0.5,
    median_after_opacity=0.55,
    mark="#57606A",
    dot_blue="#1F6FEB",
    dot_orange="#E8590C",
    headline_blue="#1F6FEB",
    headline_orange="#D14E0A",
    headline_muted="#7A838D",
    pill_fill="#FFFFFF",
    pill_border="#D0D7DE",
    pill_dollar="#636C76",
    pill_ink="#10161D",
)

BANNER_DARK = BannerTheme(
    name="dark",
    ground="#0D1117",
    band_opacity=0.10,
    split="#5B6878",
    median_before_opacity=0.55,
    median_after_opacity=0.6,
    mark="#9BA7B4",
    dot_blue="#6CB6FF",
    dot_orange="#FF9F45",
    headline_blue="#6CB6FF",
    headline_orange="#FF9F45",
    headline_muted="#8B98A7",
    pill_fill="#151C26",
    pill_border="#2A3646",
    pill_dollar="#8B98A7",
    pill_ink="#F2F6FA",
)


def _banner_dot_x(index: int) -> float:
    return round(80 + index * 1120 / 55, 1)


def _banner_dot_y(value: float) -> float:
    return round(122 + (1115 - value) * 0.44, 1)


def banner(theme: BannerTheme) -> str:
    desc = (
        "Forty-two dots for the earlier days scatter inside one band; after a dashed line,"
        " fourteen dots for the recent days sit well below the band. The dots are the daily"
        " values of the packaged example (realornoise --example), which is generated data;"
        " the command is uvx realornoise."
    )
    canvas = Canvas(BANNER_W, BANNER_H, BANNER_TITLE, desc)
    canvas.rect(0, 0, BANNER_W, BANNER_H, theme.ground)

    before_ys = [_banner_dot_y(value) for value in BANNER_BEFORE]
    band_y = round(min(before_ys) - 16)
    band_bottom = round(max(before_ys) + 16)
    canvas.rect(
        0, band_y, BANNER_W, band_bottom - band_y, theme.dot_blue, fill_opacity=theme.band_opacity
    )

    split_x = round((_banner_dot_x(41) + _banner_dot_x(42)) / 2, 1)
    canvas.line(
        split_x,
        56,
        split_x,
        430,
        theme.split,
        dasharray="3 7",
        linecap="round",
    )

    canvas.line(
        _banner_dot_x(0),
        _banner_dot_y(BANNER_MEDIAN_BEFORE),
        _banner_dot_x(41),
        _banner_dot_y(BANNER_MEDIAN_BEFORE),
        theme.dot_blue,
        opacity=theme.median_before_opacity,
    )
    canvas.line(
        _banner_dot_x(42),
        _banner_dot_y(BANNER_MEDIAN_AFTER),
        _banner_dot_x(55),
        _banner_dot_y(BANNER_MEDIAN_AFTER),
        theme.dot_orange,
        opacity=theme.median_after_opacity,
    )

    canvas.text(
        80,
        64,
        BANNER_MARK,
        size=14,
        family=MONO,
        fill=theme.mark,
        weight=500,
        spacing="2.4",
    )

    for index, value in enumerate(BANNER_VALUES):
        color = theme.dot_blue if index < len(BANNER_BEFORE) else theme.dot_orange
        canvas.circle(_banner_dot_x(index), _banner_dot_y(value), 7, color)

    canvas.text(
        80,
        560,
        [
            Span("Real ", fill=theme.headline_orange),
            Span("or ", fill=theme.headline_muted),
            Span("noise?", fill=theme.headline_blue),
        ],
        size=92,
        family=SANS,
        fill=theme.headline_blue,
        weight=700,
        spacing="-3.2",
    )

    pad = 22
    pill_h = 58
    pill_w = round(len(PILL_TEXT) * 22 * MONO_ADVANCE) + 2 * pad
    pill_x = 1200 - pill_w
    pill_y = 574 - pill_h
    canvas.rect(pill_x, pill_y, pill_w, pill_h, theme.pill_fill, rx=10, stroke=theme.pill_border)
    canvas.text(
        pill_x + pad,
        baseline(pill_y, pill_h, 22),
        [
            Span("$", fill=theme.pill_dollar),
            Span(PILL_TEXT[1:], fill=theme.pill_ink),
        ],
        size=22,
        family=MONO,
        fill=theme.pill_ink,
        weight=500,
    )
    return canvas.render()


# ---------------------------------------------------------------------------------------------
# Command line
# ---------------------------------------------------------------------------------------------


def figures() -> dict[str, str]:
    return {
        "hero-light.svg": hero(LIGHT),
        "hero-dark.svg": hero(DARK),
        "where-light.svg": where(LIGHT),
        "where-dark.svg": where(DARK),
        "decision-light.svg": decision(LIGHT),
        "decision-dark.svg": decision(DARK),
        "gate-light.svg": gate(LIGHT),
        "gate-dark.svg": gate(DARK),
        "banner-light.svg": banner(BANNER_LIGHT),
        "banner-dark.svg": banner(BANNER_DARK),
    }


def check_sources() -> list[str]:
    problems: list[str] = []
    for relative, needle in SOURCES:
        path = REPO / relative
        if not path.is_file():
            problems.append(f"missing source file {relative}")
        elif needle not in path.read_text("utf-8"):
            problems.append(f"{relative} no longer contains {needle!r}")
    return problems


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate the README figures.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true", help="regenerate docs/assets/*.svg")
    mode.add_argument("--check", action="store_true", help="fail if a committed SVG is stale")
    args = parser.parse_args(argv)

    problems = check_sources()
    if problems:
        for problem in problems:
            print(f"source check failed: {problem}", file=sys.stderr)
        return 1

    stale: list[str] = []
    for name, content in figures().items():
        path = ASSETS / name
        data = content.encode("utf-8")
        if args.write:
            path.write_bytes(data)
            print(f"wrote {path.relative_to(REPO)}")
        elif not path.is_file() or path.read_bytes() != data:
            stale.append(str(path.relative_to(REPO)))
    if stale:
        for name in stale:
            print(f"stale or missing: {name}", file=sys.stderr)
        print("run: python docs/assets/src/make_figures.py --write", file=sys.stderr)
        return 1
    if args.check:
        print("figures are current: " + ", ".join(sorted(figures())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
