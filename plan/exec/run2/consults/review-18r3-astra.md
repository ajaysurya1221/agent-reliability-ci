REVIEW 18r3 — Reviewer Astra | Verdict REVISE

1. **Medium — The deadline guarantee remains incomplete.** [ttfv-reference.yml:45](/Users/ajay/Developer/.arci-worktrees/wt-t18/.github/workflows/ttfv-reference.yml:45) reserves 300 seconds, but the probe, parsing, upload and final check allow **120 + 60 + 120 + 60 = 360 seconds**, before cleanup and step overhead. Exhausting the sampling budget therefore permits completion at 2460 seconds against the 2400-second job deadline. [test_reference_stats.py:172](/Users/ajay/Developer/.arci-worktrees/wt-t18/plan/exec/scripts/test_reference_stats.py:172) checks the probe and remaining steps separately, missing their combined cost. The README’s unconditional reserve claim also ignores the final reader join.

**Required changes:** budget the combined finalization costs plus cleanup/headroom; admit the probe only when those costs fit; assert that combined inequality and align the README guarantee.

**Resolved:** truncated journals preserve complete rows and explicitly record incomplete/missing samples. Successful samples require all ordered milestones. Both requested metadata contradictions are rejected. Budget cut-offs, hangs and unstarted samples are distinguished and retain failure ranking. Cold/warm wording matches the supplied measurement record.

**Verification:** in-memory probes passed 44 invalid-input cases, earlier reproductions, 243 failure-ranking combinations, ten parser/gate scenarios and three existing filesystem-independent tests. Ruff, basedpyright, actionlint and frozen hashes pass; both supplied diffs match Git. No files changed.

**Follow-ups:** after correcting the arithmetic, rerun the filesystem dry-run suite and inspect both hosted artifacts. Neither full filesystem execution nor hosted outcomes were independently verified here.

