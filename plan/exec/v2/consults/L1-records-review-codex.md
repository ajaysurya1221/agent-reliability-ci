1. **P1 — Fix model selection before claiming the REAL DROP bound.**  
   Where: [STATISTICS_LOGS-draft.md, “What is compared” and A2](/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/logs/STATISTICS_LOGS-draft.md:26).

   Response counts can reveal the tested values. Consider 15 days and 3,003 model IDs, randomly assigned to every five-day subset. Each model produces 21 responses of 100 tokens on its assigned days and 20 responses of 200 tokens elsewhere. Every fixed model has exchangeable days. Selecting by counts over five after-days always selects the model whose five low days are exactly those after-days. Its p-value is `1/3003`; its before-period self-check is flat. False REAL DROP occurs with probability **1**.

   **Change:** select the model/effort using pooled counts across both periods, with a fixed tie-break, or require selection independent of the evaluated data. Define A1 jointly over all candidate settings and prove that selection preserves exchangeability. For the newest-day window, explicitly justify conditioning on availability within a fixed observation horizon; “uses counts/dates only” is insufficient.

2. **P1 — Claim 2 needs an assumption about which days survive filtering.**  
   Where: [STATISTICS_LOGS-draft.md, Claim 2 proof](/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/logs/STATISTICS_LOGS-draft.md:136).

   A3 constrains values, but permits changes to response counts. Take 98 days: 49 with a latent median of 100 and 49 with 400, uniformly shuffled. Without change, their response counts are respectively 20 and 19. Fix 84 before-days and 14 after-days. After the split, multiply every token value by `3/4` **and swap the response counts**. Eligible before-days now have median 100; eligible after-days have median 300. Keep both Claude share measures at zero, with sufficient edit results.

   Whenever at least five high-type days fall after the split, every measure passes NO DROP despite the exact 25% token reduction. That event has probability **0.926441**, not at most 0.025.

   **Change:** require exchangeability of the retained counterfactual values after selection, and require the shift to preserve eligibility, missingness and model/effort assignment. Print these unchecked assumptions. The existing pointwise filter argument establishes null validity; it does not establish validity after a change.

3. **P1 — Make the self-check veto terminal.**  
   Where: [STATISTICS_LOGS-draft.md, overall result and self-check](/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/logs/STATISTICS_LOGS-draft.md:69).

   The ladder can fall through to NO DROP after the self-check fires, contradicting “a REAL DROP becomes CANNOT TELL.”

   Concrete example: before medians are five `100`s followed by five `95`s; after medians are five `90`s. Both main tests have p-value `1/3003`; the self-check has `1/252`, which rejects. With unchanged, sufficiently observed share measures, the written ladder returns NO DROP.

   **Change:** after the minimum-day gate, if any real-drop test rejects, return CANNOT TELL when the self-check fires and REAL DROP otherwise. Only evaluate the overall NO DROP branch when no real-drop test rejects. State that the self-check’s halves do not inherit the main comparison’s 10-before/5-after minimums.

4. **P1 — The privacy allow-list permits private strings.**  
   Where: [0016-logs-draft.md, Decision 6](/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/logs/0016-logs-draft.md:59).

   A model ID such as `acme-payroll-secret` passes the regex and reaches F2 and the sealed record unchanged. A numeric private string can similarly pass the version regex. These permissions contradict “no … output may carry a string read from a log.” The spike’s uppercase `CANARY-<n>` would miss the model-ID path.

   **Change:** emit model names only through a closed mapping to constant strings, with unknown identities excluded from comparison rather than pooled as one model. Keep client versions internal and emit their counts only. Test lowercase regex-valid canaries, numeric version canaries and fixed error messages.

5. **P1 — Define missing values and denominators before counting usable days.**  
   Where: [STATISTICS_LOGS-draft.md, usability and measures](/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/logs/STATISTICS_LOGS-draft.md:20).

   Twenty responses with zero reasoning tokens qualify by response count, but the positive-token median and repeated-value share are undefined. Missing reasoning sizes create another ambiguity: ten known zeros plus ten missing sizes produce a zero share of either `1` or `1/2`, depending on interpretation.

   **Change:** distinguish total responses, responses with known nonnegative counts, positive responses and eligible edit results. Define reasoning-measure eligibility using known counts; require at least one positive count for the positive median and repeated share. Never replace undefined values with zero. Apply the 10-before/5-after minimum **per measure**, and report the failing measure’s counts. Under the current overall ladder, an entirely zero-reasoning after-period therefore yields CANNOT TELL; document that consequence.

---

6. **P2 — State A3’s support restrictions explicitly.**  
   Where: [STATISTICS_LOGS-draft.md, A3](/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/logs/STATISTICS_LOGS-draft.md:106).

   A3 is a restrictive model of observed daily aggregates, not a generic model of reduced computation. With the conventional median of integer token counts, values lie on the half-integer lattice: median `5` cannot become exactly `3.75`. Likewise, a share of `0.95` cannot increase by `0.10` without leaving `[0,1]`. Rounding and clipping are different models.

   **Change:** define a separate shift parameter per measure, its admissible support, and the exact counterfactual aggregate interpretation. Explicitly exclude rounded/clipped shifts from Claim 2 unless separately proved. Preserve exact arithmetic in the margin test; do not silently round the transformed baseline.

7. **P2 — Correct the fixed texts and their probability scope.**  
   Where: [0016-logs-draft.md, F5–F14 and Markdown text](/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/logs/0016-logs-draft.md:129).

   Several statements exceed the contract:

   - F7 and F10 assert that context changed even when counts and versions are identical.
   - The Markdown sentence asserts “a shift” even for CANNOT TELL or NO DROP.
   - F10 omits model/effort selection from A2 and does not identify the bounds as **per tool**. Two tools allow an upper bound of 5% for any wrong REAL DROP by a union bound.
   - F14’s “fewer responses” is false when the user explicitly selects a less-used model.

   **Change:** use “Context counts; differences are not tested,” “Tasks, prompts, projects or client versions may have changed,” result-specific Markdown sentences, and “Not compared: … other model or effort settings.” State each bound per tool and include every strengthened assumption. Replace “more than your day-to-day variation explains” with “Evidence against interchangeable days in at least one recorded measure.” Explicitly say that this does not establish answer quality, cause or a vendor model change.

8. **P2 — Specify the calendar and window construction.**  
   Where: [STATISTICS_LOGS-draft.md, day and split definitions](/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/logs/STATISTICS_LOGS-draft.md:20).

   A future-dated record can move the default window years forward. A session spanning midnight can be assigned differently by session-based and response-based implementations. “Local time” does not specify historical daylight-saving offsets, and a valid `--since` after the newest day leaves an empty/reversed interval.

   **Change:** capture the local timezone and run-start instant once; convert each aware timestamp using the offset at that instant; use calendar-date arithmetic. Assign Claude responses by their first-line timestamp, Codex responses by their token-count event timestamp, and edits by result timestamp. Exclude and count future timestamps. Define the newest date per tool after project/main-thread filtering. A valid split with no after-days must produce CANNOT TELL with zero after-days; malformed dates must produce a fixed error.

9. **P2 — Define edit attribution and parser failure rules.**  
   Where: [0016-logs-draft.md, Decision 5](/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/logs/0016-logs-draft.md:50), and [L0-logs-spike.md, reader records](/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/tasks/L0-logs-spike.md:88).

   The supplied `EditResult` lacks model and effort, although the comparison promises one model/effort. A day containing two models can therefore mix their edit failures. The drafts also provide no threshold distinguishing counted malformed lines from `format_not_recognised`.

   **Change:** inherit each edit result’s model/effort from its matched originating `tool_use` response; exclude permission denials from both numerator and denominator; count unmatched results separately. Specify required fields, effort precedence and duplicate handling. Define an exact recognition failure rule—for example, no supported responses recovered—and fixed read/write error codes. Never render parser or validation exception text.

10. **P2 — Finish the deterministic record and rendering contract.**  
    Where: [0016-logs-draft.md, Record model and F3/F6/F11](/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/logs/0016-logs-draft.md:94).

    One `Period.usable_days` cannot represent different measure-specific day sets. Median tie handling, pooled-mode ties, table rounding, change units, absent-test fields and digest input remain unspecified. `hash_record` sorts object keys, not list elements.

    **Change:** define even medians as the exact arithmetic mean; break pooled-mode ties by the smallest numeric count; store day values in original units. Show usable counts per measure and label summaries “median day.” Define share changes in percentage points and token changes relative to baseline, with fixed display precision and rounding. Use null for unavailable summaries/tests. Fix tool, measure and date ordering, reject duplicate day rows, specify the complete day-table digest payload, and exclude only the top-level seal from the decision seal.

---

11. **P2 — Replace the ambiguous aggregate exit rule with an explicit mapping.**  
    Where: [STATISTICS_LOGS-draft.md, exit codes](/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/logs/STATISTICS_LOGS-draft.md:87).

    “Largest” numerically selects CANNOT TELL over REAL DROP, while the stated priority does the opposite. Both-tools-ERROR is unspecified. F4 can also display “exit 3” for a tool while the process exits zero under the proposed partial-success policy.

    **Change:** write: among non-error tools, any REAL DROP gives exit 1; otherwise any CANNOT TELL gives 2; otherwise NO DROP gives 0. If none remain, exit 3. Preserve and display every tool error. Show tool results separately from one process exit code. Define empty/error record templates instead of inventing dates or p-values.

12. **P2 — Do not carry the spike’s calibration into this different test.**  
    Where: [STATISTICS_LOGS-draft.md, limitations and checks](/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/logs/STATISTICS_LOGS-draft.md:152), versus [L0-logs-spike.md, rank test](/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/tasks/L0-logs-spike.md:110).

    The spike specifies a conditional midrank permutation test; this draft specifies strict counts against a distinct-value reference. They differ on tied logs. The power table is absent, and “a drop of 10 to 20% is not detectable” confuses limited power with impossibility.

    **Change:** regenerate calibration using the final statistic, selection, eligibility and veto rules. Publish design, seed, simulation count and rejection rate with each projection. Replace the categorical detectability claim with measured power at named designs and assumptions. Distinguish the finite simulation threshold from the proved bound.

13. **P3 — Recover power from ties for the REAL DROP test.**  
    Where: [STATISTICS_LOGS-draft.md, reference distribution](/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/logs/STATISTICS_LOGS-draft.md:53).

    At the minimum sample sizes, let before-values be eight `200`s and two `100`s, and after-values five `100`s. The draft gives `113/3003 ≈ 0.03763`, so no rejection. An exact conditional tie-aware test gives `1/143 ≈ 0.006993`, below `1/120`.

    **Change:** consider the spike’s exact conditional permutation test for REAL DROP and its self-check. It preserves the exchangeability bound while detecting this tied example. Retain the fixed-reference NO DROP test until a separate proof establishes the required monotonicity for a replacement; its reference distribution changes when ties change.

Checked and found sound:

- The strict-count/distinct-reference p-value is conservative under exchangeability with arbitrary ties. Independent mathematical tie-breaking is valid and requires no randomness in implementation.
- With valid individual p-values, the three-measure union bound is correct. Different measure-specific day sets are permissible; they need not intersect.
- With exchangeable retained counterfactual values, the margin transformation, monotonicity argument and all-must-pass NO DROP rule are correct. REAL DROP precedence only removes NO DROP results.
- A pooled modal count preserves null exchangeability when its selection is invariant to period labels, including a fixed numeric tie-break.

Files changed: **none**. In-memory checks used `.venv/bin/python -I -B -c …`; the enumeration’s last line was:

```text
PASS: exact reference and conservative tied rejection fractions; pooled sizes 2..10; 1860 three-level tie multisets/designs
```

These checks are not repository acceptance evidence. No network or session logs were accessed. An initial memory-registry lookup occurred before the brief’s directory prohibition was loaded; it was not evidence for the statistical findings.

