# R3d: the tool never removes a directory (2.4.0, after the last check)

Read `AGENTS.md` in the worktree `/Users/ajay/Developer/.arci-worktrees/wt-v2-logs`
(branch `v2/logs2`). Work only there. Change no git state. No network, do not call `uv`.
Never open anything under `~/.claude` or `~/.codex`, and search no memory registry. Use
only synthetic data. Plain words, short sentences, no sales wording, no em dashes. You are
the only agent editing the worktree. Do not run `ls` in a shell here (it is aliased to a
slow tool); use `/bin/ls` or Python.

## Why

Four rounds of review each found a new fault of one kind in `_write_outputs`: a failing
run removed a directory that another run was about to use. The last check
(`/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/reviews/R3d-logs2-last-check-workflow.json`;
scripts under
`/private/tmp/claude-501/-Users-ajay-Developer-agent-reliability-ci/39ca2335-7a5a-47d9-a374-69d92a47e1d0/scratchpad/review24d/`)
found it again with real processes (a `mkdir` under a parent that a failing run had just
removed: 3 of 360 runs), and found that the cleanup can remove a requested output whose
name begins with `.realornoise-`. The orchestrator decided to remove the machinery, not
to patch it again.

Record 0017 is already amended. Read, in `docs/design/0017-logs-2.md`: the paragraph
"Writing" (the Rollback sentence), the paragraph "Directories are never removed, and
reserved names", the new option bullet about reserved names under "New in 0017", and
acceptance items 33, 53, 65, 78 and 79. Do not edit `docs/design/`, `tests/acceptance/`,
`FROZEN.sha256`, any version number, `bench/selfcheck_logs.py`, `docs/results/` or
`docs/STATISTICS_LOGS.md`.

## Code (`src/arci/logs/cli.py`). This task deletes code. Add as little as possible.

1. **No directory is ever removed.** Delete the bookkeeping of created directories and
   the removal at the end of `_write_outputs`. The table directory is created, with any
   missing parents, before any file is staged: each directory this run creates gets mode
   0700; a `FileExistsError` for something that is a directory is fine (another run made
   it); the mode of an existing directory is not changed. On a failed write the directory
   stays, empty.
2. **The lock, without identity checks or rounds.** Delete the device and inode check and
   the 8-round loop. `_directory_lock` does exactly this: if `fcntl` cannot be imported,
   go on without a lock and do not open the directory; open the directory, and if that
   raises `OSError` the write fails; call `flock`, and if that raises `OSError` close the
   descriptor and go on without a lock; hold the lock until the moves and the cleanup are
   done; always close the descriptor.
3. **Reserved names.** In the option-only phase, beside the other malformed values: a
   `--json`, `--markdown` or `--html` path whose last path component, after
   `unicodedata.normalize("NFKC", name).casefold()`, begins with `.realornoise-` is a
   malformed value: the general usage line, exit 3, nothing read and nothing written.
4. **The cleanup** is the plain rule again: after a successful table write, while the
   lock is held, remove regular files in the table directory whose names begin with
   `.realornoise-`. Delete the test against `staged`; item 3 makes it unreachable.

## Tests

5. Delete the unit tests that held the deleted rules (the directory identity, the 8
   rounds, removal before the lock is released, removal of created directories, the
   cleanup skipping a requested output). List each deleted test by name in your final
   message with the rule it held.
6. Keep, and re-run, every test of: the lock being exclusive and held through the moves
   and the cleanup; `flock` raising `OSError`; a platform without the lock module; a table
   directory with mode `0o300` (write error); the two temporary prefixes; the race with
   another run's reports; rollback of files without a lock; a table that turns unreadable
   between the two reads; placeholders.
7. New in `tests/unit/logs/test_logs2.py`:
   - a failed `--keep` write (a `--json` target in a missing directory; a failed move;
     a staged table over the size limit) on a table directory that did not exist, two
     levels deep: afterwards the directory and its parent exist, are empty, have mode
     0700, and nothing else was created; a directory that existed before keeps its mode
     (`0o755`);
   - reserved names: for each of the three options, `.realornoise-x.json`,
     `.RealOrNoise-x.json` and a full-width spelling that NFKC folds to the prefix are
     refused with the general usage line, exit 3, and nothing is read or written (no
     table directory appears, no file is opened under the log directories: use the audit
     hook the privacy tests use, or a patched reader); `.realornoise.json`,
     `realornoise-report.json` and `x.realornoise-y.json` are accepted;
   - **real processes**: a test that starts 6 separate Python processes together (a
     barrier file or a start time) on a table directory that does not exist, two levels
     deep, each with its own model in synthetic logs, 2 of them made to fail (a `--json`
     target in a missing directory), repeated 5 times: every failing process exits 3 and
     changes nothing, every other process exits with its own code, the final table holds
     the rows of every process that did not fail, no temporary file of either prefix is
     left. The checker's `processes/s12.py`, `lib.py` and `child.py` show one way. Keep
     the whole test under about 20 seconds and skip it where `fcntl` is missing.
8. `tests/unit/logs/privacy/test_audit_hook.py`: adjust only what items 1 to 4 change
   (no `rmdir` is expected any more; an `rmdir` by the tool must now fail the test).
9. Check by temporary edits, restored afterwards, that a test fails for each of: the
   created directory is removed again on a failed write; a reserved name is accepted; the
   reserved-name comparison is case-sensitive; the lock is released before the cleanup.

## Documents (each sentence must be true as written)

10. `docs/recipes/logs.md`, `docs/THREAT_MODEL_LOGS.md`, `CHANGELOG.md`, and any other
    document that says a failed write removes directories, that a run checks the
    directory's identity or retries, or that the cleanup skips requested outputs (search
    for it): say what is now true. The tool never removes a directory; a table directory
    a run created stays, empty, when its write fails; output names that begin with
    `.realornoise-` are refused; a table directory that cannot be opened for the lock is
    a write error; the tool assumes no other program removes the table directory while a
    run uses it. In `CHANGELOG.md` rewrite the Fixed bullet for the write path so that it
    describes the final behaviour only, not the steps that were tried and removed.

## Done when

- `.venv/bin/pytest -o addopts='' -q tests/unit/logs tests/unit/docs tests/unit/plugin tests/unit/packaging`
  passes with no failure.
- `.venv/bin/pytest -o addopts='' -q tests/acceptance/test_logs.py`: cases that fail only
  because items 33, 53 and 65 of the record changed (they expected the directory to be
  removed) are expected; name each one. A separate agent updates that file from the
  record. Any other failure is yours to explain.
- The new and changed tests in `tests/unit/logs/test_logs2.py` pass 10 times in a row.
- `.venv/bin/ruff format --check .`, `.venv/bin/ruff check .`, `.venv/bin/basedpyright` clean.
- `.venv/bin/python bench/make_log_example.py --check` passes.
- `shasum -a 256 -c FROZEN.sha256` reports only the five released files.

## Final message

One line per numbered item; the number of lines `_directory_lock` and `_write_outputs`
have now and had before; the deleted tests; the temporary edits of item 9 and that each
failed a test; the acceptance cases that now fail and why; the commands and their last
lines; anything you could not do. No long logs.
