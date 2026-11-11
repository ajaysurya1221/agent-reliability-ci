# TASK P2b: suite support in `report`, `triage`, `diff` and `plan`; fault accounting

Worktree `/Users/ajay/Developer/.arci-worktrees/wt-v2-reports` (branch `v2/reports`, cut
from `v2/integration`; LangChain is installed in `.venv`). Work only there. No
state-changing git, no network, no new dependency. `FROZEN.sha256` has 64 entries; do not
touch frozen files. v1 behaviour, output and tests stay byte-identical.

Read: `AGENTS.md`; `docs/AGENT_SEMANTICS.md` (suite section at the end);
`docs/STATISTICS_SUITE.md`; `docs/design/0011-suite-gate.md` item 13; `src/arci/report.py`,
`triage.py`, `diff.py`, `planning.py`, `cli.py`, `suite_runner.py`, `suite_storage.py`,
`suite_gate.py`, `suite_stats.py`; `docs/design/0010-v1.0.0-triage-and-trace-check.md`.

You own: `src/arci/report.py`, `triage.py`, `diff.py`, `planning.py`, `cli.py` (suite
dispatch for these four commands only), new `src/arci/suite_report.py` if cleaner, and
tests under `tests/unit/suite_cli/`, `tests/unit/suite_report/`, `tests/unit/planning/`.

## Build

1. **`arci report <suite run>`** (Markdown and JSON, the formats v1 has; JUnit stays
   refused with its one line): verdict and exit code; the rule (alpha, delta, stakes,
   threshold, rounds, seed mode, tolerance); stopping round and pairs; cumulative counts;
   both wealths against the threshold per round; errored pairs against the tolerance; the
   guarantee sentence for the sealed seed mode, verbatim from `docs/STATISTICS_SUITE.md`;
   the per-cell table (task, condition, pairs, baseline and candidate successes, minus,
   zero, plus, errored, hard violations) labelled as descriptive, with the sentence that a
   suite-mean PASS can hide a regression in one cell; `prior_runs`. Deterministic bytes for
   a given store.
2. **Fault accounting, v1 and suite reports alike**: for each condition, how many declared
   faults fired in how many trials, counted from recorded `tool_finish` events with
   `injected_by`, per arm; a declared fault that never fired in an arm is flagged in the
   report ("declared, never fired"). For v1 reports this adds a section; existing v1 report
   tests may need their golden text extended, which is allowed only for that added
   section and nothing else. JSON reports gain one new key; no existing key changes.
3. **`arci triage <suite run>`**: v1's paired failure triage for a suite trial; the partner
   of a trial is the other arm of the same pair id from the suite schedule. Read-only, as
   ADR 0010 requires.
4. **`arci diff`** between two trials of a suite run (and of two suite runs), as v1.
5. **`arci plan <suite descriptor>`**: computes exactly, for the registered rule, the
   earliest PASS and BLOCK rounds and the never-differs PASS round; and, **for a stated
   model**, exact verdict probabilities and expected sessions, labelled as a projection
   under that model: either per-cell laws given in a file, or the homogeneous model from
   three inputs (`--baseline-rate`, `--candidate-rate`, `--agreement`), refusing inputs
   that do not define a valid joint law. Grids too large to enumerate in reasonable time
   print that and give the floors only. Prints warnings from `check_suite_plan`.
6. `minimize`, `bundle`, `replay` and `trace-check` on suite stores keep their one-line
   refusal.

Tests: every printed value compared with an independent computation in the test; golden
outputs for one PASS, one BLOCK, one INCONCLUSIVE and one ERROR store built from synthetic
envelopes (no processes), plus one end-to-end run on the offline fixture; fault accounting
on a store where one declared fault never fires; `arci plan` against
`operating_characteristics`; v1 report, triage, diff and plan tests green and unchanged
apart from the added fault-accounting section.

Acceptance (worktree root):

```sh
.venv/bin/pytest tests/unit/suite_cli tests/unit/suite_report tests/unit/report tests/unit/reports tests/unit/triage tests/unit/diff tests/unit/planning tests/unit/cli -q
LANGSMITH_TRACING=false .venv/bin/pytest -q
.venv/bin/ruff format --check . && .venv/bin/ruff check . && .venv/bin/basedpyright
shasum -a 256 -c FROZEN.sha256
```

Sandbox note as before. Stop and report if a frozen file or acceptance test blocks you
(for example a frozen v1 acceptance test that pins report text: then keep v1 report output
unchanged and put fault accounting behind the suite report and a new `--faults` flag for
v1, and say so). Report under 60 lines.
