# Outcome of the block-selection rule (private working note)

Written 2026-11-19T06:54:03Z (UTC), after the SPEC_E results were read.
Rule file: ARCI_Registration_Block_Rule_2026-11-19.md, sha256
333b51169511b7ea42100a29d3283e6e8c98a960e83ccf5af07f2897389d9ea3 (unchanged).

Applied to the reviewer's own run (drift scaled as SPEC_E words it; implementer A agrees;
implementer B's drift was about a fifth as strong and is not used for the decision):

| null | P (repository) | PM (repository x month) | bar 0.065 |
|---|---|---|---|
| E1 shared drift, share 0.3 | 0.099 | 0.077 | both fail |
| E1s shared drift, share 0.6 | 0.240 | 0.189 | both fail |
| E2 shared month levels | 0.109 | 0.051 | P fails |
| E3 two break dates | 0.063 | 0.052 | both pass (E3 as coded carries a small positive offset) |
| E4 drift plus AR(1) 0.6 | 0.085 | 0.066 | both fail (PM at the bar) |
| E0, E6, E7, E8 | 0.045 to 0.061 | 0.048 to 0.064 | both pass |

Rule 3 (PM passes every applicable null): no. Rule 4 (P passes every one): no.
**Rule 5 applies: register a description only. No p-value decides a sentence.**

Facts beside the outcome, not used to change it:
- The published pair (primary and gate, same sign) stayed low: PM and JMR 0.012 to 0.033 on
  every null except the strongest drift (0.062 to 0.070).
- At the drift strength that matches the first round's D8, PM read 0.062 and P 0.073.
- A link carried only by session length passed the gate in 0.12 to 0.25 of runs, the highest
  false "shown" rate of any case. The signal's denominator is the length.
- Per-repository signs repair the gate's own level (0.084 to 0.050 at AR(1) 0.6; 0.179 to 0.056
  under long constant runs) but the gate then cannot be formed in about 0.43 of long-run cases.

My view: the rule's outcome is also the better design. A "shown" verdict could not tell a
direct link from one carried by session length, and anything else would read "cannot tell".
The same numbers, printed as a description with the simulated yardsticks, say as much and
claim less. Astra's stated position before the results: failed calibration triggers the fixed
descriptive fallback.

## Correction, 2026-11-19T07:10:39Z (UTC)

The table above quotes the reviewer's rates at 2,000 data sets. The rule fixes 1,000. At the
reviewer's first 1,000 data sets: P 0.107 / 0.234 / 0.119 / 0.076 and PM 0.083 / 0.191 /
0.063 / 0.065 on E1 / E1s / E2 / E4. So at the rule's own count PM passes E2 and E4 ("at most
0.065") and fails E1 and E1s; P fails all four. The Monte Carlo standard error near these
rates is about 0.007 to 0.012. The outcome is unchanged: both candidates fail E1 and E1s by
far more than that error. Also: under implementer B's weaker drift only the month-blocked test
held everywhere (largest 0.061); the repository-blocked test still read 0.087 at shared month
levels.
