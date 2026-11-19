# Adversarial review of the two SPEC_D calibrations

Reviewer: a third implementation, written from `SPEC_D.md` and `FACTS.md` only, with its own
generator and its own tests. Script: `calib/review_check.py`. Results:
`review_checks.txt`, `review_nulls.txt`, `review_nulls2.txt`, `review_disputed.txt`,
`review_gate.txt`, `review_gate2.txt`, `review_breaks.txt`, `review_breaks2.txt`,
`review_alpha2.txt`, `review_alpha2a.txt`.

Synthetic data only. Standard library only, `/usr/bin/python3 -I`, fixed seeds, 6 processes.
No real data was opened. No paired signal and outcome values exist anywhere.
Nothing below claims a cause, a prediction, a measure of quality, or an order in time.
"Index" and "time order" mean only the order that labels the sessions of one repository.

Counts I used: B = 999 draws per test; 1,000 data sets per null scenario (Monte Carlo error
0.0069 near a rate of 0.05); 1,000 per alternative and per X scenario; 400 per gate scenario
in the first pass and 600 to 1,200 in the second; 2,000 to 16,000 data sets per scenario for
the scenario's own mean `rho_bar`; 200,000 draws for the enumeration check. Nothing was
reduced below SPEC_D. Total run time about 13 minutes with 6 processes.

My own code checks (`review_checks.txt`): the Monte Carlo p-value of S agrees with full
enumeration (288 arrangements, exact 0.7222, Monte Carlo 0.7236, error 0.0010); no p-value
can fall below `1/(B+1)`; the observed arrangement is inside the circular-shift set and inside
the block-shuffle set; `Var(rho_r)` under S equals `1/(n_r - 1)` by enumeration with ties;
every null scenario has a mean `rho_bar` of zero to within about two standard errors over
2,000 data sets, and N0 to `-0.0000 +/- 0.0004` over 16,000 data sets.

---

## 1. Where the two reports agree

1. **S is broken and the hole is large.** Three implementations, 3,000 data sets per cell:
   S rejects 0.052 (N0), 0.067 (N1), 0.119 (N2), 0.354 (N3), 0.098 (N4), 0.140 (N5),
   0.524 (N6). Mine alone: 0.049, 0.066, 0.130, 0.335, 0.092, 0.148, 0.519/0.528.
   The consultant's point is confirmed. S must not be registered.
2. **F holds its level under every one of N0 to N6.** Pooled over the three implementations:
   0.051, 0.045, 0.049, 0.050, 0.047, 0.048, 0.053. Mine alone: 0.045, 0.050, 0.052, 0.048,
   0.045, 0.053, 0.050 (A's walk scaling) and 0.055 (B's). No cell is above 0.058 anywhere.
3. **C fails under two independent random walks.** Pooled 0.112 (A 0.114, B 0.115, mine 0.102
   and 0.118). It is also at or just above the bar under AR(1) 0.9 (see 2.3 below).
4. **K fails.** Pooled 0.113 at AR(1) 0.9, 0.068 under regimes, 0.199 under random walks.
5. **The mean of `rho_bar` stays at zero in every null; what grows is its spread.**
   My sd of `rho_bar`: 0.051 (N0), 0.069 (N2), 0.113 (N3), 0.171 (N6). A and B report the same
   to within 0.005. The shuffle reference does not grow with it; that is the whole hole.
6. **Realised sizes.** mean m 20.1 and mean W 380 at N0, falling to m 14.0 and W 290 at N6.
   A: 20.3 / 381 and 13.9 / 288. B: 20.2 / 381 and 14.8 / 306. All three generators sit a
   little below FACTS' promise (m in [19,24], W in [385,390]) for the same reason A gives: a
   small or strongly autocorrelated repository sometimes comes out constant and drops.
7. **The extra candidates buy nothing.** A's K2 and B's CR both track an existing candidate
   (K2 near C, CR within Monte Carlo error of C). I did not add a further candidate; nothing
   in my break scenarios suggests one would help.
8. **The joint gate reduces but does not remove a length-carried pattern.** G1: the primary
   rejects 0.978 to 0.998, the pair is 0.11 to 0.16 (mine 0.125 for F; A 0.155; B 0.150).
   Not 0.05.
9. **Power.** At a realised `rho_bar` near +0.14 with independent sessions, F is 0.668 (mine),
   0.632 (A), 0.662 (B); C is about 0.80. The price of validity is about 0.13 of power.
   Below a realised `rho_bar` of about 0.14 nothing here finds a link more than half the time.
10. **The interval's coverage falls with serial dependence** and "cannot tell" is the normal
    sentence: the interval lies entirely inside (-0.15, +0.15) in 0.44 to 0.49 of null runs
    with independent sessions, 0.20 at AR(1) 0.6, 0.02 at AR(1) 0.9, 0.00 under random walks.

## 2. Where they differ by more than Monte Carlo error, and what settles it

The standard error of a difference of two independent rates is 0.0097 near 0.05 with 1,000
data sets each, and 0.0154 near 0.05 (0.021 near 0.10) with 400 each. I treat a gap above
two of those as a real difference.

### 2.1 N6, test S: A 0.548, B 0.501 (2.1 standard errors)

Cause, in the code: the two random-walk scalings. A divides each repository's walk by
`sqrt(n_r)` (`calib_A.py:173`), B by `sqrt((n_r+1)/2)` (`calib_B.py:160`). A's walk therefore
has about half the within-repository variance of B's, so more repositories come out constant
and drop out. My rerun reproduces that exactly: with A's scaling, mean m 14.0 and mean W 290
(A reports 13.9 / 288); with B's, m 14.9 and W 309 (B reports 14.8 / 306).

Settled: the scaling is **not** the cause of the rate difference. In my code the same two
scalings give S = 0.519 and 0.528 — a gap of 0.009 where A and B differ by 0.047. S's level
under two independent random walks is about 0.52; both reported figures are consistent with
that, and the rest is Monte Carlo. Neither is wrong, and the exact figure changes nothing,
because S is not registered. The scaling does matter for K (my 0.186 against 0.214).

### 2.2 N5, tests C and K: A 0.043 / 0.055, B 0.061 / 0.070 (1.8 and 1.4 standard errors)

The regime generators are equivalent (A `calib_A.py:155`, B `calib_B.py:164`; both draw a
fresh level with probability 1/5 per step, both with noise share 0.3). I found no code cause.

Settled by my rerun: C 0.051, K 0.078. Pooled over the three: C 0.052 (holds), K 0.068
(fails the 0.065 bar). A's K = 0.055 is the outlier; the majority of the evidence says K does
not hold under regimes. This matters only for K, which nobody recommends.

### 2.3 N3, test C: A 0.073, B 0.060 — the two land on opposite sides of the 0.065 bar

Settled by my rerun: C = 0.059. Pooled over 3,000 data sets: **0.064 +/- 0.0045**. So C's
level under AR(1) 0.9 is about 0.064: above 0.05, and indistinguishable from the bar itself.
A's verdict ("C fails N3") and B's ("C holds N0 to N5") are both defensible readings of the
same number. The honest statement for the page is that C's level under strong serial
dependence measured 0.06 to 0.07, not 0.05. It does not change the decision: C is a
secondary either way, and it fails N6 decisively in all three implementations.

### 2.4 N4, test S: A 0.110, B 0.091 (1.4 standard errors)

My rerun: 0.092. Pooled 0.098. Not a code difference; A's cell is high by about 1.5 standard
errors. S fails N4 on everyone's numbers.

### 2.5 X1, test F: A 0.865, B 0.905 (1.8 standard errors)

Both put a shared linear term over the index into the 8 largest repositories with variance
share 0.3 and both land on a realised `rho_bar` of +0.22. My rerun: F = 0.878 at realised
`rho_bar` +0.2249. The gap is Monte Carlo at 400 data sets (B used 400, A 400; I used 1,000).
No code cause. The finding is identical either way.

### 2.6 G2, primary test: A's F 0.120, B's F 0.105

Below two standard errors, so not a real difference, but there is a code cause worth naming:
A correlates the per-model effect on the two latents at 0.9 (`calib_A.py:44`), B at 0.8
(`calib_B.py:344`), and A draws one global per-model effect while B draws a fresh one inside
each repository. I used 0.85 and got F = 0.097. All three agree on the shape: a
model-carried pattern already shows up weakly in the primary and is almost completely removed
by the gate.

### 2.7 The gate's own level under AR(1) 0.6: A 0.090-0.122, B 0.035-0.083 (up to 2.7 SE)

This is the one difference that changes what the page must say. A reports that under G0b the
gate alone is anticonservative for every candidate (J alone 0.100 for F, 0.122 for S); B
reports 0.055 for F and 0.075 for C and concludes only S is affected.

I checked the two gate implementations line by line and they agree with each other and with
SPEC_D: terciles cut inside each repository x model group after sorting by length with the
index as the tie-break, cuts at `floor(n/3)` and `floor(2n/3)`, blocks of one session dropped,
sessions kept in index order inside a block, the same "formable" floor, the same same-sign
rule (A compares the two signs, B uses `rbj * rb > 0`; equivalent). The model-name rules do
differ (A: one name with probability 0.5, else 2 or 3 for `n >= 11`, else 1 or 2; B: 1 or 2 or
3 with equal probability for `n < 10`), so I ran both rules.

Settled by my rerun, 1,200 data sets, G0b: **J alone 0.091 for F and 0.099 for C**
(standard error 0.008); with A's model rule 0.090, with B's 0.098, so the model rule is not
the cause. B's 0.055 is 3.3 standard errors below my estimate and I could find no code reason
for it; B's primary rates under the same scenario agree with everyone's, so the most likely
explanation is Monte Carlo at 400 data sets. **A is right: the gate's own p-value is not
alpha-protected under serial dependence, for every candidate including F.** The conjunction is
protected: P&J = 0.028 (F) and 0.044 (C) in the same 1,200 runs.

### 2.8 Two separate gates against the joint gate

B could not tell them apart at 400 data sets and recommends keeping both; A added a scenario
(G4: no direct link, both numbers loading on `log d` and on a per-model effect) where they
part company, and recommends the joint gate only. I ran A's scenario in my own code,
400 data sets: with F, the joint gate holds "an association is shown" to **0.138**, while
"length-only and model-only, both required" publishes one in **0.532** of runs with no direct
link. A's figures were 0.120 and 0.515. A's extra scenario is sound and decides the question:
**register the joint gate, not two separate gates.** B's recommendation 7 would publish a
false association in about half of the runs of a case that is easy to imagine here (longer
sessions and a particular model name both going with both numbers).

### 2.9 Cells where my own implementation differs from both

- **N2, test K:** A 0.050, B 0.054, mine 0.074 (2.4 standard errors above both). The cause is
  in the generator, not the test: my signal share curve has a steeper top end than A's, which
  changes how much tie mass the largest repositories carry. It does not matter — K is not
  registered, and all three implementations put K above the bar somewhere in the
  AR/regime/random-walk family.
- **"Entirely inside (-0.15, +0.15)" at N0:** A 0.436, B 0.450, mine 0.486. This figure
  tracks the sd of `rho_bar` (A 0.0526, B 0.0525, mine 0.0506) and is sensitive to generator
  detail at the 0.05 level. Use "about 0.44 to 0.49", not a single figure.
- **Interval coverage at N5 (A 0.959, B 0.940) and at X1 (A 0.970, B 0.988)**, both about
  2 standard errors. I did not arbitrate these two cells: they do not change the decision,
  and both reports agree on the shape (coverage near 0.95 without serial dependence, 0.93 at
  AR(1) 0.9, 0.90 under two random walks). My own interval covers zero — which is the true
  mean under every null — in 0.973 (N0), 0.961 (N1), 0.944 (N2), 0.922 (N3), 0.965 (N4),
  0.950 (N5) and 0.895/0.898 (N6) of runs. That sits with both reports and confirms the shape.

## 3. Errors I looked for and what I found

I checked every item on the list, in both scripts.

| error looked for | A | B | verdict |
|---|---|---|---|
| a null scenario that is not a null | mean `rho_bar` 0 in all 7 | same | none. My own means are 0 to within standard error in all 7 nulls and in all 10 of my new nulls |
| a p-value that omits the `+1` | `(1+hit)/(B+1)` everywhere | same | none |
| the observed arrangement missing from the reference set | offset 0 included in C, identity permutation reachable in S and K, all-plus sign vector reachable in F | same | none |
| a circular shift that is not in time order | blocks keep sessions in index order (`blockset_by_key`) | blocks re-sorted to index order before use | none |
| gate blocks differing from the spec | terciles inside repository x model, cuts at `floor(n/3)`, `floor(2n/3)`, 1-session blocks dropped | same | none |
| a jackknife over the wrong units | over contributing repositories, `t(m-1)` | same | none |
| the `1/sqrt(W)` floor | applied | applied | none |
| determinism | byte-identical repeat, and identical at 1, 3, 5 processes | `cmp` of two runs identical (I verified: `results_B.txt` and `results_B_rerun.txt` are identical) | none |

Three further points that are not errors but belong in the registration:

- **Both reference sets include the observed arrangement, and the p-value adds `+1` on top.**
  That is SPEC_D's rule and both followed it; it makes every test very slightly conservative.
  With exact enumeration (see 5.5) the `+1` must be dropped, or the p-value is wrong by
  `1/2^m`.
- **Neither report measured a drift shared across repositories**, and both say so in their
  limits. It is the one case where the recommended test fails badly (section 4).
- **Neither report measured the gate under a serial structure stronger than AR(1) 0.6.**
  I did; the gate's own level reaches 0.18 (section 4, G0c).

## 4. Trying to break the test both recommend

Ten further scenarios, 1,000 data sets each (Monte Carlo error 0.0069 near 0.05). In every
one, inside every repository, the signal series and the outcome series are generated
independently of each other, and repositories are generated independently of each other —
except D8, which is flagged.

| scenario | S | C | F | K | m | W | realistic at these sizes? |
|---|---|---|---|---|---|---|---|
| D1 seasonal, period about half the repository length, random phases | 0.541 | 0.055 | **0.055** | 0.308 | 21.4 | 384 | unlikely |
| D2 seasonal, period 2 (alternating), random phases | 0.590 | 0.203 | **0.032** | 0.301 | 21.3 | 379 | unlikely, but see below |
| D3 spread grows over the index (0.2 to 3.0), both series | 0.078 | 0.076 | **0.047** | 0.082 | 21.0 | 384 | **yes** |
| D4 long constant runs, mean 15 sessions, noise share 0.05 | 0.357 | 0.078 | **0.054** | 0.140 | 13.3 | 319 | **yes** |
| D5 141 repositories of 3 sessions, AR(1) 0.6 | 0.049 | 0.051 | **0.046** | 0.047 | 82.9 | 166 | no (the half has 24 repositories of 2 or more) |
| D6 one repository holds 300 of 423 sessions, AR(1) 0.6 | 0.141 | 0.058 | **0.041** | 0.065 | 9.5 | 399 | no (the largest holds [WITHHELD: one repository's session count; disclosure rule 2 of the registration]) |
| D7 AR(1) -0.9 both | 0.370 | 0.062 | **0.056** | 0.101 | 20.9 | 379 | no |
| D10 serial structure differs by repository (AR 0.9 / random walk / none) | 0.340 | 0.067 | **0.056** | 0.131 | 16.7 | 342 | **yes** |
| D11 long constant runs and one dominant repository | 0.520 | 0.062 | **0.035** | 0.123 | 6.6 | 367 | no |
| D9 drift shared across repositories in the **signal only** | 0.043 | 0.045 | **0.055** | 0.047 | 20.1 | 381 | **yes** |
| D8 drift shared across repositories in **both** numbers | 0.337 | 0.296 | **0.306** | 0.314 | 19.7 | 377 | **yes, and it is the real worry** |

**I could not break F with any genuine null.** Its highest rate over the ten independent-series
scenarios is 0.056, and over the seven of SPEC_D 0.058. That is a strong result and it has a
reason: F conditions on the observed `|w_r * rho_r|`, so its reference distribution carries
the realised spread of the data whatever the serial structure is. It needs only that each
repository's number is symmetric about zero and that repositories are independent of each
other. Where weight concentrates on a few repositories F turns **conservative**, not
anticonservative (D6 0.041, D11 0.035, and D11 has mean m 6.6) — that costs power, which is
the honest price and which the floor in 5.9 turns into "cannot tell".

What the scenarios do break:

- **C breaks under a short seasonal period (D2, 0.203).** A circular shift of an alternating
  series by an odd offset flips the phase and by an even offset keeps it, so the reference set
  has two values instead of `n_r` and is far too narrow. The same mechanism bites whenever a
  period divides the repository length. A model name that changes every other session, or a
  two-week rhythm in a repository with about that many sessions, is the way this could arrive.
  Unlikely, but it is a second reason not to let C carry a headline.
- **C also fails under a growing spread (D3, 0.076), under long constant runs (D4, 0.078) and
  under mixed serial structures (D10, 0.067)** — all three of which I would call realistic
  here. Together with N6 (0.112) and N3 (0.064) this makes C unusable as a primary.
- **K fails in seven of the ten** (0.082 to 0.308). Do not register it.
- **S fails in eight of the ten**, up to 0.590.

**The one case that defeats F (D8).** All repositories are observed over the same months. I
gave every session a date inside one 180-day window, ordered each repository's sessions by
date, and let the signal series of every repository follow one shared random drift over the
calendar and the outcome series follow a second, independent shared drift. Across data sets
the mean `rho_bar` is zero (+0.0026 +/- 0.0027 over 2,000 data sets), but inside one data set
the two drifts happen to move together or apart, every repository then agrees in sign, and the
sd of `rho_bar` is 0.12. F rejects **0.306** of the time, and so does everything else
(S 0.337, C 0.296, K 0.314). The joint gate does not help: with F, the primary rejects 0.317,
the gate 0.233, and the pair publishes "an association is shown" in **0.188** of runs
(600 data sets, `review_gate2.txt`, G0d). The interval does not save the page either: it
covers zero in only 0.734 of these runs, against 0.973 at N0.

Is D8 a null? Not by the letter of the estimand. Conditional on the two drifts, the two
numbers of a session really do go together inside a repository, so a positive `rho_bar` is
real in that data set and the test is working as built. It is a null for the question a reader
will think the page answers. The contrast with D9 is the useful part: when only the signal
carries the shared drift, F holds (0.055). The damage needs both numbers to move over the
same window.

**A second real warning: the gate's own level under long constant runs.** With the D4
structure (`review_gate2.txt`, G0c, 600 data sets), the gate alone rejects **0.178** with F
and 0.202 with C, and `W_J` fell below 150 in 0.002 of runs. The pair is still protected
(P&J 0.023 with F). This is the same lesson as 2.7, three times larger: the gate's p-value is
not evidence on its own, at all, ever.

## 5. What should be registered

**Verdict: REGISTER-INFERENTIAL, with F (the sign flip over repositories) as the primary test
and the joint gate J as the gate.** F held its level in all 17 null scenarios across three
implementations (0.032 to 0.058), at a cost of about 0.13 of power against C at the decision
size. That is a real test, not a descriptive-only fallback. The rules below are what a
registration needs; every one of them must be written down before any joint look.

1. **Cohort.** The Codex confirmation half as already fixed by hash: 423 sessions in 33
   repositories, 24 of them with 2 or more sessions. No reader change, no second dataset, no
   other outcome, no other minimum count, no other split.
2. **One primary signal.** Name it in the registration (`no_reasoning_share` or
   `reasoning_tokens`, one of the two). The other may be reported only as a labelled secondary
   with its own p-value and the words "not the registered primary". If both are to carry a
   claim, register alpha 0.025 for each; I measured the cost: at a realised `rho_bar` of +0.14
   F's power falls from 0.668 to 0.529. Naming one is better.
3. **Outcome.** `agent_percentage`, attribution metric version 2, 0 to 100. Not quality.
4. **Statistic, unchanged from the panel.** `rho_r` = Spearman with midranks inside repository
   `r`; `w_r = n_r - 1`; `T = sum_r w_r * rho_r`; `W = sum_r w_r`; published `rho_bar = T / W`.
   A repository enters when `n_r >= 2` and, inside that repository, both numbers take at least
   two distinct values. Repositories of 2 sessions enter with weight 1 and `rho_r = +/-1`;
   they are kept (about 1% of W). Report how many repositories and sessions dropped out and
   why, because dropping changes the weighting of what is published.
5. **Primary reference distribution: the sign flip over repositories.** Draw independent
   uniform signs `s_r` in {-1, +1}, one per contributing repository, and form
   `T* = sum_r s_r * w_r * rho_r`. Register the **exact** distribution, not a Monte Carlo one:
   with `m` between 19 and 24 contributing repositories (FACTS), all `2^m` sign vectors can be
   counted exactly — directly for `m <= 22`, or by splitting the repositories into two halves,
   enumerating each half's partial sums, sorting one list and counting by binary search.
   Then `p = #{|T*| >= |T| - tol} / 2^m`, with **no `+1`** (the all-plus vector is already in
   the enumeration). If `m > 44`, fall back to B = 199,999 draws with the seed string
   registered in advance and `p = (1 + #{|T*| >= |T| - tol}) / (B + 1)`.
6. **Tolerance.** `tol = 1e-9` on `T`, which is at most W (about 390), so the tolerance is
   about `1e-12` in relative terms and far above double-precision error. Mathematically equal
   arrangements must count as equal; the all-minus vector always does, so `p >= 2 / 2^m`.
7. **F needs no time order and no offsets.** This is a reason to prefer it: with F as the
   primary and F inside the gate's blocks, the registration needs no definition of session
   order at all except the tercile tie-break in rule 10. If C is registered as a secondary,
   then also register: order = `created_at` ascending, ties broken by session id ascending;
   offset drawn uniform on `0..n_r-1` per repository, independent across repositories, with
   the seed and draw count fixed in advance.
8. **Alpha 0.05, two-sided. `rho* = 0.15`.** One analysis, one p-value, one interval, one
   gate, one result page. No subgroup search afterwards.
9. **Floors for the primary.** Run it only when at least 10 repositories carry weight and
   `W >= 150`; otherwise print "cannot tell" and no p-value. (FACTS implies m 19 to 24 and
   W 385 to 390, so this floor will be met; register it anyway, and note it is the floor that
   protects against the weight-concentration cases where F turns conservative.)
10. **The gate: joint, not two separate gates.** Blocks are
    `repository x model name x length tercile`. Terciles are cut inside each
    `repository x model name` group: sort that group by length `d` ascending, ties broken by
    `created_at` then session id, and cut at `floor(n/3)` and `floor(2n/3)`. `d` is the number
    of main-thread responses with a known reasoning count — the same denominator the signal
    uses. A block with fewer than 2 sessions, or with either number constant, carries weight 0
    and is dropped. **Sessions with no model name form one further block label `unknown`
    inside their repository** (FACTS says this has not been counted, so the rule must be fixed
    in advance rather than decided after the look).
11. **Gate reference distribution: the same sign flip, over blocks**, computed exactly by the
    same rule as 5 (about 40 blocks: use the two-halves count). The gate "can be formed" when
    `W_J >= 150` and at least 10 blocks carry weight. If it cannot be formed, the result is
    "cannot tell".
12. **The published sentence.** "An association is shown" only when the primary p <= 0.05
    **and** the gate p <= 0.05 **and** `rho_bar_J` has the same sign as `rho_bar`, with
    `rho_bar` exactly 0 counting as no match. Measured level of the pair: 0.025 to 0.033 under
    the independent-session null, 0.028 under AR(1) 0.6 (my 1,200 runs) and 0.023 under long
    constant runs. Measured power of the pair with a direct link of 0.18 on top of length
    loadings: 0.823 (A) and 0.807 (B); I did not rerun that cell, and the two agree.
13. **The interval, unchanged.** `rho_bar +/- t(m-1, 0.975) * max(SE_jack, 1/sqrt(W))`,
    cluster jackknife over contributing repositories, clipped to [-1, +1]. Print its measured
    coverage (section 6).
14. **Determinism.** Fix every seed string in the registration; the analysis must be run twice
    and the two outputs compared byte for byte before anything is published.
15. **Do not register** S, K, A's K2, B's CR, two separate gates, or the gate's p-value as
    evidence on its own.

## 6. The honest limits that must be printed

1. **A pattern over the index inside one repository cannot be told apart from a session-level
   link.** With a shared term over the index in the 8 largest repositories, `rho_bar` lands at
   +0.22 and F rejects 0.88 of the time (A 0.865, B 0.905, mine 0.878) with no session-level
   link in the data.
2. **A drift shared across repositories is the largest hole, and it is not protected at all.**
   When both numbers follow a drift over the same calendar window, F rejects 0.306 of the time
   and the registered pair publishes "an association is shown" in 0.188 of runs, with a mean
   `rho_bar` of zero across data sets and an sd of 0.12. All 423 sessions sit in one Apr-Sep
   2026 window, so this is not hypothetical. If only one of the two numbers drifts, F holds
   (0.055). A block on the month is the only handle and it is not calibrated here.
3. **More than one person inside one repository.** With 3 hidden people in contiguous runs in
   11 repositories, F rejects about 0.25 at `rho_bar` +0.10. Where nobody is identified no
   block can separate them, and 4 repositories with no identified user hold 37% of the weight.
4. **A pattern carried by session length survives the gate.** The gate cuts it from about 0.99
   to about 0.13 (mine), not to 0.05. Terciles do not hold length fixed, and the signal's
   denominator **is** the length: both numbers are built from the same responses. No
   permutation scheme repairs that.
5. **A pattern carried by the model name** is cut to about 0.01, not to zero.
6. **The gate's own p-value is not alpha-protected.** Alone it rejects 0.091 under AR(1) 0.6
   (1,200 runs) and 0.178 under long constant runs (600 runs). It is a gate and never evidence
   on its own. Print the pair or print nothing.
7. **The interval is weaker than it looks under serial structure.** Coverage of the generating
   process's mean measured 0.95 to 0.97 without serial dependence, 0.93 at AR(1) 0.9 and 0.90
   under two random walks (A and B agree; my own interval covers zero in 0.973 of N0 runs,
   0.922 at AR(1) 0.9 and 0.895 under random walks). Under the shared drift of limit 2 it
   covers zero in only **0.734** of runs, so the interval excludes zero in about a quarter of
   those runs. And the 423 sessions are the whole confirmation half, so the interval is a
   statement about a hypothetical repetition of whatever produced them, not about the sessions
   themselves, which are measured in full.
8. **Power, stated in advance.** At a realised `rho_bar` near +0.14, F finds a link about 0.67
   of the time with independent sessions and 0.46 to 0.50 with AR(1) 0.6. Below about +0.14
   nothing here is adequate. At alpha 0.025 (two signals) the figure falls to 0.53.
9. **"Cannot tell" is the expected sentence.** The interval lies entirely inside
   (-0.15, +0.15) in only 0.44 to 0.49 of null runs with independent sessions, 0.20 at
   AR(1) 0.6, 0.02 at AR(1) 0.9 and 0.00 under two random walks.
10. **Size and tie mass.** About 19 to 24 weight-carrying repositories with four dominant,
    W about 385 to 390, 73% of the outcome at an endpoint, and a signal that is a share with a
    small denominator. Where weight concentrates further, F becomes conservative (0.035 to
    0.041 in my dominant-repository scenarios) and the floor in rule 9 would refuse the
    analysis.
11. **What this is not.** A description of two records attached to the same session. No cause,
    no prediction, no claim about quality, no order in time. The index inside a repository is
    used only to build block and tercile labels.
12. **Serial structures I did not test.** A between-repository dependence in `rho_r` other
    than the shared drift of limit 2; a break at one date; a change in the reader or in the
    attribution metric inside the window. F's validity needs each repository's
    `w_r * rho_r` symmetric about zero and independent across repositories; limit 2 is what
    happens when the second half of that fails.
