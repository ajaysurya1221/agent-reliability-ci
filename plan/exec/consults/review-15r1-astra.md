REVIEW 15r1 — Reviewer Astra | Verdict REVISE

**Findings**

1. **P3 — Item 4 remains incomplete.** Both reader-5 receipts retain `.../tmp.1KNLaL5jqS/venv` in their notes ([demo:99](/Users/ajay/Developer/.arci-worktrees/wt-t15/docs/measurement/receipts/2026-10-13-ai-reader-5-haiku-demo.json:99), [own-agent:99](/Users/ajay/Developer/.arci-worktrees/wt-t15/docs/measurement/receipts/2026-10-13-ai-reader-5-haiku-own-agent.json:99)). Readers 1 and 3 also retain generated demo-directory names. The [scrubber:42](/Users/ajay/Developer/agent-reliability-ci/plan/exec/scripts/cohort_receipts.py:42) misses these forms.

**Required changes:** Extend redaction to abbreviated temporary paths and generated directory names; rebuild affected receipts.

Items 1–3 are resolved: demo exits/completion are null with reruns separated in notes; scaffold starts/durations are null for readers 2/3/5, explained and preserved for 1/4; all demo verdicts are `BLOCK`; coaching timestamps are empty with missing stamps explained.

Read-only Python checks confirm duration arithmetic, ISO-or-empty failure timestamps, unchanged answers/scores, and 16 trials per store. Independently summed execution times match: 5.802, 6.025, 6.057, 6.030, 6.287 seconds.

Both supplied diffs match Git. Only ten receipts and the two README files changed; 53 frozen hashes and `git diff --check` pass. No files changed; no network verification performed.

**Follow-ups:** Rerun the ten-receipt redaction scan after rebuilding.