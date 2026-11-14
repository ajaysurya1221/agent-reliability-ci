# V3: imported outcomes, core (ARCI v2.2.0, tasks T3, T4, T5, T6)

You are the implementer. Work only in `/Users/ajay/Developer/.arci-worktrees/wt-v2.2`
(branch `v2.2/integration`). Read `AGENTS.md` there first and obey its hard rules: never edit a
file listed in `FROZEN.sha256`; no git commands that change state; no network; no new
dependencies (runtime code uses only the stdlib, `pydantic`, `pyyaml`); use `.venv/bin/python`,
`.venv/bin/pytest`, `.venv/bin/ruff`, `.venv/bin/basedpyright` directly.

## Read first, in full

1. `docs/design/0015-imported-outcomes.md` (the specification; every rule, tag and fixed text)
2. `docs/STATISTICS_OUTCOMES.md`
3. `/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/tasks/V3-CONTRACT.md` (entry point,
   where text goes, statements and notices, Python names)
4. `src/arci/suite_gate.py` (`walk_rounds`, `RoundIncrement`, `RoundLook`), `src/arci/suite_stats.py`,
   `src/arci/suite_schema.py`, `src/arci/schema.py` (`Sealed`, `Verdict`, `EXIT_CODES`),
   `src/arci/hashing.py`, and how `src/arci/cli.py` registers and dispatches a command
5. `tests/unit/outcomes/real/README.md` and the Inspect JSON and pytest XML files beside it

## Files you own

- new: `src/arci/outcome_schema.py`, `src/arci/outcomes.py`, `src/arci/outcome_report.py`,
  `src/arci/importers/__init__.py`, `src/arci/importers/junit.py`,
  `src/arci/importers/inspect_log.py`
- changed: `src/arci/cli.py` (add the `verdict` and `verdict-rule` commands; change nothing
  about any existing command, its help text or its output)
- new tests under `tests/unit/outcomes/` (not under `tests/unit/outcomes/real/`, which is
  fixtures; do not edit those)

Touch nothing else. In particular do not create `tests/acceptance/test_outcomes*.py`: the
acceptance tests are being written by someone who cannot see your code.

## What to build

Everything the record puts in 2.2.0 except the packaged example (`arci verdict --example`
must be accepted by the parser and return exit 3 with the stderr line
`error: the packaged example is not installed`; a later task supplies the data and replaces
that), the second console command, and the documentation.

Specifically:

1. `outcome_schema.py`: the models of "Record models", pydantic, strict (`extra="forbid"`),
   `OutcomeDecision` sealed the way `SuiteDecision` is. Reuse `SuiteCounts`, `parse_rational`,
   `format_rational` and the `SuiteId` pattern by import.
2. `outcomes.py`: rule loading with duplicate-key and explicit-null refusal and the field order
   of the record; the rule digest; the CSV and JSONL readers; format dispatch by extension;
   the ordered validation list; per-round `outcomes_sha256`; inference only through
   `walk_rounds` with `candidate_hard_violations` always 0; the errored-pair rule for missing
   outcomes; counts through `last_round_evaluated` only; the `--previous` checks; the fixed empty
   template; F8/F9 computed exactly with `suite_stats` (the smallest number of further complete
   rounds of non-errored ties at which PASS crosses, inside `max_rounds`); `decide_outcomes`
   never raises.
3. `importers/junit.py` and `importers/inspect_log.py` as the record's "Formats" section
   defines them, stdlib only (`xml.etree.ElementTree`, `json`). Inspect: JSON form only.
4. `outcome_report.py`: terminal text and Markdown renderers obeying V3-CONTRACT "Where text
   goes". Every fixed string comes from one place in the code (a constants block), verbatim
   from the record's "Fixed text", so that a test can compare against the record.
5. `cli.py`: the two commands with the record's grammar, including E16 to E22, artifact
   writing in the order JSON then Markdown, and `verdict-rule` (reads ids with the same readers,
   writes a complete YAML rule with `fixed_before_runs: false`, prints F13).
6. Unit tests in `tests/unit/outcomes/`:
   - every fixed string in the code equals the record's text after whitespace normalisation
     (parse the record's "Fixed text" section in the test);
   - one test per error tag E1 to E29 that applies to this task, asserting the exact reason;
   - the validation order: for at least six pairs of simultaneous faults, the earlier one in
     the record's ordered list is the one reported;
   - kernel equality: export the trials of the packaged demo suite (`arci.demo.suite`; see how
     `tests/unit/suite/test_walk_rounds.py` builds its store) to neutral rows and check that
     `decide_outcomes` gives the same per-round counts, wealth strings, crossing flags and
     verdict as `decide_suite`, for a true and a false declaration;
   - Inspect and JUnit on the real fixtures: expected outcomes worked out in the test from the
     raw files with plain `json` / `ElementTree` code written independently of your importer;
   - `--previous`: accepted on an unchanged prefix, E23 to E28 each triggered;
   - rounds after the stop are validated (a fault there is ERROR) but change no count;
   - the rule digest is equal for two spellings of one rule and differs when
     `fixed_before_runs` differs; a round digest distinguishes a missing outcome from `error`.

## Acceptance criteria

- `git status --short` shows only the files listed under "Files you own".
- `.venv/bin/pytest tests/unit/outcomes tests/unit/suite tests/unit/cli tests/unit/suite_cli -q`
  passes. If your sandbox cannot run a test for reasons unrelated to your change (for example
  local socket binding), say exactly which and why; do not skip or edit it.
- `.venv/bin/python -c "import arci.cli"` and `.venv/bin/arci --help` import neither
  `arci.outcomes`, `arci.importers` nor `xml` at start-up (lazy import inside the command
  handlers, as the existing suite and adapter commands do). Show how you checked.
- Output of every existing command is unchanged: `.venv/bin/pytest tests/acceptance/test_cli.py
  tests/unit/suite_report tests/unit/report -q` passes with no existing test edited.
- `.venv/bin/ruff format --check`, `.venv/bin/ruff check`, `.venv/bin/basedpyright` clean on
  your files (strict; no `# pyright: ignore` unless unavoidable, each explained).
- `shasum -a 256 -c FROZEN.sha256` reports every file OK.

## When the record is unclear or wrong

Do not guess silently. Choose the reading that is most conservative statistically (ERROR over a
verdict, errored over observed), implement it, and list every such choice in your final message
with the passage quoted. If two passages of the record contradict each other, stop on that
point, implement neither, and report it.

## Final message

Files changed with line counts; the test commands and their last lines; the lazy-import check;
every choice made where the record was unclear; anything not done; risks. No long logs. Your
report is not acceptance evidence; the orchestrator re-runs everything.
