# ARCI v2.0.0: final report of the build

Orchestrator: Claude Fable 5.2. Implementer and consultant: Codex Astra 6 (high effort).
Written 2026-11-11. Branch `v2/integration`, release candidate commit `1559f90`.
Plan: `PLAN.md`. Decisions: `DECISIONS.md` (D-01 to D-10).

## What was built

| Area | Where | State |
|---|---|---|
| Suite gate: schema, schedule, statistics, gate, calibration bench | `src/arci/suite_*.py`, `bench/selfcheck_suite.py`, `docs/STATISTICS_SUITE.md` | Frozen where the design says so; 769 acceptance cases written without sight of the code |
| Suite runner, store, `arci.yaml` suites, `run`, `gate` | `suite_runner.py`, `suite_storage.py`, `descriptor.py`, `cli.py` | Reviewed, fixed, verified |
| Suite `report`, `triage`, `diff`, `plan`; fault accounting | `suite_report.py`, `report.py`, `triage.py`, `planning.py` | Reviewed, fixed, verified |
| LangChain adapter on an optional extra | `src/arci/adapters/langchain.py` | Reviewed twice, fixed twice, verified on the lowest and locked LangChain sets |
| Quickstart, recipe, `arci init --langchain` | `examples/langchain_quickstart/`, `docs/recipes/langchain.md` | Reviewed, fixed, verified; piloted on two local models |
| HTML report, PR comment | `html_report.py`, `action.yml`, `.github/scripts/` | Reviewed, fixed, re-checked, fixed again |
| Pre-registered study | `study/` | Run once: BLOCK at round 1, against a written expectation of PASS |
| Release record, changelog, README section | `docs/design/0013`, `CHANGELOG.md`, `README.md` | In the release candidate |

## Verification of the release candidate (run by the orchestrator, outside any sandbox)

| Check | Result |
|---|---|
| Core environment, LangChain absent: full suite | 2,748 passed, 16 skipped |
| Adapter environment (langchain 1.4.10): adapter, example, init, HTML tests | 617 passed |
| Adapter tests on the lowest supported set (core 1.7.5, langgraph 1.2.12) | 332 passed at the last adapter change |
| Strict type check, core and adapter configurations | 0 errors each |
| Lint and format | clean |
| Frozen hashes | 65 of 65 |
| Calibration bench | all checks pass; largest directional error 2.16% at 1 cell, 1.15% at 20, limit 2.5% |
| Hosted CI | see the last section |

## How the work was checked

Every Codex task was re-run by the orchestrator, then reviewed by independent agents with
one skeptic per serious finding, then fixed by Codex, then verified. Counts of confirmed
findings by task: suite kernel 24 (1 blocking), adapter 35 (2 blocking) and 10 more after
its fixes (2 major regressions), runner 22 (1 blocking), suite reports 15 (2 blocking),
quickstart 20 (1 blocking), HTML report 17 (3 blocking) and 10 more after its fixes
(2 major). No statistical error was found at any stage. Three briefs were corrected by
Codex's read-only review before any code was written.

Mistakes that were the orchestrator's: a frozen sentence that contradicted the next task
(found by Codex, fixed in its own commit); a version bump that broke six report goldens
(found by verification); and a wrong prediction for the study (published as such).

## What the release may claim, and may not

May: for a registered suite, each directional error of the statistical verdict is at most
2.5% at the default alpha under the assumptions in `docs/STATISTICS_SUITE.md`; a rule
changed after the run is detected; INCONCLUSIVE is reported as such; v1 is unchanged.

May not: fewer runs than other methods; a verdict from one run; per-task conclusions from a
suite PASS; anything about tasks outside the suite; anything general about the two models
in the study.

## Known limits shipped in 2.0.0

- `minimize`, `bundle`, `replay`, `trace-check` and JUnit are not built for suite stores.
- The adapter is synchronous only and rejects interrupts, tools with injected arguments,
  tool artifacts and tools that handle their own errors.
- Replay of a LangChain trial verifies the tool-call sequence, outcome and fingerprint, not
  the final answer, and does not restore exception attributes.
- A run killed by a signal loses the round in progress; there is no resume.
- A PASS at a low baseline success rate says little; the output warns below 50%.
- The HTML report and the PR comment were never tested against live GitHub or in a real
  browser beyond one headless measurement by a reviewer.
- The study is one run of 96 pairs on one machine with two local models.

## What needs the maintainer

1. Open the pull request from `v2/integration` and merge it to `main`.
2. Tag `v2.0.0` on the merged commit; the release workflow publishes to PyPI.
3. Post the launch drafts (`launch/DRAFTS.md`) after replacing the report address.
4. Day 7, 14 and 30: record stars, visitors, external issues and downloads against the
   thresholds in `PLAN.md` phase 6.
