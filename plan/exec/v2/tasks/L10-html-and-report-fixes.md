# L10 (with L6b): the HTML page, and report changes after the acceptance tests' questions

Read `/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/tasks/L-CONTRACT.md` and follow
its rules. Record 0016 changed after you built the report: read "Fixed texts", "Command line
and layout", decision 6 and "Record model" again, in full, in their current text
(`/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/logs/0016-logs-draft.md`).
Another agent is writing `bench/selfcheck_logs.py` and `tests/unit/logs/privacy/` at the
same time; do not touch those.

## You own

`src/arci/logs/report.py`, `src/arci/logs/cli.py`, `src/arci/logs/html.py` (new),
`src/arci/html_base.py` (new), `src/arci/html_report.py`, `src/arci/logs/example/`,
`bench/make_log_example.py`, `src/arci/logs/measures.py` and `decide.py` and the readers only
for item 3 below, and the unit tests and snapshots of those files under `tests/unit/logs/`
(not `tests/acceptance/`).

## Part A: bring the report in line with the record

1. Notices F9 and F14 to F17 have new wording; a notice prints only when its count is at
   least 1. F8 is left out when no measure was tested.
2. Usage errors: exactly one fixed line on `err`, the sentence alone; an unknown option or a
   malformed value prints `Usage error. Run: realornoise --help`; nothing on `out`; no
   output file written; exit 3.
3. Check these against the record and fix where the code differs (add a unit test for
   each): `split_date` is set whenever the tool has a main-thread response, also for
   `no_usable_setting`; `lines` counts only the first line of a Codex file outside the
   project; `responses` counts responses kept; a tool result answering a call of a tool that
   is not a file-edit tool is counted nowhere, and `edits_unmatched` counts only results
   whose id matches no recorded tool call; unknown names are numbered among the unknown
   ones only; `--claude-dir` is the `projects` directory itself.
4. Long fixed sentences wrap at the last space at or before column 100.
5. The packaged example: every row of both tables must have enough days. Give every Claude
   Code day at least ten file-edit results (a small share failed, the same in both periods),
   give both tools some responses with a reasoning count of 0 (about 15%, the same in both
   periods), and give Codex a small share of responses at one repeated value in both
   periods. Keep the planted 45% drop in Claude Code reasoning counts and the results (REAL
   DROP for Claude Code, NO DROP for Codex); choose the seed for that and say so. Keep the
   data under 400 KB. Regenerate the snapshots.

## Part B: the HTML page

1. `src/arci/html_base.py`: move the shared CSS and the small helper functions out of
   `src/arci/html_report.py` unchanged (the block near its top that holds `_CSS` and the
   escaping and table helpers), and import them back into `html_report.py`. The existing
   HTML output of `arci report` must stay byte-identical: the existing tests and fixtures
   under `tests/` prove it; do not edit them.
2. `src/arci/logs/html.py`: `render_html(decision: LogsDecision) -> str`, one self-contained
   page: per tool the same information as the text output (scope, periods, result, reason,
   table, context counts, notices, digest), one strip chart per gating measure as inline
   SVG (one dot per usable day, x by date, y by value; a vertical line at the split; a
   horizontal line at each period's median; no chart for a measure with no usable day), then
   the limits text and the method line, and F13 for the example. No script, no external
   reference (no `http`, no `src=`, no `href=` to anything but in-page anchors), no value
   that is not in the record, every name escaped. Deterministic: the same record gives the
   same bytes.
3. `cli.py`: `--html FILE` writes that page.

## Tests

Update the snapshots and tests for Part A. For Part B: the page for the packaged example and
for a CANNOT TELL and an ERROR record (snapshots); no `<script`, no `http`, no `src=`;
every number shown is derivable from the record (walk the visible text for digits and
check each numeric token appears in the rendered text output or the record JSON); a name
with `<`, `&` and a control character is escaped; two renders are byte-identical; the
existing `tests/unit` HTML tests for `arci report` pass untouched.

## Done when

`.venv/bin/pytest -q` passes (the whole suite; the copy of the acceptance tests at
`tests/acceptance/test_logs.py`, if present, is expected to pass too, except tests that
still assert the old notice wording: list any that fail and why); ruff format, ruff check
and basedpyright are clean on your files; `python bench/make_log_example.py --check`
passes; `shasum -a 256 -c FROZEN.sha256` still passes.
