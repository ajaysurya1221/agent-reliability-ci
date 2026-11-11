# 0011 (ACCEPTED 2026-11-11; copied to docs/design at the phase 1 re-freeze): the v2 suite gate

Status: accepted by the maintainer on 2026-11-11 ("Approve both"), with the seed rule
default `fixed` and the 1% errored-pair default as drafted (`DECISIONS.md` D-02). The
orchestrator's readings of points this record leaves open are in `DECISIONS.md` D-03.
History: draft v3, written by the orchestrator (Claude Fable 5.2) on 2026-11-11 from the
phase 0 spikes S1, S1b and S1c and their completed reviews (`plan/exec/v2/reviews/`).
Codex Astra 6 reviewed draft v2 read-only and returned REVISE with five blocking findings;
this draft answers each (see "Review record"). Awaiting the maintainer's approval. Becomes
`docs/design/0011-suite-gate.md` plus a re-freeze only when accepted. No frozen file is
changed by this draft.

## Problem

v1 gates one task under K fault conditions with about 200 trials per arm per condition. Teams
evaluate the other way round: many tasks, a few runs each. v1 has no rule for that, and its
contract says never to pool tasks as if they were identical trials. The first verdict a new
user sees is almost always INCONCLUSIVE.

A suite rule must keep what makes the v1 gate worth trusting: the rule is fixed before the
run and bound into every trial; error rates are stated and checked exactly; INCONCLUSIVE and
ERROR are first-class; nothing is tuned after the data.

## Decision

1. **A new experiment kind beside v1, not a change to v1.** New sealed records
   `SuiteManifest` and `SuiteDecision` with `schema_version: "arci-suite/1"`, in new modules,
   decided by a separate suite gate. `schema.py`, `schedule.py`, `arci.gate.decide` and every
   `arci/0.5` record, command and test stay as they are. Adding a field to the v1 `Manifest`
   would change the hash of every archived record (`schema.py:49-64`), so v1 is not extended.

2. **Unit of analysis: a pre-registered grid of cells.** A cell is one (task, fault
   condition). The grid has N cells. The estimand is `Delta`, the unweighted mean over cells
   of (candidate success probability minus baseline success probability). Verdicts and the
   margin `delta` mean what they mean in v1, applied to `Delta`.

3. **Balanced rounds, not sampled cells.** A round runs every cell exactly once, both arms.
   The decision is evaluated at the end of every complete round and nowhere else. S1b showed
   that drawing cells at random holds its error bound only on average over the draw: for one
   fixed schedule, with a regression in 3 of 20 cells, false PASS reached 23% at the 99th
   percentile and 53% at worst. With balanced rounds there is no schedule to be lucky with.

4. **One decision procedure: two one-sided betting tests.** For a pair with difference `d` in
   {-1, 0, +1}, stake fractions `q` in the pre-registered set `{1/4, 1/2}`:
   - PASS wealth: the mean over `q` of the product over all pairs so far of
     `1 + q/(1 - delta) * (d + delta)`.
   - BLOCK wealth: the mean over `q` of the product of `1 - q/(1 + delta) * (d + delta)`.
   - At a round end: PASS if the PASS wealth is at least `2/alpha`; BLOCK if the BLOCK wealth
     is at least `2/alpha`; otherwise continue. INCONCLUSIVE only after `max_rounds`.
   - All arithmetic in the decision path is exact (`Fraction` and integer comparison). No
     `log`, `sqrt` or float comparison.

5. **Why this is valid** (written out in `docs/STATISTICS_SUITE.md`, not cited away).
   Under the PASS null `Delta <= -delta`, the expected value of one round's product for a
   fixed `q` is `prod_c (1 + lam (Delta_c + delta))`. Every factor is non-negative, so by the
   inequality of arithmetic and geometric means it is at most `(1 + lam (Delta + delta))^N`,
   which is at most 1. So each product is a non-negative supermartingale across rounds, a
   fixed mixture of them is too, and Ville's inequality bounds the chance of ever reaching
   `2/alpha` by `alpha/2`. The BLOCK test is the mirror image. Stopping at the first crossing
   and capping the rounds only shrink those events. PASS and BLOCK cannot both cross.
   Reference for the wealth construction: Waudby-Smith and Ramdas, arXiv:2010.09686v7,
   section 2.2 (Theorem 1) and section 4 (equation 23). The mixture step and the round step
   are our own short derivations and are stated as such.

6. **What the proof assumes, each stated as a product requirement.**
   - Outcomes are independent across cells within a round and across rounds. Trials are fresh
     processes from reset state, as in v1. A cache that serves a later round from an earlier
     round's model response breaks this and is refused where it can be detected.
   - Each round's suite mean obeys the same null. This holds when a cell has the same law in
     every round. That is assumed, not enforced; item 7 says what the seed rule removes.
   - Every round holds every cell exactly once. No weights, no extra repeats of some cells.
   - Dependence between the two arms of a pair is unrestricted.
   - **Common-mode failure is the assumption with no slack.** A round is also a block of
     wall-clock time. An incident that hits one arm across many cells of one round (a
     provider outage, rate limiting under parallelism, one endpoint down) is exactly the
     dependence the proof cannot absorb: with 20 cells, a whole round sharing one outcome
     takes false PASS from 0.9% to 67%. Items 8 and 9 reduce the exposure; what remains is a
     stated limit, as v1 states "independent across trial ids". Process isolation does not
     establish provider independence.

7. **Scenario seeds: a sealed choice, default `fixed`.**
   - `scenario_seeds: fixed` (default). A cell's seed is the same in every round, derived by
     SHA-256 from the suite digest and the cell's identity, distinct for every cell, shared
     by both arms. The seed feeds the toolset factory, the fault generator and the agent's
     generator (`worker.py:132-150`), so a cell is one fixed scenario and variation between
     rounds must come from the agent's model. The guarantee is then for the suite as
     registered, over outcome randomness only.
   - `scenario_seeds: per_round`. Each (round, cell) gets its own derived seed, as v1 gives
     each repetition its own. This suits offline fixtures whose agents draw from the seed.
     No averaged guarantee is claimed for this mode: a deterministic hash of registered
     content is not a sampling distribution, so there is nothing to average over. The bound
     holds on one explicit condition, which ARCI neither enforces nor checks: in every
     round, the suite mean over that round's scenario instances obeys the null. The report
     prints that condition in the sentence that states the guarantee.
   - In `fixed` mode the scenario is constant, but a live model's behaviour can still drift
     during a run. That a cell's law is the same in every round is an assumption in both
     modes; `fixed` removes the seed as a cause, not the provider.
   - In both modes no two cells of a round share a seed, and derivation uses SHA-256 over
     fixed-width fields with no use of the `random` module, frozen by golden vectors on
     Python 3.11 to 3.14.

8. **Pre-registered rule, bound into every trial.** The suite rule is `alpha`, `delta`, the
   stake set, `max_rounds`, `scenario_seeds`, the error policy of item 10, the
   seed-derivation version, and the sorted cells with both arm identities. Its digest is
   computed over that content only: not over generated ids, seeds or seals, so the
   derivation is not circular. The digest is part of the suite's `experiment_id`.
   `experiment_id` is a field of every frozen-schema `TrialSpec` (`schema.py:472`), so it is
   in every `spec_sha256` (`schedule.py:17-19`). No frozen schema or schedule edit is
   needed. The v1 fields `alpha`, `delta`, `interval_method` and `looks` on a suite
   `TrialSpec` are inert mirrors, and every reader takes the rule from the `SuiteManifest`.

9. **Runner and store.**
   - The stage is one round. The runner submits a round, waits for all of it, stores it,
     then decides. There is no other look.
   - **The unit of scheduling is the pair, not the trial.** One worker slot runs both arms of
     a pair back to back; which arm goes first is fixed by a hash of the pair's identity, so
     neither arm is systematically earlier. Pairs run in parallel across slots in any order.
     This is what "the two arms run adjacently" means, and it needs the suite runner to
     schedule pairs; v1's pool schedules single trials (`runner.py:1558-1578`).
   - The suite gate accepts a store only if: the manifest seal and every trial seal are
     valid; the digest recomputed from the manifest content equals the one in
     `experiment_id`; every trial is an ordinary recorded trial whose scheduled identity and
     `spec_sha256` match the schedule rebuilt from the manifest (the checks of
     `gate.py:41-50` and `:275-318`); the trial set is exactly rounds 1 to r, every cell,
     both arms, with no duplicate or unknown id; every earlier round end recomputes as
     INCONCLUSIVE; and round r is decisive or is `max_rounds`. Anything else is ERROR,
     including a partial round and anything stored after the stopping round. A replayed
     envelope is never evidence.

10. **Errored pairs.**
    - A pair with a harness, grader or infrastructure ERROR is never dropped, never scored 0
      and never re-run inside the experiment. The manifest pre-registers
      `max_errored_pairs`. Up to that number, an errored pair is scored against each test
      separately: as -1 in the PASS wealth and as +1 in the BLOCK wealth. Each wealth can
      only be lower than under any true outcome, so both bounds hold whatever caused the
      error. Beyond that number the experiment is ERROR.
    - Default: 1% of the registered pairs, rounded up, written as an explicit number in the
      sealed manifest. 0 is allowed and gives v1's rule. The validator refuses a value that
      would leave PASS unreachable within the registered rounds. A run after an ERROR is a
      new campaign outside the bound, and the runner records the earlier run in
      `prior_runs` itself. The kernel takes the two scored streams separately, and a
      trailing partial round is no look: neither a verdict nor an exception.
    - **Infrastructure errors, exact rule.** Only ARCI's own model-call wrapper in the
      adapter may mark one, and only for: a connection failure or timeout that the client's
      own retries have exhausted, or an HTTP 429 or 5xx response. It sets a persistent
      harness-error latch on the boundary before the exception propagates, so user code that
      catches the exception cannot turn it back into an agent outcome. Injected faults, tool
      failures, output-parsing failures and budget exhaustion are never infrastructure
      errors. An agent that does not go through the adapter has no such wrapper, and a
      provider failure there is an agent FAIL; the recipe says so.

11. **Hard invariants and verdict priority.** At a round end: ERROR, then a candidate
    hard-invariant violation (BLOCK), then the statistical verdict. The false-BLOCK
    statement covers the statistical BLOCK only; the report gives the BLOCK reason.

12. **Limits enforced before any trial runs.** The budget is registered in rounds, never in
    pairs, so it is `N * max_rounds` by construction. The validator refuses:
    `N * max_rounds` below the first round end at which a candidate that never differs from
    the baseline could PASS (the first round end at or after 79 pairs at the defaults);
    duplicate cells; cells with a `ceiling` fault. It requires an explicit acknowledgement
    when `max_rounds = 1`, which is a fixed-sample test with no early stop, and warns when
    `max_rounds < 3`.

13. **Planning.** `arci plan` gains a suite mode. It computes exactly the earliest PASS and
    BLOCK rounds for the registered rule. Verdict probabilities and expected sessions are
    computed exactly **for a stated model**, and labelled as a projection under that model:
    either per-cell joint laws supplied by the user, or a homogeneous model from three
    inputs (baseline rate, candidate rate, and agreement between arms). A baseline rate and
    agreement alone do not identify the distribution, and the command does not pretend to.

14. **Defaults.** `alpha = 1/20`, `delta = 1/10`, stakes `{1/4, 1/2}`,
    `max_rounds = ceil(400 / N)`: the budget rounds up to a whole round, never down.

## Measured operating characteristics (exact enumeration, defaults)

Power and cost rows are from `plan/exec/v2/spikes/s1c/RESULTS.md` Table C: homogeneous
cells, grid sizes 10, 20 and 50 only, a 400-pair budget (800 sessions). The boundary maxima
are from the review record `plan/exec/v2/reviews/S1c-review-workflow.json`.

| Case | Result |
|---|---|
| Largest directional error found on the margin, by grid size (proved at most `alpha/2` for all laws) | 2.16% at 1 cell, 1.97% at 2, 1.67% at 5, 1.42% at 10, 1.15% at 20 |
| Identical arms at 0.95, independent, 20 cells | PASS 99.9%, about 126 pairs on average |
| 0.95 to 0.75, independent, 20 cells | BLOCK 92.8%, about 203 pairs |
| Identical arms at 0.80, independent, 20 cells | PASS 77.8%, about 251 pairs; the rest INCONCLUSIVE |
| Identical arms at 0.50, independent, 20 cells | PASS 52.0%, about 306 pairs |
| A candidate whose outcomes never differ from the baseline's | PASS at the first round end at or after 79 pairs: 4 rounds with 20 cells. A candidate that also wins some pairs can pass earlier |
| Balanced against sampled, homogeneous cells | Same at 10 cells; at most 1.8 points less power at 20 cells and 4.9 at 50; 7.5 and 25 more pairs on average |
| Balanced against sampled, heterogeneous 20-cell grid, within-margin cases | Up to 5.0 points less PASS probability |
| Grids above 50 cells | Not measured. Few looks; reviewers estimate 1.2 to 3.4 times the sampled design's pairs at high baselines. `arci plan` computes the exact figure for a registered grid |

Against v1: a separate experiment (S1b, sampled design, one task, independent arms) showed
the betting test beats v1's default Clopper-Pearson rule at the same 400-session ceiling and
gives no saving against v1's Newcombe option at equal power. That comparison has not been
re-run for balanced rounds.

## What a release may and may not say

May say: at the default `alpha`, each directional error of the statistical verdict is at
most 2.5% for the suite as registered (with `scenario_seeds: fixed`), proved under the stated
assumptions that outcomes are independent and each cell behaves the same in every round; a
rule changed after the run is detected as an inconsistent
record; the gate says INCONCLUSIVE when it does not know.

Must not say: fewer runs than v1 in general; a verdict on the first run; that a PASS covers
each task (it covers the suite mean, and can hide a regression in one cell, which is why the
per-cell table sits next to the verdict); reliability on tasks outside the suite;
deterministic live inference; that a new campaign resets the error budget; that seals
authenticate execution (they detect inconsistent records; `docs/COMPATIBILITY.md:26-28`).

## Exact frozen changes (made in the phase 1 and release re-freezes)

- New frozen files: `docs/STATISTICS_SUITE.md`, `src/arci/suite_schema.py`,
  `src/arci/suite_schedule.py`, and the suite acceptance tests under `tests/acceptance/`.
- `docs/STATISTICS.md`: **no change.** Its "Nothing else decides" sentence names
  `arci.gate.decide`, which stays the only decider for `arci/0.5`. The suite document stands
  beside it.
- `docs/AGENT_SEMANTICS.md`: one added section for suite experiments. It must state that the
  scheduler rule at lines 17-18 applies to `arci/0.5` experiments and that suite experiments
  follow the suite schedule, and define errored-pair scoring and round-end priority. No
  existing sentence changes meaning for v1.
- `pyproject.toml` and `uv.lock`: version 2.0.0 (with ADR 0012's extras).
- `FROZEN.sha256`: entries for the above and this record. Every other hash unchanged.

## Consequences

- v1 experiments, stores, decisions and all 1,404 tests are untouched.
- With `scenario_seeds: fixed`, an agent that draws its own randomness from the trial seed
  behaves identically in every round, and the packaged suite demo would be deterministic per
  cell. The demo declares `per_round` and its report prints the condition of item 7.
- A grid of 134 cells or more gets three rounds or fewer under the default budget, and a
  grid of 400 cells or more gets one. The validator says so and the user raises
  `max_rounds`.
- A candidate whose provider fails more often than `max_errored_pairs` allows ends as ERROR,
  not BLOCK. Below that number its errored pairs count against PASS and against BLOCK alike.
- The suite runner schedules pairs, so it is new code and not a reuse of v1's trial pool.

## Open points for the maintainer

1. **Seed rule default.** `fixed` gives the stronger statement and is this draft's default.
   Codex and one reviewer preferred `per_round` as the default for scenario coverage; a
   second reviewer was neutral. Both are available as a sealed choice either way. Codex's
   second review then required that `per_round` claim no averaged guarantee, only the
   explicit per-round condition now in item 7.
2. **Default for `max_errored_pairs`.** 1% of registered pairs. Two reviewers and Codex
   support a positive default because rerunning after ERROR is itself a selection. The
   number is a judgment.
3. Power for grids of 50 to 400 cells under `max_rounds = ceil(400 / N)` is not tabulated;
   phase 1's calibration bench adds it.
4. Journal reference for Waudby-Smith and Ramdas is unverified; the arXiv version is cited.

## Review record

- S1c review, five lenses, 18 agents, 13 findings, none refuted. No counterexample at round
  ends: about 220,000 boundary and near-boundary configurations with general three-point
  laws on grids of 1 to 8 cells, largest error 2.16%. Independent recomputation matched all
  23 boundary rows, the six heterogeneous rows and the floors as exact fractions.
- Codex Astra 6, read-only, on draft v2: REVISE. Blocking findings and their answers here:
  conflicting stopping rules (stage is now one round, `rounds_per_look` removed); store
  validation incomplete (item 9 now lists seal, digest, identity and `spec_sha256` checks);
  adjacency contradicted free ordering (item 9 defines pair-level scheduling); provider
  classification had no implementable boundary (item 10 gives the exact rule and the
  latch); planning promised probabilities from inputs that do not identify a distribution
  (item 13 labels a stated model). Codex confirmed that binding through `experiment_id`
  needs no frozen edit, that worst-case scoring is sound, and advised leaving
  `docs/STATISTICS.md` untouched.
