# R3e: small fixes after the check of the simpler write path (2.4.0)

Read `AGENTS.md` in the worktree `/Users/ajay/Developer/.arci-worktrees/wt-v2-logs`
(branch `v2/logs2`). Work only there. Change no git state. No network, do not call `uv`.
Never open anything under `~/.claude` or `~/.codex`, and search no memory registry. Use
only synthetic data. Plain words, short sentences, no sales wording, no em dashes. You are
the only agent editing the worktree. Do not run `ls` in a shell here; use `/bin/ls`.

The check is
`/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/reviews/R3e-logs2-simpler-design-check-workflow.json`
(three checkers; 8 findings, all low after a second agent reproduced them; the process
tests, about 900 groups of real processes, found no lost row, no hang and no removed
directory). Scripts are under
`/private/tmp/claude-501/-Users-ajay-Developer-agent-reliability-ci/39ca2335-7a5a-47d9-a374-69d92a47e1d0/scratchpad/review24e/`.

Record 0017 is already amended. Read, in `docs/design/0017-logs-2.md`: the sentence about
symbolic links in "Directories are never removed, and reserved names", the new paragraph
"A run that is interrupted or killed", and acceptance item 79. Do not edit `docs/design/`,
`tests/acceptance/`, `FROZEN.sha256`, any version number, `bench/`, `docs/results/` or
`docs/STATISTICS_LOGS.md`.

## Code (`src/arci/logs/cli.py`). Three small edits. Add nothing else.

1. **Reserved names through a symbolic link** (findings processes-1, reasoning-1). The
   reserved-name test is also made on the name of each resolved output target (the
   `targets` list in `_execute`), in the option-only phase, with the same result: the
   general usage line, exit 3, nothing read and nothing written. Use one helper for the
   test so that both places share it.
2. **An interrupt during the same-file check** (finding reasoning-2). In `_write_outputs`,
   a new target is recorded in `placeholders` before the `os.open` that creates it, so
   that an interrupt between the two leaves no empty file. If that `os.open` raises
   `FileExistsError`, the target is taken out of `placeholders` again before the error
   goes on (the file is not this run's).
3. **An interrupt at a move** (finding reasoning-3). A target is recorded in `installed`
   before its `os.replace`, so that the restore covers a move that was interrupted after
   it took effect. Check that the restore is right for a target whose move had not yet
   taken effect: one with a backup is put back from the backup; a new one that does not
   exist is skipped without stopping the restore of the others.

## Tests (`tests/unit/logs/test_logs2.py`; each must fail when its rule is removed: check by a temporary edit, restore it, and say so)

4. Item 1: `--json` given as a symbolic link (dangling, and to an existing file) whose
   target's name begins with `.realornoise-`, inside and outside the table directory,
   with and without `--keep`: usage line, exit 3, nothing read or written, link and
   target unchanged. A link to an ordinary name is accepted.
5. Item 2: an interrupt (`KeyboardInterrupt` raised from a patched `os.open` after the
   real call created the file, and from one raised before the real call) leaves no empty
   file at the new target; a `FileExistsError` from that `os.open` does not remove the
   file that was there.
6. Item 3: `KeyboardInterrupt` raised from a patched `os.replace` after the real move
   took effect, at the first, a middle and the last move, with targets that existed and
   targets that are new: every target that existed has its old bytes and mode, every new
   target is absent, the run ends with the write error and exit 3.
7. Finding reasoning-4: (a) `--keep-dir` and `--claude-dir` whose last component is
   `.realornoise-x` are accepted and the run writes its table there; (b) a regular file
   `.REALORNOISE-x` in the table directory is still there after a successful `--keep` run.
8. Findings tests-docs-2 and tests-docs-3: (a) a leftover `.realornoise-x` in an existing
   table directory is still there after a `--keep` run whose write fails; (b) when the
   re-read under the lock finds the table unreadable, the run writes no table and the
   leftover is still there.
9. Finding tests-docs-1: with `os.umask(0o100)` (restored in a `finally`), a `--keep-dir`
   two new levels deep succeeds and both new directories have mode 0700 (the mutation
   "no chmod after mkdir" must fail this test).

## Documents

10. `docs/recipes/logs.md` and `docs/THREAT_MODEL_LOGS.md`: two or three sentences from
    the record's paragraph "A run that is interrupted or killed" (what an interrupt does;
    what a killed process can leave, and that a `.realornoise.out-` file beside a report
    may be deleted by hand); the reserved-name sentence also names symbolic links.
    `CHANGELOG.md`: add to the Fixed bullet for the write path, final behaviour only.

## Done when

- `.venv/bin/pytest -o addopts='' -q tests/unit/logs tests/unit/docs tests/unit/plugin tests/unit/packaging`
  passes with no failure.
- `.venv/bin/pytest -o addopts='' -q tests/acceptance/test_logs.py` passes (233 cases).
- `tests/unit/logs/test_logs2.py` passes 10 times in a row.
- `.venv/bin/ruff format --check .`, `.venv/bin/ruff check .`, `.venv/bin/basedpyright` clean.
- `.venv/bin/python bench/make_log_example.py --check` passes.
- `shasum -a 256 -c FROZEN.sha256` reports only the five released files.

## Final message

One line per numbered item; for items 4 to 9 the temporary edit and that the test failed;
the commands and their last lines; anything you could not do. No long logs.
