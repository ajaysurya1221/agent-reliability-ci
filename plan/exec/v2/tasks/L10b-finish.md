# L10b: finish L10

Read `/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/tasks/L-CONTRACT.md` and
`L10-html-and-report-fixes.md` (same ownership). You stopped L10 at an acceptance-test
conflict; that test was wrong and has been corrected, and the acceptance tests were updated
to the current record. The copy at `tests/acceptance/test_logs.py` in the worktree is the
current one: do not edit it. Another agent owns `bench/selfcheck_logs.py`,
`tests/unit/logs/privacy/` and `tests/unit/logs/test_selfcheck_quick.py`; do not touch those.

1. `src/arci/html_report.py` must still export every name it exported before the move to
   `html_base.py` (`tests/unit/examples/test_pr_comment.py` imports `visible_text` from it
   and fails now). Compare with `git show HEAD:src/arci/html_report.py` and re-export what
   moved. Do not edit existing tests.
2. `src/arci/logs/report.py`: `__all__` lists only public names, sorted (ruff RUF022 fails
   now). Tests that need private helpers import them by name.
3. Claude Code reader: a line carrying `isApiErrorMessage` is counted in
   `lines_unknown_type` (record 0016, decision 6, "Formats"). The acceptance test
   `test_future_and_zoneless_records_are_left_out_and_counted` fails on this now.
4. Read the last paragraph of "Fixed texts" in record 0016 (wrap rule: a line of exactly
   100 characters is allowed; counter meanings for `files_read`, `files_outside_project`,
   `responses`) and make the code agree.
5. Finish what L10 left: the whole suite `.venv/bin/pytest -q` passes, including all of
   `tests/acceptance/test_logs.py`; `.venv/bin/ruff format --check .`, `.venv/bin/ruff check .`
   and `.venv/bin/basedpyright` are clean for the whole repository (ignore failures only in
   the other agent's files, and list them); `python bench/make_log_example.py --check`
   passes; `shasum -a 256 -c FROZEN.sha256` passes. If the sandbox blocks tests that bind a
   local socket, say which and run the rest.

Final message: files changed, the commands and their last lines, anything you could not do.
