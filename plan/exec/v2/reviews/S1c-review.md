# REVIEW: S1c balanced rounds

Reviewer: orchestrator (Claude Fable 5.2), 2026-11-11. Author of the spike: Codex Astra 6.
Method: I re-ran `run_all.py` myself (exit 0, 12 tests) and diffed my outputs against copies
of Codex's that I saved first. One line differs in the whole result set: a recorded lint
message says "7 files already formatted" in Codex's copy and "8 files" in mine, because
Codex's own final report is written into the folder after its last run. Every probability,
cost and table entry is byte-identical. The same mechanism explains the S1b hash mismatch
recorded in `S1-review.md`.

Then a five-lens independent review with a separate skeptic per finding. A usage limit cut
the first run after two lenses; the re-run completed all five: 18 agents, 13 findings, none
refuted. Full outputs: `S1c-review-workflow-partial.json`, `S1c-review-workflow.json`.

## Verdict: ACCEPT balanced rounds as the v2 design, with six changes to the spike's rules

**The guarantee stands.**

- Proof: every step of the arithmetic-geometric-mean argument checks out for each stake and
  for the mixture; Ville's inequality is applied correctly at round ends; first-stop keeps
  both bounds.
- Independent numerical attack: a separately written exact evaluator agreed with the spike
  on 60 of 60 random configurations, then searched about 220,000 boundary and near-boundary
  configurations with general three-point laws on grids of 1 to 8 cells. Nothing exceeded
  2.5%. The largest error found was 2.16% at one cell.
- Enumeration code: an independent plain dynamic programme matched all 23 boundary rows, the
  six heterogeneous rows, the floors and the six search maxima as exact fractions; 300
  random differential cases gave zero mismatches. The digit-packing trick has no carries.
- Looks inside a round really are unprotected: reproduced exactly, and a second, stochastic
  example gives 39% false PASS.
- Sampled cells cannot carry a per-manifest claim: for ordinary non-degenerate laws, 8 to 16
  percent of 500 frozen schedules exceed 2.5% at every grid size from 5 to 100.

**Changes adopted into ADR 0011 draft v2**

| # | Finding | Change |
|---|---|---|
| 1 | The round-end guarantee needs every round's suite mean to obey the null. A different seed per round changes a cell's law, and the bound then holds only on average over seeds | Seed fixed per cell for the whole experiment; variation between rounds must come from the model. Listed as an open point because two reviewers split on it |
| 2 | Independence inside a round has no slack. A round-wide shared outcome takes false PASS from 0.9% to 67% at 20 cells; a 2% rate of round-wide shocks breaks the bound | The two arms of a pair run adjacently; provider and transport failures become errored pairs, not agent failures; per-round per-arm rates are reported; the rest is a stated limit |
| 3 | The cap rule "largest whole rounds under 400 pairs" halves the budget between 200 and 201 cells, and nothing above 50 cells was measured | Budget registered in rounds; default `ceil(400 / N)`; acknowledgement required for one round; `arci plan` computes exact power for the registered grid |
| 4 | The spike's "worst case 1.6%" understates it: homogeneous laws and small grids reach 1.67% to 2.16% | The design record states the largest error by grid size and says the bound is proved, not searched |
| 5 | No path for an errored pair; dropping, zero-scoring or retrying breaks the bound; void-then-rerun exceeds it | Worst-case scoring per direction up to a pre-registered maximum; kernel takes two scored streams; a trailing partial round is no look |
| 6 | Three candidate release sentences were false as worded ("cannot PASS before 80 pairs" holds only for a candidate that never differs from the baseline) | Wording corrected in the design record |

**What the spike's conclusions understated** (claims lens, confirmed): the mean power loss
is diluted by the 16 scenarios that sit above 99.9% power. Over the other 20, balanced loses
0.8 points at 20 cells and 2.2 at 50, with maxima of 1.8 and 4.9. On the heterogeneous
within-margin cases it loses up to 5.0 points. Expected log-growth is identical in the two
designs; balanced removes allocation variance, which lowers the crossing chance when power
is under 50% and raises it when over.

**Brief defect, mine:** I asked for 12 heterogeneous scenarios, defined 8, and one type was
impossible. Codex computed the six feasible rows and said so plainly. The reviewers found
that handling honest and noted the missing true-regression rows would favour balanced.

## Phase 0 gate reading for the statistics

Passed, on the plan's middle branch: a proven multi-task gate that beats the v1 default at
the same ceiling and makes no general "fewer runs" claim. The design changed during phase 0
from sampled cells to balanced rounds, on evidence.
