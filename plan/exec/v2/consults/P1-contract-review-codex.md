P1 CONTRACT: REVISE

**Blocking findings**

1. **CODE — [P1-CONTRACT.md:315](/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/tasks/P1-CONTRACT.md:315): malformed trials can silently change outcomes.** The checks validate manifest values, but only trial identities and seals. `model_copy(update={"outcome": "ERROR"})` preserves the original valid seal while making `outcome is Outcome.ERROR` false. Eighty such pairs become zero differences and can PASS.
   **Fix:** revalidate every envelope from its dumped fields, use the returned normalized instances for scoring, and verify their seals. Add ordered reason `"trial values invalid"` for validation failures. Apply the same normalization rule to the manifest.

2. **CODE — [P1-CONTRACT.md:125](/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/tasks/P1-CONTRACT.md:125), lines 318–348: decision serialization is underspecified.** `manifest_sha256` has no assignment rule; ERROR fallback leaves derived fields, unhashable trial seals, exception handling and partially computed history ambiguous.
   **Fix:** specify `manifest_sha256 = manifest.record_sha256` and the same sorted-seal digest formula for round and final decisions. For invalid manifests, use one fixed metadata template: strings `""`, tuples `()`, integers `0`, with schema/verdict/exit/reasons retained. Use `trials_sha256=""` only when its prescribed digest cannot be computed. Precheck and unexpected-computation errors get empty history/cells. Map exceptions within individual checks to their named failures, in table order.

3. **CODE — [P1-CONTRACT.md:116](/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/tasks/P1-CONTRACT.md:116): per-cell success counts are ambiguous for errored pairs.** One author could exclude both arms; another could retain the successful partner.
   **Fix:** specify that `pairs` includes errored pairs; each arm’s successes count its own `Outcome.PASS`, including when its partner errored. Pair counts remain mutually exclusive minus/zero/plus/errored categories.

4. **CODE — [P1a:65](/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/tasks/P1a-suite-schema-schedule-stats.md:65): the float prohibition makes the required digest impossible.** Frozen `Budgets` includes `30.0` and `20.0`; task JSON and fault parameters also permit floats.
   **Fix:** prohibit floating-point *statistical decision arithmetic*, while preserving existing finite JSON floats in canonical hashes and permitting the two specified TrialSpec mirrors. No frozen edit is needed.

5. **CODE — [P1a:29](/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/tasks/P1a-suite-schema-schedule-stats.md:29): the brief contradicts the contract.** It permits guessing where the contract requires stopping; its digest test requires changes for `experiment_id` and `record_sha256`, which the contract explicitly excludes.
   **Fix:** replace “choose the simplest behaviour” with “stop and report the ambiguity”; make the mutation test exclude all three omitted fields and test their invariance explicitly.

**Non-blocking findings**

1. **CODE — Contract:283; P1a:45:** exact fractions reside in `spikes/s1c/results.json`, not `RESULTS.md`. Point acceptance assertions to the two matching Table C records.
2. **OPINION — Contract:157–184, 205–240:** pin helper input domains and exceptions before freezing: canonical pair-ID parsing, four-byte seed argument bounds, valid `SuiteRule` ranges, nonnegative counts and normalized probability laws.
3. **CODE — Contract:165–197:** the digest binding works without circularity or frozen edits: exclude the generated experiment ID, derive it from the digest, then include it in every spec hash. Gate-side recomputation detects inconsistent manifests.

**Numerical verification**

1. **KNOWN:** exact Fraction checks give all-zero PASS wealth **38.1605… at 78**, **40.1629… at 79**, **42.2732… at 80**. First crossing is 79 pairs: round 4 for 20 cells, round 8 for 10.
2. **KNOWN:** minimum 20-cell budget is 80 pairs, default tolerance 1. Check (b) passes: wealth with 79 wins/1 error is **5.76572… × 10¹⁵**. With 79 zeros/1 error it is **21.1702…**, confirming D-03 item 5’s distinction.
3. **KNOWN:** zero simultaneous crossings across all **1,771** count quadruples totaling 20 pairs and **91,881** totaling 80. Generally, PASS crossing requires a positive shifted sum after pessimistic scoring; BLOCK requires a negative shifted sum after optimistic scoring—impossible together.
4. **KNOWN:** the mask’s maximum is **9,007,199,254,740,991**, exactly representable in binary64. Formatting `423104/10000` gives **`4.23104e+01`**.
5. **CODE:** both 20-cell operating-characteristic rows recomputed as exact matches to `results.json`, with total probability exactly 1.

**CODE:** read-only Python checks exited 0. No files or git state changed; no test suite ran. Next: amend the contract’s trial-validation rule before implementation starts.

