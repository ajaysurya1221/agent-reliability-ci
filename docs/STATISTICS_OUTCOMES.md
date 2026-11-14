# The imported-outcomes contract (arci-outcomes/1)

This document specifies `arci verdict`, which decides a baseline against a candidate from pass/fail
results produced by another tool. It extends [STATISTICS_SUITE.md](STATISTICS_SUITE.md) and does not
restate its proof; every term below is that document's term and its section names are cited rather
than quoted. The design record is
[docs/design/0015-imported-outcomes.md](design/0015-imported-outcomes.md). ARCI runs nothing here:
it reads labels another tool wrote, checks input structure and registered task and round coverage,
and applies one rule.

The bound requires that the rule and its task list were in fact fixed before either evaluated arm
ran. The rule declares that in a required boolean `fixed_before_runs`, which ARCI never verifies.
When it is false the rule was written after the outcomes existed: the verdict and the exit code are
computed in exactly the same way, but the bound is not claimed, the output is labelled a descriptive
verdict and the two crossing reasons render as threshold crossings. `arci verdict-rule` always
writes `false`; an author who registered the rule first edits it.

## Estimand and mapping to the suite contract

A cell is a registered task id; there are N of them. A round is one complete pass of every
registered task by both arms. For task c let Y_A and Y_B be the pass/fail labels the producing tool
would record without an infrastructure error, and Delta_c = E[Y_B - Y_A]. The estimand is

    Delta = (1/N) sum_c Delta_c,

the unweighted mean over the registered task list: the estimand of "Estimand and registered
experiment" with the (task, condition) grid replaced by a flat list. A user who has conditions puts
them in the id, which only makes more cells. The pair difference D = Y_B - Y_A is in {-1, 0, +1} and
E[D] = Delta_c whatever the dependence inside the pair.

The rule is unchanged: the two one-sided betting wealths, the stake mixture, the threshold 2/alpha,
exact rational arithmetic and the inclusive crossing of "Wealth and decision rule"; that section's
round-end priority and exit codes; the supermartingale, mixture and Ville steps of "Proof at round
ends"; the scoring in "Errored pairs and hard invariants". Defaults are alpha = 1/20, delta = 1/10,
stakes {1/4, 1/2}, max_rounds = ceil(400/N), max_errored_pairs = ceil(N * max_rounds / 100).

Three things differ from a suite, and only these.

- There is no contract and no hard invariant, so the round-end ladder has no hard-violation step.
  Every BLOCK here is a statistical BLOCK and the false-BLOCK statement covers all of it.
- Y_A and Y_B are the other tool's labels, not ARCI's contract grading. The proof holds for
  suitably independent, stationary labels even when the arms were scored by different graders, but
  that gives no statement about the candidate's quality: a claim about the candidate needs a common
  grading criterion, which is condition (f). Without it the estimand is the difference between two
  complete evaluation pipelines, and that is how it must be described.
- There is no store, sealed trial record or `spec_sha256`.

## Fewer rounds, more rounds, one rule

Ville's inequality bounds the probability that a wealth ever reaches 2/alpha over the registered
round sequence 1 to max_rounds. Everything below follows from that one fact.

- **Fewer rounds than max_rounds.** A verdict is reported only if a crossing happened at one of the
  first k complete round ends, an event contained in the ever-crossed event, so its probability
  under the matching null is still at most alpha/2. Supplying fewer rounds cannot raise the error
  rate; it lowers power, which the table below quantifies.
- **Rounds supplied past the stop.** Inputs after the stopping round are still read, hashed and
  structurally validated, and a fault in them is ERROR, but they enter no count: every count in the
  record and in a report covers rounds 1 through the last round evaluated, and the errored-pair
  count is labelled with that round. Excluding them cannot enlarge a crossing event, so the bound
  is untouched. A round label above max_rounds is refused, not truncated.
- **Re-running with more rounds.** Importing rounds k+1 to k' later, under the same rule, continues
  the same process and looks at the same registered round ends. Those looks were already charged:
  no second alpha, no correction. Two things make it the same process, the same rule digest and the
  same outcomes in round positions 1 to k. The rule digest covers the rule, not the inputs, so the
  decision records a digest of every supplied round's outcomes under a recorded normalisation
  version, and `--previous DECISION.json` refuses a call whose earlier rounds differ, whose
  predecessor is unusable, or whose normalisation version differs. It is a consistency check on one
  file the user supplies: it does not establish that any run happened, that the rule preceded the
  data, that the predecessor is authentic, or that no other campaign was run and discarded, and
  without it nothing binds the earlier rounds.
- **A changed rule is a new registration.** Widening the margin, adding tasks or raising the cap
  after an INCONCLUSIVE does not extend this experiment. Such a rule needs fresh runs of both arms
  to carry the bound; applied to the outcomes already in hand it is a descriptive analysis and must
  declare itself one.
- **Re-pairing or re-ordering after the fact breaks it.** The proof conditions on a registered
  pairing and a registered round order. Choosing which baseline file pairs with which candidate
  file, or which repetition is round 1, after seeing the outcomes makes the look sequence a function
  of the data, and the bound covers one fixed sequence, not a choice among many. "Why a complete
  round matters" gives the extreme: with suite mean -1/10, nine +1 pairs then eleven -1 pairs reach
  a PASS wealth above 40 after nine pairs, so a look placed there passes with probability 1.
  Re-ordering hands an analyst that freedom at round granularity; dropping a round does too.

The arithmetic is not a comparison of totals, which is the other reason a pairing cannot be
shuffled. At stake 1/2 and delta = 1/10 the PASS factor 1 + q (d + delta) / (1 - delta) is 1/2 at
d = -1, 19/18 at d = 0 and 29/18 at d = +1. After two pairs, one loss and one win give
(1/2)(29/18) = 29/36, below 1; two ties give (19/18)^2 = 361/324, above 1. The ratio is 261/361,
about 0.723: the lost pair costs more than the won pair returns. Two won pairs give
(29/18)^2 = 841/324, so ties are not the fastest route to PASS either. These are one stake's
component; the reported wealth is the mean of the two whole products.

    .venv/bin/python - <<'PY'
    from fractions import Fraction as F
    from arci.suite_stats import SuiteRule, wealth
    one = SuiteRule(F(1, 20), F(1, 10), (F(1, 2),), 1, 400, 0)
    print([1 + F(1, 2) * (d + F(1, 10)) / (1 - F(1, 10)) for d in (-1, 0, 1)])
    r = wealth(1, 0, 1, one)[0] / wealth(0, 2, 0, one)[0]
    print(wealth(1, 0, 1, one)[0], wealth(0, 2, 0, one)[0], wealth(0, 0, 2, one)[0],
          r, f"{float(r):.3f}")
    PY

A crossing is read only at a complete round end, so the arithmetic threshold and the next permitted
look are different numbers: with 50 tasks, eight registered rounds and 50 observed ties, 29 further
ties cross arithmetically but the next permitted look is one more complete round of 50 pairs. The
report states the look, and the snippet for it is in ADR 0015, Decision item 10.

## The six conditions ARCI cannot check

The bound holds under the assumptions of "Assumptions and their failure modes" and these six
conditions, which every report prints. ARCI checks the rule, the structure of every input, the task
ids against the rule, and that both arms cover rounds 1 to k; it verifies none of the following.

- **(a) The rule and its task list were in fact fixed before either evaluated arm ran.** The author
  declares this with `fixed_before_runs: true` and ARCI does not verify it; a false declaration
  leaves no trace in any record. Fails when a user extracts the task list from existing result
  files, sees INCONCLUSIVE, widens the margin and re-runs.
- **(b) Outcomes are independent across tasks and rounds, with no response cache shared across
  pairs or rounds.** Fails when the producing tool caches model responses, which several do by
  default: three repetitions are then one response copied three times. A seed or cache shared by
  the two arms *within* one pair is permitted, since the proof puts no restriction on within-pair
  dependence; reuse across pairs or rounds is not covered.
- **(c) Each task behaves the same in every round.** Fails when the candidate's hosted model is
  swapped or silently upgraded between two imports, or when a model grader is re-prompted with a
  changed template. Rounds produced on different calendar days are not by themselves a failure: the
  condition is about the law, not the clock.
- **(d) Pairing and logical round order were fixed before outcomes were observed, and no registered
  round was omitted or replaced.** A logical order fixed in advance is enough, so epochs that ran
  concurrently are fine. Fails when a user drops the round the candidate did badly in, re-runs it
  and supplies the better copy, or sorts the files by name so round 10 precedes round 2.
- **(e) Infrastructure failures are labelled `error`, not `fail`.** The direction of the damage
  depends on the arm. A candidate timeout recorded as a failure favours BLOCK; a baseline timeout
  recorded as a failure favours PASS. Labelled `error`, the pair counts against both tests, which
  delays a verdict and, past max_errored_pairs, ends in ERROR.
- **(f) The protocol was fixed before execution and both arms were graded by the same criterion.**
  The protocol is both arm identities, the task inputs and targets, the grading procedure and its
  version, any numeric threshold, the retry policy, and the pairing and repetition schedule. Fixed
  internal transport retries are part of it; replacing a completed failed or errored sample with a
  successful re-run is not, and is a failure of (d) as well. Matching task ids do not establish
  matching inputs or targets. Fails when the arms were scored by different scorers or different
  rubric versions: the verdict is then about the two pipelines, not about the candidate.

## Errored pairs, and why missing means errored

A pair is errored when either arm's outcome is `error`, or when the outcome is absent from a
supplied round. Through max_errored_pairs it is scored against each test separately: -1 in the PASS
wealth, +1 in the BLOCK wealth. "Errored pairs and hard invariants" gives the argument. Every PASS
factor increases with d, every BLOCK factor decreases with d, and all factors are positive, so each
replacement yields the smallest product of any completion of the unobserved outcome. Each scored
crossing is pathwise contained in the crossing the complete outcomes would have produced, so both
bounds carry over, including when the missingness depends on the outcome.

Treating a missing outcome as errored is therefore conservative for PASS and BLOCK at once, and the
alternatives are not. Dropping the pair shortens the round and destroys the complete-round look the
AM-GM step needs; recording it as an observed tie invents a 0 that raises the PASS wealth; imputing
or averaging invents an outcome. The tolerance is an inference-time rule, checked at each complete
round end to the stopping round and nowhere else. Beyond it the verdict is ERROR, ahead of
everything else, and a re-import after ERROR is a new campaign outside this bound.

## Operating characteristics

Model projections, not measurements: cells independent and identical across rounds, no errors,
baseline pass rate 9/10, and per cell minus = pb(1 - pc), plus = (1 - pb)pc, zero the rest.
Defaults for alpha, delta and the stakes; max_rounds as the row says; max_errored_pairs at its
default and unused.

| Tasks | Rounds | PASS when the candidate is also 9/10 | BLOCK when the candidate is 7/10 |
|---:|---:|---:|---:|
| 50 | 1 | 0.040 | 0.022 |
| 50 | 3 | 0.504 | 0.292 |
| 50 | 8 | 0.962 | 0.800 |
| 100 | 1 | 0.263 | 0.138 |
| 200 | 2 | 0.954 | 0.767 |

A 50-pair look catches a 20-point drop with probability 0.022, and eight rounds of the same 50 tasks
catch it with probability 0.800. A truthful candidate is likewise only confirmed once enough rounds
arrive, 0.040 against 0.962. Both readings are about how much evidence 50 pairs carry, not about any
one rule being unsound: a valid one-round registration is an ordinary fixed-sample test.

The 50 by 1 row is a hypothetical 50-pair look rather than a rule that can be registered. With every
pair tied, PASS first crosses after 79 pairs (`never_differs_pass_round` at the defaults), so a
50-pair budget cannot establish PASS for a candidate that never differs and `check_rule_plan`
refuses it. That look is reachable as the first look of a longer valid registration, the 50 by 8
rule for instance, and 0.040 is the probability of crossing there on pairs the candidate won; no
amount of tying crosses it. The row is kept so the 100 by 1 row can be read against it.

The snippet prints the five rows, each row's never-differs round and the 79-pair floor, in about 13
seconds, almost all of it in the 200-task row.

    .venv/bin/python - <<'PY'
    from fractions import Fraction as F
    from arci.suite_stats import (SuiteRule, operating_characteristics,
                                  default_max_errored_pairs, never_differs_pass_round)
    law = lambda pb, pc: (pb * (1 - pc), 1 - pb * (1 - pc) - (1 - pb) * pc, (1 - pb) * pc)
    rule = lambda n, r: SuiteRule(F(1, 20), F(1, 10), (F(1, 4), F(1, 2)), n, r,
                                  default_max_errored_pairs(n, r))
    pb = F(9, 10)
    for n, r in ((50, 1), (50, 3), (50, 8), (100, 1), (200, 2)):
        ru = rule(n, r)
        p = operating_characteristics([law(pb, F(9, 10))] * n, ru).p_pass
        b = operating_characteristics([law(pb, F(7, 10))] * n, ru).p_block
        print(n, r, f"{float(p):.3f}", f"{float(b):.3f}", never_differs_pass_round(ru))
    print("never-differs pairs:", never_differs_pass_round(rule(1, 400)))
    PY

## What this rule is not for

A fixed-sample procedure designed for the same non-inferiority estimand and the same directional
error budget may offer greater power than this rule at the same alpha. This document does not
establish such a comparison, and nothing here establishes that either rule dominates the other over
the heterogeneous per-task laws this estimand allows. McNemar's exact test is not that comparison:
it tests equality of the paired marginal probabilities, not non-inferiority within a registered
margin, and its two-sided alpha is not this rule's directional alpha/2 budget.

This rule is for the sequential case: one rule fixed before either arm runs, a verdict at the end
of every registered round, and the same protection when three rounds are imported today and five
more next week. A reader who will only ever take one verdict from one fixed sample is paying, in
power, for looks they do not use.

## Permitted claims

A release, report or post may state: PASS means the candidate is not worse by the margin or more;
for a rule declaring `fixed_before_runs: true`, under conditions (a) to (f) above and the
assumptions of [STATISTICS_SUITE.md](STATISTICS_SUITE.md), at the default alpha each directional
error of the verdict is at most 2.5%; the whole rule is one file, and a well-formed rule's digest
appears in every output of that call; INCONCLUSIVE preserves uncertainty. Only the rule digest and
each round's outcome digest are the same on every machine for the same rule and the same normalised
outcomes; the decision seal also covers the input file hashes and the paths as given, so it is
machine-specific by design. A verdict from a rule declaring `fixed_before_runs: false` may be shown
only with its descriptive label and never beside the bound. Say for every number whether it is a
proved bound, a finite check or a model projection; the table above is a model projection.

It must not state: that an improvement is real or measured, since the rule is one-sided for
non-inferiority; that ARCI ran, tested or executed anything on this path; that a descriptive verdict
carries the error bound; a per-task conclusion from a PASS, which concerns the mean over the
registered tasks and can hide one bad task; reliability on tasks outside the registered list; that
`fixed_before_runs: true`, or any digest, shows the rule preceded the data; that identical outcome
digests show the same trials produced them; that seals authenticate execution; that replacing
rounds, or writing a new rule after an INCONCLUSIVE, until PASS appears is inside the bound. Adding
further registered rounds under the same rule is inside it. Everything "Permitted release claims"
forbids in the suite document remains forbidden.
