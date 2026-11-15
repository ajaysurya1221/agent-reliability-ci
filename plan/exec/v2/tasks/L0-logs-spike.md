# L0: feasibility spike for `arci logs` / `realornoise` (go or no-go)

You are the implementer. Read `AGENTS.md` first. This is a spike: scratch code that answers
one question with numbers. It is not product code and nothing here ships.

## Why

Plan approved 15 Nov 2026: ARCI 2.3.0 adds a first step with no set-up. One command reads
the Claude Code and Codex session logs already on a user's disk, compares recent days with
earlier days for the same model and effort setting, and answers REAL DROP, NO DROP or
CANNOT TELL with a stated bound on each wrong answer. Before any product code, this spike
must show that (a) both log formats can be read reliably, (b) the exact rank test is
correct and keeps its bound, (c) the test has usable power at realistic sizes.

## Hard rules

1. **You own only `plan/exec/v2/spikes/L0-logs/`.** Create files only there. Change no git
   state. No network. Standard library only (plus `pytest` for the tests).
2. **Privacy. You must never open, list, print, `cat`, `head`, `grep` or otherwise read
   anything under `~/.claude` or `~/.codex`, or run your code against them.** You develop
   and test on synthetic logs that your own generator writes. The orchestrator runs
   `run_real.py` on real logs afterwards.
3. Everything your code prints or writes, error messages included, is built from an
   allow-list: numbers, dates, booleans, names from closed lists that are written in your
   code, and model ids that match `^[a-z0-9][a-z0-9._-]{1,48}$` (anything else becomes
   `other`). No value of any other string field of a log may reach an output, a log line,
   an exception message or a traceback. Catch per-line errors and count them.
4. The code runs on Python 3.13 (`.venv/bin/python`) and on Python 3.14
   (`/Users/ajay/.local/share/mise/installs/python/3.14.6/bin/python3.14`). Reading
   `.jsonl.zst` uses the standard-library `compression.zstd`, which exists only on 3.14:
   import it lazily; on 3.13 count such files as `unread_compressed` and go on.
5. Exact arithmetic in every decision: `fractions.Fraction` and integers. No float may
   decide a result. Floats are allowed in simulation inputs and in printed summaries.
6. No randomness in the decision. Simulations use `random.Random(seed)` with printed seeds.

## Log formats (observed on real logs: field names and counts only)

Every line is one JSON object. Unknown line types and unknown keys must be skipped and
counted, never fatal.

### Claude Code

Files: `<root>/<project-dir>/<session>.jsonl` (main sessions) and, below a session folder,
`subagents/**/agent-*.jsonl`. Skip any file named `journal.jsonl`. `<root>` is
`~/.claude/projects` or `$CLAUDE_CONFIG_DIR/projects`.

- Line type is the top-level `type`. About 20 types occur (`assistant`, `user`, `system`,
  `attachment`, `api-request`, `api-request-blob`, `mode`, `queue-operation`, ...). Only
  `assistant` and `user` are needed.
- `assistant` line: `message.id`, `message.model`, `message.content[]` (blocks with `type`
  in `thinking`, `tool_use`, `text`; a `tool_use` block has `id` and `name`; a `thinking`
  block has `signature`), `message.usage.output_tokens_details.thinking_tokens` (integer;
  `output_tokens_details` can be null), `message.stop_reason`, top-level `timestamp` (ISO
  8601 with `Z`), `version`, `effort` (`high`, `medium`, ...; can be missing),
  `perTurnEffort`, `isSidechain` (true for sub-agents), `isApiErrorMessage` (present and
  true on synthetic error lines, which must be skipped).
- **One response is one distinct `message.id` within a file.** The same id appears on
  several lines (one per content block) with the usage repeated; count it once, with the
  timestamp of its first line, the union of its blocks, and the usage of its last line.
- `user` line: `message.content` is a string or a list of blocks. A block with
  `type == "tool_result"` has `tool_use_id` and optionally `is_error` (true means the tool
  failed; absent or false means it did not). The line may carry `toolDenialKind` or
  `permissionDecision.decision == "reject"`: such a result is a permission denial and is
  not a failure. `isSidechain` and `timestamp` as above.
- File-edit tools are `Edit`, `Write`, `MultiEdit`, `NotebookEdit`. Map a `tool_result` to
  its tool through the `tool_use` block with the same id earlier in the same file.

### Codex

Files: `<root>/sessions/YYYY/MM/DD/rollout-*.jsonl` and `<root>/archived_sessions/**`,
plain or `.jsonl.zst`. `<root>` is `~/.codex` or `$CODEX_HOME`. Every line is
`{"timestamp": ..., "type": ..., "payload": {...}}`.

- First line `type == "session_meta"`: `payload.cwd`, `payload.cli_version`,
  `payload.thread_source` (`subagent` means not the main thread; `user` or absent means
  main thread).
- `type == "turn_context"`: `payload.model`, `payload.effort`. It applies to every later
  response in the file until the next `turn_context`.
- `type == "event_msg"` with `payload.type == "token_count"`: one response.
  `payload.info.last_token_usage.reasoning_output_tokens` (integer) is the reasoning size.
  `payload.info.total_token_usage.total_tokens` lets you drop a repeat: skip a
  `token_count` whose `total_token_usage` equals the previous one in the same file.
  `payload.info` can be null; skip those.
- No file-edit measure for Codex (edits go through shell commands).

## What to build (all under `plan/exec/v2/spikes/L0-logs/`)

1. `records.py`: a frozen dataclass `Response` (tool, file index, timestamp as an aware
   `datetime`, sanitised model, effort from a closed list else `other`, `main_thread`,
   `reasoning_tokens: int | None`) and `EditResult` (tool, timestamp, `main_thread`,
   `failed`). The sanitisers live here.
2. `readers.py`: `read_claude(paths)` and `read_codex(paths)` yielding those records plus
   a counters object (files, lines, unparseable lines, skipped line types as a count,
   unread compressed files, responses, responses lacking model / timestamp / reasoning).
   `discover_claude(root, dir_prefix)` and `discover_codex(root, cwd_inside)`: the Codex
   filter reads only the first line of a file and only its `payload.cwd`.
3. `daytable.py`: per tool, model and effort, main thread only, one row per local calendar
   day (system time zone): number of responses and the measures below. A day is usable
   with 20 or more responses.
   - `m1` median of the positive reasoning-token values (a `Fraction`; lower is worse;
     margin: a 25% drop).
   - `m2` share of responses with reasoning tokens equal to 0 (higher is worse; margin
     10 points).
   - `m3` Claude Code only: share of failed file edits among edit results that were not
     denied; the day is usable for `m3` with 10 or more such results (higher is worse;
     margin 3 points).
   - `m4` Codex only: share, among responses with positive reasoning tokens, whose value
     equals the most common positive value pooled over all usable days of both periods
     (higher is worse; margin 10 points).
4. `rank_test.py`: `p_lower(before, after) -> Fraction`, the exact one-sided
   Wilcoxon-Mann-Whitney p-value that the after-days tend to be lower: the probability,
   over all `C(n+m, m)` equally likely choices of which pooled values are "after", that the
   midrank sum of the after group is at most the observed one. Count by integer dynamic
   programming on doubled midranks; ties handled by the conditional distribution (no
   normal approximation, no continuity correction). Cache the null distribution by
   `(n, m, tie-group sizes)`. Also `brute_p_lower` by enumeration for checking.
5. `decide.py`: inputs are two lists of usable days per measure, and a direction and
   margin per measure.
   - Fewer than 5 usable after-days or 10 usable before-days: CANNOT TELL (too few days).
   - REAL DROP for a measure: `p ≤ (1/40) / k`, `k` the number of gating measures for the
     tool (3), testing "after is worse than before".
   - NO DROP for a measure: `p ≤ 1/40` for "after is better than before moved by the
     margin". For `m1` multiply every before-day by `3/4` and test that after tends
     higher. For the share measures add the margin to every before-day and test that
     after tends lower.
   - Overall: REAL DROP if any gating measure is a real drop; NO DROP only if every gating
     measure is a no-drop; else CANNOT TELL.
   - Self-check: split the before-days by date into a first and second half; if the REAL
     test fires for any gating measure there, an overall REAL DROP becomes CANNOT TELL.
   - Return a small result object with the per-measure p-values as `Fraction`.
6. `synth.py`: a seeded generator of synthetic logs in both formats, written to a
   directory you are given: several sessions per day, main and sub-agent files, unknown
   line types, malformed lines, missing optional keys, a `.jsonl.zst` copy when the
   interpreter can write one, and a unique canary token (`CANARY-<n>`) in every string
   field that is not a closed-list value. It takes per-day parameters so a planted shift
   (for example a 45% drop in reasoning tokens after a date) can be generated.
7. `sim.py`, run as a script, printing tables:
   - (a) for every `n + m ≤ 14` and three tie patterns (no ties; values drawn from
     `{0, 1, 2}`; all equal), `p_lower` equals `brute_p_lower` exactly, and the share of
     labelings with `p ≤ α` is at most `α` for `α` in `{1/40, 1/120}`;
   - (b) null simulation, 20,000 seeded day tables for each design (after/before days)
     5/10, 7/21, 14/42, 28/84, three measures: the rate of overall REAL DROP when nothing
     changed, once with independent measures and once with identical ranks across
     measures; and the rate of overall NO DROP when `m1` sits exactly at its margin
     (after = 0.75 × before in distribution) and the other measures are unchanged. Each
     must be at most 0.0283;
   - (c) power: the rate of REAL DROP for drops of 33%, 45%, 50% and 55% in `m1`, with
     day values log-normal and the day-to-day standard deviation of the log as a
     parameter (run 0.35, 0.45 and 0.55), for the four designs; and the rate of NO DROP
     when nothing changed;
   - (d) the same null rate when the log day values follow an AR(1) process with
     coefficient 0.5 (reported, not a pass or fail);
   - (e) 50 seeded synthetic log sets with no shift and 50 with a 45% drop at 14/42 run
     through readers, day table and decision.
   Keep the whole script under about 15 minutes on a laptop; if a design is too slow at
   20,000, lower its count and print the count used.
8. `run_real.py`: `--claude-root DIR --claude-prefix NAME --codex-root DIR --codex-cwd PATH
   --out FILE`. Writes one JSON file and prints the same: counters from the readers, parse
   seconds per tool, the share of responses with model, timestamp and reasoning size, and
   for each tool, model and effort the day table (date, responses, measures as decimal
   strings), the number of usable days, the standard deviation of `ln(m1)` across usable
   days, and the decision for a split 14 days before the newest day. Every leaf of the
   JSON passes the allow-list of rule 3; include a function that walks the JSON and
   raises if a string leaf is not a date, a decimal, a closed-list name or a sanitised
   model id, and call it before writing.
9. `test_l0.py` (pytest): brute-force equality; decision on hand-made day lists; both
   readers on synthetic logs (counts match what the generator wrote; unknown and malformed
   lines are counted, not fatal); no canary token in any output of `run_real.py` run on a
   synthetic directory, nor in any exception text when a file is corrupt; the allow-list
   walker rejects a planted bad leaf.
10. `REPORT.md`: the tables from `sim.py`, the test command and its last lines, and this
    go-test table with the last three rows left for the orchestrator:

    | Check | Threshold | Result |
    |---|---|---|
    | Exact test equals brute force, `n + m ≤ 14` | all equal | |
    | Null: wrong REAL DROP, each design | ≤ 0.0283 | |
    | Null: wrong NO DROP at the margin, each design | ≤ 0.0283 | |
    | Power: 50% drop at 14/42, log-SD 0.45 | ≥ 50% | |
    | Planted 45% drop at 14/42, log-SD 0.40 | ≥ 95% (reported) | |
    | Real logs: both readers, no exception | orchestrator | |
    | Real logs: ≥ 99% of responses with model, timestamp, reasoning size | orchestrator | |
    | Real logs: parse time | orchestrator | |

## Done when

- `.venv/bin/pytest plan/exec/v2/spikes/L0-logs -q` passes, and the same tests pass under
  Python 3.14 (run `python3.14 -m pytest` if pytest is importable there; otherwise give
  `test_l0.py` a `__main__` runner and use it).
- `sim.py` has run to the end and `REPORT.md` holds its tables.
- `.venv/bin/ruff format` and `.venv/bin/ruff check` are clean on your files.
- Your final message: files written, the test command with its last lines, the go-test
  rows you could fill, anything you could not do, and risks. No long logs.
