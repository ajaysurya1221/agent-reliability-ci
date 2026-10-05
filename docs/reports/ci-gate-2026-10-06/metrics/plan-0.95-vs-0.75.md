# ARCI plan

Baseline rate 0.95, candidate rate 0.75; alpha 0.05, delta 0.1; Clopper-Pearson, one gating condition (K=1), one look. Target: P(BLOCK) >= 0.8.

| N per arm | Total trials | P(PASS) | P(BLOCK) | P(INCONCLUSIVE) | Meets target |
|---:|---:|---:|---:|---:|---|
| 20 | 40 | 0.000 | 0.000 | 1.000 | no |
| 50 | 100 | 0.000 | 0.016 | 0.984 | no |
| 100 | 200 | 0.000 | 0.093 | 0.907 | no |
| 200 | 400 | 0.000 | 0.365 | 0.635 | no |
| 400 | 800 | 0.000 | 0.828 | 0.172 | yes |

Result: smallest tested N per arm meeting P(BLOCK) >= 0.8: 400 (800 trials in total).

Probabilities are rounded to three decimals here; `--format json` carries full precision.

Assumptions: This is planning under assumptions, not observed power: the true success rates are inputs, not measurements. Independent binomial arms: each arm is N independent trials at its stated true rate. No pairing: shared seeds or any other dependence between the arms is not modelled. Fixed sample: one look at N per arm, no early stopping and no extension. One gating condition (K=1), no trial ERROR and no candidate hard-invariant violation; either of those overrides the rates in the real gate. The gate's exact rule: two-sided Clopper-Pearson per arm with tail alpha/(4K), bounds [L_B - U_A, U_B - L_A] on the difference, PASS iff L > -delta, BLOCK iff U < -delta, otherwise INCONCLUSIVE. Probabilities enumerate every pair of success counts; they are not simulated. They need not rise monotonically with N, so only the tested N values are claimed.
