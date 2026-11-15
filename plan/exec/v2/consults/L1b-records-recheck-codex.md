1. **P1 — Preserve the pooled reference under the counterfactual. Earlier #2: PARTLY.**  
   Where: [STATISTICS_LOGS-draft.md:121](/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/logs/STATISTICS_LOGS-draft.md:121), Claim 2 proof at line 161.

   A4 preserves eligibility and setting selection, but not `v*`. Changing `v*` also changes the **before-day values**, invalidating the proof’s exchangeability step.

   Concrete counterexample: randomly order 14 ordinary days and one special day across 10 before-days and five after-days. Each ordinary day has 20 positive counts, all `100`. The special day has 10,000 positive counts: 100 occurrences of each integer `50..99` and `101..140`, plus 1,000 occurrences of `1000`. Every daily median is `100`; the counterfactual pooled mode is `1000`.

   When the special day lands after the split, change the after-days so their shares at `100` are `0.1` on ordinary days and `0.2` on the special day, preserving response counts and medians. Distribute the remaining counts so `100` becomes the pooled mode. Every after-day’s repeated-value measure has increased by exactly `0.1` relative to its counterfactual value. Nevertheless, the observed before-shares are all `1`, and the after-shares are `0.1` or `0.2`. All three measures have `p_streak=1`, `p_real=1`, and `p_none=1/3003`. The result is NO DROP.

   The special day lands after the split with probability **1/3**, exceeding 2.5%. A corresponding transformation when it lands before preserves the same uniform after-day shift.

   **Exact change:** append to A4, and repeat in both output assumption statements:

   > The change also preserves the pooled reference value `v*` and every before-day aggregate. The retained counterfactual day values, computed using that same setting and reference value, must be jointly exchangeable. Claim 2 does not cover changes that alter this reference.

2. **P1 — Replace the model-name grammar with complete-name lookup. Earlier #4: PARTLY.**  
   Where: [0016-logs-draft.md:68](/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/logs/0016-logs-draft.md:68).

   `gpt-12345678-87654321` passes the proposed vocabulary rule and is printed unchanged. Arbitrarily many numeric components remain a channel for private identifiers. Separately, mapping every unknown effort to `other` merges different settings, contradicting the single-setting comparison.

   **Exact change:**

   > Render a recognized complete model identifier through a finite lookup table whose output values are code constants. Never reconstruct or copy an identifier from allowed components. Keep distinct unknown model and effort identities separate internally and render them as opaque `model-N` and `effort-N` labels. Missing identities are excluded from setting selection. Raw identifiers never enter output, exceptions or the sealed record.

   Add `gpt-12345678-87654321` as a canary and two distinct unknown efforts as a non-pooling test.

3. **P1 — Close the remaining selection loopholes. Earlier #1: PARTLY.**  
   Where: [STATISTICS_LOGS-draft.md:30](/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/logs/STATISTICS_LOGS-draft.md:30), A1–A2 at lines 106–113.

   Automatic pooled-count selection is corrected. However, A2 only prohibits choosing overrides by looking at “these measures.” Choosing `--model` using **after-period response counts** still permits the earlier 3,003-model counterexample: the selected model has `p_real=1/3003`, a constant baseline, and false REAL DROP probability one.

   “The window … is treated as fixed” also does not establish exchangeability after selecting its endpoint from availability. Unknown-model numbering has no count-tie rule, making the rendered-name selection rule incomplete.

   **Exact changes:**

   > User-supplied split dates and model, effort and project filters must be fixed independently of the evaluated records, or selected by a prespecified rule invariant to period-label permutations. This restriction includes response counts and availability.

   > A1 is an assumption about the conditional no-change distribution after the stated window-selection procedure; treating the realized window as fixed does not establish it.

   > Break pooled setting-count ties by the internal `(raw_model, raw_effort)` lexical order. Assign opaque labels deterministically from that order. Never output the internal identifiers.

4. **P2 — Remove the unsupported guard figures and 95% power gate. Earlier #12: PARTLY.**  
   Where: [STATISTICS_LOGS-draft.md:182](/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/logs/STATISTICS_LOGS-draft.md:182), check 4 at line 202; [orchestrator_guard_runs.py:37](/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/spikes/L0-logs/orchestrator_guard_runs.py:37).

   The quoted simulation applies a **global veto** when any measure is streaky. The revised contract withholds individual measures. Its quoted guard rates therefore describe a different rule.

   For 42 distinct exchangeable before-days, the proposed runs test flags `R≤17` with probability **0.07887868767**. With only the reasoning measure shifted and the other measures constant, power cannot exceed **92.1121%**, even with perfect separation. Allowing two valid null measures to reject raises the union-bound ceiling only to **93.7788%**. A finite simulation can exceed these rates by chance; it does not justify a 95% population-power requirement.

   **Exact changes:**

   > The historical guard figures used a global veto and do not estimate this version’s per-measure rule. No final-rule guard rate is claimed until regenerated.

   Replace check 4 with:

   > Report final-rule power for the 45% reasoning-token shift at 14/42 and log standard deviation 0.40, including the generator, seed, simulation count and sampling uncertainty. The former 95% threshold does not apply to the revised rule.

5. **P2 — Specify canonical records and null states. Earlier #10: PARTLY.**  
   Where: [0016-logs-draft.md:114](/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/logs/0016-logs-draft.md:114).

   “Null when not computed” permits different sealed records for identical inputs: one implementation can compute `p_none` after REAL DROP while another short-circuits. ERROR fields are declared non-nullable but later permitted to be null. Median `DayValue.count` has no defined “denominator.” Context counters have descriptions rather than field names or counting populations.

   **Exact additions:**

   > For `too_few_days`, all four test fields are null. For `streaky`, only `p_streak` is populated. For `real_drop`, populate `p_streak` and `p_real`; `u_none` and `p_none` are null. For `no_drop` and `cannot_tell`, populate all four. Validators enforce these states and their thresholds.

   > `DayValue.count` is the positive-response count for `reasoning_tokens` and `repeated_value_share`, the known-count response count for `no_reasoning_share`, and the eligible-result count for `edit_failure_share`. Canonical rationals have positive denominators; zero is `"0/1"`.

   > The digest’s `method` is `"arci-logs/1"`, `alpha_real` is `"1/120"`, and `alpha_none` is `"1/40"`. These are derived constants, not omitted record fields.

   Further cross-document gaps requiring explicit text:

   - Decision 5 promises counts of unknown **keys**, but `ReaderCounters` has none. Add `unknown_keys`.
   - F15 requires counts per known line type; aggregate counters cannot reproduce its threshold. Add closed-type maps `known_lines_by_type` and `missing_fields_by_type`.
   - `--project` is promised as an output boolean, but no field holds it. Add `project_filtered: bool`.
   - Define exact `ContextCounts` keys and whether they count the selected setting or all settings. Use all recognized responses for the selected tool/project/window, before main-thread and setting filtering; sub-agent shares are null when their denominator is zero.
   - F1–F16 and the record schema exist only in 0016. Add to the statistics contract: “The Record model and Fixed texts sections of `0016-logs-draft.md` are normative parts of this contract.” Explicitly map its `U` to `MeasureDecision.u_none`.

6. **P2 — Complete parser and I/O failure rules. Earlier #9: PARTLY.**  
   Where: [0016-logs-draft.md:55](/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/logs/0016-logs-draft.md:55), reading faults at line 85.

   Edit attribution, permission exclusions and zero-response recognition failure are now specified. Required fields, effort precedence, duplicate handling and filesystem failures remain unspecified; the referenced `docs/LOG_FORMATS.md` does not exist.

   A readable file plus an unreadable file can currently produce either a partial result or ERROR. Two copied sessions can double response counts and change usability.

   **Exact additions:**

   > Pin the response and edit formats from the L0 brief’s format sections before implementation. Claude effort uses a valid `perTurnEffort`, otherwise a valid `effort`; missing identity is excluded. Claude message fragments retain first timestamp, last usage and the union of tool blocks. Codex duplicate suppression compares the complete cumulative-usage object, not only `total_tokens`.

   > Deduplicate overlapping session copies by session and event identity; conflicting copies yield ERROR. Missing reasoning size remains unknown rather than making an otherwise supported response disappear. Reject naive timestamps.

   > A filesystem read failure yields tool ERROR with reason `read_error` and text `Session log files could not be read.` Unsupported compression is counted separately and is not a parse failure. Output-write failure prints `Requested output could not be written.` and exits 3. Exception strings and paths are never printed.

   Add the new reason and fixed text to both normative catalogs.

7. **P2 — Correct direction and assumption mismatches in output. Earlier #7: PARTLY.**  
   Where: [0016-logs-draft.md:158](/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/logs/0016-logs-draft.md:158), F10 and Markdown at lines 176–200.

   F5 and the REAL DROP Markdown sentence say a measure “sits lower.” A zero-reasoning share changing from `0` to `1` produces REAL DROP because it sits **higher**.

   F10 omits `--project`, setting preservation and the fixed-window qualification. Markdown says model and effort were not chosen “from the data,” although the default explicitly chooses them from pooled data. Both omit the repeated-use exclusion.

   **Exact replacements:**

   > F5 `real_drop`: `Evidence against interchangeable before- and after-days in at least one recorded measure, in its defined adverse direction.`

   > REAL DROP Markdown: `One person's logs. Evidence of movement toward worse in a recorded measure; this establishes no cause and says nothing about answer quality.`

   > F8: `Streak check: {k} of {K} eligible measures were not flagged.`

   Define `K` as measures with enough days and `k` as those with `p_streak>1/10`.

   Replace the assumption clauses in F10 and Markdown with the same text:

   > These per-tool bounds apply to one comparison, assuming exchangeability after window selection; independently fixed or period-label-invariant user choices; pooled automatic selection; an admissible exact uniform shift; and unchanged usable days, selected setting, pooled reference and before-day aggregates. The streak check does not establish these assumptions. Repeatedly checking until a result appears is outside these bounds.

8. **P2 — Finish result/reason mapping and empty-output templates. Earlier #11: PARTLY.**  
   Where: [STATISTICS_LOGS-draft.md:87](/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/logs/STATISTICS_LOGS-draft.md:87); [0016-logs-draft.md:137](/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/logs/0016-logs-draft.md:137).

   Process aggregation is now explicit. Remaining mismatches: `no_usable_setting` has no result-ladder branch; `no_logs` and `format_not_recognised` lack explicit result mappings; the early `too_few_days` return precedes construction of required measure findings; Markdown has no ERROR form.

   **Exact additions:**

   > Requested tools with no files yield ERROR/`no_logs`; recovered-file recognition failure yields ERROR/`format_not_recognised`. Omit unrequested tools. If no supported setting matches the comparison, yield CANNOT_TELL/`no_usable_setting`. Its text is `No supported model and effort setting matches this comparison.` Do not switch away from the selected setting because another setting has more usable days.

   > Construct every applicable measure row before selecting the tool result. A selected setting with no sufficiently observed measure yields CANNOT_TELL/`too_few_days`.

   > With no selected setting, `model`, `effort`, periods and day-table digest are null and `measures=[]`. Preserve available reader counters. Omit F2/F3/F6/F11 components requiring unavailable values; render unavailable numeric cells as `—`. ERROR Markdown contains the tool, ERROR and its fixed reason, without statistical conclusions.

   State that the documented process mapping applies after successful argument parsing and requested output writes; usage/write failures exit 3.

9. **P2 — Name the fixed-offset calendar accurately. Earlier #8: PARTLY.**  
   Where: [STATISTICS_LOGS-draft.md:21](/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/logs/STATISTICS_LOGS-draft.md:21); F2 at [0016-logs-draft.md:153](/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/logs/0016-logs-draft.md:153).

   Timestamp attribution and future exclusion are specified. The chosen calendar uses today’s offset for historical records, so F2’s “days in local time” is inaccurate across daylight-saving transitions and under `--utc`. An empty after-period still has no defined `Period` representation.

   **Exact changes:**

   > Capture the run-start instant and UTC offset once. Use calendar-date arithmetic. This is a fixed-offset calendar, not historical local civil time.

   Replace F2’s suffix with:

   > `main thread · days at fixed UTC{offset}`

   Add:

   > If `s>N`, retain `split_date=s`, set `after=null`, store empty after-day arrays, and render `after   no days`. Validate date arithmetic before subtracting the 84-day baseline; out-of-range dates produce a fixed usage error.

10. **P3 — Distinguish adverse margin from retained fraction. Earlier #6: PARTLY.**  
    Where: [STATISTICS_LOGS-draft.md:44](/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/logs/STATISTICS_LOGS-draft.md:44), A3 at line 115; [0016-logs-draft.md:125](/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/logs/0016-logs-draft.md:125).

    A3 now excludes rounding and clipping. However, the table expresses the token margin as a retained fraction `3/4`, while A3 and Claim 2 use an adverse shift `δ`. The record’s `margin` could therefore become either `"3/4"` or `"1/4"`.

    **Exact addition to both drafts:**

    > `margin` stores the adverse change: `"1/4"` for reasoning tokens, `"1/10"` for zero/repeated shares, and `"3/100"` for edit failures. The token margin transformation is `(1-margin)x`. Each measure has its own shift parameter. Claim 2 applies only where transformed counterfactual daily values are attainable: token medians remain positive half-integers and shares remain attainable fractions in `[0,1]`. Test transformations themselves are never rounded or clipped.

11. **Earlier #3: RESOLVED — The per-measure veto cannot fall through to NO DROP.**  
    Where: [STATISTICS_LOGS-draft.md:91](/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/logs/STATISTICS_LOGS-draft.md:91). A streaky measure receives `streaky`, preventing the all-three `no_drop` condition; another measure can independently establish REAL DROP. Exhaustive checking of 512 finding/veto combinations confirmed that the veto creates neither REAL DROP nor NO DROP results. This removal argument preserves valid underlying bounds; it does not repair the Claim 2 defect in item 1. **Change: none.**

12. **Earlier #5: RESOLVED — Missing values and usability are defined per measure.**  
    Where: [STATISTICS_LOGS-draft.md:44](/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/logs/STATISTICS_LOGS-draft.md:44). Unknown counts are excluded, positive-count measures require ten positives, and insufficient measures prevent NO DROP without blocking another measure’s REAL DROP. For example, ten before-days with zero-share `0` and five after-days with zero-share `1` give `p_real=1/3003`, even though the after-period token-median measure is unavailable. **Change: none.**

13. **Earlier #13: RESOLVED — The conditional rank test recovers the tied example.**  
    Where: [STATISTICS_LOGS-draft.md:64](/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/logs/STATISTICS_LOGS-draft.md:64). Eight before-values of `200`, two of `100`, and five after-values of `100` now give exactly `1/143`, below `1/120`. **Change: none.**

    Files changed: none. In-memory checks used `.venv/bin/python -I -B -c …`; their last lines included:

    ```text
    PASS: earlier finding 13 tied example p_real=1/143
    PASS: per-measure streak veto creates no REAL_DROP or NO_DROP in 512 finding/mask combinations
    PASS: all-zero after responses can give REAL_DROP via no_reasoning_share while other measures have too few days
    ```

    Separate checks verified the runs distribution across 91 small designs and the Claim 2 counterexample. These are review checks, not repository acceptance evidence. No network or session logs were accessed. An initial memory-registry lookup preceded reading the prompt’s directory prohibition; it was not used as review evidence.

OPEN FINDINGS: 10