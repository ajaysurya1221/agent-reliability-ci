# A1: blind acceptance tests for `arci-logs/2`

You write acceptance tests from the records alone. **You must not read the
implementation.** Do not open anything under `src/`, `bench/`, `tests/unit/` or any
existing snapshot in the worktree, and do not run the product to see what it prints. The
value of these tests is that their author never saw the code.

Never open anything under `~/.claude` or `~/.codex`. No network. Change no git state.
Plain words in comments and names, no em dashes.

## Read (only these)

In `/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/logs2/`:

- `0017-logs-2-draft.md`: design record 0017. Its section "Acceptance, as tests can see
  it" lists the observable behaviours; the rest of the record gives the exact rules,
  option names, fixed texts, reason codes and the JSON record model.
- `STATISTICS_LOGS-2-draft.md`: the method (windows, measures, thresholds, tests).

In `/Users/ajay/Developer/.arci-worktrees/wt-v2-logs/`:

- `docs/LOG_FORMATS.md`: the log fields the readers use. Build your synthetic logs from it.
- `docs/design/0016-logs.md`: the record of the earlier method, for the rules that 0017
  restates as unchanged.
- `tests/acceptance/test_logs.py`: the acceptance tests of the earlier method (82 cases),
  written the same blind way. Reuse its helpers and style. It is the file you replace.

## Write

One file: `/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/acceptance-staging/test_logs.py`
(it replaces the file there). It is later copied over `tests/acceptance/test_logs.py`.

- Keep every earlier case whose behaviour record 0017 leaves unchanged. Change the cases
  that 0017 changes (for example the method id, the setting that is compared, the closing
  paragraph, the footer, the F24 wording). Remove a case only when 0017 removes the
  behaviour, and say so in a comment.
- Add cases for every numbered item of "Acceptance, as tests can see it". Put the item's
  number in the test's docstring. Where one item needs several cases, parametrise.
- Tests call the public entry points the record names (`arci.logs.cli.run` with injected
  `now`, `env`, `home`, `out`, `err`; the record model for validation) and compare
  observable output: exit codes, exact fixed texts, JSON fields, files written and their
  modes. No test may depend on a private name.
- All logs are synthetic and built in `tmp_path`. Use an isolated `home` so that no real
  file is read or written. Unless a test supplies a kept table, there is none.
- Items about the self-check, the documents, the plugin and the packaged version are
  outside this file; list their numbers at the top in a comment as "covered elsewhere".

## Do not

- Do not run the tests against the product, and do not adjust an expectation to any
  observed output. You have not seen any.
- Do not weaken an assertion because a rule seems hard to implement. If the record is
  ambiguous, write the test for the plainest reading and list the ambiguity.

## Final message

The number of test functions and of cases; the acceptance items covered, and those left
out with the reason; every ambiguity you met in the record, with the reading you chose;
the earlier cases you removed or changed and why. Check only that the file imports and
collects (`/Users/ajay/Developer/.arci-worktrees/wt-v2-logs/.venv/bin/python -m pytest --collect-only -q -o addopts='' <file>`
run from the worktree is allowed, since collection does not show product output).
