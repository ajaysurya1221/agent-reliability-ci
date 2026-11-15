# F6: a guard against log-format changes

Read `AGENTS.md` in the worktree `/Users/ajay/Developer/.arci-worktrees/wt-v2-logs`
(branch `v2/logs2`). Work only there. Change no git state. No network, do not call `uv`.
Never open anything under `~/.claude` or `~/.codex`. Use only synthetic logs. Do not edit
any file listed in `FROZEN.sha256`. Plain words, short sentences, no em dashes.

Another agent is working in the same worktree on `bench/selfcheck_logs.py`,
`docs/STATISTICS_LOGS.md`, `docs/results/`, `src/arci/logs/report.py`,
`tests/unit/logs/test_selfcheck_quick.py` and `tests/unit/docs/test_logs_docs.py`.
**Do not touch those, and do not change any product code.** If a test you write shows a
product defect, do not fix it: report it with a minimal reproduction.

## Why

Both vendors call their session-log format internal, and it changes. A maintained tool
that reads the same files (`ccusage`) broke three times in 2026, each time on a change
nobody announced:

- **12 Sep 2026** (its issue 1710): Claude Code began writing a `null` model inside
  `usage.iterations[]` of an assistant line.
- **14 Oct 2026** (its issue 1888): Codex began compressing sessions idle for 7 days to
  `.jsonl.zst`, in `sessions/` and `archived_sessions/`, removing the plain file after
  checking the compressed one. During that step both files can exist.
- **6 Nov 2026** (its issue 2033): a truncated Codex record (a line cut off in the middle
  of its JSON) made the tool stop with an error for the whole report.

## You own (new files only)

1. `tests/unit/logs/test_format_incidents.py`. Read `docs/LOG_FORMATS.md`,
   `docs/design/0017-logs-2.md` and the readers' public behaviour as the existing tests
   use it (`tests/unit/logs/synth_logs.py`, `test_claude_code.py`, `test_codex.py`). One
   test or more per incident, each with a docstring naming the incident and its date:
   - a Claude Code assistant line whose `message.usage` carries an `iterations` list with
     a `null` model (and other unknown keys): the response is still read, with its model,
     effort and reasoning count taken from the documented fields, and nothing is counted
     as a fault;
   - a Codex session present twice, once as `rollout-X.jsonl` and once as
     `rollout-X.jsonl.zst` with the same content, in `sessions/` and again in
     `archived_sessions/`: each response is counted once, and the duplicate count says so
     (run this part only on a Python that can read the compressed file, and skip it with a
     stated reason otherwise; without that Python the compressed file is counted as not
     read and the plain one is used);
   - a Codex file whose last line is cut off in the middle of a JSON object, and one with
     a cut-off line in the middle: the run does not fail, the complete lines are used, and
     the cut-off line is counted where the format page says such a line is counted;
   - the same for a Claude Code file;
   - a line of a type the reader does not know, in both tools: counted, skipped, no fault;
   - an end-to-end run through `arci.logs.cli.run` on a directory that mixes all of the
     above gives a result or CANNOT TELL, never ERROR, and exits 0, 1 or 2.
2. `.github/scripts/client_versions.py` (stdlib only) and
   `.github/workflows/client-versions.yml`: a scheduled job (once a day) and manual
   dispatch. It asks the npm registry for the latest versions of `@anthropic-ai/claude-code`
   and `@openai/codex` (`npm view <name> version`), reads the client versions the readers
   were checked against from `docs/LOG_FORMATS.md` (the sentence near the top that lists
   them), and, when a newer version exists for either client, keeps **one** open issue up
   to date with the title `Newer client versions than the checked ones` (create it if
   there is none, otherwise edit its body; never open a second one; close nothing). The
   body lists, per client, the highest checked version and the latest published one, and
   says what to do: run the format tests against a session of the new client and add the
   version to `docs/LOG_FORMATS.md`. Use the `gh` command that the runner already has,
   with the job's own token. Permissions: top level `contents: read`; the job adds
   `issues: write`. Pin the checkout the way the other workflows do
   (`persist-credentials: false`). The script takes the two latest versions as arguments
   and prints the issue body or nothing, so that it can be tested without a network.
3. `tests/unit/packaging/test_client_versions.py`: the script parses the versions out of
   the real `docs/LOG_FORMATS.md`; compares versions numerically (2.1.325 is newer than
   2.1.40); prints nothing when nothing is newer; prints a body naming both clients when
   one is newer; the workflow has a schedule, the two permissions above, and no unpinned
   action (the existing `test_trust_files.py` also checks pins; do not edit that file).
4. `CHANGELOG.md`, under `## Unreleased`: one `- **Tests:**` bullet and one `- **CI:**` bullet.

## Done when

- `.venv/bin/pytest -o addopts='' -q tests/unit/logs/test_format_incidents.py tests/unit/packaging`
  passes (the compressed part may be skipped on this Python; say which Python ran it).
- Also run the incident tests with
  `/private/tmp/claude-501/-Users-ajay-Developer-agent-reliability-ci/39ca2335-7a5a-47d9-a374-69d92a47e1d0/scratchpad/venv314/bin/python -m pytest -p no:cacheprovider -o addopts='' -q tests/unit/logs/test_format_incidents.py`
  (Python 3.14, which reads the compressed files) and report its last line.
- `.venv/bin/ruff format --check .`, `.venv/bin/ruff check .`, `.venv/bin/basedpyright` clean.

Final message, concise: files added; each command with its last line; every product
defect a test exposed, with its reproduction (do not fix it); what cannot be checked here
(the workflow cannot run locally); risks.
