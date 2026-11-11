# REVIEW: S1 suite statistics spike

Reviewer: orchestrator (Claude Fable 5.2), 2026-11-10. Author of the spike: Codex Astra 6.
Method: I re-ran the tests, lint and the full enumeration and simulation myself (every value I
compared was identical; result files differ only in recorded elapsed time). I read
`suite_stats.py` and checked the algebra by hand. Then a five-lens independent review with a
separate skeptic per finding. The first run completed four lenses (proof, simulation, claims,
product contract: 10 findings, 0 refuted) before a usage limit cut off the fifth. The re-run
completed all five (18 agents, 13 findings, 0 refuted); its findings agree with the first run
and add two points, recorded below. Full outputs: `S1-review-workflow-partial.json` (first
run) and `S1-review-workflow.json` (complete run).

**Independent re-implementation (fifth lens): no bug found.** A separately written exact
implementation agreed with `suite_stats.decide` on all 2,539,107 ordered paths tried, in
verdict, stopping pair and every checkpoint wealth. Brute-force path probabilities matched
the spike's enumeration as exact fractions in 1,088 of 1,088 comparisons. An independent
absorbing recursion with no frontier assumption equalled `results.json` exactly for 360
Table A entries.

## Verdict: ACCEPT the guarantee, REVISE the defaults and the claims

**The validity argument holds.** No finding touches error control.

- Each wealth factor is non-negative with conditional expectation at most one under its null,
  for any `delta` in (0, 1) and any stake fraction in [0, 1]. Checked exactly.
- A fixed mixture of products is what the code computes, and is a non-negative
  supermartingale. Ville's inequality gives `alpha/2` per direction; checkpoints, first-stop
  and the cap only shrink the crossing event.
- Uniform with-replacement draws give `E[d | past] = Delta` for any mix of task difficulty
  and any dependence between arms.
- PASS and BLOCK cannot both cross under a fixed or mixture rule, so the ERROR branch for a
  simultaneous crossing is unreachable.
- Reviewers reproduced Table A cells to eight decimals with independent code, and a finer
  `p_zero` grid moves the worst case by less than 0.00001.
- Exact worst directional error at the recommended defaults: 1.05% against a 2.5% limit.

## What changes before ADR 0011

| # | Finding | Decision |
|---|---|---|
| 1 | The stake set {1/8, 1/4, 1/2, 3/4} is not supported by the spike's own Table C; a single stake of 1/2 beats it in most rows, and the scenario grid was too narrow to choose a default | Task S1b compares stake sets by exact enumeration on a grid and criterion declared in its brief before any number is computed. Any fixed set is valid, so this affects power only |
| 2 | The guarantee is an average over the schedule draw as well as outcomes. For one frozen schedule the directional error ranged from about 0.02% to 8% across seeds in one boundary scenario | ADR 0011 states this plainly. The suite manifest has no seed field: the schedule key is a digest of the decision-relevant content. S1b adds a conditional-on-schedule table so the spread is published |
| 3 | A schedule that is a pure function of the manifest can be chosen before any trial runs | The report shows the realised allocation next to the verdict: draws per cell against expectation, and cells never drawn. The plan's "detected or disclosed" list gains this item as disclosed, not detected |
| 4 | Cell draws and trial seeds have no version-independent specification; `random.Random` integer draws are not guaranteed stable across Python versions | Both are derived by SHA-256 from the schedule key and pair index, with rejection sampling for exact uniformity, and frozen by golden vectors in CI on Python 3.11 to 3.14 |
| 5 | Under early stopping, "rerun after an ERROR" favours runs that stopped early | An errored pair is never dropped or scored zero. ADR 0011 chooses between voiding the run (rerun is a new campaign, recorded automatically) and worst-case scoring per direction with a pre-registered cap on errored pairs |
| 6 | No decision floor is stated. A no-change candidate cannot PASS before 70 pairs (140 sessions) at the defaults | The gate computes the earliest possible PASS and BLOCK for the registered rule and refuses a `max_pairs` below the PASS floor |
| 7 | Table D compares at a 200-pair cap, not the recommended 400, and gives no bottom line | S1b regenerates it at both caps with ceiling sessions and a bottom line per comparator |
| 8 | Table B is 10 distinct laws, not 72 scenarios; it tests the sampler, not suite shapes | Relabelled. In phase 1 the same test runs against the real schedule generator and compares with the exact value per law |
| 9 | No test ties the default-parameter decision frontier to the rational reference (it is correct; the evidence was missing) | S1b adds the test; phase 1 carries it |
| 10 | Citation pinpoints may be off (capital process is probably section 4 of Waudby-Smith and Ramdas, not 2) and two short derivations are labelled as proved by citation | Checked against the paper before ADR 0011 freezes the text; the two derivations are written in line |

## Added by the complete review run

| # | Finding | Decision |
|---|---|---|
| 11 | The 400-pair default is sized for suites where the arms mostly agree. For an unchanged candidate with independent arms at success rates of 0.5 to 0.7, about half of runs end INCONCLUSIVE at the cap | The design record states the INCONCLUSIVE rate as a function of suite difficulty, and `arci plan` gets a suite mode that computes it exactly before any trial is spent |
| 12 | The ERROR verdict for PASS and BLOCK crossing together cannot occur for any fixed or mixture rule | Kept as a defensive assertion in the kernel; no acceptance test expects a real stream to produce it |

## S1b follow-up (2026-11-10)

Codex ran `plan/exec/v2/tasks/S1b-stake-set-and-schedule.md`. I re-ran `run_all.py` twice:
exit 0 both times, outputs byte-identical between my two runs, 37 tests pass.

Discrepancy, recorded as found: the `results.json` Codex left had a different SHA-256 from
my re-runs. Every headline number I checked individually matches Codex's report. I re-ran in
place and so overwrote the original before comparing; the cause is undetermined. The file
records hashes of its own sources, so a source reformatted after Codex's last run is the
likeliest explanation.

Results that feed the design record:

- Stake set `{1/4, 1/2}` wins on the pre-declared criterion (minimum correct-decision
  probability 0.5377 over 36 scenarios, within 0.001 of the best, 10 fewer expected pairs).
- Floors at the defaults: earliest possible PASS 10 pairs, PASS for a candidate that never
  differs from the baseline 80 pairs, earliest BLOCK 20 pairs.
- **Conditional on one frozen schedule the sampled design does not hold its bound.** With a
  regression in 3 of 20 cells and the suite mean on the margin, false PASS over 2,000
  schedules: median 0.05%, 90th percentile 2.4%, 99th percentile 23%, maximum 53%. The mean
  is 1.2%, consistent with the theorem. A manifest's schedule is fixed, so this is the error
  rate a user of that manifest actually faces.
- This reopens the sampling design. Task S1c tests balanced rounds, where each round runs
  every cell once and looks happen only at round ends. The proof lens derived independently
  that a complete balanced round keeps the product's expectation at or below one.

## Citation check (finding 10), done 2026-11-10

Read: arXiv:2010.09686v7 (25 Aug 2022), abstract page and HTML. Sections 1 to 3.3 and
section 4 through Proposition 2 were read verbatim; later sections by heading only.

- General recipe (non-negative process under the null plus Ville's inequality): section 2.2,
  Theorem 1. Not section 2 at large.
- Capital process `K_t(m) = prod(1 + lambda_i(m)(X_i - m))` and the bet range
  `(-1/(1-m), 1/m)` for data in [0, 1]: section 4, equation 23. `CONTRACT.md` cites section 2
  for this; that pinpoint is wrong.
- The setup needs only a constant conditional mean, not i.i.d. data: stated in sections 2,
  3.1 and 4. This supports the contract.
- Sampling without replacement is section 5, a different construction. Supports the
  contract's warning.
- A mixture of capital processes with different fixed bets: not found as a stated result in
  the text read. The mixture step is one line (a convex combination of supermartingales is a
  supermartingale by linearity of conditional expectation) and must be written in line, not
  cited. The same goes for the one-sided composite-null step.
- Journal reference: the abstract page lists none. Codex's "JRSS B 86(1), 1-27" is
  unverified. The design record cites the arXiv version with section numbers until someone
  checks the journal.

## What the release may and may not say (from the claims lens, confirmed)

May say:

1. Each directional error is at most 2.5% at any stopping point, proved under the sampling
   contract for any dependence between arms and any task mix.
2. Against the v1 default rule, independent arms, one task, same 400-session ceiling: higher
   decision probability in the four non-margin scenarios measured, at lower expected cost.
3. When the arms succeed and fail on the same tasks, a no-change candidate passes in 70 pairs.

Must not say:

1. That v2 needs fewer runs than v1 in general. Against v1's Newcombe option, with independent
   arms on one task, there is no saving at equal power.
2. That a first run decides. Nothing can PASS before 70 pairs at the default margin.
3. That a PASS covers each task. It covers the suite mean.

## Phase 0 gate reading

S1 passes error control and shows no general saving over v1 Newcombe. That is the plan's
middle branch: continue; the release claims a proven multi-task gate and makes no "fewer
runs" claim. The earlier planning estimate (104 and 183 pairs) is replaced by measured
figures once S1b fixes the stake set.
