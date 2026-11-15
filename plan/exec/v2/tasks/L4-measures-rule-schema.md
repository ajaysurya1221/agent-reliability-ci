# L4: day table, measures, the rule, and the sealed record

Read `/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/tasks/L-CONTRACT.md` and follow
its rules. The behaviour is the statistics contract in full ("What is compared", "Measures",
"The tests", the result ladder, the exit code) and record 0016, "Record model". Read both in
their current text before writing anything; where `L-CONTRACT.md` shows an older signature,
the two drafts and this brief win. `rank_test.py` and the readers exist; use them, do not
edit them. `records.py` gives `ReadResult` with `responses`, `edits`, `models`, `efforts`,
`model_order`, `effort_order`, `counters`.

## You own

- `src/arci/logs/schema.py`, `src/arci/logs/measures.py`, `src/arci/logs/decide.py`
- `tests/unit/logs/test_schema.py`, `tests/unit/logs/test_measures.py`,
  `tests/unit/logs/test_decide.py`

## Build

1. `schema.py`: the pydantic models of "Record model", exactly those names, fields and
   closed values; `extra="forbid"`, frozen; rationals and dates as validated strings
   (`"p/q"` lowest terms, positive denominator; `YYYY-MM-DD`). Validators enforce: which
   test fields are filled for each finding, and that the finding agrees with the stored
   p-values and thresholds (`p_streak ≤ 1/10` exactly when `streaky`; `real_drop` exactly
   when not streaky and `p_real ≤ 1/120`; `no_drop` only when `p_none ≤ 1/40`); the null
   rules for ERROR and `no_usable_setting`; ascending days with no repeat; the result and
   reason pairs the ladder allows; `exit_code` equal to the mapping. Provide
   `seal(decision_without_seal) -> LogsDecision` and `verify_seal(decision) -> bool` using
   `arci.hashing.hash_record`, following `src/arci/outcome_schema.py`. Model and effort
   fields accept only rendered names: a string that `records.render_model` (or the effort
   list) accepts, or `model-N` / `effort-N`.
2. `measures.py`:
   - `fraction_str(x) -> str` and `parse_fraction(s) -> Fraction` for the canonical form.
   - `build(result, *, utc_offset, now, since, model, effort) -> ToolTable` implementing "What
     is compared": day assignment at the fixed offset; `N`, split and periods; setting
     selection by pooled main-thread counts in the window with ties by
     (`model_order`, `effort_order`) position; `--model` and `--effort` given as rendered
     names (a name that matches no setting gives no selected setting); the four measures'
     day values and usable-day rules; `v*`; `ContextCounts` as defined in the record model;
     `other_settings`. Only responses and edits with `in_project` true take part. A usage
     problem (a `since` more than 83 days before `N`) raises a small `UsageError` with a
     code, never free text.
   - Rendered names: a setting's model is its `models[i]` when not `None`, else `model-N`
     where `N` is its rank (from 1) among unknown models in `model_order`; the same for
     effort. Two settings never share a rendered name.
   - `ToolTable` is a frozen dataclass holding everything `decide.py` and the record need;
     no raw string from a log.
3. `decide.py`:
   - `decide_tool(table, counters) -> ToolDecision`: per-measure findings and the ladder,
     with exactly the fields filled that the finding allows (a `real_drop` computes no
     no-drop test).
   - `error_tool(tool, reason, counters) -> ToolDecision` for `no_logs`, `read_error`,
     `format_not_recognised`.
   - `exit_code(tools) -> int` and `day_table_digest(table) -> str` per the record model.
   - The constants `ALPHA_REAL = Fraction(1, 120)`, `ALPHA_NONE = Fraction(1, 40)`,
     `ALPHA_STREAK = Fraction(1, 10)`, the margins, `MIN_AFTER = 5`, `MIN_BEFORE = 10`,
     `BEFORE_DAYS = 84`, `DEFAULT_AFTER_DAYS = 14` live here and nowhere else.

## Tests

- Hand-made `ReadResult`s (build `Response` and `EditResult` objects directly) for: each
  rung of the ladder and each reason code; a measure without enough days not blocking a
  real drop from another; a streaky measure blocking NO DROP but not another measure's
  REAL DROP; an after period with every reasoning count 0 (`reasoning_tokens` has no usable
  after-day; `no_reasoning_share` can still be a real drop); `since` later than `N`;
  `since` too early; two settings with equal counts (tie by order); a named model that does
  not exist; unknown model and effort rendered as `model-1`, `effort-1` and kept apart;
  unknown reasoning counts never counted as 0; edits attributed to their own setting;
  `v*` ties to the smallest count; even-count medians as exact means.
- Each margin move in exact arithmetic (no float, no rounding): a before-day of 5 tokens
  moves to `15/4`.
- Schema: every validator rejects a record that breaks its rule; the seal round-trips;
  changing any field breaks `verify_seal`; JSON output of a decision contains only numbers,
  booleans, nulls, dates, rationals and closed-list or rendered names (walk it).
- Determinism: the same inputs in a different response order give the same record and
  digest.

## Done when

`.venv/bin/pytest tests/unit/logs -q` passes; ruff format, ruff check and basedpyright are
clean on your files; `shasum -a 256 -c FROZEN.sha256` still passes.

## First, three small reader changes (decision D-14)

For these only you also own `src/arci/logs/records.py`, `discover.py`, `claude_code.py`,
`codex.py` and their tests. Do them before the L4 work and keep the existing tests passing.

1. `render_model`: in addition to the current rules, the id has at most six parts, and at
   most three of them are plain numbers (one or two digits). The full grammar is in record
   0016, decision 6. `gpt-12-34-56-78-87-65-43-21` and `gpt-1-2-3-4` return `None`;
   `claude-opus-5-5`, `gpt-5.3-codex-spark`, `claude-sonnet-4-5-20250929` pass.
   `MODEL_WORDS` and `EFFORTS` must equal the lists in the record exactly.
2. A response or edit-result record whose timestamp has no zone is counted in a new counter
   `records_without_timezone` (not in `lines_lacking_field`) and left out. `ReaderCounters`
   has exactly the fields of the record model, in that order.
3. `discover.claude_files` and `discover.codex_files` return paths sorted by the text of
   their path relative to the root written with `/` (`relative_to(root).as_posix()`), not by
   `Path` ordering. Add a test where the two orders differ (`a-b/x.jsonl` and `a/x.jsonl`).
