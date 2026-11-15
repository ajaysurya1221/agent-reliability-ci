1. **OPEN — Earlier #2: privacy guarantees contradict the retained grammar.**  
   Where: [0016:69](/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/logs/0016-logs-draft.md:69), lines 79–85.

   Keeping a grammar is a permissible design choice, but `gpt-12-34-56-78-87-65-43-21` passes the stated rules and carries an entire private identifier. Unlimited short components disclose more than “a few” small numbers. Printing accepted identifiers also contradicts “No … output may carry a string read from a log” and the unconditional canary test.

   **Exact change:** replace the leakage claim and qualify the privacy/test rules:

   > Accepted model identifiers and effort names are explicit exceptions to the no-log-string rule. A matching identifier is disclosed in full, including component order, repetitions and any date component. The grammar imposes no bound on the number of components and does not guarantee identifier privacy. Non-disclosure canary tests apply to rejected identifiers and other free-string fields.

   Also replace the vocabulary’s `...` and “such as `4o`” with the complete vocabulary and token pattern; otherwise implementers still have to invent the grammar.

2. **OPEN — Earlier #7: output still states broader bounds than the contract.**  
   Where: [0016:209](/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/logs/0016-logs-draft.md:209), Markdown at line 234.

   “Moved toward worse” correctly handles both directions. However, the output omits exchangeability **after window selection**, admissibility of the exact shift, and preservation of before-day aggregates. Markdown also omits the repeated-checking exclusion. Exchangeability before selecting a window does not establish exchangeability conditional on that selection.

   **Exact change:** use this assumption paragraph in both output forms:

   > These per-tool bounds apply to one comparison, assuming exchangeability after window selection; independently fixed or period-label-invariant user choices; pooled automatic selection; an admissible exact uniform shift; and unchanged usable days, selected setting, pooled reference and before-day aggregates. None of these assumptions is checked. The streak check does not establish them. Repeatedly checking until a result appears is outside these bounds.

3. **OPEN — Earlier #6: parser semantics remain incomplete.**  
   Where: [0016:59](/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/logs/0016-logs-draft.md:59), lines 90–98.

   D-13’s partial-read policy and `effort`-first precedence are acceptable. First-copy-wins is also workable, but traversal order is unspecified. Two copies with the same response identity and different usage can produce different day tables depending on which file is visited first. Fragment assembly and required fields still point to nonexistent `docs/LOG_FORMATS.md`.

   **Exact additions:**

   > The Claude Code and Codex format subsections of `plan/exec/v2/tasks/L0-logs-spike.md` are normative for response fields and fragment assembly, except where this record explicitly overrides them. Transfer those definitions into `docs/LOG_FORMATS.md` before implementation.

   > Visit files in lexical order of their root-relative POSIX paths and lines in file order. Assemble each file’s responses before deduplicating across files. For matching response identities, retain the first assembled copy, including when later copies disagree. Codex cumulative-usage comparisons use the complete object.

   > Claude Code uses a nonempty string `effort`, otherwise a nonempty string `perTurnEffort`; otherwise its effort identity is missing. Unknown string identities remain distinct. Missing reasoning size produces an unknown count, not exclusion of an otherwise supported response.

4. **OPEN — Earlier #5: unknown-key counting contradicts itself.**  
   Where: [0016:61](/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/logs/0016-logs-draft.md:61), line 93 and `ReaderCounters` at line 160.

   Decision 5 promises that unknown keys are counted; reading faults explicitly says they are not, and the schema provides no counter. The canonical test-field states, margins, digest constants and context populations are otherwise corrected. Per-type maps are unnecessary now that F15 reports every missing-field occurrence.

   **Exact change:** replace Decision 5’s sentence with:

   > Unknown line types are skipped and counted. Unknown keys are ignored and not counted.

5. **OPEN — Earlier #8: empty-result rendering is still undefined.**  
   Where: [0016:137](/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/logs/0016-logs-draft.md:137), F2–F11 and Markdown at lines 227–237.

   Result/reason mappings and ERROR Markdown are corrected. But `no_usable_setting` deliberately has null model, effort, periods, context and digest, while non-ERROR Markdown still requires those values—including `{12 hex}`. Implementers must guess whether to omit them, print placeholders or manufacture a digest.

   **Exact addition:**

   > With no selected setting, render the tool name, result and fixed reason. Omit unavailable scope components, period lines, measure table, context counts and digest. Apply the same omissions to terminal, Markdown and HTML output. Retain applicable reader notices and limits text. Never substitute a fabricated digest.

6. **OPEN — Earlier #9: calendar overflow and naive-timestamp accounting remain unspecified.**  
   Where: [STATISTICS:22](/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/logs/STATISTICS_LOGS-draft.md:22), [0016:50](/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/logs/0016-logs-draft.md:50), counters at line 160.

   Fixed-offset naming and empty after-period representation are corrected. However, valid dates can still underflow: `N=0001-01-14` gives the default split `0001-01-01`, whose baseline cannot be represented. The statistics draft also promises to count zone-less timestamps without naming their counter.

   **Exact additions:**

   > Validate timestamp conversion and all window-date arithmetic against the supported date range before performing it. An unrepresentable comparison window is a usage error, exits 3, and prints only `Comparison dates are outside the supported calendar range.`

   > `ReaderCounters.records_without_timezone` counts candidate response or edit-result records excluded because their timestamp lacks a UTC offset.

   Add that counter to the schema and the fixed error to F5.

7. **RESOLVED — Earlier #1: pooled reference and before-day preservation.**  
   Where: [STATISTICS:139](/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/logs/STATISTICS_LOGS-draft.md:139), proof at line 181.

   A4 now preserves usable days, setting, `v*` and before-day values. This closes the supplied reference-switch counterexample and supports applying the exchangeability argument to the unchanged counterfactual comparison. **Change: none.**

8. **RESOLVED — Earlier #3: selection restrictions.**  
   Where: [STATISTICS:33](/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/logs/STATISTICS_LOGS-draft.md:33), A1–A2 at lines 121–129.

   Raw-identity tie-breaking is explicit; A1 is conditional on the window procedure; A2 excludes period-dependent selection, including response counts. **Change: none.**

9. **RESOLVED — Earlier #4: historical guard rates and power requirement.**  
   Where: [STATISTICS:202](/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/logs/STATISTICS_LOGS-draft.md:202), check 4 at line 224.

   Historical global-veto rates are disclaimed for the final rule, and the unsupported 95% power requirement is removed. Final-rule reporting requires simulation conditions and sampling error. **Change: none.**

10. **RESOLVED — Earlier #10: adverse margin versus retained fraction.**  
    Where: [STATISTICS:58](/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/logs/STATISTICS_LOGS-draft.md:58), A3 at line 131; [0016:142](/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/logs/0016-logs-draft.md:142).

    The token margin is unambiguously `1/4`; its transformation retains `3/4`. Exact attainable shifts and exclusion of rounding/clipping are stated. **Change: none.**

No additional invalid statement was found in the **Proof** section. The remaining statistical mismatch is in the output’s abbreviated assumptions, identified above.

Files changed: none. Read-only checks used `.venv/bin/python -I -B -c …`; the last line was `REVIEW CHECKS COMPLETE; no repository tests run`. Checks confirmed the absent format document, admitted numeric identifier and calendar underflow. An initial memory-registry search preceded reading the directory prohibition; it supplied no review evidence.

OPEN FINDINGS: 6