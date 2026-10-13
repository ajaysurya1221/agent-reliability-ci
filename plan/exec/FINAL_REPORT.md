# FINAL_REPORT — ARCI v0.8.0 sprint (orchestrated run of 2026-10-13)

<<DRAFT; the orchestrator completes every section at wrap-up. Budget clock: Task 00 commit
2026-10-13T03:42:56Z; stop-starting at 12:57:56Z; end 13:42:56Z.>>

## 1. Shipped vs the memo's sprint

| Memo task | State | Evidence |
|---|---|---|
| S1 package pipeline | merged (T06) | `.github/workflows/release.yml`, CI wheel-smoke green on the lane |
| S2 packaged `arci demo` | merged (T02, T02b) | `uvx --from <wheel> arci demo` from an empty dir: exit 0, 72 s |
| S3 descriptor + schema | <<state>> | T03 + T03r1 |
| S4 `arci init` | <<state>> | T04 |
| S5 smoke UX | <<state>> | T05 |
| S6 README first screen | <<state>> | T11, ADR 0009 |
| S7 Python recipe | <<state>> | T08 |
| S8 MCP recipe + Inspector | <<state>> | T09; Inspector incompatibility recorded (D-03) |
| S9 TTFV harness | merged (T10) | `docs/measurement/` |
| S10 release-integrity merge | <<state>> | T12, ADR 0005 |
| S11 install/Action matrix | merged (T07) | CI jobs wheel-smoke, windows-smoke, action-fixture |
| S12 release | <<state>> | tag v0.8.0, release, PyPI |

## 2. Deviations from the memo, with the rule that decided each
- Smoke N is 8, not 5 (ADR 0008; tie-break consult; rule d).
- README PASS sentence states the positive non-inferiority finding, not "not shown to be worse"
  (ADR 0009; rules d and c: docs/STATISTICS.md).
- Inspector preflight recorded as blocked by the SDK's protocol-version check (D-03; rules c, e).
- <<others>>

## 3. Review coverage
Changes merged with two non-author reviews: <<n>>. With one: <<must be 0>>. With none: 0.
Cross-family (Astra) reviews: <<list>>.
Table: task → reviewers → verdicts → rounds (see plan/exec/reviews/*.md, plan/exec/STATUS.md).

## 4. Metrics vs the memo's targets
| Metric | Target | Measured | Where |
|---|---|---|---|
| Packaged demo TTFV | p50 ≤ 2 min | <<>> | plan/exec/measurements.md, docs/measurement/receipts |
| Own-agent TTFV (sample tree) | ≤ 10 min | <<>> | |
| Cold read of the first screen (reviewer subagent, no context) | ≥ 4/5 | <<>> | |
| Installed-package smoke on CI | green | <<>> | release workflow |
| Merge bar on the released commit | green | <<>> | |

## 5. Cuts and why
<<>>

## 6. Usage
Opus 5.5 coder/reviewer dispatches: <<count, subagent tokens from the workflow journals>>.
Fable (orchestrator): <<approx>>. Astra consults and reviews: <<count, files under plan/exec/consults>>.

## 7. Known issues
- `src/arci/mcp_boundary.py` reads `sys.stdout.buffer` at import (pre-existing; not hit by the demo).
- hatchling is version-pinned, not hash-pinned, in the release build.
- Inspector 2.10.1 (TS SDK 1.29.0) rejects the bridge's protocol revision 2026-07-28.
- <<>>

## 8. Next three steps
1. <<>>
2. <<>>
3. <<>>
