1. **Resolved:** D-20 authorizes the revised `--since` and conflicting-flag rules.
2. **Resolved:** The write-only read state is gone; `kept_table` now supports reproducing F24.
3. **Resolved:** Both readers are in scope; matching names and opaque identities preserve version counts.
4. **Resolved:** Oversized staged tables fail the entire output transaction; item 53 covers the boundary.
5. **Resolved:** The conditioning structure now includes stored-row existence and file-edit counts.
6. **Partly resolved:** Retention restrictions improved, but complete capture, deletion age and comparison-frame conditions remain incomplete.
7. **Resolved:** Competitive selection and the newly adopted-setting cell, including 535/20,000, are restored.
8. **Resolved:** A1-preserving gates now separate null and exact-margin cells with explicit denominators.
9. **Partly resolved:** Path and offset assertions are corrected; item 42 still promises V1 equality without excluding kept-table effects.
10. **Resolved:** Kept counts include unusable days; cross-measure source consistency has a named rejection.
11. **Resolved:** Both the statistics explanation and F5 distinguish a streak flag from established dependence.

**Remaining findings, most severe first**

1. **Retention equality still exceeds the specified conditions.** [0017:465](/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/logs2/0017-logs-2-draft.md:465), acceptance 26–27, and [statistics:532](/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/logs2/STATISTICS_LOGS-2-draft.md:532).

   “By age” does not specify deletion only after 30 days. A keep run *after* a day ended need not precede its deletion. Comparing against “the run before deletion” also permits different windows and newly arrived responses. Finally, the day lists cannot literally be identical when their `source` fields change.

   [S0’s actual restrictions](/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/spikes/S0-logs2/REPORT.md:91) additionally require immutable records, no late backdated arrivals, and exclude separate edit-only retention.

   **Corrected wording:** “Use immutable records with no late backdated arrivals, deleting only batches strictly older than 30 × 24 hours. Compare the retained and undeleted histories at the same instant, with identical options, offset and window. Each deleted day must have been captured completely before deletion; successful captures are at most 29 days apart. Within the admitted rows and active window, measure day lists agree after removing `source`, and results agree. Separate edit-only retention remains outside this promise.”

   Item 27(a) should name a constructed history that loses an uncaptured day: a 31-day gap alone does not guarantee loss.

2. **F24 can claim the table was unchanged when the command overwrites it.** [0017:692](/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/logs2/0017-logs-2-draft.md:692), acceptance 34.

   Without `--keep`, item 34 explicitly permits `--json` to name `days-1.json`. If that existing table is invalid, the run prints F24 and replaces it with the report.

   **Corrected F24, preserving the permitted alias behavior:**  
   `The kept day table could not be read or is not valid. It was not used.`

   Add an acceptance case with an invalid table and an explicitly aliased report target.

3. **Two implementation decisions remain ambiguous.**

   At [0017:279](/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/logs2/0017-logs-2-draft.md:279), flag errors must precede log reads, but F5 priority puts a data-dependent `--since` error first. Both rules cannot determine precedence for a run containing both errors.

   **Corrected wording:** “Check option-only errors before reading logs or the table. Within each validation phase, choose the first applicable F5 error. Data-dependent errors are checked only after option validation succeeds.”

   At [0017:396](/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/logs2/0017-logs-2-draft.md:396), the histogram cap does not explicitly settle what happens when an oversized incoming row already has a valid stored counterpart.

   **Corrected wording:** “Exclude oversized incoming log rows from the write merge and count them in `days_not_kept`; preserve any existing valid row for that key. The use rule still considers the uncapped log row.” Add that exact fixture.

4. **The acceptance list still contains ambiguous or contradictory assertions.** These corrections are needed in [“Acceptance, as tests can see it”](/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/logs2/0017-logs-2-draft.md:768).

   | Items | Corrected wording |
   |---|---|
   | 3–9 | “Unless a kept-table fixture is explicitly supplied, use an isolated home with no table.” Otherwise item 8 can select a valid kept-only setting despite every current response lacking a setting. |
   | 9 | “With one selector, choose by the count rule among matching settings; with both, compare the matching pair; with no match, return `no_usable_setting`.” |
   | 14–15 | “With exactly one rejected effort/model, render `effort-1`/`model-1`.” Multiple rejected names require distinct aliases. State their numbering rule here rather than referring a blind author to 0016. |
   | 16 | Replace “Before-period versions are never listed” with “Versions occurring **only** before the split are never listed.” |
   | 17 | Add “and no report-output options.” Otherwise the assertion forbids explicitly requested report files. |
   | 26–27 | Apply finding 1; distinguish semantic day-list equality from source equality and specify the loss fixture. |
   | 28 | “F21 prints for tools with a selected setting when the table was read.” ERROR and `no_usable_setting` are exceptions. |
   | 35 | “For otherwise valid options and non-colliding output paths, adding `--keep` to `--example` leaves output unchanged.” Option errors still apply. |
   | 39 | Replace “every prose span” with “every **backtick-delimited span**.” The surrounding explanatory prose is not a constant. |
   | 41 | “Where present, F11 and the footer name `arci-logs/2`.” Outputs without a selected setting have no digest. |
   | 42 | Require no kept-table contribution and identical effective inputs for V1 result equality. The same selected setting alone is insufficient. |
   | 46 | Replace “rows byte for byte” with “parsed row objects unchanged.” Valid input may contain whitespace/key ordering that the mandatory canonical writer changes. |
   | 53 | Require otherwise valid table files and explicit writer cases below, exactly at, and above 33,554,432 bytes; replace “just inside” with an exact boundary. |
   | 54 | “The **new client-version exception** applies only under `client_versions_after_shown`; existing allowed categories remain valid.” A literal ban elsewhere rejects the required `arci_version: "2.4.0"`. |

5. **Observable requirements remain without explicit acceptance coverage.** Field-presence checks and constant comparisons do not establish these behaviors. Add the following assertions; each group identifies the missing coverage.

   **Selection, reduction and context** — [0017:29](/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/logs2/0017-logs-2-draft.md:29), [0017:419](/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/logs2/0017-logs-2-draft.md:419):

   - Test before-period fallback when after-period responses exist but all lack a setting, and when selector filtering removes all after-period candidates.
   - Test that a valid existing table influences a run **without** `--keep`; it cannot establish `N` or rescue a tool with no logs.
   - Assert that merged rows determine `v*`, usable values, first-response date, response-day counts and `other_settings`, while context and reader counters remain log-only.
   - Test all nine effort admissions, model-grammar boundaries, and numeric version ordering with equal tuples, leading zeros, tuple lengths, repeated rejected identities and boundary-length strings.
   - Test version population explicitly: include other settings and subagents, apply the project filter, exclude before-only versions, and verify JSON list/count consistency.

   **Table persistence and faults** — [0017:396](/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/logs2/0017-logs-2-draft.md:396):

   - Assert writes and omission counts cover all eligible settings in `[N-180, N]`, regardless of selectors or split; counts are distinct settings/rows, not response counts. Cover exactly 5,000 histogram entries and the oversized-row conflict above.
   - Assert pruning applies under every offset only for requested, non-ERROR tools; ERROR tools preserve their stored rows. Cover all-ERROR runs and stored future rows on write.
   - Extend invalid-table fixtures to unreadable/nonregular files, invalid UTF-8, duplicate JSON object keys, missing keys, wrong schema, invalid dates/offsets, and invalid histogram/count relationships. Each invalidates the whole table.
   - Assert canonical serialization, existing-directory permissions unchanged, table replacement mode 0600, and report-file permission preservation. Define whether rollback removes **all newly created parent directories**; creation currently permits parents but rollback names only the table directory.
   - Test relative/tilde paths using injected `home`, implicit `--keep-dir` conflicts, `--example`/`--project` conflicts, multiple-error precedence, and same-file checks for HTML and alternate path spellings. Exercise failures after staging and during replacement, not just directory creation.

   **Record validation and rendering** — [0017:487](/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/logs2/0017-logs-2-draft.md:487):

   - Assert the outer seal and exact day-table digest payload; negatively test the remaining first-response, response-count, after-period kept-count, nullability, version-order and version-count constraints.
   - Assert that ERROR and `no_usable_setting` records carry the specified empty/null/zero fields, including notices that remain applicable.
   - Round-trip every new state through JSON and render text, Markdown and HTML from the restored record alone; item 31 currently covers only F24 in Markdown/HTML.
   - Test F18–F26 placement, suppression and zero-count behavior across formats; HTML must distinguish open/filled day markers and contain no scripts, external references or values absent from the record.
   - Resolve the footer exception: [0017:320](/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/logs2/0017-logs-2-draft.md:320) omits the digest for `no_usable_setting`, while line 717 requires a digest-bearing footer for every non-ERROR result. **Correction:** “With no selected setting, print F10 and omit the digest-bearing footer.” Add a snapshot.

   **Self-check and distribution requirements** — [0017:59](/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/logs2/0017-logs-2-draft.md:59):

   - Require the new null, margin and competitive-selection cells, their 20,000-history denominators and failure thresholds; checking the two printed correlation figures does not cover these gates.
   - Require the report-only A1 violations, adopted-setting example, conditional streak rates, power stopping counts, 14/16 designs, weekly/regime generators and revised counterexample label.
   - Assert the prescribed commands and version pins in every named document/plugin/skill, version 2.4.0, and unchanged `requires-python >=3.11`.

No stale acceptance-item cross-reference was found. The changed explicitly unwrapped fixed texts fit within 100 columns; two F10 lines are exactly 100.

Files changed: none. Read-only `.venv/bin/python -I -B -c …` document probes ended with `READ-ONLY DOCUMENT PROBES COMPLETE`. Product tests, formatting/type checks and simulations were not rerun; no prohibited directories, memory registries or network were accessed.

**Ready to build from: no.**