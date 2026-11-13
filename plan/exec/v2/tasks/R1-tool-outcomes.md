# TASK R1: tool-outcome breakdown in suite reports (for v2.1.0)

Worktree `/Users/ajay/Developer/.arci-worktrees/wt-v2.1` (branch `v2.1/integration`, cut
from `main` at 2.0.0). No state-changing git. Frozen files (`FROZEN.sha256`, 65 entries)
untouched; if one looks wrong, stop and say so. Do not bump the version.

You own: `src/arci/report.py` (additions only), `src/arci/suite_report.py`,
`src/arci/html_report.py`, the goldens `tests/unit/suite_report/*.md` and
`tests/unit/html_report/golden/*.html`, `docs/results/sample-suite-report.html`,
`docs/recipes/langchain.md` (one short paragraph), and new tests under
`tests/unit/suite_report/` and `tests/unit/html_report/`. Do not touch
`tests/unit/tool_outcomes_blind/` (another agent writes it from this same spec; your code
must pass it), `examples/`, `src/arci/init.py`, `README.md`.

## Why

Two readers of the public study asked what each arm did with its tools. The answers were
computed by hand: trials that never called a tool, trials where a tool failed through the
agent's own call and the trial still passed, and where it then failed. Put that in every
suite report, beside fault accounting. Descriptive only; it decides nothing.

## Contract

Revised after Codex's read-only review (`consults/R-brief-review.md`): the trace cannot
show *why* a call failed, so nothing in names or text may say "the agent's own" failure.
The metric is **recorded failures without an injection marker**.

In `src/arci/report.py`:

```python
class ArmToolSummary(TypedDict):
    arm: str                          # "baseline" | "candidate"
    trials: int                       # trials of this arm in the input
    uninjected_failure_trials: int    # trials with >= 1 uninjected failure (any tool)
    uninjected_then_passed: int       # of those, outcome is PASS
    uninjected_then_not_passed: int   # of those, any other outcome (FAIL, ERROR, ...)

class ToolOutcomeRow(TypedDict):
    arm: str
    tool: str
    trials: int                       # trials of this arm in the input
    trials_started: int               # trials with >= 1 tool_start for this tool
    trials_not_started: int           # trials - trials_started
    starts: int                       # tool_start events for this tool
    uninjected_failures: int          # uninjected-failure tool_finish events for this tool
    uninjected_failure_trials: int    # trials with >= 1 of them for this tool

class ToolOutcomes(TypedDict):
    arms: list[ArmToolSummary]
    tools: list[ToolOutcomeRow]

def tool_outcomes(trials: Sequence[TrialEnvelope]) -> ToolOutcomes: ...
def tool_outcomes_markdown(trials: Sequence[TrialEnvelope]) -> list[str]: ...
```

Definitions:

- An **uninjected failure** is a `tool_finish` event whose payload has `ok` exactly `False`
  (the bool, not a falsy value) and whose `injected_by` is `None`, missing, or the empty
  string. A finish whose `injected_by` is a non-empty string is never counted. A finish
  whose `injected_by` is anything else (a number, a list, ...) is malformed and is not
  counted either. Note `empty_result` only replaces the value and sets the marker; it does
  not change `ok`, so a marked finish can have `ok` false and is still excluded here.
- This counts what was **recorded at the tool boundary**, literally: every recorded attempt
  counts, including a middleware retry the model never saw; `replay_miss` failures and
  environmental exceptions are included; ERROR trials fall under "not passed"; a call
  refused before recording (argument validation, budget) leaves no event and is not
  counted; an incomplete call contributes a start and no finish. `decision:*` tool names
  are not filtered. Do not try to infer causes.
- The tool of an event is `payload["tool"]` when it is a `str`; events whose `tool` is not
  a string are ignored. Count from each event's own payload; do not join start to finish.
- `arms` always has exactly two rows, baseline then candidate, even with zero trials.
  Trials whose `arm` is neither are ignored.
- `tools` covers the union of tool names seen in any `tool_start` or any uninjected-failure
  `tool_finish`, in either arm, sorted by tool name (plain string order), baseline row
  then candidate row for each tool. A tool only one arm used still gets both rows. A tool
  seen only in successful or injected finishes with no start gets no row.
- "Not started" is per tool. There is no aggregate "trials that called no tool" count.
- "Passed" means `trial.outcome is Outcome.PASS`.
- All trials given are counted, complete rounds or not, exactly as `fault_accounting`
  treats its input. Pure function, no I/O, no subprocess, deterministic.

Markdown (`tool_outcomes_markdown`), returned as lines beginning with an empty line like
`fault_markdown`. The heading and the paragraph are fixed text, exactly:

```
## Tool outcomes (descriptive)

Counts of recorded tool attempts. An uninjected failure is a recorded tool_finish that failed with no injection marker; the record does not show why it failed, and an earlier injected fault can be the cause. A tool with no recorded start in a trial may simply not be needed by that task; compare the two arms. Retries by middleware count as attempts. Counts are descriptive and decide nothing.

| Arm | Trials | Trials with an uninjected failure | Then passed | Then not passed |
|---|---:|---:|---:|---:|
| baseline | ... |
| candidate | ... |

| Tool | Arm | Trials | Started in | Not started in | Starts | Uninjected failures | Trials with one |
|---|---|---:|---:|---:|---:|---:|---:|
| `lookup_order` | baseline | ... |
```

Tool names are shown as code spans. The existing `_cell` does **not** escape backticks and
must not be changed (v1 bytes depend on it): write a formatter local to this section that
applies `_cell` and renders a name containing backticks as a valid code span (longer
backtick fence with padding, per CommonMark). If `tools` is empty, the second table is
replaced by the single line `No tool starts recorded.` (the arm table is still shown).

Wiring:

- `render_suite_json`: new key `"tool_outcomes"` holding the `ToolOutcomes` dict.
- `render_suite_markdown`: the section goes immediately after fault accounting and before
  the prior-runs heading.
- `render_suite_html`: a section built the same way as `_faults()`, same heading text,
  same intro sentence, the two tables with the same columns, placed between `_faults(...)`
  and `_details(...)`. Tool names appear in table cells only, never in a heading.
- **v1 output must not change at all**: `arci report` on an `arci/0.5` single-task store
  gives byte-identical Markdown, JSON, JUnit and HTML to 2.0.0. Markdown and JUnit are
  pinned at `tests/unit/report/test_report_pass_k_cli.py:43` and HTML at
  `tests/unit/html_report/test_html_report.py:197`; **add the missing v1 JSON byte pin**
  (path `src/arci/cli.py:702`), computed before you change any code.
- `tool_outcomes` is a top-level key of the suite JSON report, never inside `decision`.
- Stored records do not change. A store written by 2.0.0 renders with the new section.

Also: regenerate the suite Markdown and HTML goldens and
`docs/results/sample-suite-report.html` (footer stays `ARCI 2.0.0`; the orchestrator bumps
the version later and regenerates). Do not touch `docs/results/order-desk-study.html`. Add
one short paragraph to `docs/recipes/langchain.md` beside the fault-accounting text saying
what the new section shows.

Your own tests: at least the definitions above one by one, the empty case, a malformed
payload (`tool` not a string, `ok` not a bool, `injected_by` a number), a marked failure excluded, a retry counted twice, escaping of a tool name containing `|` and
a backtick, HTML escaping of a tool name containing `<script>`, and JSON/Markdown/HTML
agreeing on the same numbers for one fixture.

## Acceptance (worktree root)

```sh
.venv/bin/pytest tests/unit/suite_report tests/unit/html_report tests/unit/report tests/unit/reports tests/unit/suite_cli -q
LANGSMITH_TRACING=false .venv/bin/pytest -q
.venv/bin/ruff format --check . && .venv/bin/ruff check . && .venv/bin/basedpyright
shasum -a 256 -c FROZEN.sha256
```

Known: about 65 tests fail inside the sandbox for socket and `ps` denials; name any other
failure. Report under 30 lines: files changed, last lines of each command, anything you
could not do, risks.
