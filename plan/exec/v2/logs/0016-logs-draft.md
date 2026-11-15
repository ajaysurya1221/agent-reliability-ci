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
   margin, for a no-drop; a self-check inside the before period whose firing ends in CANNOT
   TELL; no random numbers. The setting is chosen from response counts over both periods
   together, never from one period: choosing by the after period alone can make a wrong REAL
   DROP certain (review finding 1).

4. **Defaults.** Split date: 13 days before the newest day found, so the after period is 14
   days. Before period: 84 days. A measure is tested with at least 5 usable after-days and 10
   usable before-days; the usable-day rule is per measure (statistics contract, "Measures").
   `--since DATE` replaces the split date; a malformed date is a usage error with fixed text
   and exit 3; a date after the newest day gives CANNOT TELL with no after-days. No scan over
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
   - **Model names are rendered from a closed vocabulary, never copied.** A model id is split
     at `-`, `.` and `_`; it is shown as written only when every part is a number of at most
     8 digits or a word in the list in `records.py` (vendor and family words such as `claude`,
     `opus`, `sonnet`, `haiku`, `fable`, `gpt`, `codex`, `astra`, `mini`, `preview`). Any
     other id is shown as `model-1`, `model-2`, ... numbered by response count in the window,
     and is still compared. Effort is one of a closed list or `other`. A private deployment
     name therefore cannot reach an output (review finding 4).
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
   - **Reading faults.** A tool's logs are `format_not_recognised` when files were found and
     no response could be recovered from them. Otherwise lines that are not JSON, lines of an
     unknown type, and lines of a known type that lack a needed field are counted and left
     out, and notice F15 prints when the last kind exceeds 5% of the lines of that type.

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
`outcome_schema.py`. Rationals are strings `"p/q"` in lowest terms; dates are `YYYY-MM-DD`.

- `LogsDecision`: `schema_version: "arci-logs/1"`, `arci_version`, `example: bool`,
  `utc_offset_minutes`, `tools: list[ToolDecision]` (Claude Code first, then Codex),
  `exit_code`, `seal` (`hash_record` of the record without `seal`).
- `ToolDecision`: `tool: "claude-code" | "codex"`, `result: "REAL_DROP" | "NO_DROP" |
  "CANNOT_TELL" | "ERROR"`, `reason: ReasonCode`, `model`, `effort`, `other_settings: int`,
  `split_date`, `before: Period`, `after: Period`, `measures: list[MeasureDecision]` (in the
  order of the contract's table), `self_check: "no_shift" | "shift_found" | "not_run"`,
  `context: ContextCounts`, `counters: ReaderCounters`, `day_table_sha256`. For ERROR, and for
  a tool with no usable setting, every field without a value is null; no date or p-value is
  invented.
- `Period`: `first_day`, `last_day` (calendar bounds of the period).
- `MeasureDecision`: `id`, `worse: "lower" | "higher"`, `margin`, `before_days` and
  `after_days` (`list[DayValue]`, ascending by day, no day twice), `median_before`,
  `median_after` (median of the day values; an even number of days gives the mean of the two
  middle ones; null with no usable day), `p_real`, `u_none`, `p_none` (null when not tested),
  `finding: "real_drop" | "no_drop" | "cannot_tell" | "too_few_days"`.
- `DayValue`: `day`, `count: int` (the denominator of that measure on that day), `value`
  (in the measure's own units, not negated).
- `ContextCounts`: client versions before / after / in both; distinct working directories
  before / after; sub-agent share of responses before / after.
- `ReaderCounters`: files read, files not read (compressed), lines, lines that are not JSON,
  lines of unknown type, lines lacking a needed field, records stamped in the future,
  responses, responses without a reasoning count, edit results denied, edit results unmatched.
- `ReasonCode`: `real_drop`, `no_drop`, `not_enough_evidence`, `too_few_days`,
  `self_check_shift`, `no_logs`, `format_not_recognised`, `no_usable_setting`.
- `day_table_sha256` is `hash_record` of `{method, tool, model, effort, split_date, before,
  after, alpha_real, alpha_none, measures: [{id, margin, before_days, after_days}]}` in the
  fixed orders above.

Rendering: reasoning counts as integers rounded half up; shares as percentages with one
decimal; the change of `reasoning_tokens` as a whole percentage of the before median; the
change of a share in percentage points with one decimal; margins as `25%`, `10 pts`, `3 pts`.
Rendered numbers decide nothing.

## Fixed texts

`{}` marks a value. Numbers are rendered from the record; nothing else varies.

- **F1 header:** `realornoise {version} · reads local session logs · sends nothing · writes nothing unless asked`
- **F2 scope:** `{Tool} · {model} · effort {effort} · main thread · days in local time`
- **F3 periods:** `before  {first} to {last}` and `after   {first} to {last}   split {s}`
- **F4 result (per tool):** `RESULT: REAL DROP` / `RESULT: NO DROP` / `RESULT: CANNOT TELL` /
  `RESULT: ERROR`. The process exit code prints once, on the last line: `exit {code}`.
- **F5 reasons:**
  - `real_drop`: `In at least one recorded measure, the days after the split sit lower than the days before by more than a chance ordering of your days explains.`
  - `no_drop`: `No recorded measure moved toward worse by its margin or more. This does not say anything improved.`
  - `not_enough_evidence`: `The days are too few or too variable to tell a shift from noise.`
  - `too_few_days`: `Too few usable days for every measure (5 needed after the split, 10 before).`
  - `self_check_shift`: `A shift of the same kind shows inside the before period, so a real drop is not claimed.`
  - `no_logs`: `No session logs found. Looked under ~/.claude/projects (or CLAUDE_CONFIG_DIR) and ~/.codex (or CODEX_HOME). Use --claude-dir DIR or --codex-dir DIR, or try: realornoise --example`
  - `format_not_recognised`: `Log files were found, but this version could not recover a response from them.`
  - `no_usable_setting`: `No model and effort setting has a usable day in the window.`
  - usage error: `--since needs a date as YYYY-MM-DD.`
- **F6 table:** header `measure, median day` / `before (days)` / `after (days)` / `change` /
  `finding`; each period cell is the median followed by the number of usable days in
  brackets; row names `reasoning tokens per response`, `responses with no reasoning`,
  `file edits that failed`, `reasoning at one repeated value`; findings `real drop`,
  `no drop (margin {margin})`, `cannot tell`, `too few days`.
- **F7 context:** `Context counts; differences between the periods are not tested:` then
  `client versions {a} before, {b} after, {c} in both · working directories {d} before, {e} after · sub-agent share {f}% -> {g}%`
- **F8 self-check:** `Same test inside the before period (first half against second half): no shift found.`
- **F9 unread:** `{k} compressed Codex files were not read (Python 3.14 is needed); the result uses the rest.`
- **F10 limits (every tool with a result):**
  `This shows what your logs recorded. It does not establish answer quality, a cause, or a change`
  `to the model: your tasks, prompts, projects or client version may have changed.`
  `For this tool: if nothing shifted, REAL DROP appears at most 2.5% of the time; if a measure moved`
  `toward worse by its margin or more, NO DROP appears at most 2.5% of the time. Both hold only if`
  `days are interchangeable when nothing changes; the split date, model and effort were not chosen`
  `from these numbers; a shift moves every day alike; and a shift leaves the same days usable.`
  `None of these is checked.`
- **F11 method:** `method arci-logs/1 · exact rank tests · no random numbers · day-table digest {12 hex}`
- **F12 next:** `Share: --markdown FILE · --html FILE · --json FILE      Stronger evidence: arci verdict, arci run`
- **F13 example label:** `Example data, generated. Not anyone's logs.`
- **F14 other settings:** `Not compared: {k} other model or effort settings.`
- **F15 skipped lines:** `{k} lines of a known type lacked a needed field and were left out.`
- **F16 future records:** `{k} records stamped later than now were left out.`

The Markdown block carries F2 in bold with the result, the F6 table, one line with the split
date and F7's counts, and one closing line that depends on the result:
- REAL DROP: `One person's logs. The after-days sit lower in a recorded measure; this shows no cause and says nothing about answer quality.`
- NO DROP: `One person's logs. No recorded measure moved toward worse by its margin; this does not say anything improved.`
- CANNOT TELL: `One person's logs. Not enough to tell a shift from noise.`

followed in each case by: `Wrong REAL DROP and wrong NO DROP are each at most 2.5% for this
tool, only under unchecked assumptions (interchangeable days; split, model and effort not
chosen from the data; uniform shift; same usable days). arci-logs/1, digest {12 hex}.
Yours: uvx realornoise`.

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
