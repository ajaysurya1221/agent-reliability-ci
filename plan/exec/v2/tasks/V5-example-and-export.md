# V5: the packaged example and the store exporter (ARCI v2.2.0, task T7)

You are the implementer. Work only in `/Users/ajay/Developer/.arci-worktrees/wt-v2.2`
(branch `v2.2/integration`). Read `AGENTS.md` there first and obey its hard rules: never edit a
file listed in `FROZEN.sha256`; no git commands that change state; no network; no new
dependencies; use `.venv/bin/python`, `.venv/bin/pytest`, `.venv/bin/ruff`,
`.venv/bin/basedpyright` directly.

## Read first

- `docs/design/0015-imported-outcomes.md`: Decision item 10, "Command grammar", "Fixed text"
  (F14), and the appendix
- `/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/tasks/V3-CONTRACT.md`
- `src/arci/outcomes.py`, `src/arci/outcome_report.py`, the `verdict` handler in `src/arci/cli.py`
  (written in the previous task; `--example` is a placeholder there)
- how a suite store is loaded: `load_suite_run` and its use in `src/arci/cli.py`
- the two committed study stores under `docs/results/order-desk-study/run-1/` and `run-2/`, and
  `tests/unit/docs/test_order_desk_stores.py`

## Files you own

- new: `bench/export_outcomes.py`
- new: `src/arci/demo/outcomes/` (package data: `__init__.py` if the package layout needs it,
  `order-desk-run-1/rule.yaml`, `baseline.csv`, `candidate.csv`)
- new: `examples/outcomes/order-desk/` (`README.md`, `run-1/` and `run-2/`, each with
  `rule.yaml`, `baseline.csv`, `candidate.csv`)
- changed: `src/arci/cli.py` (only the `--example` branch of `verdict`), and `src/arci/outcomes.py`
  or `src/arci/outcome_report.py` only as far as the example needs (F14 as a notice)
- new tests: `tests/unit/outcomes/test_example.py`, `tests/unit/outcomes/test_export.py`

Touch nothing else.

## What to build

1. `bench/export_outcomes.py`, run as `python -m bench.export_outcomes STORE OUT_DIR`:
   loads a suite store with the public loader, and writes `OUT_DIR/baseline.csv`,
   `OUT_DIR/candidate.csv` (columns `task_id,outcome,round`, rows sorted by round then task id)
   and `OUT_DIR/rule.yaml`.
   - The cell id is `<task_id>/<condition_id>`.
   - `outcome` is `pass`, `fail` or `error` from the trial's recorded outcome (the suite's
     `Outcome.PASS`, the non-passing non-error outcomes, `Outcome.ERROR`; read
     `src/arci/suite_gate.py` `_Counts.add` to see exactly how the suite classifies, and follow it).
   - Only complete rounds that the suite decision evaluated are exported (rounds 1 to the
     store's last evaluated round).
   - `rule.yaml` is a complete `arci-outcomes/1` rule: `suite_id` the store's suite id,
     `alpha`, `margin` (the manifest's `delta`), `stakes`, `max_rounds`, `max_errored_pairs`
     copied from the suite manifest, `tasks` the cell ids, and `fixed_before_runs: false`,
     because this rule file is written after the outcomes exist. Start the file with a YAML
     comment of at most three lines saying where it came from and why the declaration is false.
   - It prints one line per file written and returns 0; any failure is a single `error:` line
     and exit 3, no traceback.
2. Run the exporter on both committed study stores and commit the results under
   `examples/outcomes/order-desk/run-1/` and `run-2/`. Copy run 1's three files to
   `src/arci/demo/outcomes/order-desk-run-1/` byte for byte. `examples/outcomes/order-desk/README.md`
   (at most 30 lines, plain): what the files are, the exact commands to regenerate them and to
   get the two verdicts, the expected first two lines of each output, and one sentence that
   these verdicts are descriptive because the outcomes rule was written afterwards while the
   study's own suite rule was registered before each run (link `docs/results/order-desk-study.md`).
3. `arci verdict --example`: reads the packaged rule and files through `importlib.resources`
   (it must work from an installed wheel, not only from a source tree), runs the ordinary
   verdict path on them, and adds F14 to `notices`. `--json` and `--markdown` work as for any
   verdict. Expected: exit 1, line 1 is F1, line 2 is `VERDICT: BLOCK (exit 1)`, the reason is
   F16, round 1 counts are minus 26, zero 70, plus 0, errored 0, PASS wealth `1.92124e-03`,
   BLOCK wealth `1.56229e+02`, and F10 does not print (run 1 has one round).
4. Tests:
   - `test_export.py`: exporting each committed store and running `arci.cli.main(["verdict", ...])`
     on the result gives the same verdict, stopping round, per-round counts and wealth strings as
     the store's own `decision.json` (run 1 BLOCK at round 1; run 2 INCONCLUSIVE after 5 rounds
     with PASS wealth `1.97265e-02` and BLOCK wealth `4.87762e-01`); the committed example files
     equal a fresh export byte for byte; the packaged copy equals `examples/.../run-1/`.
   - `test_example.py`: the expectations in item 3; the example works when the current
     directory is an empty temporary directory; F14 is in `notices` of the JSON artifact.

## Acceptance criteria

- `git status --short` shows only the files listed under "Files you own".
- `.venv/bin/pytest tests/unit/outcomes tests/unit/docs -q` passes.
- A wheel built from the tree contains the packaged example: run
  `.venv/bin/python -m zipfile -l` on a wheel if you can build one offline with the tools
  present; if you cannot build offline, show from `pyproject.toml` why the files are included
  and say that you could not build.
- `.venv/bin/ruff format --check`, `.venv/bin/ruff check`, `.venv/bin/basedpyright` clean on your
  files (strict).
- `shasum -a 256 -c FROZEN.sha256` reports every file OK.

## When something does not match

If an exported store does not reproduce its own stored decision, do not adjust the exporter
until it does: stop and report the difference with the numbers.

## Final message

Files changed; test command and last lines; the first two output lines of `arci verdict
--example`; sizes of the committed example files; anything not done or unclear; risks.
