"""tool_outcomes_markdown: exact fixed text, table shape, and code-span escaping.

From the "Contract" section of R1-tool-outcomes.md. The heading and paragraph are given
verbatim in the contract; the escaping rule (CommonMark code spans, `_cell` left as-is) is
checked structurally rather than by pinning one exact byte sequence, since the contract
only requires a *valid* code span, not one specific encoding of it.
"""

from __future__ import annotations

import re

from arci.report import tool_outcomes, tool_outcomes_markdown
from tests.unit.tool_outcomes_blind.helpers import finish, start, trial

HEADING = "## Tool outcomes (descriptive)"
PARAGRAPH = (
    "Counts of recorded tool attempts. An uninjected failure is a recorded tool_finish that "
    "failed with no injection marker; the record does not show why it failed, and an earlier "
    "injected fault can be the cause. A tool with no recorded start in a trial may simply not "
    "be needed by that task; compare the two arms. Retries by middleware count as attempts. "
    "Counts are descriptive and decide nothing."
)
ARM_HEADER = "| Arm | Trials | Trials with an uninjected failure | Then passed | Then not passed |"
ARM_SEP = "|---|---:|---:|---:|---:|"
TOOL_HEADER = (
    "| Tool | Arm | Trials | Started in | Not started in | Starts | Uninjected failures "
    "| Trials with one |"
)
TOOL_SEP = "|---|---|---:|---:|---:|---:|---:|---:|"


def test_first_line_is_empty_like_fault_markdown() -> None:
    lines = tool_outcomes_markdown([])
    assert lines[0] == ""


def test_exact_heading_and_paragraph() -> None:
    lines = tool_outcomes_markdown([])
    assert lines[1] == HEADING
    assert PARAGRAPH in lines


def test_exact_arm_table_header_and_separator() -> None:
    lines = tool_outcomes_markdown([])
    assert ARM_HEADER in lines
    idx = lines.index(ARM_HEADER)
    assert lines[idx + 1] == ARM_SEP


def test_exact_tool_table_header_and_separator_when_tools_present() -> None:
    t = trial("t", arm="baseline", events=[start("t", 0, "lookup_order")])
    lines = tool_outcomes_markdown([t])
    assert TOOL_HEADER in lines
    idx = lines.index(TOOL_HEADER)
    assert lines[idx + 1] == TOOL_SEP


def test_no_tool_starts_recorded_when_tools_empty_but_arm_table_present() -> None:
    lines = tool_outcomes_markdown([])
    assert ARM_HEADER in lines
    assert "No tool starts recorded." in lines
    assert TOOL_HEADER not in lines


def test_arm_row_numbers_match_tool_outcomes() -> None:
    trials = [
        trial("b1", arm="baseline", events=[finish("b1", 0, "x", ok=False)]),
        trial("b2", arm="baseline"),
        trial("c1", arm="candidate"),
    ]
    computed = tool_outcomes(trials)
    lines = tool_outcomes_markdown(trials)
    base = computed["arms"][0]
    cand = computed["arms"][1]
    assert (
        f"| baseline | {base['trials']} | {base['uninjected_failure_trials']} "
        f"| {base['uninjected_then_passed']} | {base['uninjected_then_not_passed']} |"
    ) in lines
    assert (
        f"| candidate | {cand['trials']} | {cand['uninjected_failure_trials']} "
        f"| {cand['uninjected_then_passed']} | {cand['uninjected_then_not_passed']} |"
    ) in lines


def test_tool_row_numbers_match_tool_outcomes() -> None:
    t = trial(
        "t",
        arm="baseline",
        events=[start("t", 0, "fetch"), start("t", 1, "fetch"), finish("t", 2, "fetch", ok=False)],
    )
    computed = tool_outcomes([t])
    lines = tool_outcomes_markdown([t])
    row = next(r for r in computed["tools"] if r["arm"] == "baseline")
    assert (
        f"| `fetch` | baseline | {row['trials']} | {row['trials_started']} "
        f"| {row['trials_not_started']} | {row['starts']} | {row['uninjected_failures']} "
        f"| {row['uninjected_failure_trials']} |"
    ) in lines


# --- GFM-table-aware splitting, respecting code spans and escaped pipes -----------------


def _split_table_row(line: str) -> list[str]:
    """Split a `| a | b |` row on unescaped, non-code-span pipes (minimal GFM subset)."""
    assert line.startswith("|") and line.endswith("|")
    body = line[1:-1]
    cells: list[str] = []
    buf = ""
    i = 0
    in_code = False
    fence_len = 0
    while i < len(body):
        ch = body[i]
        if ch == "`":
            j = i
            while j < len(body) and body[j] == "`":
                j += 1
            run = j - i
            if not in_code:
                in_code = True
                fence_len = run
            elif run == fence_len:
                in_code = False
            buf += body[i:j]
            i = j
            continue
        if ch == "\\" and not in_code and i + 1 < len(body):
            buf += body[i : i + 2]
            i += 2
            continue
        if ch == "|" and not in_code:
            cells.append(buf)
            buf = ""
            i += 1
            continue
        buf += ch
        i += 1
    cells.append(buf)
    return cells


def _decode_code_span(cell: str) -> str:
    cell = cell.strip()
    m = re.match(r"^(`+)", cell)
    assert m, f"not a code span: {cell!r}"
    fence = m.group(1)
    assert cell.endswith(fence) and len(cell) >= 2 * len(fence)
    inner = cell[len(fence) : len(cell) - len(fence)]
    if len(inner) >= 2 and inner[0] == " " and inner[-1] == " " and inner.strip() != "":
        inner = inner[1:-1]
    # `_cell` (left unchanged, frozen behaviour) backslash-escapes pipes for table safety;
    # undo that to recover the original tool name.
    return inner.replace("\\|", "|")


def test_tool_name_containing_pipe_keeps_the_right_column_count_and_decodes() -> None:
    t = trial("t", arm="baseline", events=[start("t", 0, "weird|tool")])
    lines = tool_outcomes_markdown([t])
    rows = [line for line in lines if line.startswith("| `")]
    target = next(row for row in rows if "baseline" in row)
    cells = _split_table_row(target)
    assert len(cells) == 8
    assert _decode_code_span(cells[0]) == "weird|tool"


def test_tool_name_containing_backtick_keeps_the_right_column_count_and_decodes() -> None:
    t = trial("t", arm="baseline", events=[start("t", 0, "weird`tool")])
    lines = tool_outcomes_markdown([t])
    rows = [line for line in lines if line.startswith("| `")]
    target = next(row for row in rows if "baseline" in row)
    cells = _split_table_row(target)
    assert len(cells) == 8
    assert _decode_code_span(cells[0]) == "weird`tool"
