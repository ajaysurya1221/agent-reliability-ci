# S1b stake selection, decision floors and schedule limits

Selected equal-weight stake set: **{1/4, 1/2}**. alpha=1/20, delta=1/10, batch=10, max_pairs=400 (800 sessions).

Offline standard-library research spike. S1 is imported unchanged. All probability enumerations use exact rational mass and integer decision frontiers; displayed decimals are rounded. Expected pairs are capped first-stop expectations, including INCONCLUSIVE at the cap. Fractions are retained in results.json.

## 1. Preregistered stake selection

The five candidates, 36 scenarios and tie rule are exactly the task brief's grid. An earlier informal reviewer grid favoured {1/4, 1/2}; that prior information was disclosed before this systematic run. No grid or criterion was changed.

Winner minimum correct-decision probability: 0.537656134; maximum across sets: 0.538704716; shortfall: 0.001048582. The inclusive 0.01 band ties candidates 1 and 3 (zero-based); candidate 1 has lower mean stopping pairs. Probability tie-band membership uses exact fractions; mean costs are displayed as binary64 values from S1's exact integer stopping-mass sum. The cost gap is over ten pairs, far above display rounding.

| stakes | minimum correct probability | mean expected pairs |
|---|---:|---:|
| {1/2} | 0.231260671 | 155.629507 |
| {1/4, 1/2} | 0.537656134 | 158.916535 |
| {1/4, 1/2, 3/4} | 0.491135445 | 157.438143 |
| {1/8, 1/4, 1/2} | 0.538704716 | 168.986210 |
| {1/8, 1/4, 1/2, 3/4} | 0.500283050 | 164.428676 |

Each cell below is **correct-decision probability / expected pairs**. Correct means PASS for no change, BLOCK for either regression. Intermediate coupling is the equal mixture of independent and Frechet upper laws.

| baseline → candidate | dependence | {1/2} | {1/4, 1/2} | {1/4, 1/2, 3/4} | {1/8, 1/4, 1/2} | {1/8, 1/4, 1/2, 3/4} |
|---|---|---:|---:|---:|---:|---:|
| 0.50 → 0.50 | independent | 0.231261 / 335.078 | 0.537656 / 297.677 | 0.491135 / 309.531 | 0.538705 / 304.946 | 0.500283 / 313.204 |
| 0.50 → 0.50 | intermediate | 0.776841 / 212.943 | 0.891623 / 207.739 | 0.862836 / 218.374 | 0.876817 / 220.934 | 0.853379 / 226.940 |
| 0.50 → 0.30 | independent | 0.386688 / 305.918 | 0.595049 / 290.050 | 0.542717 / 301.660 | 0.571349 / 301.268 | 0.530966 / 308.595 |
| 0.50 → 0.30 | intermediate | 0.742547 / 231.340 | 0.809264 / 236.255 | 0.770761 / 244.238 | 0.782551 / 250.739 | 0.751710 / 254.303 |
| 0.50 → 0.20 | independent | 0.995430 / 96.732 | 0.999536 / 101.526 | 0.999235 / 103.925 | 0.999442 / 109.367 | 0.999176 / 109.418 |
| 0.50 → 0.20 | intermediate | 0.999965 / 74.622 | 0.999993 / 82.798 | 0.999985 / 78.038 | 0.999990 / 89.445 | 0.999982 / 82.974 |
| 0.65 → 0.65 | independent | 0.288784 / 322.196 | 0.595078 / 286.714 | 0.547786 / 299.113 | 0.590552 / 295.138 | 0.552335 / 303.546 |
| 0.65 → 0.65 | intermediate | 0.839356 / 195.673 | 0.920234 / 195.208 | 0.896474 / 204.463 | 0.906847 / 208.477 | 0.887217 / 213.422 |
| 0.65 → 0.45 | independent | 0.361063 / 311.057 | 0.577090 / 293.743 | 0.525106 / 305.274 | 0.554534 / 304.622 | 0.514169 / 311.928 |
| 0.65 → 0.45 | intermediate | 0.721800 / 236.123 | 0.796981 / 239.895 | 0.756859 / 248.313 | 0.769801 / 254.287 | 0.737771 / 258.292 |
| 0.65 → 0.35 | independent | 0.984604 / 110.307 | 0.998581 / 110.830 | 0.997808 / 115.352 | 0.998387 / 119.153 | 0.997721 / 121.061 |
| 0.65 → 0.35 | intermediate | 0.999843 / 78.711 | 0.999975 / 86.687 | 0.999951 / 83.743 | 0.999965 / 93.626 | 0.999942 / 88.932 |
| 0.80 → 0.80 | independent | 0.574172 / 260.629 | 0.790628 / 241.380 | 0.750190 / 254.268 | 0.775658 / 253.319 | 0.743369 / 261.105 |
| 0.80 → 0.80 | intermediate | 0.969436 / 144.454 | 0.982025 / 154.469 | 0.974467 / 157.009 | 0.977159 / 166.612 | 0.970431 / 165.788 |
| 0.80 → 0.60 | independent | 0.508980 / 281.424 | 0.672725 / 272.745 | 0.622043 / 283.922 | 0.645514 / 285.438 | 0.605926 / 292.302 |
| 0.80 → 0.60 | intermediate | 0.823876 / 211.319 | 0.859686 / 220.458 | 0.828188 / 226.170 | 0.835948 / 235.194 | 0.811226 / 236.444 |
| 0.80 → 0.50 | independent | 0.995430 / 96.732 | 0.999536 / 101.526 | 0.999235 / 103.925 | 0.999442 / 109.367 | 0.999176 / 109.418 |
| 0.80 → 0.50 | intermediate | 0.999965 / 74.622 | 0.999993 / 82.798 | 0.999985 / 78.038 | 0.999990 / 89.445 | 0.999982 / 82.974 |
| 0.90 → 0.90 | independent | 0.942070 / 158.969 | 0.968206 / 166.705 | 0.956135 / 171.717 | 0.960600 / 179.395 | 0.950257 / 180.771 |
| 0.90 → 0.90 | intermediate | 0.999647 / 103.853 | 0.999704 / 116.049 | 0.999503 / 106.221 | 0.999538 / 125.927 | 0.999348 / 114.069 |
| 0.90 → 0.70 | independent | 0.770098 / 224.815 | 0.825891 / 231.211 | 0.789616 / 238.535 | 0.799924 / 245.800 | 0.770902 / 248.699 |
| 0.90 → 0.70 | intermediate | 0.937012 / 175.814 | 0.940153 / 190.447 | 0.924615 / 189.373 | 0.925938 / 204.868 | 0.913084 / 199.213 |
| 0.90 → 0.60 | independent | 0.999865 / 78.233 | 0.999978 / 86.244 | 0.999957 / 83.102 | 0.999969 / 93.151 | 0.999948 / 88.268 |
| 0.90 → 0.60 | intermediate | 0.999999 / 68.450 | 1.000000 / 76.384 | 0.999999 / 68.272 | 1.000000 / 82.547 | 0.999999 / 72.621 |
| 0.95 → 0.95 | independent | 0.999409 / 106.143 | 0.999516 / 118.405 | 0.999210 / 109.595 | 0.999259 / 128.471 | 0.998974 / 117.481 |
| 0.95 → 0.95 | intermediate | 1.000000 / 87.648 | 1.000000 / 98.899 | 1.000000 / 80.793 | 1.000000 / 107.074 | 0.999999 / 88.073 |
| 0.95 → 0.75 | independent | 0.927815 / 179.403 | 0.932962 / 193.588 | 0.915716 / 193.438 | 0.917666 / 208.098 | 0.903571 / 203.377 |
| 0.95 → 0.75 | intermediate | 0.981138 / 153.227 | 0.978715 / 169.615 | 0.972135 / 160.962 | 0.971546 / 183.185 | 0.966617 / 169.713 |
| 0.95 → 0.65 | independent | 0.999999 / 69.155 | 1.000000 / 77.152 | 0.999999 / 69.457 | 0.999999 / 83.370 | 0.999999 / 73.890 |
| 0.95 → 0.65 | intermediate | 1.000000 / 64.764 | 1.000000 / 72.377 | 1.000000 / 61.998 | 1.000000 / 78.288 | 1.000000 / 65.874 |
| 0.99 → 0.99 | independent | 1.000000 / 78.910 | 1.000000 / 89.637 | 1.000000 / 67.716 | 1.000000 / 96.487 | 1.000000 / 75.126 |
| 0.99 → 0.99 | intermediate | 1.000000 / 75.329 | 1.000000 / 85.858 | 1.000000 / 63.695 | 1.000000 / 92.603 | 1.000000 / 71.807 |
| 0.99 → 0.79 | independent | 0.995068 / 139.454 | 0.993290 / 155.848 | 0.991631 / 140.373 | 0.990414 / 168.738 | 0.989432 / 148.125 |
| 0.99 → 0.79 | intermediate | 0.997574 / 134.710 | 0.996363 / 151.079 | 0.995820 / 132.681 | 0.994572 / 163.705 | 0.994670 / 139.992 |
| 0.99 → 0.69 | independent | 1.000000 / 62.379 | 1.000000 / 69.925 | 1.000000 / 57.972 | 1.000000 / 75.673 | 1.000000 / 61.597 |
| 0.99 → 0.69 | intermediate | 1.000000 / 61.529 | 1.000000 / 69.073 | 1.000000 / 56.517 | 1.000000 / 74.745 | 1.000000 / 60.092 |

Winner disadvantages exceeding 0.02 probability (strict, exact comparison):

| other stakes | baseline → candidate | dependence | other minus winner |
|---|---|---|---:|
| {1/2} | none | — | — |
| {1/4, 1/2, 3/4} | none | — | — |
| {1/8, 1/4, 1/2} | none | — | — |
| {1/8, 1/4, 1/2, 3/4} | none | — | — |

## 2. Decision floors

Floors are earliest registered checkpoints within the 400-pair horizon, including a terminal partial batch. Earliest possible PASS uses all +1; earliest BLOCK all -1. The loss rows use exactly k differences -1 and zeros otherwise; they describe attainable checkpoint wealth, not an ordering-independent first-stop promise. Counts alone cannot certify that a supplied ordered stream did not stop earlier. validate_plan rejects a cap at which the all-zero stream cannot PASS.

| delta | batch | any PASS | all-zero PASS | 1 loss | 2 losses | 3 losses | 5 losses | any BLOCK | max losses / zeros at 200, 400 | max losses / wins at 200, 400 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| 1/20 | 1 | 10 | 165 | 192 | 220 | 247 | 302 | 12 | 1, 8 | 83, 175 |
| 1/20 | 10 | 10 | 170 | 200 | 220 | 250 | 310 | 20 | 1, 8 | 83, 175 |
| 1/10 | 1 | 9 | 79 | 93 | 107 | 120 | 148 | 13 | 8, 23 | 88, 184 |
| 1/10 | 10 | 10 | 80 | 100 | 110 | 120 | 150 | 20 | 8, 23 | 88, 184 |
| 1/5 | 1 | 8 | 37 | 44 | 50 | 57 | 71 | 15 | 24, 57 | 97, 202 |
| 1/5 | 10 | 10 | 40 | 50 | 50 | 60 | 80 | 20 | 24, 57 | 97, 202 |

## 3. Portable schedule and coverage

schedule_key hashes b'arci-suite/1 key' followed by compact sorted-key ASCII-escaped JSON encoded as UTF-8. Cells sort by (task_id, condition_id); cell field order and cosmetic fields do not matter. Arm identities and prior-run list order are bound. Rule fractions are reduced numerator/denominator strings and stakes sort numerically. The caller supplies immutable content identities; this spike is not a product manifest parser or a verifier of those identities. See schedule.py for the exact field contract.

Cell draw: SHA-256(b'arci-suite/1 cell' + key + uint64be(i) + uint32be(attempt)); the first uint64 is accepted below 2**64 - (2**64 % n_cells), then reduced modulo n_cells. Attempts start at zero. Seed: first uint64 of SHA-256(b'arci-suite/1 seed' + key + uint64be(i)), high bit cleared. Both arms use the same pair seed. Repeated cells use distinct indices; 63-bit truncation cannot promise collision freedom over arbitrary inputs. Tests confirm distinct seeds in the exercised sample.

Tests freeze 24 literal (key,index,n_cells) vectors with expected draws and seeds, exercise rejection with a 4-bit helper, and check 200,000 draws for each of 7, 20, 60 and 150 cells. The conservative chi-square diagnostic threshold is df + 2*sqrt(df*log(1e6)) + 2*log(1e6), fixed before results. These finite checks do not prove IID behavior or cross-version execution; only this host was run.

Exact formulas: P(given cell unseen)=(1-1/C)^n; E(unseen cells)=C*(1-1/C)^n. The following decimals are rounded; full exact fractions are in results.json.

| cells | pairs | P(given cell unseen) | E(unseen cells) |
|---:|---:|---:|---:|
| 20 | 70 | 0.0275836904 | 0.55167381 |
| 20 | 200 | 0.0000350527 | 0.00070105 |
| 20 | 400 | 0.0000000012 | 0.00000002 |
| 60 | 70 | 0.3083566282 | 18.50139769 |
| 60 | 200 | 0.0346858428 | 2.08115057 |
| 60 | 400 | 0.0012031077 | 0.07218646 |
| 150 | 70 | 0.6261100212 | 93.91650319 |
| 150 | 200 | 0.2624229851 | 39.36344776 |
| 150 | 400 | 0.0688658231 | 10.32987346 |

## 4. Conditional on a frozen schedule

Declared before computation: concentrated law has 3/20 cells with P(-1)=2/3 and 17/20 deterministic-zero cells; even law has P(-1)=1/10 in all 20 cells. Both have P(+1)=0, suite mean -1/10 and marginal law (-,0,+)=(1/10,9/10,0). One realization is baseline always succeeds, with candidate success 1/3 in the three affected cells and 1 elsewhere; the even candidate succeeds with 9/10. Both PASS and BLOCK are directional errors at this boundary.

Exactly 2,000 keys: schedule_key on task-00 through task-19, condition clean, baseline identity boundary-baseline-v1 and candidate identity boundary-candidate-0000 through boundary-candidate-1999, empty prior runs, selected rule. The same keys are used for both laws. These are synthetic identities, not actual campaign history or an assertion that changed laws share a valid production manifest. There was no key selection by observed outcomes. An exact position-dependent absorbing DP evaluates each concentrated schedule. The even-law result is schedule-invariant and computed once, recorded for every key. Median averages the middle two; p90/p99 use nearest rank.

| law | direction | mean | min | median | p90 | p99 | max |
|---|---|---:|---:|---:|---:|---:|---:|
| concentrated | false PASS | 0.012215387 | 0.000000003 | 0.000507889 | 0.024143762 | 0.230517942 | 0.528509877 |
| concentrated | false BLOCK | 0.004781349 | 0.000000000 | 0.000000186 | 0.004534775 | 0.129205849 | 0.383807779 |
| even | false PASS | 0.011278584 | 0.011278584 | 0.011278584 | 0.011278584 | 0.011278584 | 0.011278584 |
| even | false BLOCK | 0.005407036 | 0.005407036 | 0.005407036 | 0.005407036 | 0.005407036 | 0.005407036 |

Selected-stake S1 Table-A-method IID reference: false PASS=0.011278584, false BLOCK=0.005407036. Original S1 Table A at p_zero=0.90, cap=400, batch=10: PASS=0.009739118, BLOCK=0.006662747; its rational values reproduce exactly. The original stakes differ, so equality between the new means and the old numeric table is not expected and is not claimed. The even schedule agrees exactly with S1's enumeration under the selected rule. Concentrated means satisfy the predeclared finite-key agreement diagnostic (five empirical standard errors plus 1e-12); the individual probabilities are exact, but their 2,000-key mean is a finite schedule sample, not an exact average over all possible keys.

| mean comparison | absolute difference | schedule-sample standard error | check |
|---|---:|---:|---|
| concentrated_PASS | 0.000936803 | 0.000957574 | True |
| concentrated_BLOCK | 0.000625687 | 0.000578604 | True |
| even_PASS | 0.000000000 | 0.000000000 | True |
| even_BLOCK | 0.000000000 | 0.000000000 | True |

**A single manifest does not receive a conditional 2.5% error guarantee.** The theorem averages over an honest schedule draw as well as trial outcomes; hashing a chosen manifest does not itself establish that randomization assumption. Some conditional errors are much larger than 2.5%, even before any cherry-picking. A user may interpret PASS as suite-mean noninferiority under the stated sampling contract, not per-cell reliability, absolute reliability or a posterior probability. Key grinding and selecting manifests by allocations are disclosed risks, not detected violations. A future report must show draws per cell and cells never drawn.

## 5. Published v1 comparison

v1 values are rounded published inputs from docs/STATISTICS.md, K=1, independent arms: fixed N=200 or sequential looks 50/100/200. The ceiling is 400 sessions. N=400 v1 values for this complete scenario set are not published, nor are intermediate-coupling values; neither is invented. v2 cap 200 has the same ceiling; v2 cap 400 has twice that ceiling. Intermediate rows are v2-only, not claims against independent-arm v1. At 0.95→0.85 both decisions are errors, so correct probability is N/A and directional errors are shown. No significance claim is made about comparisons with rounded published values.

| rates | v1 method | correct probability | false/total PASS | false/total BLOCK | expected sessions | ceiling sessions |
|---|---|---:|---:|---:|---:|---:|
| 0.95 → 0.95 | Clopper-Pearson fixed | 0.889 | 0.889 | 0.0 | 400.0 | 400 |
| 0.95 → 0.75 | Clopper-Pearson fixed | 0.365 | 0.0 | 0.365 | 400.0 | 400 |
| 0.95 → 0.65 | Clopper-Pearson fixed | 0.985 | 0.0 | 0.985 | 400.0 | 400 |
| 0.80 → 0.80 | Clopper-Pearson fixed | 0.218 | 0.218 | 0.0 | 400.0 | 400 |
| 0.95 → 0.85 | Clopper-Pearson fixed | not published / N/A | 0.001 | 0.0 | 400.0 | 400 |
| 0.95 → 0.95 | Newcombe fixed | 0.989 | 0.989 | not published / N/A | 400.0 | 400 |
| 0.95 → 0.75 | Newcombe fixed | 0.838 | not published / N/A | 0.838 | 400.0 | 400 |
| 0.95 → 0.65 | Newcombe fixed | 0.9998 | not published / N/A | 0.9998 | 400.0 | 400 |
| 0.80 → 0.80 | Newcombe fixed | 0.706 | 0.706 | not published / N/A | 400.0 | 400 |
| 0.95 → 0.85 | Newcombe fixed | not published / N/A | 0.025 | 0.022 | 400.0 | 400 |
| 0.95 → 0.95 | Clopper-Pearson sequential | 0.735 | 0.735 | not published / N/A | 350.0 | 400 |
| 0.95 → 0.65 | Clopper-Pearson sequential | 0.943 | not published / N/A | 0.943 | 302.0 | 400 |
| 0.95 → 0.95 | Newcombe sequential | 0.969 | 0.969 | not published / N/A | 239.0 | 400 |
| 0.95 → 0.65 | Newcombe sequential | 0.9989 | not published / N/A | 0.9989 | 159.0 | 400 |

| rates | v2 dependence | cap | correct probability | PASS | BLOCK | expected sessions | ceiling sessions |
|---|---|---:|---:|---:|---:|---:|---:|
| 0.95 → 0.95 | independent | 200 | 0.936106 | 0.936106 | 0.000000 | 230.807 | 400 |
| 0.95 → 0.95 | independent | 400 | 0.999516 | 0.999516 | 0.000000 | 236.810 | 800 |
| 0.95 → 0.95 | intermediate | 200 | 0.996155 | 0.996155 | 0.000000 | 197.590 | 400 |
| 0.95 → 0.95 | intermediate | 400 | 1.000000 | 1.000000 | 0.000000 | 197.797 | 800 |
| 0.95 → 0.75 | independent | 200 | 0.619066 | 0.000007 | 0.619066 | 310.459 | 400 |
| 0.95 → 0.75 | independent | 400 | 0.932962 | 0.000007 | 0.932962 | 387.177 | 800 |
| 0.95 → 0.75 | intermediate | 200 | 0.726108 | 0.000001 | 0.726108 | 296.145 | 400 |
| 0.95 → 0.75 | intermediate | 400 | 0.978715 | 0.000001 | 0.978715 | 339.231 | 800 |
| 0.95 → 0.65 | independent | 200 | 0.996784 | 0.000000 | 0.996784 | 154.116 | 400 |
| 0.95 → 0.65 | independent | 400 | 1.000000 | 0.000000 | 1.000000 | 154.303 | 800 |
| 0.95 → 0.65 | intermediate | 200 | 0.999446 | 0.000000 | 0.999446 | 144.729 | 400 |
| 0.95 → 0.65 | intermediate | 400 | 1.000000 | 0.000000 | 1.000000 | 144.755 | 800 |
| 0.80 → 0.80 | independent | 200 | 0.424708 | 0.424708 | 0.000017 | 329.763 | 400 |
| 0.80 → 0.80 | independent | 400 | 0.790628 | 0.790628 | 0.000017 | 482.761 | 800 |
| 0.80 → 0.80 | intermediate | 200 | 0.770224 | 0.770224 | 0.000000 | 271.589 | 400 |
| 0.80 → 0.80 | intermediate | 400 | 0.982025 | 0.982025 | 0.000000 | 308.939 | 800 |
| 0.95 → 0.85 | independent | 200 | N/A (boundary) | 0.008636 | 0.005327 | 397.969 | 400 |
| 0.95 → 0.85 | independent | 400 | N/A (boundary) | 0.012420 | 0.010413 | 790.423 | 800 |
| 0.95 → 0.85 | intermediate | 200 | N/A (boundary) | 0.007400 | 0.003395 | 398.638 | 400 |
| 0.95 → 0.85 | intermediate | 400 | N/A (boundary) | 0.011904 | 0.008651 | 792.189 | 800 |

Clopper-Pearson fixed: mixed overall; at the same 400-session ceiling, v2 has higher correct-decision probability and lower expected sessions in all four measured non-margin independent cases, but higher boundary error rates.
Newcombe fixed: mixed; at cap 200, v2 has lower correct-decision probability and lower expected sessions in all four measured independent cases; at cap 400 power is higher in all four, but the ceiling doubles and the 0.80 no-change case averages 482.76 sessions versus 400.
Newcombe sequential: mixed; for both published independent cases v2 at cap 200 uses fewer expected sessions with lower power; at cap 400 it has higher power and lower expected sessions, with twice the ceiling (800 versus 400).

## 6. Verification and limits

Every checkpoint through 400 pairs compares S1's integer frontier with rational count_wealth plus classify at both sides of both frontiers for every minus count. The agreement point uses 1,000 seeded paired Bernoulli streams (0.80→0.80, independent, cap 400) through suite_stats.decide, never the shared frontier; each verdict frequency is checked within five binomial SE plus 1/reps of exact enumeration. An exhaustive six-pair ordered-path test independently checks the conditional recurrence.

Stream agreement: `{"check": "within five binomial SE plus 1/reps", "counts": {"BLOCK": 0, "ERROR": 0, "INCONCLUSIVE": 220, "PASS": 780}, "exact_mean_pairs": 241.38034330431452, "expected_counts": {"BLOCK": 0.017363589773828802, "ERROR": 0.0, "INCONCLUSIVE": 209.35488534709734, "PASS": 790.6277510631289}, "mean_pairs": 243.27, "reps": 1000, "seed": 20261110}`.

- pytest: exit 0; last line: `37 passed (elapsed excluded)`
- ruff_format: exit 0; last line: `9 files already formatted`
- ruff_check: exit 0; last line: `All checks passed!`
- basedpyright: exit 0; last line: `0 errors, 0 warnings, 0 notes`
- frozen: exit 0; last line: `uv.lock: OK`

Regenerate: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=plan/exec/v2/spikes/s1:plan/exec/v2/spikes/s1b .venv/bin/python plan/exec/v2/spikes/s1b/run_all.py --verify-repeat`. The repeat option recomputes all results and checks, comparing output bytes; elapsed.txt is the only output allowed to change. Source/input hashes are recorded in results.json. No frozen or S1 file is modified; bytecode and test caches are disabled. This is a statistical spike, not production runner integration, cross-platform validation, or evidence of provider stationarity.

Unexpected result: the concentrated schedule's conditional errors have a much wider spread than the earlier review's illustrative range. That is a valid result for this explicitly declared sparse-loss law, not a failed unconditional error bound. The selected set's all-zero floor rises from S1's 70 to 80 pairs.
