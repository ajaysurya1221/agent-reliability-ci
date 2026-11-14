# V6: reconcile the implementation with the blind acceptance tests (ARCI v2.2.0)

You are the implementer. Work only in `/Users/ajay/Developer/.arci-worktrees/wt-v2.2`
(branch `v2.2/integration`). `AGENTS.md` rules as before: no frozen file edited, no git
commands that change state, no network, no new dependencies, `.venv/bin/*` directly.

## Context

Acceptance tests written from the specification by someone who could not see your code are now
in `tests/acceptance/test_outcomes.py` and `tests/acceptance/outcomes_helpers.py` (123 tests;
120 pass). Do NOT edit those two files, and do not edit anything under `docs/`: the
orchestrator owns them and is correcting two test slips and clarifying the record at the same
time. Rulings on the points where the record was unclear:

1. **An input file with no records is E6, in every format.** An empty or whitespace-only file, a
   CSV with a header and no rows, a JSONL file with no object, a JUnit file with no test case,
   and an Inspect log with no samples are all `unreadable or unsupported input: <path>`. Today an
   empty unlabelled file is treated as a positional round whose outcomes are all missing; that
   reading is withdrawn. (A file that has records but lacks some registered tasks is unchanged:
   those are missing outcomes.)
2. **The fixed empty template's `statements` holds F2 alone**, whether or not inputs had been
   read, and whether the rule declares true or false. F4 never appears in a pre-inference ERROR.
3. **Terminal report order and length** (stdout only; Markdown and JSON keep every row):
   - order: F1 when it applies; the verdict line; the reasons; the notices (W1, F12, F7, F8 or
     F9, F10, F14, in that order when they apply); the rule digest; the per-round table; the
     errored-pair label (F11) with its count; the task table; the statements other than F1.
   - the terminal task table lists only tasks whose `minus` or `errored` count is above zero,
     sorted by `minus` descending, then `errored` descending, then task id, and at most 10 rows.
     Its heading is `Tasks where the candidate did worse or a pair errored, through round <k>`.
     When rows are left out, one line follows: `<n> more such tasks are in the Markdown and JSON
     outputs`. When no task qualifies, print the heading and `none`.
   - these two strings are layout, not statistical statements; put them with the other
     constants and do not add them to `statements` or `notices`.
4. Keep everything else as it is, including: `rounds_registered` 0 in the fixed empty template;
   E26 raised where it is today; reasons rendered as F15 and F16 at top level and in each history
   entry when the declaration is false.

## Files you own

`src/arci/outcomes.py`, `src/arci/outcome_report.py`, `src/arci/importers/*.py`,
`src/arci/cli.py` (verdict commands only), tests under `tests/unit/outcomes/` (not `real/`).

## Acceptance criteria

- `.venv/bin/pytest tests/acceptance/test_outcomes.py tests/unit/outcomes tests/unit/docs -q`:
  every test passes except, possibly, these two acceptance tests, whose expectations the
  orchestrator is correcting; say whether each passes for you:
  `test_missing_outcomes_are_errored_pairs_through_the_tolerance_then_error` and
  `test_pytest_repeat_suffixes_stay_literal_task_ids`.
- New unit tests for rulings 1 (one per format), 2 and 3 (order of sections; 10-row cap with
  the "more such tasks" line; `none`).
- `arci verdict --example` output still begins with F1 then `VERDICT: BLOCK (exit 1)`.
- `.venv/bin/ruff format --check`, `.venv/bin/ruff check`, `.venv/bin/basedpyright` clean;
  `shasum -a 256 -c FROZEN.sha256` all OK; `git status --short` shows only files you own (plus
  the orchestrator's edits under `docs/` and `tests/acceptance/`, which you leave alone).

## Final message

Files changed; test command and last lines; the first 14 lines of `arci verdict --example`;
anything unclear; risks.
