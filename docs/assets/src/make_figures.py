"""Generate the README figures: ``docs/assets/{hero,where}-{light,dark}.svg``.

Standard library only, deterministic, no network. ``--write`` regenerates the four files;
``--check`` regenerates them in memory and exits 1 if a committed file is missing or differs.

The SVGs are plain ``<text>``, ``<rect>`` and ``<path>`` elements: no ``<style>`` blocks, no
scripts, no raster images, no external fonts. Text uses system font stacks so GitHub renders
it without web fonts, and every box leaves room for font-metric differences between platforms.
``<title>`` and ``<desc>`` carry the full text of each figure.

Every number shown traces to a committed file, and both modes first confirm that the exact
strings below are still present in those files (``SOURCES``), so the figures cannot drift from
the evidence silently:

- ``docs/results/retry-demo-n200.md``: 200 trials per arm (``n_per_arm`` 200), A 192/200,
  B 132/200, bounds on the difference [-0.405, -0.183], margin (``delta``) 0.10,
  BLOCK with exit 1.
- ``docs/reports/ci-gate-2026-10-06/logs/hero-demo-2026-10-05.txt`` (the unedited demo log):
  BLOCK (exit 1) for A vs B, the condition shrunk from 3 injected faults to ``tool_timeout``,
  ``1-minimal``, and the offline replay ``REPRODUCED``.
- ``examples/retry_agent/experiment.py``: the timeout is injected on the first ``reserve``
  call (``tool="reserve"``, ``at_occurrence=0``).
- ``src/arci/schema.py`` (frozen): the four verdicts and their exit codes 0, 1, 2 and 3.

The pipeline figure contains no measured numbers.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from html import escape
from pathlib import Path

ASSETS = Path(__file__).resolve().parent.parent
REPO = ASSETS.parent.parent

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
)

SERIF = "Georgia, 'Times New Roman', serif"
MONO = "ui-monospace, 'SF Mono', Menlo, Consolas, 'Liberation Mono', monospace"
SANS = "system-ui, -apple-system, 'Segoe UI', Helvetica, Arial, sans-serif"
MONO_ADVANCE = 0.6  # em; ui-monospace, SF Mono, Menlo, Liberation Mono and DejaVu all use ~0.6

MINUS = chr(0x2212)  # typographic minus
ARROW = chr(0x2192)
DOT = chr(0x00B7)  # middle dot


@dataclass(frozen=True)
class Theme:
    name: str
    ground: str
    thesis: str
    soft: str
    muted: str
    accent: str
    card: str
    card_text: str
    card_muted: str
    good: str
    bad: str
    lane_outer: str
    lane_inner: str
    box: str
    box_border: str
    arrow: str


LIGHT = Theme(
    name="light",
    ground="#F4F1EA",
    thesis="#16211D",
    soft="#3E3D38",
    muted="#6B6A65",
    accent="#B8431F",
    card="#16211D",
    card_text="#E9E4D8",
    card_muted="#A8A397",
    good="#7FD1A8",
    bad="#F0A48A",
    lane_outer="#ECE8DD",
    lane_inner="#E9E4D8",
    box="#FFFFFF",
    box_border="#D9D4C7",
    arrow="#6B6A65",
)

DARK = Theme(
    name="dark",
    ground="#0F1512",
    thesis="#F0ECE2",
    soft="#CFCBC1",
    muted="#9A978E",
    accent="#E07A55",
    card="#F4F1EA",
    card_text="#16211D",
    card_muted="#6B6A65",
    good="#1F7A4D",
    bad="#B8431F",
    lane_outer="#161E1A",
    lane_inner="#1A231F",
    box="#212B26",
    box_border="#34413A",
    arrow="#9A978E",
)

# Verdict colours on the light ground (the pipeline figure's PASS arrow on the light theme).
LIGHT_GOOD_ON_GROUND = "#1F7A4D"
DARK_GOOD_ON_GROUND = "#7FD1A8"


@dataclass(frozen=True)
class Span:
    text: str
    fill: str | None = None
    weight: int | None = None
    x: int | None = None


class Canvas:
    def __init__(self, width: int, height: int, title: str, desc: str) -> None:
        self.width = width
        self.height = height
        self.title = title
        self.desc = desc
        self.body: list[str] = []

    def rect(
        self,
        x: int,
        y: int,
        w: int,
        h: int,
        fill: str,
        rx: int = 0,
        stroke: str | None = None,
        stroke_width: int = 1,
    ) -> None:
        extra = f' stroke="{stroke}" stroke-width="{stroke_width}"' if stroke else ""
        radius = f' rx="{rx}"' if rx else ""
        self.body.append(
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}"{radius} fill="{fill}"{extra}/>'
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
CARD_A, CARD_B = "192/200", "132/200"
CARD_BOUNDS = f"[{MINUS}0.405, {MINUS}0.183]"
CARD_MARGIN = f" {DOT} margin {MINUS}0.10"
CARD_VERDICT = "VERDICT: BLOCK (exit 1)"
CARD_CHAIN = f"3 faults {ARROW} 1-minimal {ARROW} replay "
CARD_REPLAY = "REPRODUCED"
CARD_FOOT = ("B is A with one retry removed", "docs/results/retry-demo-n200.md")


def hero(theme: Theme) -> str:
    desc = " ".join(
        [
            f"{EYEBROW[0]}: {EYEBROW[1]}, {EYEBROW[2]}.",
            " ".join(THESIS),
            " ".join(SUBLINE),
            "Evidence card:",
            "Seeded retry demo, 200 trials per arm, timeout on the first reserve call.",
            f"A {CARD_A}, B {CARD_B}.",
            f"Bounds on the difference {CARD_BOUNDS}, margin {MINUS}0.10.",
            f"{CARD_VERDICT}; 3 injected faults reduced to 1, 1-minimal; offline replay"
            f" {CARD_REPLAY}.",
            f"{CARD_FOOT[0]}. Source: {CARD_FOOT[1]}.",
        ]
    )
    canvas = Canvas(HERO_W, HERO_H, " ".join(THESIS), desc)
    canvas.rect(0, 0, HERO_W, HERO_H, theme.ground)

    pad_y, col_x, col_w, gap, card_w = 56, 72, 760, 56, 640
    card_x = col_x + col_w + gap
    card_h = HERO_H - 2 * pad_y

    # Left column: eyebrow (2 lines), thesis (3 lines), subline (2 lines), vertically centred.
    eyebrow_lh, thesis_size, thesis_lh, sub_size, sub_lh, block_gap = 30, 56, 61, 27, 38, 22
    total = 2 * eyebrow_lh + block_gap + 3 * thesis_lh + block_gap + 2 * sub_lh
    top = pad_y + (card_h - total) // 2
    first_w = round(len(EYEBROW[0]) * 22 * MONO_ADVANCE) + 14
    canvas.text(
        col_x,
        baseline(top, eyebrow_lh, 22),
        [
            Span(EYEBROW[0], fill=theme.accent, weight=600),
            Span(EYEBROW[1], x=col_x + first_w),
        ],
        size=22,
        family=MONO,
        fill=theme.muted,
        spacing="0.44",
    )
    canvas.text(
        col_x,
        baseline(top + eyebrow_lh, eyebrow_lh, 22),
        EYEBROW[2],
        size=22,
        family=MONO,
        fill=theme.muted,
        spacing="0.44",
    )
    top += 2 * eyebrow_lh + block_gap
    for index, line in enumerate(THESIS):
        canvas.text(
            col_x,
            baseline(top + index * thesis_lh, thesis_lh, thesis_size),
            line,
            size=thesis_size,
            family=SERIF,
            fill=theme.thesis,
            weight=600,
        )
    top += 3 * thesis_lh + block_gap
    for index, line in enumerate(SUBLINE):
        canvas.text(
            col_x,
            baseline(top + index * sub_lh, sub_lh, sub_size),
            line,
            size=sub_size,
            family=SANS,
            fill=theme.soft,
        )

    # Evidence card.
    canvas.rect(card_x, pad_y, card_w, card_h, theme.card, rx=16)
    inner_x = card_x + 34
    rows: list[tuple[int, int, int]] = []  # (gap before, line height, font size) per line
    label_lh, num_lh, body_lh, foot_lh = 24, 48, 32, 22
    rows += [(0, label_lh, 17), (0, label_lh, 17)]
    rows += [(18, num_lh, 40)]
    rows += [(18, body_lh, 22), (0, body_lh, 22)]
    rows += [(12, body_lh, 22), (0, body_lh, 22)]
    rows += [(18, foot_lh, 16), (0, foot_lh, 16)]
    content_h = sum(gap_before + lh for gap_before, lh, _ in rows)
    y = pad_y + (card_h - content_h) // 2
    baselines: list[int] = []
    for gap_before, lh, size in rows:
        y += gap_before
        baselines.append(baseline(y, lh, size))
        y += lh

    for index, line in enumerate(CARD_LABEL):
        canvas.text(
            inner_x,
            baselines[index],
            line,
            size=17,
            family=MONO,
            fill=theme.card_muted,
            spacing="1.36",
        )
    b_x = inner_x + round(len(f"A {CARD_A}") * 40 * MONO_ADVANCE) + 40
    canvas.text(
        inner_x,
        baselines[2],
        [
            Span("A "),
            Span(CARD_A, fill=theme.good),
            Span("B ", x=b_x),
            Span(CARD_B, fill=theme.bad),
        ],
        size=40,
        family=MONO,
        fill=theme.card_text,
        weight=600,
    )
    canvas.text(
        inner_x,
        baselines[3],
        "bounds on the difference",
        size=22,
        family=MONO,
        fill=theme.card_text,
    )
    canvas.text(
        inner_x,
        baselines[4],
        [Span(CARD_BOUNDS, fill=theme.bad), Span(CARD_MARGIN)],
        size=22,
        family=MONO,
        fill=theme.card_text,
    )
    canvas.text(
        inner_x,
        baselines[5],
        CARD_VERDICT,
        size=22,
        family=MONO,
        fill=theme.bad,
        weight=600,
    )
    canvas.text(
        inner_x,
        baselines[6],
        [Span(CARD_CHAIN), Span(CARD_REPLAY, fill=theme.good, weight=600)],
        size=22,
        family=MONO,
        fill=theme.card_text,
    )
    for index, line in enumerate(CARD_FOOT):
        canvas.text(
            inner_x,
            baselines[7 + index],
            line,
            size=16,
            family=MONO,
            fill=theme.card_muted,
        )
    return canvas.render()


# ---------------------------------------------------------------------------------------------
# Where arci sits, 1600 x 560
# ---------------------------------------------------------------------------------------------

WHERE_W, WHERE_H = 1600, 560
WHERE_TITLE = "Where arci sits"
WHERE_SUB = (
    "Between an agent change and the merge decision: a frozen, repeated experiment,"
    " and diagnosis from the same records."
)
VERDICTS = f"PASS {DOT} BLOCK {DOT} INCONCLUSIVE {DOT} ERROR"
EXITS = f"exit 0 {DOT} 1 {DOT} 2 {DOT} 3"
WHERE_NOTE = (
    "Diagnosis does not need a BLOCK: it compares any passing and failing trial in the records."
    " Replay re-serves the recorded boundary calls; it does not repeat model inference."
)


@dataclass(frozen=True)
class Node:
    x: int
    y: int
    w: int
    h: int
    title: str
    lines: tuple[str, ...]


MANIFEST = Node(
    88,
    200,
    256,
    128,
    "Frozen manifest",
    ("baseline and candidate,", "oracle, faults, seeds, N", "and the decision rule"),
)
TRIALS = Node(
    424,
    200,
    296,
    128,
    "Recorded trials",
    ("seeded trials per arm,", "injected tool faults,", "sealed boundary records"),
)
GATE = Node(
    768,
    186,
    384,
    156,
    "arci gate",
    ("exact Clopper-Pearson bounds", "on the difference, frozen margin"),
)
MERGE = Node(
    1240,
    200,
    272,
    128,
    "Merge",
    ("on PASS (exit 0)", "BLOCK and ERROR fail the job;", "INCONCLUSIVE fails by default"),
)
DIFF = Node(
    424,
    392,
    232,
    104,
    "Trace comparison",
    ("first divergent step,", "passing vs failing trial"),
)
SHRINK = Node(
    692,
    392,
    220,
    104,
    "Fault reduction",
    ("ddmin over injected", "faults, same fingerprint"),
)
REPLAY = Node(
    948,
    392,
    232,
    104,
    "Offline replay",
    ("recorded boundary calls,", "not fresh model inference"),
)


def _node(canvas: Canvas, node: Node, theme: Theme) -> None:
    canvas.rect(node.x, node.y, node.w, node.h, theme.box, rx=10, stroke=theme.box_border)
    title_lh, line_lh = 26, 22
    total = title_lh + line_lh * len(node.lines)
    top = node.y + (node.h - total) // 2
    cx = node.x + node.w // 2
    canvas.text(
        cx,
        baseline(top, title_lh, 18),
        node.title,
        size=18,
        family=SANS,
        fill=theme.thesis,
        weight=600,
        anchor="middle",
    )
    for index, line in enumerate(node.lines):
        canvas.text(
            cx,
            baseline(top + title_lh + index * line_lh, line_lh, 15),
            line,
            size=15,
            family=SANS,
            fill=theme.soft,
            anchor="middle",
        )


def where(theme: Theme) -> str:
    good = LIGHT_GOOD_ON_GROUND if theme.name == "light" else DARK_GOOD_ON_GROUND
    on_card = theme.name == "dark"  # the dark theme inverts the highlighted box to cream
    gate_bg = theme.card if on_card else LIGHT.card
    gate_text = theme.card_text if on_card else LIGHT.card_text
    gate_title = theme.bad if on_card else LIGHT.bad
    gate_muted = theme.card_muted if on_card else LIGHT.card_muted

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
        WHERE_NOTE,
    ]
    canvas = Canvas(WHERE_W, WHERE_H, "Where arci sits in a CI pipeline", " ".join(desc_parts))
    canvas.rect(0, 0, WHERE_W, WHERE_H, theme.ground)
    canvas.text(64, 84, WHERE_TITLE, size=32, family=SERIF, fill=theme.thesis, weight=600)
    canvas.text(64, 122, WHERE_SUB, size=18, family=SANS, fill=theme.soft)

    lanes = ((64, 304, "BEFORE THE RUN", theme.lane_outer), (400, 800, "CI", theme.lane_inner))
    lanes += ((1216, 320, "MERGE DECISION", theme.lane_outer),)
    for x, w, label, fill in lanes:
        canvas.rect(x, 146, w, 374, fill, rx=12)
        canvas.text(
            x + 18,
            176,
            label,
            size=13,
            family=MONO,
            fill=theme.muted,
            spacing="1.56",
        )

    for node in (MANIFEST, TRIALS, MERGE, DIFF, SHRINK, REPLAY):
        _node(canvas, node, theme)

    # The highlighted gate.
    canvas.rect(GATE.x, GATE.y, GATE.w, GATE.h, gate_bg, rx=12, stroke=theme.accent, stroke_width=2)
    gx = GATE.x + GATE.w // 2
    canvas.text(
        gx,
        GATE.y + 36,
        GATE.title,
        size=20,
        family=MONO,
        fill=gate_title,
        weight=600,
        anchor="middle",
    )
    for index, line in enumerate(GATE.lines):
        canvas.text(
            gx,
            GATE.y + 64 + index * 22,
            line,
            size=15,
            family=SANS,
            fill=gate_text,
            anchor="middle",
        )
    canvas.text(
        gx,
        GATE.y + 118,
        VERDICTS,
        size=15,
        family=MONO,
        fill=gate_text,
        weight=600,
        anchor="middle",
    )
    canvas.text(gx, GATE.y + 140, EXITS, size=14, family=MONO, fill=gate_muted, anchor="middle")

    mid = 264  # vertical centre of the top row
    canvas.arrow(((MANIFEST.x + MANIFEST.w, mid), (TRIALS.x - 4, mid)), theme.arrow)
    canvas.arrow(((TRIALS.x + TRIALS.w, mid), (GATE.x - 4, mid)), theme.arrow)
    canvas.arrow(((GATE.x + GATE.w + 2, mid), (MERGE.x - 4, mid)), good)
    canvas.text(
        (GATE.x + GATE.w + MERGE.x) // 2,
        mid - 12,
        "verdict",
        size=13,
        family=MONO,
        fill=good,
        anchor="middle",
    )
    branch_x = TRIALS.x + 116
    canvas.arrow(((branch_x, TRIALS.y + TRIALS.h), (branch_x, DIFF.y - 4)), theme.accent)
    canvas.text(
        branch_x + 14,
        (TRIALS.y + TRIALS.h + DIFF.y) // 2 + 5,
        "from the records, any verdict",
        size=13,
        family=MONO,
        fill=theme.accent,
    )
    row = DIFF.y + DIFF.h // 2
    canvas.arrow(((DIFF.x + DIFF.w, row), (SHRINK.x - 4, row)), theme.arrow)
    canvas.arrow(((SHRINK.x + SHRINK.w, row), (REPLAY.x - 4, row)), theme.arrow)

    canvas.text(64, 546, WHERE_NOTE, size=14, family=SANS, fill=theme.muted)
    return canvas.render()


def _describe(node: Node) -> str:
    return f"{node.title} ({' '.join(node.lines)})"


# ---------------------------------------------------------------------------------------------
# Command line
# ---------------------------------------------------------------------------------------------


def figures() -> dict[str, str]:
    return {
        "hero-light.svg": hero(LIGHT),
        "hero-dark.svg": hero(DARK),
        "where-light.svg": where(LIGHT),
        "where-dark.svg": where(DARK),
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
