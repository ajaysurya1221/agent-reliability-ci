# The suite gate's statistical contract (arci-suite/1)

This document specifies `arci.suite_gate.decide_suite`. It is separate from the
`arci/0.5` gate specified by [STATISTICS.md](STATISTICS.md); that gate, its records,
intervals and guarantees are unchanged. A suite is a new experiment kind, not an
instruction to pool the trials of several v1 experiments.

## Estimand and registered experiment

Freeze tasks, fault conditions, both arm identities, the oracle, fixtures, budgets
and the entire decision rule before observing outcomes. Cells are the full grid
of (task, condition), sorted by task id then condition id. There are N cells.
A round runs each cell exactly once, with one baseline trial A and one candidate
trial B per cell. Define each pair's true, complete binary outcomes Y_A and Y_B
as the PASS/FAIL outcomes that independent contract grading (oracle and hard
invariants) would produce without a harness or grader error. These outcomes exist even when an infrastructure error prevents
observation; they are not conditional on the pair being observed without error.

For cell c let Delta_c = E[Y_B - Y_A]. The estimand is

    Delta = (1/N) sum_c Delta_c.

This is the unweighted mean for this registered grid. Cells may have very
different laws; no identical-distribution assumption across cells is made.
A PASS concerns this mean and can hide a regression in a particular cell.
Per-cell counts are descriptive and never supply another statistical verdict.
Neither the grid nor its weights may be selected after looking at results.

For every pair its complete-outcome difference D = Y_B - Y_A is in {-1, 0, +1}.
Linearity gives E[D] = Delta_c regardless of dependence within the pair.
On non-errored pairs the gate observes d = [B PASS] - [A PASS]. A pair with
either arm ERROR is scored against each test separately, as specified below;
it is not dropped or counted as an observed zero. Outcome-dependent errors can
make E[D | non-errored] differ from Delta_c; that conditional mean is not the estimand.
The registered budget is N times max_rounds pairs; every pair runs two trials.
All looks are at the ends of complete balanced rounds. A trailing partial
round is not a statistical look.

Defaults are alpha = 1/20, delta = 1/10, the stake set {1/4, 1/2}, and
max_rounds = ceil(400/N). The manifest holds explicit max_rounds and
max_errored_pairs, not a request to infer them after execution. The default
error tolerance is ceil(N * max_rounds / 100). It may be set to zero.

## Wealth and decision rule

For each registered stake 0 < q < 1 set lambda_q = q/(1-delta) and
mu_q = q/(1+delta). Through a complete round, for every pair observed so far:

    P_q = product_i [1 + lambda_q (d_i + delta)]
    B_q = product_i [1 - mu_q (d_i + delta)]
    W_PASS  = (1/Q) sum_q P_q
    W_BLOCK = (1/Q) sum_q B_q
    threshold = 2/alpha.

Each process starts at 1. The mixture averages whole products, not individual
pair factors. For cumulative counts (m,z,p), a product is the -1 factor to power
m times the 0 factor to power z times the +1 factor to power p. The kernel uses
integer powers for standalone wealth queries. The gate instead carries one
integer product per stake and direction forward from round to round, with a
shared denominator in each direction. It never recomputes cumulative wealth
from scratch at each look.

A crossing is inclusive: wealth >= 2/alpha. Counts, wealth and all comparisons
that decide use integers or exact rational arithmetic. The six-significant-digit
scientific-notation wealth strings in decisions are truncated displays only.
Neither a displayed value nor a float decides a crossing. The ordinary v1
TrialSpec alpha/delta fields are compatibility mirrors; the suite rule comes
from the SuiteManifest's exact rational strings.

At each complete round end the priority is:

1. More errored pairs than max_errored_pairs: ERROR, reason
   `errored pairs exceed max_errored_pairs`.
2. Any candidate hard-severity contract violation: BLOCK, reason
   `candidate hard violation`. Count violation entries, including entries on
   errored candidate trials; a missing contract result contributes zero.
3. Both wealths crossed: ERROR, reason `both tests crossed`. This defensive
   check detects an impossible state under the specified arithmetic.
4. PASS crossed: PASS, reason `non-inferiority established`. Otherwise, BLOCK
   crossed: BLOCK, reason `regression established`.
5. Neither crossed: INCONCLUSIVE, reason `no test crossed`. Continue unless
   this is max_rounds; then stop INCONCLUSIVE without changing the boundary.

True crossing flags are recorded even when ERROR or a hard violation overrides
inference. Stop at the first non-INCONCLUSIVE round. Statistical PASS means
non-inferiority within delta; statistical BLOCK establishes a drop exceeding
delta. INCONCLUSIVE establishes neither. PASS is not absolute reliability.
Exit codes are PASS 0, BLOCK 1, INCONCLUSIVE 2, ERROR 3.

## Proof at round ends

Condition on the entire registered manifest. First suppose every pair has a
well-defined binary outcome without errors. Write x_rc = d_rc + delta, and let
F_(r-1) contain all previous complete rounds. Assume differences are jointly
independent across distinct (round, cell) pairs and each cell has the same law
across rounds. A sufficient conditional generalization is given below.

**Positivity.** Since -(1-delta) <= x_rc <= 1+delta, the PASS and BLOCK factors
are each at least 1-q > 0. Their expectations are positive too. The stake is the
same for all cells within a component; cell-specific stakes are not allowed.

**Round expectation and AM-GM.** For a PASS component's next-round multiplier,
independence within the round and from the past gives

    E[product_c (1 + lambda_q x_rc) | F_(r-1)]
      = product_c [1 + lambda_q (Delta_c + delta)]
      <= [1 + lambda_q (Delta + delta)]^N.

The inequality is arithmetic mean >= geometric mean for the N positive
expectation factors. Under the PASS null Delta <= -delta, the base is at most
1 and positive, so the round expectation is at most 1. Under the BLOCK null
Delta >= -delta the same steps give

    E[product_c (1 - mu_q x_rc) | F_(r-1)]
      = product_c [1 - mu_q (Delta_c + delta)]
      <= [1 - mu_q (Delta + delta)]^N <= 1.

No factorization across the two arms of a pair was used. Mere pairwise
independence across cells would not suffice to factor the N-factor product.

**Supermartingale and mixture.** Each component wealth at round r is its
nonnegative F_(r-1)-measurable preceding wealth times the round multiplier.
Taking conditional expectations therefore gives E[P_q(r)|F_(r-1)] <= P_q(r-1)
under the PASS null, and analogously for B_q under the BLOCK null. Thus each is
a nonnegative supermartingale starting at 1. Linearity of conditional
expectation preserves this property for the fixed equal-weight mixture.
The mixture weights and stakes cannot be chosen using observed outcomes.

**Ville's inequality, stopping and cap.** For a nonnegative supermartingale
starting at 1, Ville's inequality bounds P(sup_r W(r) >= h) by 1/h. Taking
h = 2/alpha gives

    P(ever PASS-crossed | Delta <= -delta, manifest) <= alpha/2
    P(ever BLOCK-crossed | Delta >= -delta, manifest) <= alpha/2.

A reported statistical verdict at the first stopping round is a subset of its
crossing event. Stopping when the other test crosses, or on a hard violation
or ERROR, cannot enlarge that event. Capping at max_rounds also only shrinks
it. At Delta = -delta both nulls hold: each directional error is at most
alpha/2 and their union at most alpha. These are repeated-experiment outcome
probabilities, not posterior probabilities that a hypothesis is true.
There is no separate alpha charge for each additional registered round.

**Why both cannot cross.** For any realized nonempty sequence let S = sum_i x_i
and n be its length. Applying AM-GM to its positive PASS factors yields
P_q <= (1 + lambda_q S/n)^n. If S <= 0 every PASS component is at most 1,
so its mixture is at most 1. Hence PASS crossing requires S > 0, because
2/alpha >= 4. The analogous BLOCK inequality says BLOCK crossing requires
S < 0. Both cannot occur on the same sequence. At n=0 both wealths are 1.
This argument works for every allowed stake set, not only the defaults.

**Why a complete round matters.** The AM-GM step uses the mean over all cells.
With 20 deterministic cells, nine +1 followed by eleven -1 have suite mean
-1/10. At defaults, after nine pairs the PASS wealth is
((47/36)^9 + (29/18)^9)/2 >= 40. A look there would falsely PASS with
probability 1. At whole-round ends both component round multipliers are less
than 1. Ending execution at a partial round supplies no protected verdict.

The wealth construction is referenced to Waudby-Smith and Ramdas,
[arXiv:2010.09686v7](https://arxiv.org/abs/2010.09686v7), section 2.2
(Theorem 1) and section 4 (equation 23). The balanced-round AM-GM argument and
the fixed-mixture step above are this project's own derivations. This document
writes out the complete argument rather than relying on a separate proof file.

## Assumptions and their failure modes

- **Joint independence across cells within each round and across rounds.**
  Trials must start in fresh processes from reset state. Reusing a previous
  model response in a later round, shared mutable state, or a shared provider
  incident can violate independence. Process isolation alone does not prove
  provider independence. Detectable cross-round response reuse must be refused;
  detecting every hidden dependency is not a capability of this gate.
- **The same null in every round.** Stationary per-cell laws suffice. Model
  updates, provider drift, changing conditions or scenario selection may break
  this premise. Arm order is chosen afresh by the round hash and can flip between
  rounds in both seed modes. An effect of executing first or second therefore
  breaks the same-law-every-round assumption even with fixed seeds. Assume no
  order effect, or establish the per-round conditional null below; an
  order-averaged or pooled mean over rounds does not replace it.
- **Every cell exactly once in each look.** Omissions, unequal repetitions,
  weights, outcome-dependent cell selection or mid-round looks invalidate the
  stated AM-GM step. The gate checks the balanced prefix of the sealed schedule.
- **Within-pair dependence is unrestricted.** Shared seeds, positive coupling,
  negative coupling and identical paired outcomes are allowed. This permission
  does not extend across different cells or rounds.
- **Common-mode failures have no allowance in the proof.** A provider outage,
  rate limit or endpoint failure affecting one arm across many cells correlates
  that round's outcomes. Running the two arms adjacently and recording genuine
  infrastructure errors reduce exposure but cannot establish independence.
  A round is also an interval of wall-clock time. Remaining common-mode effects
  are a limit of the guarantee, not covered by its nominal error budget.
  In the extreme model from ADR 0011 item 6, with 20 cells and 20 rounds at
  defaults and P(D=-1)=1/10, P(D=0)=9/10, false PASS increases from 0.9034%
  with independent cells to 67.2777% when every cell in a round shares one
  outcome. This is an illustrative dependence model, not a typical inflation
  rate. The tracked source and exact recomputation are
  [`report_common_mode`](../bench/selfcheck_suite.py); the corresponding
  false BLOCK probabilities are 0.4849% and 31.8217%.

For nonstationary conditional laws it is sufficient that, conditional on
F_(r-1), the cell differences in round r are jointly independent and the
conditional suite mean Delta_r obeys Delta_r <= -delta for every round for the
PASS bound, or Delta_r >= -delta for every round for the BLOCK bound. The same
conditional factorization and AM-GM argument then applies verbatim. Neither
this condition nor stationarity is empirically certified by the kernel.

## Scenario seeds

`fixed`, the default, derives one seed per cell from the registered rule digest
and keeps it across rounds. Both arms share that seed. It feeds environment,
fault and agent randomness; round-to-round variation must come from other
outcome randomness, such as live inference. A deterministic agent using only
that seed repeats its result. The claim is for the registered scenarios over
outcome randomness. Fixing seeds removes seed changes as a cause of changing
laws, but does not stop a live provider from drifting or remove an execution-order
effect. The seed also changes when any content bound into the rule digest changes;
"fixed" means fixed across rounds of this experiment.

`per_round` derives a seed for each (round, cell). This is useful for offline
fixtures. **Its error guarantee requires that in every round the suite mean
over that round's scenario instances obey the relevant null**, with the
independence conditions above (or their conditional form). ARCI does not check
or enforce this premise. There is no guarantee averaged over seeds: a
deterministic hash of registered content is not a sampling distribution.
A report stating a guarantee for this mode must include the per-round condition
in the same sentence.

Both modes use the sealed sha256-v1 derivation, 53-bit seeds shared by paired
arms, and distinct seeds for distinct cells in each round. A collision is
refused. Cell order is canonical. A separate hash uses the actual round to
choose which arm executes first; execution must keep the two arms adjacent in
one worker slot. This execution requirement is distinct from the gate's
order-independent validation of supplied envelopes. Because the actual round
is hashed, the arm order can flip across rounds even in fixed mode. If execution
order affects success, stationarity fails and the per-round null condition above
is required for the statistical guarantee.

## Errored pairs and hard invariants

Never drop, zero-score or retry an errored pair inside the experiment. Through
the registered tolerance, score each against the particular test: replace its
difference by -1 in PASS wealth and by +1 in BLOCK wealth. Thus for counts
(m,z,p,e), compute PASS from (m+e,z,p) and BLOCK from (m,z,p+e).

Each PASS factor increases with d, and each BLOCK factor decreases with d.
All factors are positive, so these replacements lower each component product
and its mixture relative to every possible completion of the missing outcomes.
Pathwise, each scored crossing is therefore a subset of the corresponding
unobserved complete-outcome crossing. This remains true for outcome-dependent
missingness. It requires an underlying outcome process satisfying the proof's
assumptions; arbitrary correlated observed failures are not repaired by calling
other pairs errors. The scored process need not itself be proved a
supermartingale: pathwise domination supplies both crossing bounds.

For mutual exclusion with errors, the PASS-scored sum S_P is no greater than
the BLOCK-scored sum S_B. PASS crossing requires S_P > 0; BLOCK crossing
requires S_B < 0. They still cannot both cross. Exceeding the error tolerance
ends ERROR, ahead of all other verdicts. A new run after ERROR is a new campaign
outside this bound; listing its predecessor in prior_runs does not reset alpha.

The infrastructure policy distinguishes exhausted connection/timeout retries
and HTTP 429/5xx in ARCI's model-call wrapper from agent failure. Injected
faults, tool failures, parsing failures and budget exhaustion are not
infrastructure errors. A persistent boundary latch must survive an agent's
catching the wrapper exception. Without that wrapper a provider failure can
be an agent FAIL. The decision kernel consumes sealed outcomes; it does not
establish that a producer classified infrastructure failures correctly.

Any candidate hard invariant violation causes BLOCK unless error tolerance
was exceeded. **The false-BLOCK bound covers statistical BLOCK only**, not a
BLOCK imposed by this independent contract rule. Reports must show the reason.
A baseline hard violation does not impose the candidate override. Per-cell
success totals count actual PASS outcomes even when the partner errored; each
pair still occupies exactly one of minus, zero, plus or errored.

## Validation, limits and record integrity

Before execution, structural validation requires unique task and condition ids;
nonempty grids; no ceiling faults or decision perturbations; compatible Python
arms and toolset, or command arms and MCP server; canonical positive rational
strings in lowest terms with at most seven digits in each part;
1/1000000 <= alpha <= 1/2; 0 < delta < 1; and one to
eight strictly increasing stakes in (0,1). At least one round is required,
N * max_rounds <= 100000, and error tolerance is between zero and registered
pairs. Acknowledgement is true if and only if max_rounds is one. The manifest's
experiment_id must have the shape SuiteId@ followed by 64 lowercase hex digits;
the gate additionally requires its exact recomputed value.

The statistical plan additionally refuses a budget where a never-differing
candidate cannot cross by the cap, or where PASS is unreachable after using
all the error tolerance even if every other pair is +1. It warns exactly
`max_rounds below 3: few looks` for fewer than three rounds. A single round is
a fixed-sample test with no early stopping, not multiple looks disguised as one.
At defaults, the all-zero stream first crosses after 79 pairs; the earliest
all-+1 PASS is 9 pairs and earliest all--1 BLOCK is 13 pairs. Only the next
complete round end can decide. For 20 cells these are respectively rounds
4, 1 and 1; for 10 cells, rounds 8, 1 and 2. These are distinct floors: a
candidate winning pairs can PASS before the never-differs floor.

The rule digest binds all manifest content except the generated experiment id,
seal and volatile created_at, after canonical sorting of tasks and conditions.
The derived experiment id is in each ordinary TrialSpec and hence its
spec_sha256. Changing a rule and resealing the manifest cannot make old trial
identities match the new schedule. Integrity seals are not authentication.

The gate rebuilds supplied records with Pydantic before reading outcomes, and
requires canonical JSON, including finite numbers and UTF-8 encodable text.
Supplied trial seals must already be strings; a bytes seal is rejected before
coercion. Rebuild dumps suppress serialization warnings even for wrong-typed
records. Round digests cover that round alone, while the decision-level digest
covers all supplied trials.
It checks, in order: manifest values, manifest seal, derived experiment id,
plan feasibility, trial values, scheduled identities, trial seals, and a
nonempty exact prefix of complete rounds. All failures are collected in that
order, except that bad manifest values skip all remaining checks, bad trial
values skip the last three, and a schedule mismatch skips the whole-round check.
Pre-walk failures have no history or cell table. Walked decisions keep both;
the cell table describes all supplied trials even when some followed a stop.

Stored trials after the first decisive or ERROR round, or an inconclusive
stop before the cap, yield ERROR. Every ERROR has stopped_at_round zero.
Malformed values and computation failures produce sealed ERROR records rather
than exceptions; an unsealable decision falls back to a fixed empty template.
Replay rebuilds the supplied decision too, then requires its valid seal and exact
equality with a fresh recomputation. Replayed trial specs do not match ordinary
scheduled specs.
None of these checks proves that the claimed execution happened.

## Calibration and operating characteristics

`python -m bench.selfcheck_suite` computes exact rational probabilities under
independent cell laws, repeated unchanged across rounds, with no errors or hard
violations. This is model-based enumeration, not measured live-agent behavior.
The round count polynomial is the product over cells of
p_minus*x + p_zero + p_plus*y. Convolving surviving cumulative count states with
all cells before absorption enforces whole-round looks. The implementation uses
integer coefficient packing with a base larger than total probability mass;
no coefficient carries, rounding, simulation or pruning alter probabilities.
Expected pairs sums surviving probability before each complete round times N.

The bench checks both errors at the margin and the applicable error just inside
each null, on grids 1, 2, 5, 10 and 20, at a 400-pair budget. It includes
homogeneous laws at positive/negative Frechet dependence endpoints and
independence, and strongly different per-cell laws for N > 1. Offsets are
-1/100, 0 and +1/100 from mean -delta. The equal-mean three-point family sets
P(0) freely in {0, 1/10, ..., 9/10, 1/9, 9/20}, with
P(-1)=(1-P(0)+delta)/2 and P(+1)=(1-P(0)-delta)/2. The bench prints each
maximum and its exact difference in percentage points from ADR 0011's rounded
search maxima (2.16%, 1.97%, 1.67%, 1.42%, 1.15%). The copied source row and
recomputation live in [`ADR_MARGIN_PERCENT`](../bench/selfcheck_suite.py).
These are finite search grids, not universal maxima; the proof supplies the bound.

The bench separately enumerates all 243 and 729 ordered outcome paths on tiny
grids through the validating gate, comparing each stopping round and verdict
with independently multiplied factors, plus all three aggregate verdict
probabilities and expected pairs with exact enumeration. Its asymmetric laws
expose reversed difference signs; both PASS and BLOCK occur before the cap on
multiple paths. Explicit errored-pair paths at and above tolerance, hard
violations and their priority also use independent expectations. Default rules
come from a default SuiteManifest through rule_of, so schema-default drift
cannot hide behind duplicated bench literals.

These concrete ADR 0011 operating-characteristic rows use 20 homogeneous cells,
20 rounds, and independent arms. The four complete vectors of exact fractions
are literal Table C receipts in the tracked
[`bench/selfcheck_suite.py`](../bench/selfcheck_suite.py); the two 0.95-baseline
rows also appear in [`table_c.json`](../tests/unit/suite/table_c.json).
All four components, including expected pairs, must match exactly.
Rounded values below are displays of those receipts:

| Baseline | Candidate | Statistical result probability | Expected pairs |
|---:|---:|---|---:|
| 0.95 | 0.95 | PASS 0.999462 | 125.863 |
| 0.95 | 0.75 | BLOCK 0.928342 | 202.522 |
| 0.80 | 0.80 | PASS 0.778260 | 251.494 |
| 0.50 | 0.50 | PASS 0.519844 | 306.319 |

The bench also prints report-only power and expected pairs for 50, 100, 200 and
400 cells, under the default budget, at independent rates 0.95 versus 0.95 and
0.95 versus 0.75. These projections assert no minimum power. `--quick` trims
calibration and receipts and omits these larger projections; it is not the full
calibration run. Runtime is printed. The full P1b run completed all these rows
(no skips); rounded projections are:

| Cells | Rounds | PASS at 0.95 / 0.95 | Expected pairs | BLOCK at 0.95 / 0.75 | Expected pairs |
|---:|---:|---:|---:|---:|---:|
| 50 | 8 | 0.999359 | 142.692 | 0.920200 | 221.617 |
| 100 | 4 | 0.999261 | 164.556 | 0.912509 | 247.533 |
| 200 | 2 | 0.999159 | 217.681 | 0.903825 | 291.244 |
| 400 | 1 | 0.999077 | 400.000 | 0.896481 | 400.000 |

Source: this bench's full large-grid table, exact enumeration with the stated
laws, rendered as rounded decimals. At 400 cells every path uses its only
registered round, hence expected pairs is exactly 400. Historical sampled-design
comparisons are not evidence of superiority for this balanced gate over either
v1 method.

## Permitted release claims

A release may state: at default alpha each directional error of the statistical
verdict is at most 2.5% for the registered suite in fixed mode, under the stated
independence and per-cell stationarity assumptions, including no execution-order
effect (otherwise the per-round conditional null is required); post-run rule changes are
detected as inconsistent records; and INCONCLUSIVE preserves uncertainty.
For per_round mode, include its exact per-round null condition with the claim.
State whether numbers are proved bounds, finite-grid checks or model projections.

A release must not promise fewer runs than v1 in general, a decisive first run,
a PASS for every task, reliability on tasks outside the suite, deterministic
live inference, a reset error budget on a new campaign, or authenticated
execution from integrity seals. Retrying unchanged candidates until PASS is
selection outside this experiment's guarantee. No trial execution, adoption,
provider independence or production reliability is established by this bench.
