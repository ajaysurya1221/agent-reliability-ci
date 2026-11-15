# L8c: integrate (streak rule D-15, stale unit tests, whole suite green)

Read `/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/tasks/L-CONTRACT.md` and follow
its rules. You are the only agent working in the worktree now. The two records are the
truth: `STATISTICS_LOGS-draft.md` and `0016-logs-draft.md` (paths in the contract), in their
current text. Read both in full first; they changed several times today.

## You own

Everything under `src/arci/logs/`, `src/arci/html_base.py`, `src/arci/html_report.py`,
`bench/selfcheck_logs.py`, `bench/make_log_example.py`, `docs/results/logs-selfcheck.md`,
and **all unit tests and snapshots under `tests/unit/logs/`** (you may and must edit them
where they state behaviour the records no longer state). You do not own
`tests/acceptance/` (never edit), `packages/`, `.github/`, `plugins/`, `integrations/`,
`tests/unit/plugin/`, `tests/unit/packaging/`.

## Do, in this order

1. Carry out `/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/tasks/L8b-streak-veto.md`
   (the ladder change, the `not used` rendering, the three-variant streak section of the
   self-check with enough runs per cell, the full re-run).
2. Make every unit test under `tests/unit/logs/` agree with the records and pass. Eleven
   fail now: reader tests that predate the counter meanings of record 0016 decision 6
   (`files_read`, `lines`, `lines_unknown_type` for API-error lines, a Codex file whose
   first line is not a `session_meta`), and `test_every_fixed_text_matches_record`. For
   each, decide from the records whether the test or the code is wrong and fix that side;
   say which in your final message.
3. `basedpyright` reports one error (`tests/unit/logs/test_report.py` uses the private
   `_wrap`): fix it without an ignore comment (test the wrap through the public renderers).
4. Whole repository: `.venv/bin/pytest -q` passes except tests that need a local socket or
   a subprocess if your sandbox blocks them (list those), and except acceptance tests in
   `tests/acceptance/test_logs.py` that still state the per-measure streak rule (list
   those: the orchestrator has them updated). `.venv/bin/ruff format --check .`,
   `.venv/bin/ruff check .`, `.venv/bin/basedpyright` clean. `python bench/make_log_example.py
   --check` passes. `shasum -a 256 -c FROZEN.sha256` passes.

Final message: the gate table and the three-variant streak table from the full self-check;
for each of the eleven tests, whether the test or the code was changed; the acceptance tests
that fail and why; files changed; anything you could not do.
