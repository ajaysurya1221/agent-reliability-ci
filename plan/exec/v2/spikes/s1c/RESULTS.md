# S1c: balanced rounds versus sampled cells

All probabilities and expected costs are exact rational absorbing-DP results; decimal table entries are rounded. Full fractions, cell laws, candidate configurations, schedule keys and source hashes are in `results.json`. Fixed alpha=1/20, delta=1/10, stakes={1/4,1/2}; sampled batch=10, cap=400; balanced cap=N*floor(400/N). Each pair runs both arms. No outcome simulation is used.

## A and B. Boundary error control and conditional sampled schedules

Even: every cell has P(-1)=0.1 and P(0)=0.9. Concentrated-k: k cells have P(-1)=N/(10k), the others are deterministic zero; infeasible k are omitted (N=20: k=1; N=50 and 100: k=1,2,3). Half-improving: floor(N/2) cells have mean +0.3, others compensate; all have only -1/+1 support. Mixed: floor(N/2) cells have mean -0.4 and the rest compensate, again both signs possible. Every suite mean is exactly -0.1. Exact cell probabilities are recorded.

For B, 500 synthetic schedule keys per law use S1b schedule_key/cell_index with task-000...task-(N-1), clean condition, baseline s1c-boundary-baseline-v1 and candidate s1c-boundary-candidate-0000...0499. The same keys are used across laws at each N. Ordered, position-dependent laws feed the absorbing DP; allocations alone do not suffice. The mean over these keys is a finite schedule sample, not an exact expectation over all schedules. Median averages the central pair; p90/p99 use nearest rank.

| N | law | error | balanced | sampled mean | median | p90 | p99 | max |
|---:|---|---|---:|---:|---:|---:|---:|---:|
| 5 | even | PASS | 0.012263126 | 0.011278584 | 0.011278584 | 0.011278584 | 0.011278584 | 0.011278584 |
| 5 | even | BLOCK | 0.006035934 | 0.005407036 | 0.005407036 | 0.005407036 | 0.005407036 | 0.005407036 |
| 5 | concentrated-1 | PASS | 0.001190820 | 0.009603481 | 0.002023581 | 0.022908649 | 0.111028848 | 0.224450090 |
| 5 | concentrated-1 | BLOCK | 0.000048999 | 0.006890895 | 0.000186049 | 0.016654461 | 0.115292405 | 0.312121840 |
| 5 | concentrated-2 | PASS | 0.006469905 | 0.010554953 | 0.007108927 | 0.023948797 | 0.049971581 | 0.054280863 |
| 5 | concentrated-2 | BLOCK | 0.002096263 | 0.005345240 | 0.002429881 | 0.013977725 | 0.036923933 | 0.069213773 |
| 5 | concentrated-3 | PASS | 0.009445374 | 0.010974816 | 0.009094110 | 0.020604435 | 0.042823727 | 0.052296120 |
| 5 | concentrated-3 | BLOCK | 0.003990553 | 0.005522410 | 0.003838996 | 0.011435828 | 0.023633869 | 0.029856974 |
| 5 | half-improving | PASS | 0.008399874 | 0.011356511 | 0.008245525 | 0.023013897 | 0.049129855 | 0.070140444 |
| 5 | half-improving | BLOCK | 0.009760641 | 0.012511379 | 0.010162052 | 0.024784276 | 0.044873557 | 0.068112490 |
| 5 | mixed | PASS | 0.010454964 | 0.010955480 | 0.009525050 | 0.019204027 | 0.031285070 | 0.042671841 |
| 5 | mixed | BLOCK | 0.012472302 | 0.013160010 | 0.011148891 | 0.022804810 | 0.041664642 | 0.051772030 |
| 10 | even | PASS | 0.011278584 | 0.011278584 | 0.011278584 | 0.011278584 | 0.011278584 | 0.011278584 |
| 10 | even | BLOCK | 0.005407036 | 0.005407036 | 0.005407036 | 0.005407036 | 0.005407036 | 0.005407036 |
| 10 | concentrated-1 | PASS | 0.000000000 | 0.008000000 | 0.000000000 | 0.000000000 | 0.000000000 | 1.000000000 |
| 10 | concentrated-1 | BLOCK | 0.000000000 | 0.010000000 | 0.000000000 | 0.000000000 | 0.000000000 | 1.000000000 |
| 10 | concentrated-2 | PASS | 0.001055854 | 0.010021183 | 0.002277210 | 0.024031173 | 0.115759787 | 0.292424549 |
| 10 | concentrated-2 | BLOCK | 0.000041013 | 0.007276827 | 0.000151762 | 0.018552946 | 0.120314712 | 0.388210437 |
| 10 | concentrated-3 | PASS | 0.003720466 | 0.010609569 | 0.004766366 | 0.027511410 | 0.079890508 | 0.142393862 |
| 10 | concentrated-3 | BLOCK | 0.000779465 | 0.006275864 | 0.001221908 | 0.019179074 | 0.059383225 | 0.108463478 |
| 10 | half-improving | PASS | 0.004759651 | 0.012331515 | 0.007767677 | 0.029765553 | 0.067339072 | 0.115192667 |
| 10 | half-improving | BLOCK | 0.005971156 | 0.012885943 | 0.007492182 | 0.029995820 | 0.072089622 | 0.107335760 |
| 10 | mixed | PASS | 0.007213118 | 0.011013282 | 0.008223490 | 0.022350719 | 0.046882189 | 0.059118169 |
| 10 | mixed | BLOCK | 0.008678212 | 0.013932692 | 0.010953807 | 0.027802203 | 0.051884450 | 0.076282418 |
| 20 | even | PASS | 0.009034434 | 0.011278584 | 0.011278584 | 0.011278584 | 0.011278584 | 0.011278584 |
| 20 | even | BLOCK | 0.004849156 | 0.005407036 | 0.005407036 | 0.005407036 | 0.005407036 | 0.005407036 |
| 20 | concentrated-2 | PASS | 0.000000000 | 0.014000000 | 0.000000000 | 0.000000000 | 1.000000000 | 1.000000000 |
| 20 | concentrated-2 | BLOCK | 0.000000000 | 0.004000000 | 0.000000000 | 0.000000000 | 0.000000000 | 1.000000000 |
| 20 | concentrated-3 | PASS | 0.000089451 | 0.011690366 | 0.000647968 | 0.029359245 | 0.154680156 | 0.337882179 |
| 20 | concentrated-3 | BLOCK | 0.000000003 | 0.003737468 | 0.000000186 | 0.002701793 | 0.086957344 | 0.274070264 |
| 20 | half-improving | PASS | 0.003357481 | 0.011331081 | 0.007159980 | 0.027139346 | 0.062085479 | 0.138010588 |
| 20 | half-improving | BLOCK | 0.005209590 | 0.013824766 | 0.008847760 | 0.031641064 | 0.072880445 | 0.110584520 |
| 20 | mixed | PASS | 0.005173271 | 0.011652290 | 0.009244890 | 0.024156023 | 0.043261792 | 0.062935917 |
| 20 | mixed | BLOCK | 0.007581221 | 0.012969115 | 0.010211549 | 0.026476215 | 0.048520469 | 0.101017164 |
| 50 | even | PASS | 0.007114543 | 0.011278584 | 0.011278584 | 0.011278584 | 0.011278584 | 0.011278584 |
| 50 | even | BLOCK | 0.003762279 | 0.005407036 | 0.005407036 | 0.005407036 | 0.005407036 | 0.005407036 |
| 50 | half-improving | PASS | 0.002403444 | 0.011193281 | 0.007064702 | 0.025691803 | 0.065794470 | 0.078065532 |
| 50 | half-improving | BLOCK | 0.002586093 | 0.013142445 | 0.008281614 | 0.029145512 | 0.074511111 | 0.126510165 |
| 50 | mixed | PASS | 0.003686722 | 0.011287075 | 0.008786349 | 0.022987920 | 0.048731063 | 0.058795033 |
| 50 | mixed | BLOCK | 0.003890886 | 0.012953661 | 0.010445072 | 0.024297189 | 0.049020252 | 0.058937972 |
| 100 | even | PASS | 0.004570826 | 0.011278584 | 0.011278584 | 0.011278584 | 0.011278584 | 0.011278584 |
| 100 | even | BLOCK | 0.002979061 | 0.005407036 | 0.005407036 | 0.005407036 | 0.005407036 | 0.005407036 |
| 100 | half-improving | PASS | 0.001198606 | 0.011575466 | 0.006701093 | 0.026208322 | 0.070194056 | 0.092050316 |
| 100 | half-improving | BLOCK | 0.001516404 | 0.012830897 | 0.008377032 | 0.030506866 | 0.062793691 | 0.126832020 |
| 100 | mixed | PASS | 0.001883342 | 0.011202703 | 0.008730956 | 0.023430521 | 0.042049900 | 0.068938252 |
| 100 | mixed | BLOCK | 0.002316850 | 0.013333744 | 0.010270242 | 0.025986500 | 0.049238888 | 0.063752142 |

### Adversarial search

1000 loss-zero and 1000 loss-win laws on a 1/100 lattice; random restarts; no global optimality claim. Exactly 2,000 distinct ordered configurations per N; both maxima use all 2,000 evaluations. Boundary total loss units are fixed at 10N (loss-zero) or 55N (loss-win). Each restart draws a feasible bounded integer partition sequentially and shuffles its coordinates. This search is not uniform over the simplex and does not include general three-support laws. The proof, not the search, supplies the universal guarantee.

| N | direction | maximum found | candidate index | seed |
|---:|---|---:|---:|---:|
| 5 | PASS | 0.013858709 | 1589 | 2026111005 |
| 5 | BLOCK | 0.015956374 | 1589 | 2026111005 |
| 10 | PASS | 0.009302253 | 735 | 2026111010 |
| 10 | BLOCK | 0.008937202 | 1930 | 2026111010 |
| 20 | PASS | 0.004609987 | 186 | 2026111020 |
| 20 | BLOCK | 0.006232690 | 1676 | 2026111020 |

## C. Power and cost

Correct means PASS for equal arms, BLOCK for drops of 0.20 or 0.30. Intermediate coupling is S1b's equal mixture of independent and Frechet upper joint laws. Homogeneous cells give both designs the same marginal law; only registered looks differ. Values are correct-decision probability / expected pairs.

| baseline → candidate | coupling | N | balanced | sampled |
|---|---|---:|---:|---:|
| 0.50 → 0.50 | independent | 10 | 0.537656 / 297.677 | 0.537656 / 297.677 |
| 0.50 → 0.50 | independent | 20 | 0.519844 / 306.319 | 0.537656 / 297.677 |
| 0.50 → 0.50 | independent | 50 | 0.488250 / 322.922 | 0.537656 / 297.677 |
| 0.50 → 0.50 | intermediate | 10 | 0.891623 / 207.739 | 0.891623 / 207.739 |
| 0.50 → 0.50 | intermediate | 20 | 0.885144 / 217.772 | 0.891623 / 207.739 |
| 0.50 → 0.50 | intermediate | 50 | 0.873358 / 238.198 | 0.891623 / 207.739 |
| 0.50 → 0.30 | independent | 10 | 0.595049 / 290.050 | 0.595049 / 290.050 |
| 0.50 → 0.30 | independent | 20 | 0.578508 / 298.734 | 0.595049 / 290.050 |
| 0.50 → 0.30 | independent | 50 | 0.550119 / 316.016 | 0.595049 / 290.050 |
| 0.50 → 0.30 | intermediate | 10 | 0.809264 / 236.255 | 0.809264 / 236.255 |
| 0.50 → 0.30 | intermediate | 20 | 0.799280 / 245.257 | 0.809264 / 236.255 |
| 0.50 → 0.30 | intermediate | 50 | 0.781190 / 265.029 | 0.809264 / 236.255 |
| 0.50 → 0.20 | independent | 10 | 0.999536 / 101.526 | 0.999536 / 101.526 |
| 0.50 → 0.20 | independent | 20 | 0.999484 / 108.967 | 0.999536 / 101.526 |
| 0.50 → 0.20 | independent | 50 | 0.999393 / 127.095 | 0.999536 / 101.526 |
| 0.50 → 0.20 | intermediate | 10 | 0.999993 / 82.798 | 0.999993 / 82.798 |
| 0.50 → 0.20 | intermediate | 20 | 0.999992 / 88.888 | 0.999993 / 82.798 |
| 0.50 → 0.20 | intermediate | 50 | 0.999990 / 105.308 | 0.999993 / 82.798 |
| 0.65 → 0.65 | independent | 10 | 0.595078 / 286.714 | 0.595078 / 286.714 |
| 0.65 → 0.65 | independent | 20 | 0.577920 / 295.687 | 0.595078 / 286.714 |
| 0.65 → 0.65 | independent | 50 | 0.548201 / 313.263 | 0.595078 / 286.714 |
| 0.65 → 0.65 | intermediate | 10 | 0.920234 / 195.208 | 0.920234 / 195.208 |
| 0.65 → 0.65 | intermediate | 20 | 0.915294 / 204.986 | 0.920234 / 195.208 |
| 0.65 → 0.65 | intermediate | 50 | 0.906315 / 225.414 | 0.920234 / 195.208 |
| 0.65 → 0.45 | independent | 10 | 0.577090 / 293.743 | 0.577090 / 293.743 |
| 0.65 → 0.45 | independent | 20 | 0.560380 / 302.345 | 0.577090 / 293.743 |
| 0.65 → 0.45 | independent | 50 | 0.531403 / 319.268 | 0.577090 / 293.743 |
| 0.65 → 0.45 | intermediate | 10 | 0.796981 / 239.895 | 0.796981 / 239.895 |
| 0.65 → 0.45 | intermediate | 20 | 0.786492 / 248.923 | 0.796981 / 239.895 |
| 0.65 → 0.45 | intermediate | 50 | 0.767598 / 268.636 | 0.796981 / 239.895 |
| 0.65 → 0.35 | independent | 10 | 0.998581 / 110.830 | 0.998581 / 110.830 |
| 0.65 → 0.35 | independent | 20 | 0.998433 / 118.903 | 0.998581 / 110.830 |
| 0.65 → 0.35 | independent | 50 | 0.998165 / 137.742 | 0.998581 / 110.830 |
| 0.65 → 0.35 | intermediate | 10 | 0.999975 / 86.687 | 0.999975 / 86.687 |
| 0.65 → 0.35 | intermediate | 20 | 0.999972 / 93.107 | 0.999975 / 86.687 |
| 0.65 → 0.35 | intermediate | 50 | 0.999966 / 109.949 | 0.999975 / 86.687 |
| 0.80 → 0.80 | independent | 10 | 0.790628 / 241.380 | 0.790628 / 241.380 |
| 0.80 → 0.80 | independent | 20 | 0.778260 / 251.494 | 0.790628 / 241.380 |
| 0.80 → 0.80 | independent | 50 | 0.759039 / 271.352 | 0.790628 / 241.380 |
| 0.80 → 0.80 | intermediate | 10 | 0.982025 / 154.469 | 0.982025 / 154.469 |
| 0.80 → 0.80 | intermediate | 20 | 0.980540 / 162.950 | 0.982025 / 154.469 |
| 0.80 → 0.80 | intermediate | 50 | 0.977842 / 182.590 | 0.982025 / 154.469 |
| 0.80 → 0.60 | independent | 10 | 0.672725 / 272.745 | 0.672725 / 272.745 |
| 0.80 → 0.60 | independent | 20 | 0.658194 / 281.834 | 0.672725 / 272.745 |
| 0.80 → 0.60 | independent | 50 | 0.632782 / 300.316 | 0.672725 / 272.745 |
| 0.80 → 0.60 | intermediate | 10 | 0.859686 / 220.458 | 0.859686 / 220.458 |
| 0.80 → 0.60 | intermediate | 20 | 0.851730 / 229.446 | 0.859686 / 220.458 |
| 0.80 → 0.60 | intermediate | 50 | 0.837135 / 249.225 | 0.859686 / 220.458 |
| 0.80 → 0.50 | independent | 10 | 0.999536 / 101.526 | 0.999536 / 101.526 |
| 0.80 → 0.50 | independent | 20 | 0.999484 / 108.967 | 0.999536 / 101.526 |
| 0.80 → 0.50 | independent | 50 | 0.999393 / 127.095 | 0.999536 / 101.526 |
| 0.80 → 0.50 | intermediate | 10 | 0.999993 / 82.798 | 0.999993 / 82.798 |
| 0.80 → 0.50 | intermediate | 20 | 0.999992 / 88.888 | 0.999993 / 82.798 |
| 0.80 → 0.50 | intermediate | 50 | 0.999990 / 105.308 | 0.999993 / 82.798 |
| 0.90 → 0.90 | independent | 10 | 0.968206 / 166.705 | 0.968206 / 166.705 |
| 0.90 → 0.90 | independent | 20 | 0.965800 / 175.717 | 0.968206 / 166.705 |
| 0.90 → 0.90 | independent | 50 | 0.961564 / 195.756 | 0.968206 / 166.705 |
| 0.90 → 0.90 | intermediate | 10 | 0.999704 / 116.049 | 0.999704 / 116.049 |
| 0.90 → 0.90 | intermediate | 20 | 0.999670 / 123.464 | 0.999704 / 116.049 |
| 0.90 → 0.90 | intermediate | 50 | 0.999607 / 140.106 | 0.999704 / 116.049 |
| 0.90 → 0.70 | independent | 10 | 0.825891 / 231.211 | 0.825891 / 231.211 |
| 0.90 → 0.70 | independent | 20 | 0.816604 / 240.189 | 0.825891 / 231.211 |
| 0.90 → 0.70 | independent | 50 | 0.799641 / 260.003 | 0.825891 / 231.211 |
| 0.90 → 0.70 | intermediate | 10 | 0.940153 / 190.447 | 0.940153 / 190.447 |
| 0.90 → 0.70 | intermediate | 20 | 0.935907 / 199.335 | 0.940153 / 190.447 |
| 0.90 → 0.70 | intermediate | 50 | 0.928468 / 218.284 | 0.940153 / 190.447 |
| 0.90 → 0.60 | independent | 10 | 0.999978 / 86.244 | 0.999978 / 86.244 |
| 0.90 → 0.60 | independent | 20 | 0.999975 / 92.625 | 0.999978 / 86.244 |
| 0.90 → 0.60 | independent | 50 | 0.999970 / 109.425 | 0.999978 / 86.244 |
| 0.90 → 0.60 | intermediate | 10 | 1.000000 / 76.384 | 1.000000 / 76.384 |
| 0.90 → 0.60 | intermediate | 20 | 1.000000 / 82.295 | 1.000000 / 76.384 |
| 0.90 → 0.60 | intermediate | 50 | 1.000000 / 97.615 | 1.000000 / 76.384 |
| 0.95 → 0.95 | independent | 10 | 0.999516 / 118.405 | 0.999516 / 118.405 |
| 0.95 → 0.95 | independent | 20 | 0.999462 / 125.863 | 0.999516 / 118.405 |
| 0.95 → 0.95 | independent | 50 | 0.999359 / 142.692 | 0.999516 / 118.405 |
| 0.95 → 0.95 | intermediate | 10 | 1.000000 / 98.899 | 1.000000 / 98.899 |
| 0.95 → 0.95 | intermediate | 20 | 1.000000 / 104.125 | 1.000000 / 98.899 |
| 0.95 → 0.95 | intermediate | 50 | 1.000000 / 119.753 | 1.000000 / 98.899 |
| 0.95 → 0.75 | independent | 10 | 0.932962 / 193.588 | 0.932962 / 193.588 |
| 0.95 → 0.75 | independent | 20 | 0.928342 / 202.522 | 0.932962 / 193.588 |
| 0.95 → 0.75 | independent | 50 | 0.920200 / 221.617 | 0.932962 / 193.588 |
| 0.95 → 0.75 | intermediate | 10 | 0.978715 / 169.615 | 0.978715 / 169.615 |
| 0.95 → 0.75 | intermediate | 20 | 0.977056 / 177.997 | 0.978715 / 169.615 |
| 0.95 → 0.75 | intermediate | 50 | 0.974217 / 195.554 | 0.978715 / 169.615 |
| 0.95 → 0.65 | independent | 10 | 1.000000 / 77.152 | 1.000000 / 77.152 |
| 0.95 → 0.65 | independent | 20 | 0.999999 / 83.046 | 1.000000 / 77.152 |
| 0.95 → 0.65 | independent | 50 | 0.999999 / 98.528 | 1.000000 / 77.152 |
| 0.95 → 0.65 | intermediate | 10 | 1.000000 / 72.377 | 1.000000 / 72.377 |
| 0.95 → 0.65 | intermediate | 20 | 1.000000 / 78.452 | 1.000000 / 72.377 |
| 0.95 → 0.65 | intermediate | 50 | 1.000000 / 92.767 | 1.000000 / 72.377 |
| 0.99 → 0.99 | independent | 10 | 1.000000 / 89.637 | 1.000000 / 89.637 |
| 0.99 → 0.99 | independent | 20 | 1.000000 / 92.672 | 1.000000 / 89.637 |
| 0.99 → 0.99 | independent | 50 | 1.000000 / 107.150 | 1.000000 / 89.637 |
| 0.99 → 0.99 | intermediate | 10 | 1.000000 / 85.858 | 1.000000 / 85.858 |
| 0.99 → 0.99 | intermediate | 20 | 1.000000 / 87.394 | 1.000000 / 85.858 |
| 0.99 → 0.99 | intermediate | 50 | 1.000000 / 102.966 | 1.000000 / 85.858 |
| 0.99 → 0.79 | independent | 10 | 0.993290 / 155.848 | 0.993290 / 155.848 |
| 0.99 → 0.79 | independent | 20 | 0.992767 / 163.305 | 0.993290 / 155.848 |
| 0.99 → 0.79 | independent | 50 | 0.991803 / 179.573 | 0.993290 / 155.848 |
| 0.99 → 0.79 | intermediate | 10 | 0.996363 / 151.079 | 0.996363 / 151.079 |
| 0.99 → 0.79 | intermediate | 20 | 0.996034 / 158.196 | 0.996363 / 151.079 |
| 0.99 → 0.79 | intermediate | 50 | 0.995496 / 173.999 | 0.996363 / 151.079 |
| 0.99 → 0.69 | independent | 10 | 1.000000 / 69.925 | 1.000000 / 69.925 |
| 0.99 → 0.69 | independent | 20 | 1.000000 / 75.984 | 1.000000 / 69.925 |
| 0.99 → 0.69 | independent | 50 | 1.000000 / 89.355 | 1.000000 / 69.925 |
| 0.99 → 0.69 | intermediate | 10 | 1.000000 / 69.073 | 1.000000 / 69.073 |
| 0.99 → 0.69 | intermediate | 20 | 1.000000 / 75.070 | 1.000000 / 69.073 |
| 0.99 → 0.69 | intermediate | 50 | 1.000000 / 88.011 | 1.000000 / 69.073 |

### Heterogeneous grid (N=20)

Baseline cells: twelve at 0.99, six at 0.80, two at 0.30. The 0.5 drop affects the first two 0.99 cells, fixed before outcomes. Equal, every-cell -0.05, and concentrated -0.5 in 10% have means 0, -0.05, -0.05: all three are no-regression/within-margin cases. PASS is the correct directional decision; INCONCLUSIVE makes no directional error. BLOCK is erroneous. Sampled unconditional laws average cells before enumeration, assuming independent uniform cell draws; these are not conditional guarantees for a hashed manifest.

**Brief defect:** four listed scenario types times two couplings define eight combinations, not twelve. A 1.0 drop in 20% of cells is impossible from every specified baseline (<1); both corresponding combinations are infeasible. Six feasible combinations are evaluated; no probabilities are clipped and no missing scenarios are invented.

| scenario | coupling | mean | balanced PASS / cost | sampled PASS / cost |
|---|---|---:|---:|---:|
| equal | independent | 0 | 0.986547 / 156.771 | 0.987396 / 148.371 |
| equal | intermediate | 0 | 0.999953 / 116.509 | 0.999952 / 109.386 |
| all-minus-005 | independent | -1/20 | 0.346583 / 342.435 | 0.364364 / 336.009 |
| all-minus-005 | intermediate | -1/20 | 0.534897 / 311.471 | 0.552252 / 303.443 |
| concentrated-minus-05 | independent | -1/20 | 0.295163 / 354.137 | 0.341903 / 339.929 |
| concentrated-minus-05 | intermediate | -1/20 | 0.479528 / 327.313 | 0.529121 / 307.499 |

## D. Floors

Floors are earliest registered complete-round looks, not promises of power for arbitrary laws. Earliest possible PASS uses all +1; earliest BLOCK uses all -1. All-zero PASS is a useful low-noise feasibility diagnostic.

| N | whole rounds | actual cap | all-zero PASS | earliest possible PASS | earliest BLOCK |
|---:|---:|---:|---:|---:|---:|
| 5 | 80 | 400 | 80 | 10 | 15 |
| 10 | 40 | 400 | 80 | 10 | 20 |
| 20 | 20 | 400 | 80 | 20 | 20 |
| 50 | 8 | 400 | 100 | 50 | 50 |
| 100 | 4 | 400 | 100 | 100 | 100 |
| 150 | 2 | 300 | 150 | 150 | 150 |
| 300 | 1 | 300 | 300 | 300 | 300 |

Every listed N can reach both a verdict and an all-zero PASS under 400 pairs. N=150 and 300 have only 300 usable pairs; every other listed N uses 400. N>400 admits no whole round and hence no protected look. Within 1<=N<=400 no size is excluded by the all-zero floor: for N<79 its rounded-up floor is <=156, and for N>=79 the first round suffices. This is attainability, not a power guarantee.

## E. Mid-round counterexample

Nine deterministic +1 cells, then eleven deterministic -1 cells, have suite mean -0.1. Pairwise looks stop with PASS at pair 9 with exact probability 1. Twenty complete rounds remain INCONCLUSIVE with exact probability 1. A terminal partial round ending after the ninth cell is equally unprotected.

Exact PASS wealth at pair 8: `151874368379777/5642219814912`; at pair 9: `316547748620285/7522959753216`. Threshold: 40. See `PROOF.md` for the line-by-line proof and assumptions.

## Conclusions

(1) Balanced controls each directional error at 1/40=2.5% conditional on every frozen manifest satisfying independent cell/round differences and stationary laws. The largest A error is 1.247230%; the largest searched error is 1.595637%. This is a theorem under assumptions, not empirical provider validation. Sampled conditional errors reach 100.000000% in B; mid-round balanced looks reach 100%.

(2) Against sampled on the 36 homogeneous cases, N=10: mean probability change +0.000000 (range +0.000000 to +0.000000), mean cost change +0.000 pairs (range +0.000 to +0.000); N=20: mean probability change -0.004441 (range -0.017813 to +0.000000), mean cost change +7.520 pairs (range +1.536 to +10.114); N=50: mean probability change -0.012222 (range -0.049406 to +0.000000), mean cost change +24.913 pairs (range +17.108 to +30.458). Differences come from checkpoint spacing. Heterogeneous comparisons additionally remove cell-allocation randomness; their six exact rows appear above.

(3) All seven requested sizes (5,10,20,50,100,150,300) can decide within 400 pairs. Their whole-round counts are 80,40,20,8,4,2,1; N=150 and 300 use only 300 pairs. N>400 cannot yield a complete round. A large grid can meet a best-case floor yet have weak power; floors alone do not promise utility.

(4) Recommend balanced only for the claimed conditional-per-manifest guarantee, with N<=400 and round-end checks enforced. For N>400, require a larger preregistered budget or an explicitly narrower grid. Sampled is not an equivalent fallback: B has errors above 2.5% for fixed schedules, and deterministic hashing does not prove honest randomization. An unconditional sampled research option would require a separately stated randomization contract, not the balanced guarantee.

## Verification and limits

The adversarial search covers two restricted rational-law families, not every configuration; the analytic proof supplies the general result. Within-pair dependence is unrestricted but across-cell or across-round dependence is not. No runtime integration, network, dependency installation, or git mutation was performed. All source and artifact writes stay in s1c.
- pytest: exit 0; `12 passed (elapsed excluded)`
- ruff_format: exit 0; `8 files already formatted`
- ruff_check: exit 0; `All checks passed!`
- basedpyright: exit 0; `0 errors, 0 warnings, 0 notes`
- frozen: exit 0; `uv.lock: OK`

Regenerate and independently repeat: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=plan/exec/v2/spikes/s1:plan/exec/v2/spikes/s1b:plan/exec/v2/spikes/s1c .venv/bin/python plan/exec/v2/spikes/s1c/run_all.py --verify-repeat`. All computation reruns; elapsed time is written only to `elapsed.txt`.
