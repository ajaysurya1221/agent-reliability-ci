REVIEW 15 — Reviewer Astra | Verdict REVISE

**Findings, by severity**

1. **P2 — Mixed attempts:** Readers 1–4 combine first-demo timestamps with rerun exit codes, yet mark `completed: true` ([reader 1 evidence](/Users/ajay/Developer/.arci-worktrees/wt-t15/docs/measurement/receipts/2026-10-13-ai-reader-1-opus-demo.json:104)). Keep first-attempt exit/completion unknown; record reruns separately.
2. **P2 — Wrong scaffold milestone:** Readers 2, 3 and 5 stamp the failed first `init`, whereas §4 requires the successful invocation ([reader 2](/Users/ajay/Developer/.arci-worktrees/wt-t15/docs/measurement/receipts/2026-10-13-ai-reader-2-opus-own-agent.json:44)). Use a supported successful-start timestamp, otherwise null; recompute scaffold duration.
3. **P2 — Invalid field values:** All five demo `outcome.verdict` fields contain prose instead of `BLOCK` ([example](/Users/ajay/Developer/.arci-worktrees/wt-t15/docs/measurement/receipts/2026-10-13-ai-reader-1-opus-demo.json:63)). Move explanations into notes. Coaching-event `at: "pre-attempt"` also violates §6’s ISO timestamp requirement; explicitly represent the missing timestamp.
4. **P3 — Path redaction:** Notes expose `/Users/ajay/...` ([example](/Users/ajay/Developer/.arci-worktrees/wt-t15/docs/measurement/receipts/2026-10-13-ai-reader-1-opus-demo.json:99)), contrary to the receipts README’s prohibition on usernames in paths.

**Required changes:** Fix 1–4 before acceptance.

Read-only Python checks passed: ten receipts retain all 84 keys; duration arithmetic, verbatim answers and scorer booleans match. I agree with readers 1 and 5’s q3/q4 scores: scoped relative non-inferiority and distinct README limits are present. Reader-3’s store-validation correction and reader-5’s null completion are justified.

Both README edits are supported locally; first screen remains byte-identical, 191 words. Exactly 12 candidate files changed; 53 frozen hashes and `git diff --check` pass. AI/coaching exclusions are explicit. No files changed; live PyPI was not rechecked.

**Follow-ups:** Correct [measurements.md:66](/Users/ajay/Developer/agent-reliability-ci/plan/exec/measurements.md:66): reader-5 demo install is 0 seconds; own-agent install is unknown. Start with reader-1’s mixed-attempt outcome.

