# R3c: fixes after the final check of the write path (2.4.0)

Read `AGENTS.md` in the worktree `/Users/ajay/Developer/.arci-worktrees/wt-v2-logs`
(branch `v2/logs2`). Work only there. Change no git state. No network, do not call `uv`.
Never open anything under `~/.claude` or `~/.codex`, and search no memory registry. Use
only synthetic data. Plain words, short sentences, no sales wording, no em dashes. You are
the only agent editing the worktree.

The check is
`/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/reviews/R3c-logs2-final-check-workflow.json`
(three checkers, each finding reproduced by a second agent: 12 findings, all confirmed;
the two medium ones each found twice). Scripts are under
`/private/tmp/claude-501/-Users-ajay-Developer-agent-reliability-ci/39ca2335-7a5a-47d9-a374-69d92a47e1d0/scratchpad/review24c/`;
you may read them. Every item below was decided by the orchestrator.

Record 0017 was amended first: read the new paragraph "The order at the end of a run, and a
directory that cannot be locked" in the section on the kept day table. Do not edit
`docs/design/`, `tests/acceptance/`, `FROZEN.sha256`, any version number,
`bench/selfcheck_logs.py`, `docs/results/` or `docs/STATISTICS_LOGS.md`.

## Code (`src/arci/logs/cli.py`, functions `_directory_lock` and `_write_outputs` only)

Keep the change small. Do not restructure what is not named here.

1. **Remove created directories before the lock is released** (findings races-1, logic-1).
   In the `finally` block of `_write_outputs`, the removal of the directories this run
   created (when the write did not succeed) happens before `locks.close()`.
2. **Remove only what this run created, and go on past a missing one** (findings races-3,
   races-4). When a directory is created, record its device and inode with its path, once
   per path (a path created again in a later round replaces its earlier entry; no
   duplicates). At rollback, deepest first: a path that no longer exists is skipped; a
   path that exists with another identity stops the rollback; a path with the recorded
   identity is removed, and a failure to remove it (not empty) stops the rollback.
3. **A directory that cannot be opened for the lock** (findings races-2, logic-3). In
   `_directory_lock`, separate the open from the lock call:
   - `os.open` raises `FileNotFoundError` or `NotADirectoryError`: yield "not current", so
     the caller's loop runs another round (it creates the directory again);
   - `os.open` raises any other `OSError`: the write fails (raise `OSError`);
   - `fcntl` cannot be imported, or `fcntl.flock` raises `OSError`: go on without a lock,
     as now (close the descriptor).
   After 8 rounds the write fails, as now.
4. **The cleanup skips this run's outputs** (finding logic-2). After a successful table
   write, the cleanup of `.realornoise-` files in the table directory does not remove any
   path that is a target of this run's outputs.

## Tests (`tests/unit/logs/test_logs2.py`; each must fail when its rule is removed: check by a temporary edit, restore it, and say so)

5. Item 1: run A creates the table directory and then fails (for example `--json` into a
   missing directory); run B waits for the lock. With a hook that lets A's directory
   removal and lock release run in the order the code gives them, B succeeds, the
   directory exists and the table holds B's rows. The checker's
   `races/s1_unlock_before_rmdir.py` shows the timing. Moving the removal back below
   `locks.close()` must fail this test.
6. Item 2: (a) the table directory this run created is removed from outside between the
   lock and the check, the run creates it again, the write then fails: the directory and
   the parent this run created are both gone afterwards; (b) the directory is removed and
   created again by another process (another inode), the run locks that one, the write
   then fails: that directory is still there.
7. Item 3: (a) the directory is missing at the open (removed after the existence check):
   the run creates it again, takes the lock and succeeds, and `flock` was called (the
   checker's `races/s5_open_fails_unlocked.py`); (b) a table directory with mode `0o300`
   and `--keep`: exit 3, the write error, nothing written (skip where the test runs as a
   user for whom that mode does not block the open); (c) `flock` raising `OSError` still
   goes on without a lock (the existing test); (d) the open missing on every round: exit 3
   after exactly 8 rounds.
8. Item 4: `--keep` with `--json` at `<table directory>/.realornoise-report.json`: the run
   ends with its own exit code and the JSON file exists and is valid.
9. Finding tests-docs-1: an output that lives in the table directory during a `--keep`
   run is staged with the `.realornoise.out-` prefix (the mutation "outputs in the table
   directory get the table prefix" must fail a test).
10. Finding tests-docs-2: the identity check compares device and inode (a test in which
    `os.stat` reports the same inode on another device is "not current"); the 8-round
    limit (covered by 7d).
11. Finding tests-docs-4: `test_unlocked_cleanup_failure_rolls_back_all_outputs` also
    runs with requested outputs that did not exist before, and asserts that none of them
    exists afterwards (the mutation that turns the rollback `target.unlink()` into `pass`
    must fail it).
12. Finding tests-docs-5 (`tests/unit/docs/test_logs_docs.py`): the provenance test
    checks at least one figure in every document it covers (require `checked > 0` per
    document) and matches the recipe's form `(n/N, Wilson 95% interval [lo, hi], seed S)`
    and the design mention near line 663 of `docs/STATISTICS_LOGS.md`. The verifier's
    three edits (`verify-tests-docs/docmut.py`) must each fail the test; add them as a
    test on edited copies. Do not edit the documents' figures.

## Documents

13. `docs/recipes/logs.md` and `docs/THREAT_MODEL_LOGS.md`: one or two sentences: a table
    directory that exists but cannot be opened for the lock is a write error; a run that
    fails removes the directories it created before it releases the lock. `CHANGELOG.md`:
    add these fixes to the existing Fixed bullet for the write path, in the file's style.

## Done when

- `.venv/bin/pytest -o addopts='' -q tests/unit/logs tests/unit/docs tests/unit/plugin tests/unit/packaging`
  passes with no failure.
- `.venv/bin/pytest -o addopts='' -q tests/acceptance/test_logs.py` passes (225 cases). If
  a case fails because of item 3, do not change the code to pass it: name the case and
  the rule it meets.
- The new and changed tests in `tests/unit/logs/test_logs2.py` pass 10 times in a row.
- `.venv/bin/ruff format --check .`, `.venv/bin/ruff check .`, `.venv/bin/basedpyright` clean.
- `.venv/bin/python bench/make_log_example.py --check` passes.
- `shasum -a 256 -c FROZEN.sha256` reports only the five released files.

## Final message

One line per numbered item. For items 5 to 12: the temporary edit and that the test
failed. The commands and their last lines. Anything you could not do. No long logs.
