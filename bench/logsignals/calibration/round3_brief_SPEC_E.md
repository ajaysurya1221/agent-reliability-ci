# SPEC_E: the shared calendar drift under the real month structure, and repository-level flips for the gate

Synthetic data only. Standard library only, `/usr/bin/python3 -I`, fixed seeds, use several
processes. No real data exists for you: nothing under `~/arci-data` may be opened. Read first, in
this folder: `FACTS.md`, `SPEC_D.md`, `calib/REVIEW.md` (sections 4 to 6 above all), and
`calib/month_structure.txt`. You may read `calib/review_check.py`, `calib/calib_A.py` and
`calib/calib_B.py` for conventions, but write your own script.

This is the last calibration before a pre-registration is drafted. Report every number
honestly, including bad ones. Keep the compute under about 15 minutes of wall time.

## Why

The review of the first calibration recommends test **F** (sign flip over repositories on
`T = sum_r w_r * rho_r`) and a joint gate **J**. It found one case that defeats F: scenario D8,
a drift over the calendar shared by all repositories in **both** numbers (the two drifts
independent of each other). F rejected 0.306 there. But D8 gave every repository sessions over
one whole 180-day window. The real confirmation half is different: most repositories sit inside
one or two calendar months. `calib/month_structure.txt` has one row per repository (33 rows):
its session count and its count per month, April to September 2026. Counts only; there are no
names and no paired values anywhere.

Two questions decide what is registered:

1. How large is the shared-drift hole **under the real month structure**, and does computing
   the statistic inside `repository x calendar month` blocks (sign flips still per repository)
   close it, at what cost in power?
2. The gate J's own p-value was not protected (0.09 under AR(1) 0.6, 0.18 under long constant
   runs) when signs are flipped per block. Does flipping the sign **per repository** (all blocks
   of one repository flip together) repair the gate's own level, and what does it cost?

## Fixed inputs

- Repository sizes and month counts: `calib/month_structure.txt`. Give every session a date
  uniformly inside its month (30 days per month, window of 180 days). Sessions of a repository
  are ordered by date. Marginals for the two numbers, session length `d` and model names as in
  SPEC_D (state your choices).
- A second, optional variant for the model name: tie it to the calendar (one shared change date
  per name, the same for all repositories), because in real data a model name changes for
  everyone at a release. Report it as its own row where it matters.

## Statistics (all two-sided, alpha 0.05)

- **P** primary as reviewed: blocks = repositories; `rho_b` Spearman with midranks inside a
  block, `w_b = n_b - 1`, a block needs `n_b >= 2` and both numbers non-constant;
  `T = sum_b w_b rho_b`. Reference: one independent random sign per **repository**.
- **PM** the same statistic with blocks = `repository x calendar month`; reference: one sign
  per **repository** (all month blocks of a repository flip together).
- **J** gate as reviewed: blocks = `repository x model name x length tercile` (SPEC_D rule),
  one sign per **block**.
- **JR** the same blocks as J, one sign per **repository**.
- **JMR** blocks = `repository x calendar month x model name x length tercile` (terciles cut
  inside each `repository x month x model name` group), one sign per **repository**.
- A gate "can be formed" when its weight is at least 150 and at least 10 **repositories** carry
  weight (for J also report the old rule: at least 10 blocks).
- p-value: exact enumeration of all sign vectors when the number of sign units is at most 22
  (`p = #{|T*| >= |T| - 1e-9} / 2^units`, no `+1`), by a two-halves count (enumerate partial
  sums of each half, sort one, count by binary search) up to 44, else Monte Carlo with 9,999
  draws and the `+1` rule. Check the two-halves count against brute force for 16 units on a
  case with tied sums.

## Scenarios

Nulls for a session-level link (inside each repository the two series are generated
independently of each other, given the drifts). 1,000 data sets each:

- **E0** independent sessions, no drift (control; expect 0.05).
- **E1** shared drift in both numbers: two independent random walks over the 180 days, each
  shared by all repositories, drift variance share 0.3 of a latent (state your scaling), plus
  independent noise. Also **E1s** with drift share 0.6.
- **E2** shared **month levels**: one level per calendar month in each number (two independent
  sets of six levels), share 0.3.
- **E3** one shared break date in each number, drawn independently for the two numbers (uniform
  over the window), size giving share 0.3.
- **E4** E1 plus AR(1) 0.6 inside each repository in both numbers.
- **E5** the reviewer's D8 itself (every repository spread over the whole window, ignoring the
  month file), to reproduce about 0.31 for P. If you cannot reproduce it within Monte Carlo
  error, say so and say why.
- **E6** E1 with the drift in the signal only (expect about 0.05).
- **E7** long constant runs (mean 15 sessions, noise share 0.05), no drift, under the real
  month structure.
- **E8** AR(1) 0.6 in both, no drift.

Not a null by the letter, report separately (400 data sets):

- **E9** one shared break date common to **both** numbers (a single event that moves both).

Alternatives (400 data sets each): innovation correlation 0.18 and 0.25, once with independent
sessions and once with AR(1) 0.6, no drift.

Gate scenarios (400 each, under the real month structure): G0 (E0), G0b (E8), G0c (E7),
G0d (E1), G1 (link fully carried by length, SPEC_D), G4 (no direct link; both numbers load on
`log d` and on a per-model effect), G3a (direct 0.18 on top of G1).

## Report

For every scenario: rejection rate of P, PM, and of each gate alone (J, JR, JMR); the pairs
"primary rejects, gate rejects, same sign" for (P, J), (P, JR), (PM, JR), (PM, JMR); mean number
of weight-carrying repositories and mean weight for each statistic; how often each gate cannot
be formed. Mean and SD of `rho_bar` for P and PM.

Checks on your own code: the two-halves count against brute force; a second run with the same
seed is byte-identical; E0 gives 0.05 within Monte Carlo error for every statistic.

Write to `calib2/` in this folder: your script, a results file, and `REPORT_E_<label>.md` with
the tables and, in at most 12 lines, your recommendation: which primary blocks (repository, or
repository x month), which gate and which sign unit, and what still is not protected, in plain
words. A test "holds" when its rate is at most 0.065 at 1,000 data sets.
