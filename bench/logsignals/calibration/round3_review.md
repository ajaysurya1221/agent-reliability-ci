# REVIEW_E — adversarial review of the two SPEC_E calibrations

Reviewer: a third implementation written from `SPEC_E.md`, `calib/REVIEW.md` and
`calib/month_structure.txt`, with its own generator, its own statistic and its own sign-flip
count. Script: `calib2/review_E.py`. Numbers: `calib2/results_E_review.txt`
(2 runs, 10 and 6 processes, 1:51 and 2:46 wall; the two result files are byte-identical
apart from the line that prints the process count). Synthetic data only; no real data was
opened; standard library only, `/usr/bin/python3 -I` 3.9.6.

Nothing in this file is a cause, a prediction or a measure of quality. Every figure is the
rejection rate, or a summary statistic, of a described test on generated numbers.

My own checks: the two-halves count equals direct enumeration of all `2^16` sign vectors to
the last bit on four 16-unit cases including tied sums (largest difference 0.000e+00); the
extreme statistic gives `2/2^16 = 3.052e-05`; the Monte Carlo fallback differs from the exact
count by at most 0.0109 over 20 E0 repository vectors; E0 gives 0.051 / 0.048 / 0.054 /
0.057 / 0.056 for P / PM / J / JR / JMR at 3,000 data sets.

My drift parameter `lam` is the variance share of a calendar field that is **demeaned and
scaled to unit standard deviation over the 180-day grid**, with the within-repository share
`0.7 - lam` and a repository effect of 0.3. This is A's convention and it makes the
drift-to-within variance ratio explicit: `lam/(0.7 - lam)`.

---

## 1. Where the two agree

53 of the 90 rate cells I could line up (18 scenarios x 5 statistics) sit within two Monte
Carlo standard errors of each other, and my own run sits with them:

- **E0.** All five statistics at 0.05: A 0.046-0.054, B 0.047-0.057, mine 0.048-0.057.
- **E6** (drift in the signal only): A 0.042-0.064, B 0.043-0.061, mine 0.047-0.062.
- **E8** (AR(1) 0.6, no drift) for the primary: P 0.057 / 0.052 / 0.045, PM 0.052 / 0.055 /
  0.054; and J above the bar in all three (0.086 / 0.104 / 0.084).
- **E7** for the primary: P and PM hold in all three (0.038-0.061).
- **E3** for every statistic (0.042-0.072 across all three).
- **The alternatives.** A18 P 0.662 / 0.657 / 0.653, PM 0.642 / 0.635 / 0.617; A25 P 0.922 /
  0.905 / 0.918; A18ar P 0.485 / 0.468 / 0.485; A25ar P 0.750 / 0.705 / 0.728. The
  P-to-PM power cost is 0.020-0.036 in all three reports.
- **`rho_bar` is centred under every drift null in all three** (|mean| <= 0.010 except the E3
  and E9 rows, item 3 below); only its spread moves. E5 spread: P 0.189 / 0.119 / 0.186
  against PM 0.066 / 0.061 / 0.070.
- **Weights and block counts**, to about 0.2: E0 P 20.1-20.3 repositories and W 381; PM
  29.4-29.5 blocks, W 361-362; J 42.5-42.8 blocks on 13.3-13.4 repositories, W 299-300;
  JMR 50.0-50.4 blocks, W 264-265. PM costs about 5% of the weight and no repositories under
  the month file; under a whole-window spread it costs a third of the weight.
- **Formation.** The repository floor bites and the old block floor does not: E7 J/JR cannot
  be formed in 0.417 / 0.448 / 0.427 of runs against 0.002 / 0.005 / 0.003 under the 10-block
  rule. JMR cannot be formed in 0.971 / 0.952 / 0.968 of whole-window runs and 0.547 / 0.551 /
  0.535 of E7 runs.
- **Both pass the 16-unit brute-force check and both are byte-identical on a repeat run with a
  different worker count.** So does mine.
- **Both reach the same qualitative verdict on the sign unit**: one sign per repository, not
  per block.

## 2. Cells that differ by more than two Monte Carlo standard errors

37 of the 90 cells differ by more than two standard errors of the difference (ratios 2.1 to
16.1; the arithmetic is in the table below, computed from the two reports' own counts). They
fall into four causes, all of them in the generators or in the reporting convention, not in
the statistic.

| row | stat | A | B | diff / SE |
|---|---|---|---|---|
| E1 | P, J, JR | 0.090, 0.097, 0.066 | 0.048, 0.046, 0.043 | 3.7, 4.4, 2.3 |
| E1s | all five | 0.237 … 0.122 | 0.059 … 0.040 | 6.8 to 15.9 |
| E2 | P, J | 0.116, 0.177 | 0.087, 0.111 | 2.1, 4.2 |
| E4 | P, J, JR | 0.094, 0.164, 0.085 | 0.050, 0.095, 0.056 | 3.8, 4.6, 2.5 |
| E5 | P, J, JR, JMR | 0.629, 0.531, 0.424, 0.069 | 0.291, 0.205, 0.166, 0.001 | 8.4 to 16.1 |
| E7 | P, J, JR, JMR | 0.061, 0.182, 0.046, 0.062 | 0.038, 0.095, 0.028, 0.014 | 2.1 to 5.7 |
| E9 | P, J, JR | 0.182, 0.236, 0.118 | 0.098, 0.085, 0.050 | 3.4, 5.9, 3.5 |
| G1, G4, G3a | gates and P/PM | 0.288, 0.196, 0.930 (J) | 0.145, 0.122, 0.812 | 2.8 to 5.2 |

### Cause 1 — the drift field is scaled differently, by a factor of 5 to 12

`calib_E_A.py` lines 316-336 standardize the shared field to **unit standard deviation over
the 180-day grid** and then take the drift share out of the within-repository budget
(`w_in = 1 - 0.3 - drift - length - model`, line 391). `calib_E_B.py` lines 138-146 and
345-352 keep the raw walk, scaled so the **mean variance over days** is 1, and take the share
off the within-repository latent only. I measured the field's within-window variance: A's walk
1.0000 by construction, B's walk 0.3412, B's break field 0.6704 against A's 1. The resulting
drift-to-within variance ratio at the same nominal share:

| nominal share | A (and mine) | B | ratio |
|---|---|---|---|
| 0.3 | 0.750 | 0.146 | 5.1x |
| 0.6 | 6.000 | 0.512 | 11.7x |

**Which is right.** For the words of SPEC_E ("drift variance share 0.3 of a latent"), A is
right and B's drift rows at a nominal 0.3 are at about a fifth of that strength. My own run on
A's convention reproduces A and not B: E1 P 0.099 (A 0.090), E1s P 0.240 (A 0.237), E2 P 0.109
(A 0.116), E4 P 0.085 (A 0.094), E5 P 0.618 (A 0.629), E9 P 0.199 (A 0.182). Every E1 / E1s /
E2 / E4 / E5 / E9 cell in the table above has this one cause, and A's column is the one my
implementation confirms.

### Cause 2 — E5 was run at a different drift share by B, undeclared

`calib_E_B.py` line 229 sets `driftshare=0.5` for E5 while E1/E1s/E2/E3/E4 use 0.3/0.6. B's
report says E5 is "whole window, share 0.5" in the table but its Deviations list does not
mention it, and B's claim that E5 reproduces D8 rests on it. A kept 0.3 everywhere, reported
E5 = 0.629, said plainly that the review's 0.306 was not reproduced, and added E5a/E1a at
0.15.

**Which is right.** Both, on different questions, and SPEC_E's two demands for E5 (share 0.3
*and* about 0.31 for P) cannot both be met under either scaling. I located the matched
strength myself: the drift-to-within ratio that reproduces the review's D8 (P 0.306,
sd(`rho_bar`) 0.12) is about 0.27-0.34, that is `lam` 0.15 in A's parametrisation, not 0.30 —
my E5 at `lam` 0.15 reads P 0.322 with sd 0.1036, and at `lam` 0.30 reads 0.618 with sd 0.186.
A's E5a (0.284, sd 0.0997) and B's E5 (0.291, sd 0.1185) bracket the anchor; A's headline
0.629 and my 0.618 are at a strength about five times the anchor.

### Cause 3 — the denominator of a gate rate

A's Table 1 reports the rate **among the data sets in which the statistic could be formed**
(and gives the other reading in `results_E_A.txt` Table 1b). B counts a gate that cannot be
formed as "does not reject". Where the cannot-form share is large this alone is the whole
difference, and my run brackets both:

| cell | A conditional | A unconditional | B | mine conditional | mine unconditional |
|---|---|---|---|---|---|
| E7 J | 0.182 | 0.106 | 0.095 | 0.179 | 0.102 |
| E7 JMR | 0.062 | 0.028 | 0.014 | 0.055 | 0.025 |
| E7 JR | 0.046 | 0.027 | 0.028 | 0.056 | 0.032 |
| E5 JMR | 0.069 | 0.002 | 0.001 | 0.000 | 0.000 |

**Which is right.** Neither is an error; they answer different questions and both belong in a
registration. The conditional rate is the gate's own level given that it ran, and it is the one
to compare with the review's 0.178; the unconditional rate is what a reader of the published
sentence meets, because a gate that cannot be formed prints "cannot tell". A printed both; B
printed one. The E7-J row is therefore not a disagreement at all: 0.182 (A) and 0.095 (B) are
the same measurement under two denominators.

### Cause 4 — the length share in G1/G4/G3a

A puts 0.3 of the **total** latent on `log d`; B puts 0.3 of the within latent after a 0.3
repository share, i.e. 0.21 of the total. Realised `rho_bar`: A +0.345, B +0.238. My run at
0.30 gives J 0.271 and the pair 0.247 (A 0.288 / 0.245); at 0.21 it gives J 0.118 and the pair
0.123 (B 0.145 / 0.122). **Both are right for their own stated strength**, and the gate's leak
rate at G1 scales with that strength, so no single number should be quoted as "the" leak.

## 3. Errors found

1. **A null that is not a null: E3.** Both implementations code the shared break as a step with
   a **fixed direction in both numbers** (A: the standardized indicator, `calib_E_A.py`
   328-334; B: `-1` then `+1`, `calib_E_B.py` 155-158). Two such fields are both monotone in
   the day whatever their two dates, so the two break fields are positively correlated by
   construction and E3 does not have a mean-zero `rho_bar`: measured mean +0.0160 (mine),
   +0.0186 (A), +0.0100 (B) against standard errors of 0.0013 to 0.0019. With a random
   direction drawn per number (my `E3r`) the mean is +0.0013. The rates move little (my P
   0.063 fixed against 0.072 random, 2,000 sets each), so the E3 conclusion stands, but as
   coded E3 carries a positive offset in the published number and should be re-coded with a
   per-number sign before it is used as a null.
2. **E1 / E1s / E5 are nulls only in SPEC_E's sense**, which both reports follow; the review
   itself records that D8 "is not a null by the letter of the estimand". E9 is flagged as not a
   null by both. No report claims otherwise, so this is a labelling point, not an error.
3. **Sign units: no error.** I read both block builders and both sign-unit aggregators
   (`calib_E_A.py` 503-547, `calib_E_B.py` 441-465). P, PM, JR and JMR flip one sign per
   repository, summing that repository's block contributions first; J flips one per block.
   The unit counts agree with mine (E0: P 20.1, JR 13.3, JMR 12.7, J 42.5).
4. **Month blocks: no error.** Both draw a day uniformly inside the session's own month
   (`30*m + U(0,30)`), order a repository's sessions by day, and label the block
   `floor(day/30)`, re-derived for the whole-window E5. My month counts reproduce FACTS
   (102, 76, 109, 104, 25, 7).
5. **The p-value rule departs from the spec in both, in the same way and only for J.** SPEC_E
   asks for the exact two-halves count up to 44 sign units. A cuts it at 28, B at 38, and both
   fall back to 9,999 Monte Carlo draws with the `+1` rule above that; both declare it and both
   measure the cost against the exact count (A: largest difference 0.0095, no decision changed
   over 40 cases; B: 0.0119, 0 of 44 changed). My own cut is 24, so all of my J is Monte Carlo
   and my P/PM/JR/JMR are always exact. P, PM, JR and JMR have at most 24 units in all three
   implementations, so the primary is exact everywhere and only the gate's own p-value is
   affected. No other p-value rule difference: both use `|T*| >= |T| - 1e-9`, no `+1` in the
   exact count, two-sided, alpha 0.05.
6. **Gate floors: no error.** Both form a gate on `W >= 150` and at least 10 weight-carrying
   repositories, and both also print the old 10-block rule. One comparison trap follows from
   cause 3: A's J level is measured under the repository floor and conditioned on it, while the
   review's 0.178 was measured under the block floor, so the two cannot be set side by side
   without fixing the denominator first.

## 4. The two questions of SPEC_E, with numbers (my own run)

**Q1. The shared-drift hole under the real month structure, and what month blocking costs.**

| | E1 `lam` 0.05 | E1 `lam` 0.15 (D8-matched) | E1 `lam` 0.30 | E1s `lam` 0.60 | E2 | E3 | E4 | E5 whole window 0.15 / 0.30 |
|---|---|---|---|---|---|---|---|---|
| P | 0.047 | 0.073 | 0.099 | 0.240 | 0.109 | 0.063 | 0.085 | 0.322 / 0.618 |
| PM | 0.053 | 0.062 | 0.077 | 0.189 | 0.051 | 0.052 | 0.066 | 0.050 / 0.075 |

- Under the real month structure the hole is far smaller than the reviewer's whole-window
  figure at the same drift strength: at the D8-matched strength, 0.073 against 0.322; at a
  nominal share 0.3, 0.099 against 0.618.
- Month blocking **closes the whole-window hole** (0.618 to 0.075, and 0.322 to 0.050) and the
  shared-month-level hole (0.109 to 0.051), and takes the spread of `rho_bar` at E5 from 0.186
  back to 0.070, the E0 figure (0.053).
- Month blocking **does not close the part of a drift that moves inside one calendar month**:
  PM 0.062 at the matched strength, 0.077 at share 0.3, 0.189 at share 0.6, 0.066 at E4.
- **Power cost:** A18 0.653 to 0.617 (-0.036), A25 0.918 to 0.896 (-0.022), A18ar 0.485 to
  0.461 (-0.024), A25ar 0.728 to 0.694 (-0.034). Weight 381 to 361 (-5%), blocks 20.1 to 29.4,
  sign units unchanged at 20.1, and `rho_bar` under an alternative moves by 0.001.

**Q2. Whether a per-repository sign repairs the gate's own level, and what it costs.**

| | E0 | E8 AR 0.6 | E7 long runs | E4 | E2 | E1 0.30 | E1s 0.60 |
|---|---|---|---|---|---|---|---|
| J, sign per block | 0.054 | 0.084 | 0.179 | 0.142 | 0.148 | 0.105 | 0.339 |
| JR, sign per repository | 0.057 | 0.050 | 0.056 | 0.067 | 0.096 | 0.080 | 0.179 |
| JMR, month in the blocks too | 0.056 | 0.056 | 0.055 | 0.065 | 0.050 | 0.066 | 0.123 |

- **Yes for the two rows the review flagged.** The per-repository sign takes AR(1) 0.6 from
  0.084 to 0.050 and long constant runs from 0.179 to 0.056 (0.102 to 0.032 counting a gate
  that cannot be formed as no rejection).
- **It does not make the gate safe by itself.** JR is 0.096 at shared month levels, 0.080 at
  E1, 0.179 at E1s, 0.423 under the whole-window drift. JMR is the only gate at or below 0.066
  on every null row here.
- **Cost:** the gate alone falls from 0.655 (J) to 0.498 (JR) to 0.436 (JMR) at correlation
  0.18, and from 0.902 to 0.772 to 0.728 at 0.25. The pair falls from P&J 0.531 to P&JR 0.454
  to PM&JR 0.437 to PM&JMR 0.386 at correlation 0.18. Sign units fall from 42.5 to 13.3, so the
  10-repository floor refuses the gate in 0.427 of E7 runs (0.003 under the old 10-block rule)
  and 0.174 of E1s runs; JMR cannot be formed in 0.535 of E7 runs and 0.968 of whole-window
  runs.

## 5. The decision rule, applied

The rule fixed in advance: PM must hold its level (at most 0.065) under E1, E1s, E2, E3 and E4
and come within 0.05 of P's power on the alternatives.

| condition | measured | holds? |
|---|---|---|
| PM at E1 (share 0.3) | 0.077 (0.083 on the first 1,000 sets) | no |
| PM at E1s (share 0.6) | 0.189 | no |
| PM at E2 | 0.051 | yes |
| PM at E3 | 0.052 | yes |
| PM at E4 | 0.066 (0.065 on the first 1,000 sets) | no, at the bar |
| power within 0.05 of P | largest gap 0.036 (A18) | yes |

**Primary verdict: PRIMARY-REPOSITORY, with the month-blocked estimate as a labelled
secondary.** The level condition fails at E1, E1s and E4.

Two facts the drafter should see next to that outcome, both measured:

- On the same five rows P reads 0.099, 0.240, 0.109, 0.063, 0.085 — higher than PM on four of
  the five. The rule as written selects the blocks whose measured rates on the triggering rows
  are the larger ones.
- The outcome does not change at the D8-matched drift strength (PM 0.062 at `lam` 0.15 holds,
  but the doubled share reads 0.077) and it does not change under A's numbers. It **does**
  change under B's numbers, where PM holds everywhere (largest 0.061) and the rule would give
  PRIMARY-REPOSITORY-X-MONTH. The whole primary verdict turns on the drift scaling of cause 1,
  and B's nominal 0.3 is about a fifth of the strength the words of SPEC_E describe.

**Gate verdict: GATE-FLIP-PER-REPOSITORY.** Unanimous across all three implementations
(E8 0.084 to 0.050 and E7 0.179 to 0.056 in my run; 0.086 to 0.046 and 0.182 to 0.046 in A's;
0.104 to 0.055 and 0.095 to 0.028 in B's).

**Which gate blocks go with the chosen primary:** `J`'s blocks — repository x model name x
length tercile — flipped once per repository, i.e. **JR**, since the chosen primary blocks are
repositories. `JMR` belongs with the month-blocked secondary, where it is the better-behaved
gate (0.050 to 0.066 on every null row) at a cost of about 0.05 of pair power and a 0.535
cannot-form share under long constant runs. Published pair rates: P&JR 0.025 at E0, 0.044 at
E1, 0.057 at E2, 0.015 at E7, 0.017 at E8, 0.407 under the whole-window drift; PM&JMR 0.022,
0.033, 0.018, 0.012, 0.022, 0.000 on the same rows.

## 6. What stays unprotected, in plain words

1. **A drift over the calendar that moves both numbers inside the months a repository already
   occupies.** Repository blocks reject 0.073 at the D8-matched strength, 0.099 at share 0.3
   and 0.240 at share 0.6; month blocks 0.062, 0.077 and 0.189. The pair publishes in 0.025,
   0.044 and 0.118 of those runs (P&JR), or 0.022, 0.033 and 0.070 (PM&JMR).
2. **One level per calendar month shared by both numbers.** Repository blocks 0.109, pair P&JR
   0.057. Month blocks take this to 0.051 and the pair to 0.018.
3. **Repositories whose sessions spread across the whole window.** Repository blocks 0.322 at
   the D8-matched strength and 0.618 at share 0.3, pair P&JR 0.149 and 0.407. Month blocks hold
   (0.050, 0.075), but the month-blocked gate cannot be formed in 0.909 to 0.968 of such runs,
   so there the result is "cannot tell" rather than a protected answer.
4. **One dated event that moves both numbers at once** (not a null by the letter): repository
   blocks 0.199, month blocks 0.127, pair P&JR 0.092, PM&JMR 0.052, and the published
   `rho_bar` carries +0.094 (repository) or +0.054 (month).
5. **Anything carried by session length.** With 0.3 of each latent on `log d` the primary
   rejects 0.998 and the gate still passes in 0.247 of runs (0.123 at a length share of 0.21);
   with length and a per-model effect together (G4) the primary rejects 0.998 and the pair
   publishes 0.213. The signal's denominator is the length, so this is the leak with the
   highest measured pair rate of any scenario here.
6. **The gate's own p-value under long constant runs**, if it is ever read alone: J 0.179 given
   that it ran. Under the repository sign it is 0.056, but the gate then cannot be formed in
   0.427 of those runs.
7. **Anything inside one `repository x month` block** — more than one person, a pattern over
   the index, a change that is not dated — because no label used here separates it. The
   residue is visible as PM 0.189 at share 0.6.
8. **A model name that moves with the calendar**, under a drift: repository blocks 0.087,
   month blocks 0.062, JR 0.080, JMR 0.077, pair 0.038 and 0.032 (600 data sets).
9. **E3 as both implementations coded it** is not a mean-zero null (item 3.1), so the
   protection measured on that row is measured against a generator that already carries a
   positive offset of about +0.016 in `rho_bar`.
