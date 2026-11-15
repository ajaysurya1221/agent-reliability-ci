# 0016: v2.3.0, a result from session logs the user already has

Draft record by the orchestrator (Claude Fable 5.2), 2026-11-15, for read-only review before
any product code. Implementation by Codex from briefs under `plan/exec/v2/tasks/`. Plan
approved by the maintainer on 2026-11-15. Becomes `docs/design/0016-logs.md`. No frozen file is
changed by this record; the re-freeze below is made at the release.

## Why

Twelve versions brought no user. Both existing ways ask for work before they give anything:
tools, tasks and a checker for `arci run`; repeated runs of two versions for `arci verdict`.
Open issues read on 2026-11-15 show little demand for that question among people who build
evaluations (about 14 reactions in total) and a large, recurring one among people who use
coding agents: "the model got worse under me" (about 4,900 reactions on the top issues), argued
twice from hand-made analyses of local session logs. Those logs are already on disk. This
record adds a first step that needs nothing else: read them, and say whether a recorded
measure dropped by more than the user's own day-to-day variation, did not, or cannot be told.

Other tools read the same logs (ccusage for cost; NerfTrack, is-gpt-nerfed and
claude-nerf-watcher for usage limits; claude-session-analyzer, nerfd and NerfWatch for
behaviour). ARCI does not claim to be the only one and compares nothing. What this step has:
one fixed rule with a stated bound on each wrong result, exact arithmetic, a result that can be
"cannot tell", outputs that hold numbers only, and two stronger steps behind it.

## Decision

1. **A new command and a new record kind.** `arci logs`, also installed as the command
   `realornoise` by a second distribution of the same name. Its decision record is
   `arci-logs/1`. It shares no statistics with suites or imported outcomes;
   `docs/STATISTICS_LOGS.md` is its whole contract.

2. **Observational, and named so.** The results are REAL DROP, NO DROP, CANNOT TELL and ERROR
   (exit 1, 0, 2, 3). PASS and BLOCK are not used: they are verdicts on a registered
   experiment, and this is not one. No output says that a model, an agent or its answers got
   worse or better; it says that a recorded measure moved toward worse, or did not move by its
   margin. No output says "improved".

3. **The rule** is the one in `docs/STATISTICS_LOGS.md`: one tool, one setting (model and
   effort), main thread; usable days before and after a split date; three gating measures per
   tool; per measure an exact conditional rank test at `(1/40)/3` for a real drop, and a
   strict-count test against a fixed reference at `1/40`, after moving the before-days by the
   margin, for a no-drop; a streak check on the before-days (an exact runs test) that withholds
   a measure whose days come in streaks; no random numbers. The setting is chosen from response counts over both periods
   together, never from one period: choosing by the after period alone can make a wrong REAL
   DROP certain (review finding 1).

4. **Defaults.** Split date: 13 days before the newest day found, so the after period is 14
   days. Before period: 84 days. A measure is tested with at least 5 usable after-days and 10
   usable before-days; the usable-day rule is per measure (statistics contract, "Measures").
   `--since DATE` replaces the split date; a malformed date, or one more than 83 days before the
   newest day, is a usage error with fixed text and exit 3; a date after the newest day gives
   CANNOT TELL with no after-days. No scan over
   dates, no comparison of two models, no stored history: each is left out of this version
   and named in "Not built".

5. **Which logs.** Claude Code: `$CLAUDE_CONFIG_DIR/projects` or `~/.claude/projects`. Codex:
   `$CODEX_HOME` or `~/.codex`, folders `sessions` and `archived_sessions`. `--claude-dir` and
   `--codex-dir` override; `--project PATH` keeps only sessions whose working directory is
   that path or below it; `--tool` limits to one tool. Formats are specified in
   `docs/LOG_FORMATS.md`, which lists the client versions the readers were checked against.
   Unknown line types and keys are skipped and counted. Compressed Codex files need Python
   3.14; on older Pythons they are counted and reported as not read, and the result is
   computed from the rest with notice F9.

6. **Privacy is a tested property.**
   - The command opens no socket, starts no process, and writes only the files named by
     `--markdown`, `--html` and `--json`.
   - Readers return records made of numbers, timestamps and names from closed lists.
   - **Model and effort names are rendered by rule, never copied through.** A model id is
     shown as written only when it passes a closed grammar in `records.py`: lower-case parts
     separated by `-`, `.` or `_`, each part a word from a fixed list (`claude`, `opus`,
     `sonnet`, `haiku`, `fable`, `gpt`, `codex`, `astra`, `mini`, ...), a number of at most two
     digits, or a short letter-digit token such as `4o`, with at most one eight-digit date
     part that starts with `20`. An effort is shown as written only when it is in the fixed
     list. Anything else is shown as `model-1`, `model-2`, ... or `effort-1`, ..., numbered in
     the text order of the raw values, and is still compared: two different unknown names are
     never merged. The review asked for a table of complete names instead; the grammar is
     kept because a table would print every new model as `model-1` until the next release,
     and what the grammar can leak is the choice of a few listed words and small numbers.
   - Client versions and working directories are never output: each is reduced to counts of
     distinct values and, for `--project`, to a yes or no.
   - No exception text, warning or output may carry a string read from a log. Per-line faults
     are counted. Errors are the fixed texts below and nothing else.
   - Tests: canary tokens in every free string of synthetic logs, including a lower-case one
     shaped like a model id and a numeric one shaped like a version, must appear in no output
     and no error; an audit hook fails the run on a socket, a subprocess or a write outside
     the named paths; a walk of the JSON output accepts only numbers, booleans, nulls, dates,
     rationals as strings and names the code can generate; an import allow-list covers
     `src/arci/logs/`.
   - **Reading faults.** Lines that are not JSON, lines of a type the reader does not use, and
     lines of a used type that lack a needed field are counted and left out; notice F15
     prints when any line lacked a needed field. A file that cannot be opened or decoded is
     counted and left out, with notice F17. Unknown keys are ignored and not counted. The
     same response found in two files (a resumed or copied session) is counted once: Claude
     Code by message id, Codex by session id, event time and cumulative usage.
   - **Effort.** Claude Code: the line's `effort`, else its `perTurnEffort` (on this
     project's logs `effort` matched the effort of the recorded request on every one of
     12,986 lines). Codex: the latest `turn_context`.
   - **`--project` on Codex** reads the first line of a session file and skips the rest of
     the file when its working directory is outside the project.

7. **Outputs.** Terminal text (fixed texts below), `--markdown FILE` (a block made to paste
   into an issue thread), `--json FILE` (the sealed `arci-logs/1` record), `--html FILE` (one
   self-contained page, no script, no external reference). `--example` runs on synthetic logs
   packaged in the wheel and labels every output "example data, generated". The sealed record
   holds the day table, so a result can be recomputed from the JSON alone; it holds nothing
   else from the logs.

8. **The second distribution.** `packages/realornoise/` builds a wheel that depends on
   `agent-reliability-ci==<same version>`, declares `requires-python >=3.14`, and provides
   the console script `realornoise = "arci.logs.cli:main"`. It carries no code of its own. The
   release workflow builds, smoke-tests and publishes both, the main package first.

9. **Plugin and skill.** `plugins/realornoise/` (Claude Code) and
   `integrations/codex/skills/realornoise/` (Codex) each run the command and show its output
   unchanged. Their text states that the numeric output then enters that agent's context.

10. **Version 2.3.0.** Additive under `docs/COMPATIBILITY.md`: a new command, a new record
    kind, a new distribution. Nothing existing changes meaning.

## Record model (`src/arci/logs/schema.py`, pinned)

Pydantic models, `extra="forbid"`, frozen, sealed with `hashing.hash_record` like
`outcome_schema.py`. Rationals are strings `"p/q"` in lowest terms with a positive
denominator (`"0/1"` for zero); dates are `YYYY-MM-DD`.

- `LogsDecision`: `schema_version: "arci-logs/1"`, `arci_version`, `example: bool`,
  `utc_offset_minutes: int`, `project_filtered: bool`, `tools: list[ToolDecision]` (Claude
  Code first, then Codex; only requested tools), `exit_code`, `seal` (`hash_record` of the
  record without `seal`).
- `ToolDecision`: `tool: "claude-code" | "codex"`, `result: "REAL_DROP" | "NO_DROP" |
  "CANNOT_TELL" | "ERROR"`, `reason: ReasonCode`, `model: str | None`, `effort: str | None`
  (rendered names), `other_settings: int`, `split_date: date | None`,
  `before: Period | None`, `after: Period | None`, `measures: list[MeasureDecision]` (in the
  order of the contract's table; empty when there is no selected setting),
  `context: ContextCounts | None`, `counters: ReaderCounters`,
  `day_table_sha256: str | None`. With ERROR or `no_usable_setting`, `model`, `effort`,
  `before`, `after`, `context` and `day_table_sha256` are null and `measures` is empty;
  `split_date` is kept when it is known. When the split is later than the newest day,
  `after` is null and the after-day lists are empty.
- `Period`: `first_day`, `last_day` (calendar bounds of the period).
- `MeasureDecision`: `id`, `worse: "lower" | "higher"`, `margin` (the adverse change:
  `"1/4"`, `"1/10"`, `"3/100"`), `before_days` and `after_days` (`list[DayValue]`, ascending
  by day, no day twice), `median_before`, `median_after` (median of the day values; an even
  number of days gives the mean of the two middle ones; null with no usable day),
  `p_streak`, `p_real`, `u_none`, `p_none`, `finding: "streaky" | "real_drop" | "no_drop" |
  "cannot_tell" | "too_few_days"`. Which test fields are filled is fixed by the finding and
  enforced by a validator, together with the thresholds: `too_few_days`: none; `streaky`:
  `p_streak` only; `real_drop`: `p_streak` and `p_real`; `no_drop` and `cannot_tell`: all
  four.
- `DayValue`: `day`, `count: int`, `value` (in the measure's own units, not negated).
  `count` is the number of positive counts for `reasoning_tokens` and
  `repeated_value_share`, of known counts for `no_reasoning_share`, and of file-edit results
  for `edit_failure_share`.
- `ContextCounts`, over all responses of the tool in the window after the `--project`
  filter, before the main-thread and setting filters: `client_versions_before`,
  `client_versions_after`, `client_versions_both`, `workdirs_before`, `workdirs_after`
  (counts of distinct values), `subagent_share_before`, `subagent_share_after` (rationals;
  null when the period has no response).
- `ReaderCounters`: `files_read`, `files_unread_compressed`, `files_unreadable`,
  `files_outside_project`, `lines`, `lines_not_json`, `lines_unknown_type`,
  `lines_lacking_field`, `records_in_future`, `responses`, `responses_duplicate`,
  `responses_without_reasoning`, `responses_without_setting`, `edits_denied`,
  `edits_unmatched`.
- `ReasonCode`: `real_drop`, `no_drop`, `not_enough_evidence`, `too_few_days`,
  `streaky_days`, `no_usable_setting`, `no_logs`, `read_error`, `format_not_recognised`.
- `day_table_sha256` is `hash_record` of `{method: "arci-logs/1", tool, model, effort,
  split_date, before, after, alpha_real: "1/120", alpha_none: "1/40", measures: [{id, margin,
  before_days, after_days}]}` in the fixed orders above, with the rendered model and effort.

Rendering: reasoning counts as integers rounded half up; shares as percentages with one
decimal; the change of `reasoning_tokens` as a whole percentage of the before median; the
change of a share in percentage points with one decimal; margins as `25%`, `10 pts`, `3 pts`;
a value that is not available as `-`. Rendered numbers decide nothing.

## Fixed texts

`{}` marks a value. Numbers are rendered from the record; nothing else varies.

- **F1 header:** `realornoise {version} · reads local session logs · sends nothing · writes nothing unless asked`
- **F2 scope:** `{Tool} · {model} · effort {effort} · main thread · days at UTC{+hh:mm}`
- **F3 periods:** `before  {first} to {last}` and `after   {first} to {last}   split {s}`; with no
  after-days the second line is `after   no days   split {s}`
- **F4 result (per tool):** `RESULT: REAL DROP` / `RESULT: NO DROP` / `RESULT: CANNOT TELL` /
  `RESULT: ERROR`. The process exit code prints once, on the last line: `exit {code}`.
- **F5 reasons:**
  - `real_drop`: `In at least one recorded measure, the days after the split moved toward worse by more than a chance ordering of your days explains.`
  - `no_drop`: `No recorded measure moved toward worse by its margin or more. This does not say anything improved.`
  - `not_enough_evidence`: `The days are too few or too variable to tell a shift from noise.`
  - `too_few_days`: `Too few usable days for every measure (5 needed after the split, 10 before).`
  - `streaky_days`: `Your earlier days come in streaks in a recorded measure, so this comparison cannot tell a streak from a drop.`
  - `no_usable_setting`: `No model and effort setting has a response in the window.`
  - `no_logs`: `No session logs found for {Tool}. Looked under {default}. Use {flag} DIR, or try: realornoise --example`
    where `{default}` and `{flag}` are `~/.claude/projects (or CLAUDE_CONFIG_DIR)` and
    `--claude-dir`, or `~/.codex (or CODEX_HOME)` and `--codex-dir`
  - `read_error`: `Session log files could not be read.`
  - `format_not_recognised`: `Log files were found, but this version could not recover a response from them.`
  - usage errors (exit 3): `--since needs a date as YYYY-MM-DD.` · `--since can be at most 83 days before the newest day in the logs.` · `Requested output could not be written.`
- **F6 table:** header `measure, median day` / `before (days)` / `after (days)` / `change` /
  `finding`; each period cell is the median followed by the number of usable days in
  brackets; row names `reasoning tokens per response`, `responses with no reasoning`,
  `file edits that failed`, `reasoning at one repeated value`; findings `real drop`,
  `no drop (margin {margin})`, `cannot tell`, `too few days`, `days come in streaks`.
- **F7 context:** `Context counts; differences between the periods are not tested:` then
  `client versions {a} before, {b} after, {c} in both · working directories {d} before, {e} after · sub-agent share {f}% -> {g}%`
- **F8 streak check:** `Streak check: {k} of {K} tested measures were not flagged.` (`K` measures with
  enough days, `k` of them with `p_streak > 1/10`)
- **F9 unread:** `{k} compressed Codex files were not read (Python 3.14 is needed); the result uses the rest.`
- **F10 limits (every tool with REAL DROP, NO DROP or CANNOT TELL):**
  `This shows what your logs recorded. It does not establish answer quality, a cause, or a change`
  `to the model: your tasks, prompts, projects or client version may have changed.`
  `For this tool and this one comparison: if nothing shifted, REAL DROP appears at most 2.5% of the`
  `time; if a measure moved toward worse by its margin or more, NO DROP appears at most 2.5% of the`
  `time. Both hold only if: (1) days are interchangeable when nothing changes; (2) any date, model,`
  `effort or project you gave was not chosen from these logs; (3) a change moves every day alike;`
  `(4) a change leaves the same days, setting and reference value in use. None of these is checked,`
  `and the streak check does not prove them. Running this again and again until a result appears`
  `is not covered.`
- **F11 method:** `method arci-logs/1 · exact rank tests · no random numbers · day-table digest {12 hex}`
- **F12 next:** `Share: --markdown FILE · --html FILE · --json FILE      Stronger evidence: arci verdict, arci run`
- **F13 example label:** `Example data, generated. Not anyone's logs.`
- **F14 other settings:** `Not compared: {k} other model or effort settings.`
- **F15 skipped lines:** `{k} lines lacked a needed field and were left out.`
- **F16 future records:** `{k} records stamped later than now were left out.`
- **F17 unreadable files:** `{k} files could not be read; the result uses the rest.`

The Markdown block carries F2 in bold with the result, the F6 table, one line with the split
date and F7's counts, and one closing line that depends on the result:
- REAL DROP: `One person's logs. Evidence of movement toward worse in a recorded measure; this establishes no cause and says nothing about answer quality.`
- NO DROP: `One person's logs. No recorded measure moved toward worse by its margin; this does not say anything improved.`
- CANNOT TELL: `One person's logs. Not enough to tell a shift from noise.`
- ERROR: the tool name, `ERROR` and the F5 text, and nothing else.

followed, except for ERROR, by: `Wrong REAL DROP and wrong NO DROP are each at most 2.5% for
this tool and one comparison, only under unchecked assumptions (interchangeable days; no date,
model, effort or project chosen from these logs; a uniform shift; the same days, setting and
reference value in use). arci-logs/1, digest {12 hex}. Yours: uvx realornoise`.

## Files

New: `src/arci/logs/{__init__,records,discover,claude_code,codex,measures,rank_test,decide,
schema,report,html,cli}.py`, `src/arci/logs/example/`, `src/arci/html_base.py` (helpers moved
unchanged from `html_report.py`), `bench/make_log_example.py`, `bench/selfcheck_logs.py`,
`docs/STATISTICS_LOGS.md`, `docs/LOG_FORMATS.md`, `docs/recipes/logs.md`,
`tests/acceptance/test_logs.py`, `tests/unit/logs/`, `packages/realornoise/`,
`plugins/realornoise/`, `integrations/codex/skills/realornoise/`.

Changed: `src/arci/cli.py` (dispatch and help), `src/arci/html_report.py`,
`src/arci/__init__.py`, `README.md`, `CHANGELOG.md`, `CITATION.cff`, `docs/COMPATIBILITY.md`,
`docs/ROADMAP.md`, `docs/RELEASING.md`, `docs/results/order-desk-study.md` (one link),
`.github/workflows/{release,ci,ttfv-reference}.yml`, `.github/scripts/wheel_smoke.sh`.

Re-freeze at the release: `pyproject.toml`, `uv.lock`, `AGENTS.md` (rule 1 names
`FROZEN.sha256` as the list of record). Newly pinned: this record, `docs/STATISTICS_LOGS.md`,
`src/arci/logs/schema.py`, `tests/acceptance/test_logs.py`.

The README first screen changes (three steps, the log step first), so this record supersedes
0014 for that screen from 2.3.0; the 250-word limit of 0014 stays.

## Not built

A scan over split dates; a comparison of two models; a stored day table that outlives log
retention; a plausible range for the change; other coding agents; Windows paths checked on a
real machine; log formats older than the client versions listed in `docs/LOG_FORMATS.md`;
usage-limit or cost measures; anything that sends data anywhere.
