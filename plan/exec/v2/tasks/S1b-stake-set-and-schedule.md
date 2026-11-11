# TASK S1b: stake-set selection, schedule derivation and published limits (phase 0)

You are the implementer. The orchestrator re-runs everything you report; your report is not
acceptance evidence. Read `AGENTS.md` first and obey its hard rules.

## Why this task exists

S1 established the guarantee. Its review (`plan/exec/v2/reviews/S1-review.md`) accepted the
validity argument and asked for six additions before the design record is written. Read that
review and `plan/exec/v2/spikes/s1/` (`suite_stats.py`, `suite_stats_sim.py`, `CONTRACT.md`,
`RESULTS.md`) first. Reuse S1's code by importing it; do not edit it.

## Owned files

Only `plan/exec/v2/spikes/s1b/`. Create nothing and edit nothing anywhere else. No changes
under `src/`, `tests/`, `docs/` or `bench/`. No git commands that change state. No network.
Standard library only. Run Python as `.venv/bin/python` with
`PYTHONPATH=plan/exec/v2/spikes/s1:plan/exec/v2/spikes/s1b`.

## Part 1: choose the stake set by a rule fixed here, before you compute anything

Any pre-registered fixed set of stake fractions is valid; the choice affects power only. The
grid and criterion below are declared by the orchestrator now. One reviewer has already run
an informal grid that favoured {1/4, 1/2}; that is disclosed, and it is why the criterion is
fixed in writing before the systematic run. Do not change the grid, the candidates or the
criterion. If you believe one is badly chosen, say so in the report and still run it as
written.

- Candidate sets (equal weights): `{1/2}`, `{1/4, 1/2}`, `{1/4, 1/2, 3/4}`, `{1/8, 1/4, 1/2}`,
  `{1/8, 1/4, 1/2, 3/4}`.
- Fixed design: `alpha = 1/20`, `delta = 1/10`, `batch = 10`, `max_pairs = 400`.
- Scenario grid, all by exact count-based enumeration (no simulation):
  - baseline success probability in {0.50, 0.65, 0.80, 0.90, 0.95, 0.99};
  - candidate: no change; a regression of 0.20; a regression of 0.30;
  - dependence: independent arms; and an intermediate coupling whose joint law is the equal
    mixture of the independent law and the maximal positive (Frechet upper) coupling.
  - That is 36 scenarios. The correct decision is PASS for no change and BLOCK for a
    regression.
- Criterion, in order: (1) the set with the highest minimum correct-decision probability over
  the 36 scenarios; (2) sets within 0.01 of that maximum are tied, and the tie goes to the
  lowest mean expected stopping pairs over the 36 scenarios; (3) then to the set with fewer
  stakes.
- Report the full 36 by 5 table (correct-decision probability and expected pairs), the
  winner, and where the winner is worse than each other set by more than 0.02.

## Part 2: decision floors

For the winning set and for `delta` in {1/20, 1/10, 1/5} at `alpha = 1/20`, `batch` in {1, 10}:
the earliest checkpoint at which PASS is possible at all; the earliest PASS for a stream of
all zeros (a no-change candidate that never differs from the baseline); how that moves with
1, 2, 3 and 5 losses; the earliest BLOCK; the maximum number of losses a PASS tolerates at
200 and at 400 pairs. Provide a pure function `decision_floors(plan)` returning these, and a
function `validate_plan(plan)` that rejects a `max_pairs` at which the all-zero stream cannot
PASS.

## Part 3: schedule derivation, exact and portable

Implement and test, with no use of the `random` module:

- `schedule_key(...)`: SHA-256 over a canonical byte encoding of the decision-relevant
  content only: the cells sorted by (task id, condition id), the two arm identities, the rule
  (`alpha`, `delta`, stake set, `batch`, `max_pairs`) and the list of prior run ids. Field
  order and cosmetic fields must not change the key; reordering tasks must not change it;
  adding a prior run id must.
- `cell_index(key, i, n_cells)`: for attempt a = 0, 1, ...: `h = SHA-256(b"arci-suite/1 cell"
  + key + i as 8 bytes big-endian + a as 4 bytes big-endian)`; `v` = the first 8 bytes of `h`
  as a big-endian integer; accept when `v < 2**64 - (2**64 % n_cells)` and return
  `v % n_cells`.
- `trial_seed(key, i)`: a 63-bit integer from `SHA-256(b"arci-suite/1 seed" + key + i as 8
  bytes big-endian)`, shared by both arms of pair i, distinct for a repeated cell.
- Tests: golden vectors for at least 20 (key, i, n_cells) triples written into the test file
  as literals; a chi-square uniformity check over 200,000 draws for n_cells in {7, 20, 60,
  150}; independence of the key from field order; the rejection branch exercised with a
  crafted small modulus helper.
- A table: expected number of cells never drawn, and the probability that a given cell is
  never drawn, at 70, 200 and 400 pairs for grids of 20, 60 and 150 cells, exact.

## Part 4: the guarantee conditional on one frozen schedule

The 2.5 percent bound averages over the schedule draw. For two boundary scenarios with suite
mean exactly `-delta` (a regression concentrated in 3 of 20 cells, and one spread evenly over
20 cells), compute by exact enumeration the false-PASS and false-BLOCK probability
conditional on each of 2,000 schedule keys (derived as in part 3), with the winning stake
set. Report mean, minimum, median, 90th and 99th percentile and maximum of each. State
plainly what a user may conclude about a single manifest. Confirm the mean agrees with S1's
Table A value for the same law.

## Part 5: an honest comparison with v1

Regenerate S1's Table D for the winning set at caps 200 and 400, independent arms and the
intermediate coupling from part 1, with these columns: correct-decision probability, expected
sessions, ceiling sessions. Use the v1 numbers published in `docs/STATISTICS.md` and say
where a v1 number does not exist. End with one bottom-line sentence per comparator
(v1 Clopper-Pearson fixed, v1 Newcombe fixed, v1 Newcombe sequential): better, worse or
mixed, and on what.

## Part 6: the missing frontier test

A pytest test at the recommended defaults that, for every checkpoint up to `max_pairs`,
checks the count-based decision frontier used by S1's enumeration against
`suite_stats.count_wealth` plus `suite_stats.classify` on the states adjacent to the
frontier. Also one agreement point at cap 400 that goes through `suite_stats.decide` on
simulated streams, not through the shared frontier object.

## Deliverables

`stake_selection.py`, `floors.py`, `schedule.py`, `conditional.py`, `compare_v1.py`,
`test_s1b.py`, `RESULTS.md` (all tables, the winner, the bottom lines, and anything that did
not come out as expected) and `results.json`. One entry point `run_all.py` that regenerates
everything and exits non-zero if a test or a stated check fails; target under 30 minutes on
15 cores.

## Pass conditions

1. `run_all.py` exits 0 and its outputs are byte-identical on a second run, apart from a
   recorded elapsed time kept out of `results.json`.
2. `.venv/bin/pytest plan/exec/v2/spikes/s1b -q` passes; `ruff format --check` and
   `ruff check` are clean on the owned directory.
3. `shasum -a 256 -c FROZEN.sha256` passes.

A result you did not expect is a valid result. Report it; do not adjust the declared grid,
candidates or criterion.

## Final message

Files created, exact commands with their last lines, the winning stake set with its margin,
the floors at the defaults, the conditional-on-schedule spread in one line, the three bottom
lines against v1, anything you could not do, and risks. No long logs.
