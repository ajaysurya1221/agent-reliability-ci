# R3b: fixes after the second review of 2.4.0 (the review of the R3a fixes)

Read `AGENTS.md` in the worktree `/Users/ajay/Developer/.arci-worktrees/wt-v2-logs`
(branch `v2/logs2`). Work only there. Change no git state. No network, do not call `uv`.
Never open anything under `~/.claude` or `~/.codex`, and search no memory registry. Use
only synthetic data. Plain words, short sentences, no sales wording, no em dashes. You are
the only agent editing the worktree.

The review is
`/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/reviews/R3b-logs2-fixes-review-workflow.json`
(four reviewers, each finding reproduced by a second agent: 11 findings, all confirmed or
partly confirmed; one medium, ten low). The reviewers' and verifiers' scripts are under
`/private/tmp/claude-501/-Users-ajay-Developer-agent-reliability-ci/39ca2335-7a5a-47d9-a374-69d92a47e1d0/scratchpad/review24b/`;
you may read them. Every item below was decided by the orchestrator.

Record 0017 was amended first: read the new paragraph "Whose temporary files the cleanup
may remove" in the section on the kept day table. Do not edit `docs/design/`,
`tests/acceptance/`, `FROZEN.sha256`, any version number, `bench/selfcheck_logs.py` or
`docs/results/logs-selfcheck.md` (the self-check is not re-run in this task).

## Code (`src/arci/logs/cli.py`)

1. **Temporary file names** (finding write-path-1, medium). In `_write_outputs`, only the
   table's staged file and the table's backup are named with the prefix `.realornoise-`.
   The staged file and the backup of every other output are named with the prefix
   `.realornoise.out-`, in whatever directory they are. The cleanup after a successful
   table write is unchanged: it removes regular files in the table directory whose names
   begin with `.realornoise-`. Result: a `--keep` run never removes a file another run is
   using for its other outputs.
2. **A waiting run and a removed directory** (finding write-path-2, low). After the lock on
   the table directory is taken, compare the locked descriptor with the path
   (`os.fstat` against `os.stat`: device and inode). If the path is gone or is another
   directory, release, create the directory again as the code does for a missing one
   (mode 0700, recorded so that a failed write removes it again), lock that one, and
   check again; at most 8 rounds, then treat it as a failed write. Where no lock is
   available nothing changes.

## Tests (each must fail when the rule it holds is removed; check by a temporary edit and say so)

3. **Race with another run's outputs** (`tests/unit/logs/test_logs2.py`): a run without
   `--keep` writes `--json` and `--markdown` into a table directory where both files
   already exist, and is paused before its second move; a `--keep-dir` run on that
   directory then completes; the first run then finishes with its own exit code (not 3),
   both of its outputs are the new ones, and no temporary file of either prefix is left.
   The reviewer's `write-path/t6.py` shows the timing.
4. **Without a lock** (same file): with `fcntl.flock` patched to raise `OSError`, a
   `--keep` run whose staged table is removed by another run's cleanup before its move
   fails with the write error, exit 3, and leaves the stored table and every requested
   output byte for byte as they were.
5. **The lock is exclusive and held to the end** (finding tests-1): a second writer
   (thread or subprocess) cannot pass the lock while the first is paused between its
   re-read and its move; it proceeds only after the first has moved its table and removed
   leftovers; both writers' rows are in the table. The four mutations the verifier ran
   (`verify-tests/mut.py`: descriptor closed right after `flock`, `LOCK_SH`, lock released
   before the moves, lock released before the cleanup) must each fail a test.
6. **The removed directory** (item 2): the reviewer's `write-path/t10.py` case as a unit
   test: the waiting run succeeds and the table holds its rows.
7. **A table that turns unreadable between the two reads** (finding tests-5): the injected
   pause writes `{not json` to the table; after the `--keep` run the file is byte for byte
   unchanged.
8. **The injected-failure test for placeholders** (finding tests-2): record inside the
   patched function whether any target exists, and assert on that record after `cli.run`
   returns, so that removing the placeholder-unlink loop fails
   `test_failed_write_removes_new_targets` itself.
9. **Gates stay explicit** (findings self-check-1 and tests-3,
   `tests/unit/logs/test_selfcheck_quick.py`): a test that parses `bench/selfcheck_logs.py`
   with `ast` and finds no `Assert` node; and a test that runs the quick mode under
   `python -O` with one gate deliberately broken through a small wrapper (for example a
   patched `decide.decide_tool` or rank-test function) and expects a non-zero exit and a
   failed gate in the output.
10. **Figure provenance** (finding tests-4, `tests/unit/docs/test_logs_docs.py`): do not
    split a sentence at `;` inside parentheses, or take the seeds and the design from the
    whole sentence when a clause names none. The verifier's three edits
    (`verify-tests/t4.py`: seed 18112185 changed to 18112184; the design changed to
    "7 days after against 21 before"; both changed together) must each fail the test. Add
    them as a test on edited copies.
11. **The privacy audit-hook test** (`tests/unit/logs/privacy/test_audit_hook.py`): allow
    the new prefix only for outputs given, and the old prefix only in the table directory
    with `--keep`. Every existing check that no temporary file is left looks for both
    prefixes.

## Documents (each sentence must be true as written)

12. `README.md` (finding documents-1): the availability sentence pins the LangChain extra
    at `agent-reliability-ci[langchain]==2.4.0`. In
    `tests/unit/packaging/test_review_fixes.py::test_every_release_version_matches` the
    README pattern also matches a bracketed extra, so a stale pin there fails.
13. `README.md` (finding documents-2): the section "What it does not do" no longer lists
    stored history beyond log retention as missing. Say what is true: days are kept only
    with `--keep`, and only days captured while their files still existed.
14. `docs/STATISTICS_LOGS.md` (finding documents-3; a pinned file released for change; edit
    only these two sentences): the two gate descriptions copied from the self-check file
    (near lines 528 and 540) read as the results file now reads: each single-measure
    exact-margin cell gates both the tool's NO DROP and the moved measure's own no drop
    finding at `<= 566/20000`. Copy the sentence from `docs/results/logs-selfcheck.md`.
    If a doc test compares these sentences, make it hold them equal to the results file.
15. `docs/recipes/logs.md` and `docs/THREAT_MODEL_LOGS.md`: one or two sentences on the
    rule of item 1 (other outputs use their own temporary names and are never removed by
    the table's cleanup; without a lock an overlapping `--keep` run can fail with the
    write error and leaves everything as it was). `CHANGELOG.md`: the fixes of this task
    under Fixed, in the file's style.

## Done when

- `.venv/bin/pytest -o addopts='' -q tests/unit/logs tests/unit/docs tests/unit/plugin tests/unit/packaging`
  passes with no failure.
- `.venv/bin/pytest -o addopts='' -q tests/acceptance/test_logs.py` passes (225 cases).
- `.venv/bin/ruff format --check .`, `.venv/bin/ruff check .`, `.venv/bin/basedpyright` clean.
- `.venv/bin/python bench/make_log_example.py --check` passes.
- `shasum -a 256 -c FROZEN.sha256` reports only the five released files.

## Final message

One line per numbered item. For items 3 to 10: the temporary edit you made to check that
the test fails, and that it failed. The commands and their last lines. Anything you could
not do. No long logs.
