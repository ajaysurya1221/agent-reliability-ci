REVIEW 12 — Reviewer Astra | Verdict REVISE

1. **P2 — Stale v0.8.0 claims.** [CHANGELOG.md:71](/Users/ajay/Developer/.arci-worktrees/wt-release/CHANGELOG.md:71) says the README opens with the recorded result; [CHANGELOG.md:115](/Users/ajay/Developer/.arci-worktrees/wt-release/CHANGELOG.md:115) retains the superseded main/v0.7.0 availability distinction and says CITATION’s release date is October 5. The candidate opens with the question, pins v0.8.0, and dates CITATION October 13. **Required:** reconcile these carried-forward bullets with the final release while preserving archived results.

2. **P2 — Unmeasured onboarding claim.** [ROADMAP.md:7](/Users/ajay/Developer/.arci-worktrees/wt-release/docs/ROADMAP.md:7) states that the first experiment is a “ten-minute job.” The measurement protocol explicitly reports no collected receipts and treats ten minutes as a target. **Required:** describe the shipped onboarding capabilities or label the timing as an unverified target.

3. **P2 — Import-path claim omits an explicit exception.** [CHANGELOG.md:45](/Users/ajay/Developer/.arci-worktrees/wt-release/CHANGELOG.md:45) promises cwd on every child’s import path. Amended ADR 0006 and `mcp_boundary._server_environment` preserve an MCP server’s configured `PYTHONPATH`. **Required:** qualify the statement accordingly.

**Verified:** candidate `3ca5794` against base `f0915f9`; supplied diff matches. All 53 frozen hashes match committed bytes, with no required paths missing or entries dropped. Versions/date agree. Pyproject changes match ADR 0005. Lockfile marker normalization preserves the reachable dependency graph across 24 checked environments; dependency versions and artifacts are unchanged. README changes stay within the four requested locations; its 191-word first screen and limitations are unchanged. Protected evidence, acceptance tests, decision logic and calibration are untouched. All 18 archived decisions re-derived byte-for-byte.

**Checks:** formatting, lint, basedpyright, figures and schema pass; focused pytest checks: **46 passed**. `.venv/bin/pytest -o addopts='' tests/unit/report tests/unit/examples tests/unit/stats -q --capture=sys -p no:cacheprovider -x`: **74 passed, 1 error**, caused by unavailable temporary storage. `reproduce.py --check` and offline `uv lock --check` were also permission-blocked.

**Follow-ups:** rerun blocked checks and obtain exact-candidate hosted CI before tagging. Publication remains unverified. Files changed: none.

