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

3. **The rule** is the one in `docs/STATISTICS_LOGS.md`: one tool, one model and effort, main
   thread; usable days before and after a split date; three gating measures per tool; an exact
   one-sided Mann-Whitney test per measure with strict counting, at `(1/40)/3` for a real drop
   and at `1/40`, after moving the before-days by the margin, for a no-drop; a self-check
   inside the before period; no random numbers.

4. **Defaults.** Split date: 13 days before the newest day found, so the after period is 14
   days. Before period: 84 days. Minimum usable days: 5 after, 10 before. A usable day has 20
   or more responses (10 or more edit results for the edit measure). `--since DATE` replaces
   the split date. No scan over dates, no comparison of two models, no stored history: each is
   left out of this version and named in "Not built".

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
   - Readers return records made of numbers, timestamps and names from closed lists. A model
     id is kept only if it matches `^[a-z0-9][a-z0-9._-]{1,48}$`, else `other`; a client
     version only if it matches `^[0-9]+(\.[0-9]+){1,3}$`, else `other`. Working directories
     are never kept: they are reduced to a count of distinct values and, for `--project`, to a
     yes or no.
   - No exception text, warning or output may carry a string read from a log. Per-line faults
     are counted.
   - Tests: a canary token in every free string of synthetic logs must appear in no output and
     no error; an audit hook fails the run on a socket, a subprocess or a write outside the
     named paths; a walk of the JSON output accepts only numbers, booleans, nulls, dates,
     rationals as strings, closed-list names and sanitised ids; an import allow-list covers
     `src/arci/logs/`.

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
  `tools: list[ToolDecision]`, `exit_code`, `seal`.
- `ToolDecision`: `tool: "claude-code" | "codex"`, `result: "REAL_DROP" | "NO_DROP" |
  "CANNOT_TELL" | "ERROR"`, `reason: ReasonCode`, `model`, `effort`, `split_date`,
  `before: Period`, `after: Period`, `measures: list[MeasureDecision]`,
  `self_check: "none" | "shift_found" | "not_run"`, `context: ContextCounts`,
  `counters: ReaderCounters`, `day_table_sha256`.
- `Period`: `first_day`, `last_day`, `usable_days: int`.
- `MeasureDecision`: `id`, `worse: "lower" | "higher"`, `margin`, `before_days: list[DayValue]`,
  `after_days: list[DayValue]`, `typical_before`, `typical_after` (median of day values),
  `u_real`, `p_real`, `u_none`, `p_none`, `finding: "real_drop" | "no_drop" | "cannot_tell" |
  "too_few_days"`.
- `DayValue`: `day`, `responses: int`, `value`.
- `ContextCounts`: client versions before / after / in both; distinct working directories
  before / after; sub-agent share of responses before / after.
- `ReaderCounters`: files read, files not read (compressed), lines, unparseable lines, lines
  of unknown type, responses, responses without a reasoning size.
- `ReasonCode`: `real_drop`, `no_drop`, `not_enough_evidence`, `too_few_days`,
  `self_check_shift`, `no_logs`, `format_not_recognised`, `no_usable_model`.

## Fixed texts

`{}` marks a value. Numbers are rendered from the record; nothing else varies.

- **F1 header:** `realornoise {version} · reads local session logs · sends nothing · writes nothing unless asked`
- **F2 scope:** `{Tool} · {model} · effort {effort} · main thread · days in local time`
- **F3 periods:** `before  {first} to {last}   {n} usable days (20 or more responses)` and
  `after   {first} to {last}   {m} usable days`
- **F4 result:** `RESULT: REAL DROP (exit 1)` / `RESULT: NO DROP (exit 0)` /
  `RESULT: CANNOT TELL (exit 2)` / `RESULT: ERROR (exit 3)`
- **F5 reasons:**
  - `real_drop`: `At least one measure moved toward worse by more than your day-to-day variation explains.`
  - `no_drop`: `No measure moved toward worse by its margin or more. This does not say anything improved.`
  - `not_enough_evidence`: `The days are too few or too variable to tell a shift from noise.`
  - `too_few_days`: `Too few usable days: {m} after the split (5 needed), {n} before (10 needed).`
  - `self_check_shift`: `A shift of the same kind shows inside the before period, so a real drop is not claimed.`
  - `no_logs`: `No session logs found. Looked under {claude default} and {codex default}. Use --claude-dir DIR or --codex-dir DIR, or try: realornoise --example`
    (the two defaults are fixed strings naming the environment variable, never a resolved path)
  - `format_not_recognised`: `These logs are not in a format this version reads ({n} of {N} lines of a known type lack a required field).`
  - `no_usable_model`: `No model has a usable day in the after period.`
- **F6 table:** header `measure, typical day` / `before` / `after` / `change` / `finding`;
  row names `reasoning tokens per response`, `responses with no reasoning`,
  `file edits that failed`, `reasoning at one repeated value`; findings `real drop`,
  `no drop (margin {margin})`, `cannot tell`, `too few days`.
- **F7 context:** `Also different between the periods, not tested, each could be the cause:`
  then `client versions {a} before, {b} after, {c} in both · working directories {d} before, {e} after · sub-agent share {f}% -> {g}%`
- **F8 self-check:** `Same test inside the before period (first half against second half): no shift found.`
- **F9 unread:** `{k} compressed Codex files were not read (Python 3.14 is needed); the result uses the rest.`
- **F10 limits (every run with a result):**
  `This shows what your logs recorded, not why. Your tasks, prompts, projects and client changed too.`
  `If nothing shifted, REAL DROP appears at most 2.5% of the time. If a measure fell by its margin or`
  `more, NO DROP appears at most 2.5% of the time. Both hold only if days are interchangeable when`
  `nothing changes, the split date was not chosen from these numbers, and a shift moves every day alike.`
  `None of these is checked.`
- **F11 method:** `method arci-logs/1 · exact rank test · no random numbers · day-table digest {12 hex}`
- **F12 next:** `Share: --markdown FILE · --html FILE · --json FILE      Stronger evidence: arci verdict, arci run`
- **F13 example label:** `Example data, generated. Not anyone's logs.`
- **F14 other models:** `Not compared: {k} other model or effort settings with fewer responses.`

The Markdown block carries F2 in bold with the result, the F6 table with day counts in its
header, one line with the split date and F7's counts, and one line: `One person's logs. A shift
in recorded measures, not its cause. Wrong REAL DROP and wrong NO DROP are each at most 2.5%,
only under unchecked assumptions (days interchangeable, split date not chosen from the data,
uniform shift). arci-logs/1, digest {12 hex}. Yours: uvx realornoise`.

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
