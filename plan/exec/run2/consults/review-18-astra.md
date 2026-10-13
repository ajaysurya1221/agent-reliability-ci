REVIEW 18 — Reviewer Astra | Verdict REVISE

1. **High — Mixed samples misrepresent the target.** [reference_stats.py:68](/Users/ajay/Developer/.arci-worktrees/wt-t18/plan/exec/scripts/reference_stats.py:68) pools one cold run with four warm runs. Reproduced: `[150,10,10,10,10]` reports both targets met, although the only cold run exceeds 120 seconds. **Required:** separate cold/warm results; collect repeated cold observations before claiming clean-machine percentiles.

2. **Medium — Timeouts escape failure accounting.** [ttfv-reference.yml:75](/Users/ajay/Developer/.arci-worktrees/wt-t18/.github/workflows/ttfv-reference.yml:75) records a sample only after completion. A hanging command exhausts the job timeout and prevents JSON parsing. **Required:** bound individual attempts below the job deadline, record timed-out/missing attempts, and preserve their failure ranking.

3. **Medium — Invalid data can produce misleading success.** [reference_stats.py:35](/Users/ajay/Developer/.arci-worktrees/wt-t18/plan/exec/scripts/reference_stats.py:35) accepts negative durations; `report()` claims percentiles from one sample and crashes on `{"samples":[null]}`, violating “always exits 0.” **Required:** validate structure, sample count and timestamp ordering; report invalid input without favorable target claims or crashes.

4. **Low — README claims need correction.** [README.md:16](/Users/ajay/Developer/.arci-worktrees/wt-t18/docs/measurement/reference-machines/README.md:16) overlooks setup/artifact network traffic; line 24 incorrectly says `sprint/**`. **Required:** describe actual network activity and `sprint/t18-**`.

Security/scope controls match the brief. Fresh-cache construction, marker parsing, environment metadata and one-second disclosure are sound on inspection. Nearest-rank/failure ordering passed 243 synthetic cases. Actionlint, Ruff, basedpyright and frozen hashes pass. Pytest: **2 passed, 3 errors**, blocked by unavailable writable temporary directories. No files changed.

**Follow-ups:** rerun the five-test suite in a writable environment; inspect Linux/macOS hosted artifacts before publishing timing claims.

