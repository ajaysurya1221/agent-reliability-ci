# L6 (with L5): text and Markdown reports, the command line, and the packaged example

Read `/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/tasks/L-CONTRACT.md` and follow
its rules. Behaviour: record 0016 in its current text, sections "Fixed texts", "Command line
and layout", decisions 5 to 7, and "Record model"; the statistics contract for everything
the record means. `rank_test.py`, the readers, `schema.py`, `measures.py` and `decide.py`
exist; use them, do not change their behaviour (a bug you find there: stop and report it).

## You own

- `src/arci/logs/report.py`, `src/arci/logs/cli.py`, `src/arci/logs/example/` (data and a
  small loader), `bench/make_log_example.py`
- `src/arci/cli.py`: only the dispatch of `logs` and its one-line help entry, done the way
  `verdict` is dispatched there
- `tests/unit/logs/test_report.py`, `tests/unit/logs/test_cli.py`,
  `tests/unit/logs/test_example.py`, `tests/unit/logs/snapshots/`
- `pyproject.toml` is frozen: do not touch it. If packaging the example data needs a change
  there, stop and say exactly which line; the orchestrator makes it at the re-freeze.

## Build

1. `report.py`: `render_text(decision) -> str` and `render_markdown(decision) -> str`, pure
   functions of the sealed record, producing exactly the fixed texts and the layout of the
   record: every sentence character for character, numbers rendered by the record's
   rendering rules, columns aligned with spaces, lines at most 100 characters, names passed
   through `arci.outcome_report.escape_terminal`. No text is produced from anything but the
   record.
2. `cli.py`: `run(argv, *, now=None, env=None, home=None, out=None, err=None) -> int` and
   `main(argv=None) -> int`, with the options of the record. It resolves roots with
   `discover`, lists files, reads each requested tool, builds the table, decides, seals the
   `LogsDecision`, writes the requested files, prints the text, returns the exit code.
   - Usage errors and write failures: one fixed line on `err`, exit 3, as the record says.
     Use an `argparse.ArgumentParser` subclass whose `error` does not print the offending
     value.
   - No exception may escape `run`; an unexpected one becomes exit 3 with the fixed line
     `Internal error.` on `err` and nothing else (no traceback, no message).
   - `--json`, `--markdown`, `--html` write UTF-8 files; `--html` calls
     `arci.logs.html.render_html` if that module exists and otherwise is a usage error with
     the fixed line `--html is not available in this build.` (another task adds the module).
   - It never prints a path, a directory name or an environment value.
3. The packaged example: `bench/make_log_example.py` is a seeded generator that writes a
   small synthetic history for both tools into `src/arci/logs/example/` (56 days, about 24
   main-thread responses a day, a few sub-agent responses, a few edit results; Claude Code
   with a planted 45% drop in reasoning counts over the last 14 days; Codex unchanged), plus
   `now.txt` with the fixed instant. Keep the data small (aim under 400 KB in total; write
   only the fields the readers use, plus a little harmless filler to exercise unknown
   keys). Choose the seed so that the packaged example gives REAL DROP for Claude Code and
   NO DROP for Codex, and say in the generator's docstring that the seed was chosen for
   that. Model ids in the example are `claude-example-1`-style ids that the grammar rejects
   on purpose, so they render as `model-1`; efforts are `high`.
   `python bench/make_log_example.py --check` exits 0 when the packaged files equal a fresh
   generation byte for byte.
4. `src/arci/cli.py`: `arci logs ...` reaches `arci.logs.cli.main` without importing
   anything from `arci.logs` for other commands (`arci --help` must not import it).

## Tests

- Snapshots under `tests/unit/logs/snapshots/` for the text and Markdown of: the packaged
  example; a NO DROP; each CANNOT TELL reason; a tool ERROR beside a tool result; both tools
  `no_logs`; `--utc`. A test fails with a readable diff when a snapshot differs.
- Every fixed text of the record appears in `report.py` exactly once as a constant, and a
  test compares those constants with the text of the record file
  (`/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/logs/0016-logs-draft.md`, skipped
  when that file is absent).
- `run` with synthetic logs (use `tests/unit/logs/synth_logs.py`): exit codes for each
  result; `--tool` values; `--since` good, malformed, too early, after the newest day;
  `--model` and `--effort` by rendered name; `--project`; output files written and equal to
  the renderers' output; an unwritable output path; an unknown option; nothing on `err` in
  a normal run; no canary token, path or directory name in any stream or file.
- `arci logs --example` through `arci.cli` gives exit 1, the snapshot text, and F13 on line 2.
- `bench/make_log_example.py --check` passes.
- Importing `arci.cli` does not import `arci.logs` (check `sys.modules` in a subprocess-free
  way: import in a fresh interpreter is not allowed here, so assert on the module's source
  that the import is inside the dispatch branch).

## Done when

`.venv/bin/pytest tests/unit/logs tests/unit/cli -q` passes; the whole suite
`.venv/bin/pytest -q` passes; ruff format, ruff check and basedpyright are clean on your
files; `shasum -a 256 -c FROZEN.sha256` still passes.
