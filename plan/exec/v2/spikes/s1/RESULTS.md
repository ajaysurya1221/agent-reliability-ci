# S1 suite statistics spike

Run: FULL, 537.3 seconds including checks.
Standard library only; no network, product edits, or git-state changes.

## Decision and preregistered comparison

Proposed default: equal mixture q=(1/8,1/4,1/2,3/4), with lambda_plus=q/(1-delta)
and lambda_minus=q/(1+delta); alpha=1/20, delta=1/10, batch=10, max_pairs=400.
A final partial batch is a checkpoint. Maximum cost is 800 agent sessions per suite,
not per cell. This is a budget choice, not a guarantee of a verdict or task coverage.
Mixture/adaptive capped mean-cost ratio: min 0.624, max 1.167.
Mixture within 15% at every comparison point: NO.
Recommend the mixture: exact count-based calibration and simple fixed stakes.
It has lower or equal measured capped mean cost at 23/30 comparison points. The 15% condition above is not concealed or relaxed.
The largest disadvantage is the deterministic d=0 positive-coupling case: 70 pairs
versus adaptive's 60. This simplicity/cost tradeoff does not imply universal superiority.
No stake parameters were tuned in response to errors. All three rules and the grids
are constants in the source. Expected pairs below are capped stopping times, including
INCONCLUSIVE at the cap; they are not uncapped expected time to a decision.

| pass condition | result |
|---|---|
| 1_A_exact_error_control | GO |
| 2_B_upper99_le_alpha | GO |
| 3_five_shared_points | GO |
| 4_tests_and_lint | GO |
| 5_frozen | GO |

## A. Certified error enumeration

| cap | batch | boundary PASS | null BLOCK | no-change-or-above BLOCK | below-boundary PASS supremum | max lost mass |
|---:|---:|---:|---:|---:|---:|---:|
| 50 | 1 | 0.01007868 | 0.01032611 | 0.00247805 | 0.01007868 | 0.00e+00 |
| 50 | 10 | 0.00466184 | 0.00386627 | 0.00060165 | 0.00466184 | 0.00e+00 |
| 50 | 20 | 0.00346441 | 0.00332758 | 0.00051003 | 0.00346441 | 0.00e+00 |
| 100 | 1 | 0.01243460 | 0.01272454 | 0.00261292 | 0.01243460 | 0.00e+00 |
| 100 | 10 | 0.00625023 | 0.00592622 | 0.00066629 | 0.00625023 | 0.00e+00 |
| 100 | 20 | 0.00454541 | 0.00438605 | 0.00052366 | 0.00454541 | 0.00e+00 |
| 200 | 1 | 0.01528704 | 0.01542264 | 0.00264617 | 0.01528704 | 0.00e+00 |
| 200 | 10 | 0.00835701 | 0.00779018 | 0.00068092 | 0.00835701 | 0.00e+00 |
| 200 | 20 | 0.00611096 | 0.00591773 | 0.00053405 | 0.00611096 | 0.00e+00 |
| 400 | 1 | 0.01754383 | 0.01802007 | 0.00265089 | 0.01754383 | 0.00e+00 |
| 400 | 10 | 0.01045702 | 0.01017187 | 0.00068319 | 0.01045702 | 0.00e+00 |
| 400 | 20 | 0.00821431 | 0.00803707 | 0.00053581 | 0.00817857 | 0.00e+00 |
| 1000 | 1 | 0.02032110 | 0.02090523 | 0.00265101 | 0.02032110 | 0.00e+00 |
| 1000 | 10 | 0.01321433 | 0.01298007 | 0.00068324 | 0.01321433 | 0.00e+00 |
| 1000 | 20 | 0.01096167 | 0.01076628 | 0.00053585 | 0.01096167 | 0.00e+00 |

Entries are exact rational probabilities, displayed rounded to eight decimals;
the pass check uses the rationals in results.json. No Monte Carlo in A.
p_zero grid: 0, 1/20, 1/10, 3/20, 1/5, 1/4, 3/10, 7/20, 2/5, 9/20, 1/2, 11/20, 3/5, 13/20, 7/10, 3/4, 4/5, 17/20, 9/10, 19/20
At Delta=-.10, p_zero=.95 is infeasible (negative p_plus),
so it is recorded as a null-edge point Delta=-.05, not a fabricated boundary point.
For fixed p_zero, increasing Delta increases PASS and decreases BLOCK even with
first-stop absorption (pathwise monotone coupling). Boundary values therefore bound
all smaller means for false PASS and all larger means for false BLOCK. For p_zero<.90,
the strictly-below-boundary supremum equals the boundary value by continuity. At .90,
no smaller mean is feasible; that point is excluded from the below-boundary column.
The no-change line bounds all Delta>=0 at each grid p_zero. Between-grid p_zero
values are covered by the theorem, not an assertion of exhaustive enumeration.

## B. Actual cell-sampling simulations

Every point has suite mean exactly -.10, so BOTH directions count as errors.
Positive/negative mean the maximal feasible positive/negative Bernoulli coupling,
not a universal Pearson correlation coefficient. Cells are sampled with replacement.
99% bounds are one-sided Clopper-Pearson roots enclosed upward on a 2^-20 grid,
using exact integer binomial-tail comparisons. They are pointwise, not simultaneous.
Full B uses 20,000 replications at max_pairs=400, batch=10 at every point.

| T | K | difficulty | dependence | reps | false PASS | upper99 | false BLOCK | upper99 |
|---:|---:|---|---|---:|---:|---:|---:|---:|
| 10 | 1 | equal | independent | 20000 | 0.01055 | 0.012356 | 0.01025 | 0.012033 |
| 10 | 1 | equal | positive | 20000 | 0.00905 | 0.010734 | 0.00640 | 0.007839 |
| 10 | 1 | equal | negative | 20000 | 0.01020 | 0.011978 | 0.00960 | 0.011330 |
| 10 | 1 | mixed | independent | 20000 | 0.01045 | 0.012248 | 0.00945 | 0.011168 |
| 10 | 1 | mixed | positive | 20000 | 0.01050 | 0.012302 | 0.00740 | 0.008937 |
| 10 | 1 | mixed | negative | 20000 | 0.00975 | 0.011492 | 0.00940 | 0.011113 |
| 10 | 1 | concentrated | independent | 20000 | 0.01035 | 0.012140 | 0.00860 | 0.010245 |
| 10 | 1 | concentrated | positive | 20000 | 0.00910 | 0.010788 | 0.00585 | 0.007232 |
| 10 | 1 | concentrated | negative | 20000 | 0.01050 | 0.012302 | 0.01095 | 0.012787 |
| 10 | 3 | equal | independent | 20000 | 0.01080 | 0.012626 | 0.01030 | 0.012086 |
| 10 | 3 | equal | positive | 20000 | 0.00875 | 0.010408 | 0.00610 | 0.007508 |
| 10 | 3 | equal | negative | 20000 | 0.00970 | 0.011437 | 0.01000 | 0.011763 |
| 10 | 3 | mixed | independent | 20000 | 0.00990 | 0.011654 | 0.00975 | 0.011492 |
| 10 | 3 | mixed | positive | 20000 | 0.01120 | 0.013056 | 0.00660 | 0.008060 |
| 10 | 3 | mixed | negative | 20000 | 0.00965 | 0.011384 | 0.01055 | 0.012356 |
| 10 | 3 | concentrated | independent | 20000 | 0.01095 | 0.012787 | 0.01055 | 0.012356 |
| 10 | 3 | concentrated | positive | 20000 | 0.00965 | 0.011384 | 0.00640 | 0.007839 |
| 10 | 3 | concentrated | negative | 20000 | 0.01025 | 0.012033 | 0.01095 | 0.012787 |
| 20 | 1 | equal | independent | 20000 | 0.01000 | 0.011763 | 0.00940 | 0.011113 |
| 20 | 1 | equal | positive | 20000 | 0.00995 | 0.011708 | 0.00660 | 0.008060 |
| 20 | 1 | equal | negative | 20000 | 0.01025 | 0.012033 | 0.01100 | 0.012841 |
| 20 | 1 | mixed | independent | 20000 | 0.00970 | 0.011437 | 0.01000 | 0.011763 |
| 20 | 1 | mixed | positive | 20000 | 0.01030 | 0.012086 | 0.00705 | 0.008554 |
| 20 | 1 | mixed | negative | 20000 | 0.01080 | 0.012626 | 0.01005 | 0.011816 |
| 20 | 1 | concentrated | independent | 20000 | 0.01130 | 0.013164 | 0.00950 | 0.011221 |
| 20 | 1 | concentrated | positive | 20000 | 0.01030 | 0.012086 | 0.00615 | 0.007564 |
| 20 | 1 | concentrated | negative | 20000 | 0.01135 | 0.013218 | 0.01040 | 0.012195 |
| 20 | 3 | equal | independent | 20000 | 0.01145 | 0.013325 | 0.00980 | 0.011546 |
| 20 | 3 | equal | positive | 20000 | 0.00885 | 0.010516 | 0.00695 | 0.008444 |
| 20 | 3 | equal | negative | 20000 | 0.01035 | 0.012140 | 0.00950 | 0.011221 |
| 20 | 3 | mixed | independent | 20000 | 0.00935 | 0.011059 | 0.00820 | 0.009809 |
| 20 | 3 | mixed | positive | 20000 | 0.01075 | 0.012571 | 0.00680 | 0.008279 |
| 20 | 3 | mixed | negative | 20000 | 0.01005 | 0.011816 | 0.00850 | 0.010137 |
| 20 | 3 | concentrated | independent | 20000 | 0.01030 | 0.012086 | 0.01025 | 0.012033 |
| 20 | 3 | concentrated | positive | 20000 | 0.01055 | 0.012356 | 0.00720 | 0.008718 |
| 20 | 3 | concentrated | negative | 20000 | 0.00980 | 0.011546 | 0.01065 | 0.012464 |
| 50 | 1 | equal | independent | 20000 | 0.01005 | 0.011816 | 0.00965 | 0.011384 |
| 50 | 1 | equal | positive | 20000 | 0.00950 | 0.011221 | 0.00630 | 0.007729 |
| 50 | 1 | equal | negative | 20000 | 0.01185 | 0.013755 | 0.00970 | 0.011437 |
| 50 | 1 | mixed | independent | 20000 | 0.01000 | 0.011763 | 0.00820 | 0.009809 |
| 50 | 1 | mixed | positive | 20000 | 0.01065 | 0.012464 | 0.00800 | 0.009592 |
| 50 | 1 | mixed | negative | 20000 | 0.00975 | 0.011492 | 0.00990 | 0.011654 |
| 50 | 1 | concentrated | independent | 20000 | 0.00950 | 0.011221 | 0.00865 | 0.010300 |
| 50 | 1 | concentrated | positive | 20000 | 0.00935 | 0.011059 | 0.00695 | 0.008444 |
| 50 | 1 | concentrated | negative | 20000 | 0.00995 | 0.011708 | 0.01030 | 0.012086 |
| 50 | 3 | equal | independent | 20000 | 0.00935 | 0.011059 | 0.00870 | 0.010354 |
| 50 | 3 | equal | positive | 20000 | 0.00955 | 0.011275 | 0.00625 | 0.007673 |
| 50 | 3 | equal | negative | 20000 | 0.01065 | 0.012464 | 0.01095 | 0.012787 |
| 50 | 3 | mixed | independent | 20000 | 0.00965 | 0.011384 | 0.00840 | 0.010028 |
| 50 | 3 | mixed | positive | 20000 | 0.00975 | 0.011492 | 0.00630 | 0.007729 |
| 50 | 3 | mixed | negative | 20000 | 0.00945 | 0.011168 | 0.01090 | 0.012733 |
| 50 | 3 | concentrated | independent | 20000 | 0.00960 | 0.011330 | 0.01000 | 0.011763 |
| 50 | 3 | concentrated | positive | 20000 | 0.01030 | 0.012086 | 0.00640 | 0.007839 |
| 50 | 3 | concentrated | negative | 20000 | 0.01025 | 0.012033 | 0.01125 | 0.013110 |
| 100 | 1 | equal | independent | 20000 | 0.01060 | 0.012410 | 0.00930 | 0.011004 |
| 100 | 1 | equal | positive | 20000 | 0.01015 | 0.011925 | 0.00495 | 0.006232 |
| 100 | 1 | equal | negative | 20000 | 0.01045 | 0.012248 | 0.01020 | 0.011978 |
| 100 | 1 | mixed | independent | 20000 | 0.01085 | 0.012679 | 0.00830 | 0.009918 |
| 100 | 1 | mixed | positive | 20000 | 0.00860 | 0.010245 | 0.00590 | 0.007287 |
| 100 | 1 | mixed | negative | 20000 | 0.01110 | 0.012949 | 0.01115 | 0.013002 |
| 100 | 1 | concentrated | independent | 20000 | 0.01035 | 0.012140 | 0.00935 | 0.011059 |
| 100 | 1 | concentrated | positive | 20000 | 0.00985 | 0.011600 | 0.00570 | 0.007066 |
| 100 | 1 | concentrated | negative | 20000 | 0.01055 | 0.012356 | 0.00995 | 0.011708 |
| 100 | 3 | equal | independent | 20000 | 0.01145 | 0.013325 | 0.00935 | 0.011059 |
| 100 | 3 | equal | positive | 20000 | 0.01010 | 0.011870 | 0.00650 | 0.007949 |
| 100 | 3 | equal | negative | 20000 | 0.00985 | 0.011600 | 0.01000 | 0.011763 |
| 100 | 3 | mixed | independent | 20000 | 0.00925 | 0.010951 | 0.00915 | 0.010842 |
| 100 | 3 | mixed | positive | 20000 | 0.00900 | 0.010679 | 0.00640 | 0.007839 |
| 100 | 3 | mixed | negative | 20000 | 0.01085 | 0.012679 | 0.00980 | 0.011546 |
| 100 | 3 | concentrated | independent | 20000 | 0.00990 | 0.011654 | 0.01090 | 0.012733 |
| 100 | 3 | concentrated | positive | 20000 | 0.00955 | 0.011275 | 0.00675 | 0.008224 |
| 100 | 3 | concentrated | negative | 20000 | 0.01050 | 0.012302 | 0.00945 | 0.011168 |

## C. Power and cost, and stake comparison

Seeded Monte Carlo; each full-run row has 20,000 replications. Maximum Bernoulli
standard error is 0.00354 (roughly +/-0.00693 at 95%); means/quantiles are empirical.
Seeds and exact trinomial inputs are reproducible from source/results.json.
Positive uses the Frechet upper coupling (d=0 deterministically for equal arms).
The fixed comparator uses q=1/2. Adaptive uses ONLY previous outcomes, rational
mean/second-moment stakes damped by 1/2, clipped at 3/4 of the legal cap and rounded
down to 1/64-cap increments. No superiority claim beyond these scenarios.

| A -> B | dependence | rule | cap | PASS | BLOCK | INC | ERROR | mean pairs | median | p90 |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.95->0.95 | independent | fixed | 100 | 0.59225 | 0.00000 | 0.40775 | 0.00000 | 85.34 | 100 | 100 |
| 0.95->0.95 | independent | fixed | 200 | 0.95705 | 0.00000 | 0.04295 | 0.00000 | 103.40 | 100 | 170 |
| 0.95->0.95 | independent | fixed | 400 | 0.99975 | 0.00000 | 0.00025 | 0.00000 | 105.80 | 90 | 170 |
| 0.95->0.95 | independent | mixture | 100 | 0.49320 | 0.00000 | 0.50680 | 0.00000 | 85.47 | 100 | 100 |
| 0.95->0.95 | independent | mixture | 200 | 0.90290 | 0.00000 | 0.09710 | 0.00000 | 112.53 | 100 | 200 |
| 0.95->0.95 | independent | mixture | 400 | 0.99890 | 0.00000 | 0.00110 | 0.00000 | 117.33 | 100 | 200 |
| 0.95->0.95 | independent | adaptive | 100 | 0.33045 | 0.00000 | 0.66955 | 0.00000 | 91.52 | 100 | 100 |
| 0.95->0.95 | independent | adaptive | 200 | 0.78815 | 0.00000 | 0.21185 | 0.00000 | 135.51 | 140 | 200 |
| 0.95->0.95 | independent | adaptive | 400 | 0.99540 | 0.00000 | 0.00460 | 0.00000 | 148.53 | 140 | 250 |
| 0.95->0.95 | positive | fixed | 100 | 1.00000 | 0.00000 | 0.00000 | 0.00000 | 70.00 | 70 | 70 |
| 0.95->0.95 | positive | fixed | 200 | 1.00000 | 0.00000 | 0.00000 | 0.00000 | 70.00 | 70 | 70 |
| 0.95->0.95 | positive | fixed | 400 | 1.00000 | 0.00000 | 0.00000 | 0.00000 | 70.00 | 70 | 70 |
| 0.95->0.95 | positive | mixture | 100 | 1.00000 | 0.00000 | 0.00000 | 0.00000 | 70.00 | 70 | 70 |
| 0.95->0.95 | positive | mixture | 200 | 1.00000 | 0.00000 | 0.00000 | 0.00000 | 70.00 | 70 | 70 |
| 0.95->0.95 | positive | mixture | 400 | 1.00000 | 0.00000 | 0.00000 | 0.00000 | 70.00 | 70 | 70 |
| 0.95->0.95 | positive | adaptive | 100 | 1.00000 | 0.00000 | 0.00000 | 0.00000 | 60.00 | 60 | 60 |
| 0.95->0.95 | positive | adaptive | 200 | 1.00000 | 0.00000 | 0.00000 | 0.00000 | 60.00 | 60 | 60 |
| 0.95->0.95 | positive | adaptive | 400 | 1.00000 | 0.00000 | 0.00000 | 0.00000 | 60.00 | 60 | 60 |
| 0.95->0.75 | independent | fixed | 100 | 0.00000 | 0.28435 | 0.71565 | 0.00000 | 92.94 | 100 | 100 |
| 0.95->0.75 | independent | fixed | 200 | 0.00005 | 0.67630 | 0.32365 | 0.00000 | 144.90 | 150 | 200 |
| 0.95->0.75 | independent | fixed | 400 | 0.00000 | 0.92880 | 0.07120 | 0.00000 | 180.28 | 150 | 360 |
| 0.95->0.75 | independent | mixture | 100 | 0.00005 | 0.23455 | 0.76540 | 0.00000 | 93.75 | 100 | 100 |
| 0.95->0.75 | independent | mixture | 200 | 0.00005 | 0.55495 | 0.44500 | 0.00000 | 155.57 | 190 | 200 |
| 0.95->0.75 | independent | mixture | 400 | 0.00000 | 0.90285 | 0.09715 | 0.00000 | 203.38 | 180 | 400 |
| 0.95->0.75 | independent | adaptive | 100 | 0.00005 | 0.05785 | 0.94210 | 0.00000 | 98.88 | 100 | 100 |
| 0.95->0.75 | independent | adaptive | 200 | 0.00000 | 0.28750 | 0.71250 | 0.00000 | 183.42 | 200 | 200 |
| 0.95->0.75 | independent | adaptive | 400 | 0.00000 | 0.74655 | 0.25345 | 0.00000 | 277.83 | 280 | 400 |
| 0.95->0.75 | positive | fixed | 100 | 0.00000 | 0.36285 | 0.63715 | 0.00000 | 92.57 | 100 | 100 |
| 0.95->0.75 | positive | fixed | 200 | 0.00000 | 0.89980 | 0.10020 | 0.00000 | 125.20 | 120 | 200 |
| 0.95->0.75 | positive | fixed | 400 | 0.00000 | 0.99920 | 0.00080 | 0.00000 | 129.85 | 120 | 210 |
| 0.95->0.75 | positive | mixture | 100 | 0.00000 | 0.37185 | 0.62815 | 0.00000 | 91.76 | 100 | 100 |
| 0.95->0.75 | positive | mixture | 200 | 0.00000 | 0.89195 | 0.10805 | 0.00000 | 125.47 | 120 | 200 |
| 0.95->0.75 | positive | mixture | 400 | 0.00000 | 0.99820 | 0.00180 | 0.00000 | 132.05 | 120 | 210 |
| 0.95->0.75 | positive | adaptive | 100 | 0.00000 | 0.07760 | 0.92240 | 0.00000 | 98.85 | 100 | 100 |
| 0.95->0.75 | positive | adaptive | 200 | 0.00000 | 0.51835 | 0.48165 | 0.00000 | 172.55 | 200 | 200 |
| 0.95->0.75 | positive | adaptive | 400 | 0.00000 | 0.96620 | 0.03380 | 0.00000 | 211.74 | 200 | 330 |
| 0.95->0.65 | independent | fixed | 100 | 0.00000 | 0.88335 | 0.11665 | 0.00000 | 65.45 | 60 | 100 |
| 0.95->0.65 | independent | fixed | 200 | 0.00000 | 0.99735 | 0.00265 | 0.00000 | 68.98 | 60 | 110 |
| 0.95->0.65 | independent | fixed | 400 | 0.00000 | 1.00000 | 0.00000 | 0.00000 | 68.84 | 60 | 110 |
| 0.95->0.65 | independent | mixture | 100 | 0.00000 | 0.83695 | 0.16305 | 0.00000 | 67.53 | 60 | 100 |
| 0.95->0.65 | independent | mixture | 200 | 0.00000 | 0.99350 | 0.00650 | 0.00000 | 73.56 | 60 | 120 |
| 0.95->0.65 | independent | mixture | 400 | 0.00000 | 1.00000 | 0.00000 | 0.00000 | 73.58 | 60 | 120 |
| 0.95->0.65 | independent | adaptive | 100 | 0.00000 | 0.58185 | 0.41815 | 0.00000 | 84.15 | 100 | 100 |
| 0.95->0.65 | independent | adaptive | 200 | 0.00000 | 0.96830 | 0.03170 | 0.00000 | 102.94 | 100 | 170 |
| 0.95->0.65 | independent | adaptive | 400 | 0.00000 | 0.99995 | 0.00005 | 0.00000 | 103.95 | 100 | 170 |
| 0.95->0.65 | positive | fixed | 100 | 0.00000 | 0.97175 | 0.02825 | 0.00000 | 60.27 | 60 | 90 |
| 0.95->0.65 | positive | fixed | 200 | 0.00000 | 1.00000 | 0.00000 | 0.00000 | 60.48 | 60 | 90 |
| 0.95->0.65 | positive | fixed | 400 | 0.00000 | 1.00000 | 0.00000 | 0.00000 | 60.74 | 60 | 90 |
| 0.95->0.65 | positive | mixture | 100 | 0.00000 | 0.97350 | 0.02650 | 0.00000 | 58.15 | 60 | 80 |
| 0.95->0.65 | positive | mixture | 200 | 0.00000 | 1.00000 | 0.00000 | 0.00000 | 58.50 | 60 | 80 |
| 0.95->0.65 | positive | mixture | 400 | 0.00000 | 1.00000 | 0.00000 | 0.00000 | 58.55 | 60 | 80 |
| 0.95->0.65 | positive | adaptive | 100 | 0.00000 | 0.81155 | 0.18845 | 0.00000 | 77.73 | 80 | 100 |
| 0.95->0.65 | positive | adaptive | 200 | 0.00000 | 0.99910 | 0.00090 | 0.00000 | 82.66 | 80 | 120 |
| 0.95->0.65 | positive | adaptive | 400 | 0.00000 | 1.00000 | 0.00000 | 0.00000 | 82.73 | 80 | 120 |
| 0.80->0.80 | independent | fixed | 100 | 0.23100 | 0.00000 | 0.76900 | 0.00000 | 92.02 | 100 | 100 |
| 0.80->0.80 | independent | fixed | 200 | 0.40510 | 0.00005 | 0.59485 | 0.00000 | 160.26 | 200 | 200 |
| 0.80->0.80 | independent | fixed | 400 | 0.57345 | 0.00010 | 0.42645 | 0.00000 | 260.49 | 300 | 400 |
| 0.80->0.80 | independent | mixture | 100 | 0.14700 | 0.00000 | 0.85300 | 0.00000 | 94.68 | 100 | 100 |
| 0.80->0.80 | independent | mixture | 200 | 0.34950 | 0.00005 | 0.65045 | 0.00000 | 171.29 | 200 | 200 |
| 0.80->0.80 | independent | mixture | 400 | 0.74850 | 0.00000 | 0.25150 | 0.00000 | 260.97 | 270 | 400 |
| 0.80->0.80 | independent | adaptive | 100 | 0.04870 | 0.00000 | 0.95130 | 0.00000 | 98.83 | 100 | 100 |
| 0.80->0.80 | independent | adaptive | 200 | 0.17755 | 0.00000 | 0.82245 | 0.00000 | 188.74 | 200 | 200 |
| 0.80->0.80 | independent | adaptive | 400 | 0.52485 | 0.00000 | 0.47515 | 0.00000 | 319.81 | 390 | 400 |
| 0.80->0.80 | positive | fixed | 100 | 1.00000 | 0.00000 | 0.00000 | 0.00000 | 70.00 | 70 | 70 |
| 0.80->0.80 | positive | fixed | 200 | 1.00000 | 0.00000 | 0.00000 | 0.00000 | 70.00 | 70 | 70 |
| 0.80->0.80 | positive | fixed | 400 | 1.00000 | 0.00000 | 0.00000 | 0.00000 | 70.00 | 70 | 70 |
| 0.80->0.80 | positive | mixture | 100 | 1.00000 | 0.00000 | 0.00000 | 0.00000 | 70.00 | 70 | 70 |
| 0.80->0.80 | positive | mixture | 200 | 1.00000 | 0.00000 | 0.00000 | 0.00000 | 70.00 | 70 | 70 |
| 0.80->0.80 | positive | mixture | 400 | 1.00000 | 0.00000 | 0.00000 | 0.00000 | 70.00 | 70 | 70 |
| 0.80->0.80 | positive | adaptive | 100 | 1.00000 | 0.00000 | 0.00000 | 0.00000 | 60.00 | 60 | 60 |
| 0.80->0.80 | positive | adaptive | 200 | 1.00000 | 0.00000 | 0.00000 | 0.00000 | 60.00 | 60 | 60 |
| 0.80->0.80 | positive | adaptive | 400 | 1.00000 | 0.00000 | 0.00000 | 0.00000 | 60.00 | 60 | 60 |
| 0.95->0.85 | independent | fixed | 100 | 0.00705 | 0.00285 | 0.99010 | 0.00000 | 99.75 | 100 | 100 |
| 0.95->0.85 | independent | fixed | 200 | 0.01445 | 0.00960 | 0.97595 | 0.00000 | 197.90 | 200 | 200 |
| 0.95->0.85 | independent | fixed | 400 | 0.01780 | 0.01575 | 0.96645 | 0.00000 | 391.77 | 400 | 400 |
| 0.95->0.85 | independent | mixture | 100 | 0.00440 | 0.00275 | 0.99285 | 0.00000 | 99.75 | 100 | 100 |
| 0.95->0.85 | independent | mixture | 200 | 0.00805 | 0.00585 | 0.98610 | 0.00000 | 198.60 | 200 | 200 |
| 0.95->0.85 | independent | mixture | 400 | 0.00975 | 0.00835 | 0.98190 | 0.00000 | 395.42 | 400 | 400 |
| 0.95->0.85 | independent | adaptive | 100 | 0.00130 | 0.00000 | 0.99870 | 0.00000 | 99.96 | 100 | 100 |
| 0.95->0.85 | independent | adaptive | 200 | 0.00215 | 0.00025 | 0.99760 | 0.00000 | 199.74 | 200 | 200 |
| 0.95->0.85 | independent | adaptive | 400 | 0.00295 | 0.00110 | 0.99595 | 0.00000 | 399.13 | 400 | 400 |
| 0.95->0.85 | positive | fixed | 100 | 0.00300 | 0.00045 | 0.99655 | 0.00000 | 99.96 | 100 | 100 |
| 0.95->0.85 | positive | fixed | 200 | 0.01125 | 0.00315 | 0.98560 | 0.00000 | 199.13 | 200 | 200 |
| 0.95->0.85 | positive | fixed | 400 | 0.01740 | 0.01020 | 0.97240 | 0.00000 | 394.84 | 400 | 400 |
| 0.95->0.85 | positive | mixture | 100 | 0.00375 | 0.00050 | 0.99575 | 0.00000 | 99.94 | 100 | 100 |
| 0.95->0.85 | positive | mixture | 200 | 0.00685 | 0.00220 | 0.99095 | 0.00000 | 199.34 | 200 | 200 |
| 0.95->0.85 | positive | mixture | 400 | 0.01045 | 0.00675 | 0.98280 | 0.00000 | 396.33 | 400 | 400 |
| 0.95->0.85 | positive | adaptive | 100 | 0.00330 | 0.00000 | 0.99670 | 0.00000 | 99.91 | 100 | 100 |
| 0.95->0.85 | positive | adaptive | 200 | 0.00530 | 0.00000 | 0.99470 | 0.00000 | 199.42 | 200 | 200 |
| 0.95->0.85 | positive | adaptive | 400 | 0.00635 | 0.00015 | 0.99350 | 0.00000 | 398.17 | 400 | 400 |

## D. Published v1 comparison, K=1

v1 inputs below are the rounded published values in docs/STATISTICS.md, not reruns.
Fixed v1 costs 400 sessions. Sequential v1 uses looks 50/100/200. v2 rows use the
same 200-pair cap, independent arms, batch=10. Multi-task suite-mean and per-condition
v1 claims differ; this homogeneous K=1 comparison does not equate their guarantees.
At the margin both decisions are errors; fewer decisions there is better error control.
Higher/lower labels compare measured point estimates with the published rounded numbers;
they are not significance tests. Table C states Monte Carlo uncertainty.

| rates | method | PASS | BLOCK | expected sessions | comparison with v2 |
|---|---|---:|---:|---:|---|
| 0.95->0.95 | CP fixed | 0.889 | 0.0 | 400 | v2 measured correct-decision probability higher; v2 cost 225.1 (lower) |
| 0.95->0.95 | Newcombe fixed | 0.989 | 0.0 | 400 | v2 measured correct-decision probability lower; v2 cost 225.1 (lower) |
| 0.95->0.75 | CP fixed | 0.0 | 0.365 | 400 | v2 measured correct-decision probability higher; v2 cost 311.1 (lower) |
| 0.95->0.75 | Newcombe fixed | 0.0 | 0.838 | 400 | v2 measured correct-decision probability lower; v2 cost 311.1 (lower) |
| 0.95->0.65 | CP fixed | 0.0 | 0.985 | 400 | v2 measured correct-decision probability higher; v2 cost 147.1 (lower) |
| 0.95->0.65 | Newcombe fixed | not published | 0.9998 | 400 | v2 measured correct-decision probability lower; v2 cost 147.1 (lower) |
| 0.80->0.80 | CP fixed | 0.218 | 0.0 | 400 | v2 measured correct-decision probability higher; v2 cost 342.6 (lower) |
| 0.80->0.80 | Newcombe fixed | 0.706 | 0.0 | 400 | v2 measured correct-decision probability lower; v2 cost 342.6 (lower) |
| 0.95->0.85 | CP fixed | 0.001 | 0.0 | 400 | v2 measured false-PASS higher, false-BLOCK higher; v2 cost 397.2 (lower) |
| 0.95->0.85 | Newcombe fixed | 0.025 | 0.022 | 400 | v2 measured false-PASS lower, false-BLOCK lower; v2 cost 397.2 (lower) |
| 0.95->0.95 | CP sequential | 0.735 | not published | 350 | v2 measured correct-decision probability higher; v2 cost 225.1 (lower) |
| 0.95->0.95 | Newcombe sequential | 0.969 | not published | 239 | v2 measured correct-decision probability lower; v2 cost 225.1 (lower) |
| 0.95->0.65 | CP sequential | not published | 0.943 | 302 | v2 measured correct-decision probability higher; v2 cost 147.1 (lower) |
| 0.95->0.65 | Newcombe sequential | not published | 0.9989 | 159 | v2 measured correct-decision probability lower; v2 cost 147.1 (lower) |
| 0.95->0.95 | v2 mixture | 0.90290 | 0.00000 | 225.1 | reference |
| 0.95->0.75 | v2 mixture | 0.00005 | 0.55495 | 311.1 | reference |
| 0.95->0.65 | v2 mixture | 0.00000 | 0.99350 | 147.1 | reference |
| 0.80->0.80 | v2 mixture | 0.34950 | 0.00005 | 342.6 | reference |
| 0.95->0.85 | v2 mixture | 0.00805 | 0.00585 | 397.2 | reference |

Other v1 sequential scenarios are not published; no values were invented.
The full C table shows how increasing v2's cap to 400 trades additional sessions
for decisions. Strong-positive v2 cases are not compared with independent v1 numbers.

## Independent implementation checks

Float/reference corpus: 351 exact verdict/stopping-count agreements.
Five shared points use unrounded rational DP mass (not the enclosure optimization),
and independently generated cell simulations. Prespecified tolerance: five binomial
standard errors plus 1/reps, for each of PASS/BLOCK/INCONCLUSIVE.

| trinomial (-,0,+) | reps | exact PASS/BLOCK | simulated PASS/BLOCK | check |
|---|---:|---|---|---|
| 19/400, 181/200, 19/400 | 20000 | 0.498305/0.000000 | 0.495050/0.000000 | GO |
| 19/80, 29/40, 3/80 | 20000 | 0.000025/0.235352 | 0.000000/0.234650 | GO |
| 133/400, 127/200, 13/400 | 20000 | 0.000000/0.833916 | 0.000000/0.833000 | GO |
| 4/25, 17/25, 4/25 | 20000 | 0.147184/0.000045 | 0.146700/0.000050 | GO |
| 57/400, 163/200, 17/400 | 20000 | 0.004900/0.002714 | 0.004700/0.002850 | GO |

## Verification and limits

- pytest: exit 0; last lines: `['.............................                                            [100%]']`
- ruff_format: exit 0; last lines: `['7 files already formatted']`
- ruff_check: exit 0; last lines: `['All checks passed!']`
- basedpyright: exit 0; last lines: `['0 errors, 0 warnings, 0 notes']`
- frozen: exit 0; last lines: `['tests/acceptance/test_schedule.py: OK', 'tests/acceptance/test_schema.py: OK', 'tests/acceptance/test_sequential.py: OK', 'tests/acceptance/test_stats_gate.py: OK', 'uv.lock: OK']`

A uses exact integer decision frontiers and exact common-denominator probability mass.
Its lost-mass column is zero. Full rational numerators/denominators are in results.json.
An optional faster dyadic-enclosure implementation is included and tested against exact
probabilities, but is not used for Table A or the five shared exact/simulation points.
No provider stationarity, future runner implementation, cross-platform CI, or suite
sampling independence is established by this spike. Golden vectors ran on this host.
A hard-invariant BLOCK is outside these statistical false-BLOCK rates.
