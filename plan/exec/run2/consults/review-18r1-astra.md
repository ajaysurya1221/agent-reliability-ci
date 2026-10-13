REVIEW 18r1 — Reviewer Astra | Verdict REVISE

1. **Medium — Job deadline remains unprotected.** [ttfv-reference.yml:75](/Users/ajay/Developer/.arci-worktrees/wt-t18/.github/workflows/ttfv-reference.yml:75) starts the 1200-second budget after unbounded setup, followed by a 120-second probe. Four minutes of setup permits 26 minutes before JSON generation against a 25-minute job limit. **Required:** bound setup/probe and reserve finalization time within the overall deadline; `always()` cannot extend it.

2. **Medium — Interrupted journal can prevent JSON generation.** [ttfv-reference.yml:239](/Users/ajay/Developer/.arci-worktrees/wt-t18/.github/workflows/ttfv-reference.yml:239) assumes every journal line is complete. Reproduced: one valid row followed by a truncated row raises `JSONDecodeError`, producing no JSON. **Required:** preserve complete rows and explicitly record incomplete/missing attempts.

3. **Medium — Contradictory samples still pass validation.** [reference_stats.py:52](/Users/ajay/Developer/.arci-worktrees/wt-t18/plan/exec/scripts/reference_stats.py:52) accepts successful samples missing banner/verdict timestamps, or explicitly carrying `started: false`. Five such ten-second samples report both targets “within.” **Required:** require complete successful milestone sequences and reject contradictory execution/cache metadata.

Original findings **1 and 4 are resolved**: cold/warm blocks remain separate, insufficient samples receive no percentiles, and README corrections match implementation. Failure ranking passed 243 cases. Both supplied diffs match their Git comparisons; only the four intended files changed.

Actionlint, Ruff, basedpyright and frozen hashes pass. Pytest: **3 passed; 21 setup errors** from unavailable writable temporary directories. Extracted timeout checks pass. No files changed.

**Follow-ups:** after fixes, rerun `plan/exec/scripts/test_reference_stats.py` in a writable environment. Hosted timing remains unverified.

