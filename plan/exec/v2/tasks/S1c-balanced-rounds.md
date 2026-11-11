# TASK S1c: balanced rounds versus sampled cells (phase 0, decides the v2 design)

You are the implementer. The orchestrator re-runs everything you report; your report is not
acceptance evidence. Read `AGENTS.md` first and obey its hard rules.

## Why this task exists

S1b measured the sampled-cell design conditional on one frozen schedule
(`plan/exec/v2/spikes/s1b/RESULTS.md` section 4). When a regression sits in 3 of 20 cells
with the suite mean exactly on the margin, the false-PASS probability for a single manifest
has median 0.05 percent, 90th percentile 2.4 percent, 99th percentile 23 percent and maximum
53 percent over 2,000 schedules. The 2.5 percent bound holds only on average over the
schedule draw. A manifest's schedule is fixed, so rerunning does not average it out.

The alternative is a **balanced design**: a round runs every cell of the grid exactly once,
both arms; the test is evaluated only at the end of complete rounds. There is then no
schedule randomness in which cells are observed.

## The claim to prove or refute

Notation as in S1: cell c has paired difference `d_c` in {-1, 0, +1} with mean `Delta_c`;
`Delta` is the mean of `Delta_c` over the N cells; stakes are fixed fractions `q` of the
legal maximum; wealth is the equal mixture over `q` of products.

Claim: with trials independent across cells and rounds, and each cell's law the same in
every round, the round-level factor for the PASS test is
`B = prod over cells of (1 + lam * (d_c + delta))`, and
`E[B] = prod (1 + lam * (Delta_c + delta)) <= (1 + lam * (Delta + delta)) ** N <= 1`
whenever `Delta <= -delta`, by the inequality of arithmetic and geometric means, since every
term is non-negative for a legal stake. Symmetrically for the BLOCK test with
`1 - lam * (d_c + delta)`. So each product, and each fixed mixture of products, is a
non-negative supermartingale across rounds, and Ville's inequality gives `alpha/2` per
direction at round ends, for every manifest, over outcome randomness only.

Check every step. In particular: independence needed between cells within a round;
non-negativity of each expectation term; whether equality cases exist; whether the argument
survives a final partial round (expected answer: no, mid-round looks are unprotected; show
it with a concrete counterexample or prove otherwise); and whether within-pair dependence
between arms is still unrestricted.

## Owned files

Only `plan/exec/v2/spikes/s1c/`. Create nothing and edit nothing anywhere else. Import S1 and
S1b code; do not edit it. No changes under `src/`, `tests/`, `docs/` or `bench/`. No git
commands that change state. No network. Standard library only. Run Python as
`.venv/bin/python` with
`PYTHONPATH=plan/exec/v2/spikes/s1:plan/exec/v2/spikes/s1b:plan/exec/v2/spikes/s1c`.

## Fixed design for every table

`alpha = 1/20`, `delta = 1/10`, stake set `{1/4, 1/2}` (S1b's winner, not to be re-tuned).
Sampled design: `batch = 10`, `max_pairs = 400`. Balanced design: checkpoints at round ends
only; the cap is the largest whole number of rounds with at most 400 pairs.

For fixed stakes the wealth depends only on the running counts of +1 and -1. Under the
balanced design the per-round increment of those counts is the convolution of the cells'
trinomial laws, so every probability below is computable exactly with an absorbing dynamic
programme over rounds. Use exact rational arithmetic. No simulation except as a cross-check.

## Deliverables (inside the owned directory)

1. `PROOF.md`: the argument above written out line by line, each step marked PROVED-IN-LINE,
   CHECKED-BY-ENUMERATION or ASSUMED, with the counterexample (or proof) for mid-round looks.
2. `balanced.py`: reference decision procedure for the balanced design (input: an ordered
   list of rounds, each a list of N differences) and the exact enumeration.
3. `run_all.py`, `test_s1c.py`, `RESULTS.md`, `results.json`.

## Tables required

A. **Error control at the boundary, balanced design, exact.** Grid sizes N in {5, 10, 20, 50,
   100}. Laws with suite mean exactly `-delta`: even; concentrated in 1, 2 and 3 cells (as far
   as feasible for each N); half the cells at `+0.3`-style improvement and the rest
   regressing to compensate; cells with P(+1) > 0 and P(-1) > 0 mixed. Report false PASS and
   false BLOCK for each. Then an adversarial search: for N in {5, 10, 20}, search over cell
   laws with suite mean exactly `-delta` (coordinate ascent or random restarts, at least
   2,000 candidate configurations per N, seeds recorded) for the configuration that maximises
   false PASS, and separately false BLOCK. Report the maxima found. The claim predicts none
   exceeds `alpha/2`.
B. **The same boundary laws under the sampled design, conditional on the schedule**, reusing
   S1b's method with 500 schedule keys per law: mean, median, 90th, 99th percentile, maximum.
   Side by side with A.
C. **Power and cost, balanced versus sampled (unconditional)**, on S1b's 36-scenario grid
   with every cell having the same law (so both designs face the same marginal law), for
   N in {10, 20, 50}: correct-decision probability and expected pairs. Then 12 heterogeneous
   scenarios declared here: baseline mix of cells at 0.99, 0.80 and 0.30 success in
   proportions (60%, 30%, 10%); candidate equal to baseline; candidate with every cell 0.05
   worse; candidate with a 0.5 drop concentrated in 10 percent of cells; candidate with a 1.0
   drop in 20 percent of cells (suite mean -0.20); each with independent arms and with the
   intermediate coupling of S1b, for N = 20. Three of these are no-regression or
   within-margin cases where the correct decision is PASS or no decision; say which.
D. **Floors for the balanced design**: earliest PASS for an all-zero stream and earliest
   BLOCK, for N in {5, 10, 20, 50, 100, 150, 300}; and the number of whole rounds that fit
   under 400 pairs. State for which N the design cannot reach a verdict within 400 pairs.
E. **Mid-round looks**: the counterexample, with its exact false-PASS probability if looks
   were allowed after every pair in a fixed cell order.

## What the report must conclude

One paragraph each, with numbers: (1) does the balanced design control each directional
error at `alpha/2` for every manifest; (2) what it costs or gains in power and expected
pairs against the sampled design; (3) for which grid sizes it is usable under a 400-pair
cap; (4) a recommendation: balanced only, sampled only, or balanced by default with sampled
as a declared option for grids too large for whole rounds, with the reason.

## Pass conditions

1. `run_all.py` exits 0 and a second run is byte-identical apart from a recorded elapsed
   time kept out of `results.json`. Target under 30 minutes on 15 cores.
2. `.venv/bin/pytest plan/exec/v2/spikes/s1c -q` passes; `ruff format --check` and
   `ruff check` clean on the owned directory.
3. `shasum -a 256 -c FROZEN.sha256` passes.

If the claim is false, that is the result. Report the counterexample; do not adjust the
design to rescue it.

## Final message

Files created, exact commands with their last lines, the answer to each of the four
conclusions in one or two lines, anything you could not do, and risks. No long logs.
