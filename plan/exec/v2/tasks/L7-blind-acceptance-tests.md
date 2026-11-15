# L7: acceptance tests for `arci logs`, written blind

You write the acceptance tests for a feature you have not seen the code of. They become
`tests/acceptance/test_logs.py`, are hash-pinned at the release, and are the source of truth
for behaviour. Another agent is implementing the feature at the same time from the same
records.

## Hard rules

1. **You may read only these files** (all under
   `/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/`):
   `logs/STATISTICS_LOGS-draft.md`, `logs/0016-logs-draft.md`, `tasks/L-CONTRACT.md` (its
   "Module interfaces" block is partly out of date: the two drafts win), and the section
   "Log formats" of `tasks/L0-logs-spike.md`.
   For test style you may read `tests/acceptance/test_outcomes.py` in
   `/Users/ajay/Developer/.arci-worktrees/wt-v2-logs/` (use `git -C <that dir> show origin/main:tests/acceptance/test_outcomes.py`).
2. **You must not read** anything under `src/arci/logs/`, `tests/unit/logs/`, `bench/`, or
   `plan/exec/v2/spikes/` anywhere, nor any other task brief. Do not run the feature.
3. **Never open, list or read anything under `~/.claude` or `~/.codex`.**
4. You own one file: `/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/acceptance-staging/test_logs.py`.
   Change no git state. No network. Standard library and `pytest` only (plus `arci` imports
   named below).
5. The only entry points the tests may use: `arci.logs.cli.run(argv, *, now, env, home, out,
   err) -> int` as the record describes it, and `arci.hashing.hash_record` to check a seal.
   No other import from `arci.logs`: the tests must not depend on internal names.

## What to write

A self-contained pytest file with its own small generator of synthetic Claude Code and Codex
log files (written into `tmp_path`, from the format facts), and tests that state the
contract. Each test builds logs, calls `run` with `--claude-dir`, `--codex-dir`, a fixed
`now`, an empty `env`, a `home` under `tmp_path`, and in-memory `out` and `err`, and checks
the exit code, the text, and the `--json` record.

Cover at least:

1. **The ladder.** One scenario per result and reason: REAL DROP; NO DROP; CANNOT TELL for
   `too_few_days`, `not_enough_evidence`, `streaky_days`, `no_usable_setting`; ERROR for
   `no_logs`, `format_not_recognised`. Exit codes 1, 0, 2, 3 and the two-tool mapping
   (a REAL DROP beside a CANNOT TELL; an ERROR beside a result; both ERROR).
2. **The numbers.** For small designs (for example 5 after-days and 10 before-days), compute
   `p_real`, `u_none`, `p_none` and `p_streak` yourself by brute-force enumeration in the
   test file, from the day values you planted, and require the record's rationals to equal
   yours exactly. Include tied day values, a higher-is-worse measure, and the margin move in
   exact arithmetic (a before-day of 5 tokens moves to 15/4).
3. **Measures and usable days.** The 20 and 10 thresholds at the boundary (19 and 20 known
   counts; 9 and 10 positive counts; 9 and 10 edit results); unknown reasoning counts never
   counted as 0; an after period where every count is 0; `v*` and its tie rule; even-count
   medians; a measure without enough days not blocking a REAL DROP from another measure;
   permission denials and unmatched edit results left out; edits attributed to the setting
   of the response that made the call.
4. **What is compared.** Sub-agent responses ignored for the measures; the setting chosen by
   pooled counts and the tie rule; `--model` and `--effort` by rendered name; a named model
   that does not exist; `--since` (valid, malformed, too early, later than the newest day);
   `--project`; `--utc` against a local offset given through `now`; a response found in two
   files counted once; records in the future and without a zone left out and counted.
5. **Privacy.** Canary tokens in every free string (upper case, lower case shaped like a
   model id, digits shaped like a version, a private-looking model id such as
   `acme-payroll-secret` and `gpt-12345678-87654321`, working directories, prompts, tool
   inputs and outputs): none appears in `out`, `err`, the JSON, the Markdown, or any
   exception. Unknown model ids render as `model-1`, `model-2` and are still compared; two
   unknown ids are never merged. Every string leaf of the JSON is a date, a rational, a
   closed-list name from the record, a rendered name, or a hex digest.
6. **Robustness.** Unknown line types, lines that are not JSON, a truncated last line,
   missing optional keys, an unreadable file beside a readable one: counted in
   `ReaderCounters`, never an exception; `run` never raises and never prints a traceback.
7. **The record.** `schema_version`, the fields and null rules of the record model for each
   result, which test fields are filled for each finding, ascending days, `seal` equal to
   `hash_record` of the record without `seal`, `day_table_sha256` unchanged when the logs
   are read in a different file order and changed when one day value changes.
8. **Fixed texts.** F4, the F5 reason for each scenario, F10 with its first sentence and its
   "For each tool above and one comparison" sentence, F11 with a 12-hex digest, F12, and the
   last line `exit {code}`, exactly as the record gives them; no line longer than 100
   characters; no word "improved" outside the sentence that says it does not say anything
   improved; no output on `err` in a normal run.
9. **Determinism.** Two runs on the same logs give byte-identical text and JSON.

Write the tests so that a wrong implementation fails loudly and a right one passes; when the
records leave something open, do not guess: leave it out and list it in your final message.

## Done when

The file imports cleanly (`python -m py_compile`), `ruff format` and `ruff check` are clean
on it (use `/Users/ajay/Developer/agent-reliability-ci/.venv/bin/ruff`), and your final
message lists: the number of tests, what each group covers, and every place where the
records were ambiguous or silent. You cannot run the tests; do not try.
