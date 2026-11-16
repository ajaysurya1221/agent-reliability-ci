# R6: count script A for run 3

Write one file: `plan/exec/v2/study/counts-run-3/count_a.py`, standard library only, that
computes the descriptive counts exactly as `plan/exec/v2/study/counts-run-3/SPEC.md` defines
them. Read the specification first; it is your only definition of the counts.

Learn the store format from the published run 2 store under
`/Users/ajay/Developer/.arci-worktrees/wt-v2-logs/docs/results/order-desk-study/run-2/`
(manifest.json, trials.jsonl, events.jsonl). Run your script on it and check internal
consistency (per arm: passed + failed + errored == trials; by_condition and by_task each sum
to trials; read_again.trials + not_read_again.trials == empty_result_delivered).

Rules:
- Do NOT read any write-up of results: not `docs/results/order-desk-study.md`, nothing under
  `docs/blog/`, not `plan/exec/v2/study/RESULT*.md`, `report-run-*.md`, `PREREGISTRATION*.md`
  or `PLAN-run-3.md`, nothing under `plan/exec/v2/launch/` or `plan/exec/v2/signals/`.
- Do NOT open `count_b.py` or any other count script; a second agent writes that one
  separately and the two outputs are compared afterwards.
- The script must not assume particular arm names, four conditions or 24 tasks: the next
  store has one condition and 8 tasks. Missing file or missing field: a clear message and
  exit status 2. Never guess.
- Change no other file. No git command that changes state. No network. Install nothing. Do
  not call `uv`. No model, no `arci run`.
- Python: `/private/tmp/claude-501/-Users-ajay-Developer-agent-reliability-ci/39ca2335-7a5a-47d9-a374-69d92a47e1d0/scratchpad/run3-env/bin/python`.

Report (short): the command you ran on the run 2 store, the JSON it printed, and any place
where the specification was ambiguous and how you read it.
