# S1 sampling and decision contract

Scope: statistical suite-mean gate only; `alpha=1/20`, `delta=1/10` in the calibration.
Labels distinguish mathematics, finite checks, and requirements not established by this spike.

- **ASSUMED** — Freeze the task/condition grid, success oracle, arm identities, margin,
  alpha, stakes, checkpoint spacing and cap before sampling. Bind them into trial identities;
  the future gate must reject mismatches. This prototype receives differences, not sealed records.
- **ASSUMED** — Draw each cell uniformly **with replacement**, independently across pairs,
  independently of outcome randomness. Both arms receive the same cell. Freeze a schedule seed
  chosen without outcome-based selection. A deterministic PRNG derived from a manifest alone
  does **not prove** IID sampling: validity assumes a faithful randomized experiment/PRNG model
  over seed selection. Recomputing the schedule detects tampering, not cherry-picked seeds.
- **ASSUMED** — Each cell's joint binary-outcome law is stationary; fresh processes and reset
  environments must prevent carryover. Within-pair dependence is unrestricted. Independence
  across pairs and absence of provider drift are not detected by this spike or by seals.
  An oracle/harness failure is ERROR, never a dropped observation or a zero difference.
- **PROVED-BY-CITATION** — With the preceding assumptions, total probability gives
  `P(d=x)=sum_cells P(d=x|cell)/(T*K)` independently each pair. Thus d is IID trinomial and
  `E[d]=Delta`, the uniform suite mean. More generally the betting proof needs the relevant
  conditional null `E[d_i|past] <= -delta` (PASS) or `>= -delta` (BLOCK) at every step;
  an unconditional mean alone is insufficient [1, §2, bounded-mean betting model].
- **PROVED-BY-CITATION** — With `x=d+delta`, nonnegative predictable stakes in
  `[0,1/(1-delta)]` and `[0,1/(1+delta)]` make `1+lambda_plus*x` and
  `1-lambda_minus*x` nonnegative. Under their respective conditional nulls their conditional
  expectations are at most one. Wealth starts at one; products and a **fixed nonnegative
  convex mixture of products** are nonnegative supermartingales [1, §2]. Averaging stakes
  inside a product is a different procedure. The task brief's signs and caps are correct.
- **PROVED-BY-CITATION** — Ville's maximal inequality [2, named theorem] gives
  `P(sup_n W_n >= 2/alpha) <= alpha/2` per direction, including the boundary where both
  nulls hold. Checkpoints, stopping and a finite cap do not increase this bound. No alpha
  recycling, cell multiplicity correction, or correction for repeated checkpoints is needed
  for this **one** estimand. Separate campaigns are not covered by the same guarantee.
- **ASSUMED** — The future runner must consume complete pairs in schedule order, check
  every batch and the terminal partial batch, and stop at the first decisive checkpoint.
  Missing, duplicated, reordered, errored or padded stores must become ERROR. The reference
  consumes a planned stream and ignores a valid unused suffix; store validation belongs to
  the future gate. A simultaneous crossing returns ERROR. Hard-invariant BLOCK overrides
  are outside the statistical false-BLOCK claim. No runtime scheduling behavior is tested here.
- **CHECKED-BY-ENUMERATION** — Fixed-stake and fixed-mixture wealth depends only on
  `(n,n_minus,n_plus)`; absorbing DP still needs survivor mass, not just a terminal multinomial.
  Table A compares exact integer thresholds and exact rational probability mass. Exhaustive
  ordered-path tests independently check the recursion. For fixed p_zero, monotone coupling
  in Delta bounds each composite null by its boundary; finite-horizon probabilities are
  continuous. At Delta=-.10, p_zero>.90 is infeasible. The .95 row uses the feasible null edge;
  .90 has no strictly-below-boundary feasible mean and is excluded from that supremum.
- **CHECKED-BY-SIMULATION** — Table B draws actual cells and paired binary outcomes;
  reports 20,000 repetitions/point and pointwise one-sided exact-binomial 99% upper bounds.
  Inversion uses exact integer tail tests and rounds the bound upward [3, binomial-tail
  confidence-limit construction]. These checks support, but do not prove, runner assumptions.
- **CHECKED-BY-ENUMERATION** — Golden vectors compare float simulation verdicts/stops
  against the rational reference, including equality and zero wealth. Cross-platform execution
  remains untested. General adaptive wealth is path-dependent: count-only DP does **not**
  apply; the predictable adaptive comparator is simulated. Balancing without replacement,
  cycling cells, reusing state, outcome-dependent cell choice, omissions, retries until green,
  or selecting a stake after observing the current pair breaks the stated IID reduction/proof.
- **ASSUMED** — A suite-mean PASS may hide arbitrarily bad individual tasks; per-cell tables
  are descriptive. No guarantee transfers to unseen tasks, other providers or absolute reliability.

References (bibliographic citations; no network retrieval was permitted):

1. Waudby-Smith & Ramdas (2024; online 2023), *Estimating means of bounded random
   variables by betting*, JRSS B 86(1), 1–27, §2 (betting/wealth construction).
2. Ville (1939), *Étude critique de la notion de collectif*, nonnegative-martingale maximal
   inequality; its nonnegative-supermartingale form is the theorem used above.
3. Clopper & Pearson (1934), *The use of confidence or fiducial limits illustrated in the
   case of the binomial*, Biometrika 26(4), 404–413, binomial-tail confidence-limit construction.
