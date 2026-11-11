# REVIEW: phase 1 suite kernel (P1a + P1b)

Reviewer: orchestrator (Claude Fable 5.2), 2026-11-11. Author: Codex Astra 6.
Method: the orchestrator re-ran every acceptance command outside the sandbox, read
`suite_gate.py`, `suite_schema.py`, `suite_schedule.py` and `suite_stats.py` in full, ran
the blind acceptance tests, then ran a five-lens independent review (attack the gate; the
proof and document; the bench; what gets frozen; portability) with one skeptic per finding.
29 agents, 24 findings: 13 confirmed, 9 narrowed, 1 refuted, 1 contract-level. Full output:
`P1-review-workflow.json`.

## Verdict: REVISE (no statistical error; one blocking robustness defect)

| Check | Result |
|---|---|
| Blind acceptance tests (683 cases, authors never saw the code) | all pass, first run |
| Full suite outside the sandbox | 1,614 passed, 2 skipped, exit 0 |
| Calibration bench | exit 0, 184 s |
| ruff, strict basedpyright, 54 frozen hashes | clean |
| Proof in `docs/STATISTICS_SUITE.md` | valid as written; 193,430 exact evaluations at and inside each null, 0 violations |
| Gate against 100,311 enumerated paths with errors and hard violations | 0 mismatches |

## Findings that change code or contract (contract section 8, task P1c)

1. **Blocking: rationals had no size bound.** A sealed manifest with a huge numerator sent
   every decision into the last-resort guard, and a 5 KB manifest made the gate run for
   minutes. Now at most 7 digits each side.
2. **Major: gate cost grew faster than the store.** About 9.5 hours for a valid 1-cell,
   100,000-round store. Wealth is now carried forward as integers and round digests cover
   one round.
3. **Major: a `bytes` seal gave a sealed PASS with an empty trials digest.** A supplied
   seal must now be a string.
4. **Major: the bench's gate cross-check could not see the sign of the difference** and
   reached BLOCK on 1 path of 729. New laws and rule, plus errored-pair and hard-violation
   paths.
5. **Major: the bench did not reproduce ADR 0011's boundary maxima.** The equal-mean
   three-point family is added.
6. **Major (document): the per-round arm-order flip is a breaker of the stationarity
   assumption and was not named.** Added, with the common-mode magnitude.
7. Minor: `experiment_id` now has a fixed shape (it names the run directory);
   `replay_suite_decision` normalises the decision; no warnings; document wording.

## Accepted as they are, by decision

Suite-wide contract and budgets; seeds derived from the whole rule digest (a different
candidate gives different fixed scenarios); `evaluate_rounds` trusting its stated
assumptions; scoring on `outcome` alone, as v1 does; Windows path limits (experiments are
unsupported on Windows).

## Carried to phase 2

The suite store must refuse to create a run directory unless
`experiment_id == suite_experiment_id(manifest)`.

## Closing (2026-11-11, after task P1c)

ACCEPT. All section 8 items are implemented. The updated blind acceptance tests pass
(769 cases). Outside the sandbox: 2,409 tests passed, 2 skipped; calibration bench exit 0
in 246 s; ruff and strict basedpyright clean; 63 of 63 frozen hashes OK, the 54 earlier
ones unchanged. The orchestrator fixed seven type annotations in the acceptance tests
(no assertion changed). Frozen in this step: `suite_schema.py`, `suite_schedule.py`,
`docs/STATISTICS_SUITE.md`, `docs/design/0011-suite-gate.md` and the five acceptance files.
The branch is also pushed as `sprint/v2-suite` so hosted CI runs it on Ubuntu and macOS.
Not done in this re-freeze: the suite section of `docs/AGENT_SEMANTICS.md` (phase 2).
