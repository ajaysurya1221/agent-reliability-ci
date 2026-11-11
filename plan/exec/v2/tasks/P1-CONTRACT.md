# P1 contract: the suite decision kernel

Written by the orchestrator on 2026-11-11 from ADR 0011 (`plan/exec/v2/adr-0011-draft.md`,
accepted, see `DECISIONS.md` D-02 and D-03). This file is the source of truth for names,
signatures and behaviour in phase 1. Two parties work from it without seeing each other's
output: the implementer (Codex) and the author of the acceptance tests. If this file is
wrong or silent on something you need, stop and say so; do not guess and do not work
around it.

Reference code that already passed review (read it, do not import it):
`plan/exec/v2/spikes/s1/suite_stats.py` (wealth and thresholds),
`plan/exec/v2/spikes/s1c/balanced.py` (exact enumeration),
`plan/exec/v2/spikes/s1c/PROOF.md` (the proof), `plan/exec/v2/spikes/s1c/RESULTS.md`
(exact numbers).

Nothing in v1 changes. `schema.py`, `schedule.py`, `gate.py`, `stats.py` and every existing
test stay byte-identical. Suite trials are ordinary `TrialSpec` and `TrialEnvelope` records.

## 1. Terms

- **Cell**: one (task, fault condition). The cells are the full grid, `N = T * K`, sorted by
  `(task_id, condition_id)` in Python string order. The cell index is the 0-based position
  in that order.
- **Round**: every cell once, both arms. Rounds are numbered from 1.
- **Pair**: the two trials (baseline, candidate) of one cell in one round.
- **Difference** of a pair: `d = [candidate PASS] - [baseline PASS]`, in {-1, 0, +1}, where
  PASS means `trial.outcome is Outcome.PASS`.
- **Errored pair**: either trial has `outcome is Outcome.ERROR`. It has no difference.
- **Registered pairs**: `N * max_rounds`.

## 2. `src/arci/suite_schema.py` (frozen after phase 1)

Imports only the standard library, `pydantic` and `arci.schema` / `arci.hashing`.
No statistics here.

```python
SUITE_SCHEMA_VERSION = "arci-suite/1"
SUITE_SEED_DERIVATION = "sha256-v1"
SUITE_MAX_PAIRS = 100_000

SuiteId  = Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")]
Rational = Annotated[str, Field(pattern=r"^[1-9][0-9]*/[1-9][0-9]*$")]

def parse_rational(text: str) -> Fraction: ...   # ValueError unless the whole text matches the Rational
                                                 # pattern and is in lowest terms (so no sign, space,
                                                 # leading zero, underscore or zero denominator)
def format_rational(value: Fraction) -> str: ... # "n/d", lowest terms; ValueError unless > 0

class SuiteTask(Model):
    task_id: SuiteId
    task: dict[str, JsonValue] = {}

class SuiteManifest(Sealed):
    schema_version: Literal["arci-suite/1"] = SUITE_SCHEMA_VERSION
    experiment_id: str
    created_at: str = ""                      # VOLATILE, like v1
    suite_id: SuiteId
    tasks: tuple[SuiteTask, ...]              # at least 1
    conditions: tuple[Condition, ...]         # at least 1
    toolset: AgentRef | None = None
    mcp_server: McpServerSpec | None = None
    contract: ContractSpec
    baseline: ArmSpec
    candidate: ArmSpec
    alpha: Rational = "1/20"
    delta: Rational = "1/10"
    stakes: tuple[Rational, ...] = ("1/4", "1/2")
    max_rounds: int                           # no default: an explicit sealed number
    scenario_seeds: Literal["fixed", "per_round"] = "fixed"
    max_errored_pairs: int                    # no default: an explicit sealed number
    seed_derivation: Literal["sha256-v1"] = SUITE_SEED_DERIVATION
    acknowledge_single_round: bool = False
    budgets: Budgets = Budgets()
    fixtures_sha256: str = ""
    prior_runs: tuple[str, ...] = ()

    @property
    def n_cells(self) -> int: ...             # len(tasks) * len(conditions)
    @property
    def registered_pairs(self) -> int: ...    # n_cells * max_rounds
```

Construction raises `pydantic.ValidationError` when any of these fails (structure only):

1. `task_id` values are unique; `condition_id` values are unique and match `SuiteId`.
2. No fault has `bucket is Bucket.CEILING`. No fault has a name in
   `DECISION_PERTURBATIONS` or a `tool` starting with `DECISION_TOOL_PREFIX`.
3. The v1 rule for arm kinds: both arms Python agents with `toolset` set and `mcp_server`
   unset, or both arms commands with `mcp_server` set and `toolset` unset.
4. `alpha`, `delta` and every stake are in lowest terms. `1/1000000 <= alpha <= 1/2`.
   `0 < delta < 1`. `stakes` has 1 to 8 entries, each with `0 < q < 1`, strictly increasing.
5. `max_rounds >= 1` and `n_cells * max_rounds <= SUITE_MAX_PAIRS`.
6. `0 <= max_errored_pairs <= n_cells * max_rounds`.
7. `acknowledge_single_round` is true if and only if `max_rounds == 1`.

Decision records:

```python
class SuiteCounts(Model):          # every field ge=0
    minus: int                     # non-errored pairs with d = -1
    zero: int
    plus: int
    errored: int

class SuiteRoundDecision(Model):
    round: int                     # 1-based
    pairs: int                     # cumulative: round * n_cells
    trials_sha256: str             # hash_record({"trials": sorted record_sha256 of trials in rounds 1..round})
    counts: SuiteCounts            # cumulative through this round
    candidate_hard_violations: int # cumulative, see section 5
    pass_wealth: str               # wealth_text, display only
    block_wealth: str
    pass_crossed: bool
    block_crossed: bool
    verdict: Verdict               # the verdict had the run stopped at this round end
    reasons: tuple[str, ...]

class SuiteCellStats(Model):       # descriptive only, never decides
    task_id: str
    condition_id: str
    pairs: int                     # every pair of the cell, errored ones included
    baseline_successes: int        # baseline trials with Outcome.PASS, even if the partner errored
    candidate_successes: int       # candidate trials with Outcome.PASS, even if the partner errored
    counts: SuiteCounts            # each pair in exactly one of minus / zero / plus / errored
    candidate_hard_violations: int

class SuiteDecision(Sealed):
    schema_version: Literal["arci-suite/1"] = SUITE_SCHEMA_VERSION
    experiment_id: str
    manifest_sha256: str           # manifest.record_sha256, as supplied
    trials_sha256: str             # hash_record({"trials": sorted record_sha256 of all supplied trials})
    alpha: str
    delta: str
    stakes: tuple[str, ...]
    threshold: str                 # format_rational(2 / alpha), e.g. "40/1"
    n_cells: int
    max_rounds: int
    scenario_seeds: str
    max_errored_pairs: int
    history: tuple[SuiteRoundDecision, ...] = ()
    stopped_at_round: int = 0      # the deciding round; 0 for an ERROR decision
    cells: tuple[SuiteCellStats, ...] = ()   # in cell order
    verdict: Verdict
    exit_code: int                 # EXIT_CODES[verdict]
    reasons: tuple[str, ...]
    prior_runs: tuple[str, ...] = ()
```

## 3. `src/arci/suite_schedule.py` (frozen after phase 1)

Imports only the standard library, `arci.hashing`, `arci.schema`, `arci.suite_schema`.
No `random` module anywhere in this file.

```python
def suite_cells(manifest) -> tuple[tuple[SuiteTask, Condition], ...]   # cell order
def suite_rule_sha256(manifest: SuiteManifest) -> str
def suite_experiment_id(manifest: SuiteManifest) -> str
def create_suite_manifest(**fields: Any) -> SuiteManifest
def cell_seed(rule_sha256: str, cell_index: int, round: int, scenario_seeds: str) -> int
def arm_order(rule_sha256: str, cell_index: int, round: int) -> tuple[Arm, Arm]
def suite_pair_id(round: int, task_id: str, condition_id: str) -> str
def pair_round(pair_id: str) -> int
def build_suite_round(manifest: SuiteManifest, round: int) -> tuple[TrialSpec, ...]
def build_suite_schedule(manifest: SuiteManifest) -> tuple[TrialSpec, ...]
```

- **Rule digest.** Let `payload = digest_payload(manifest)` (so `record_sha256` and
  `created_at` are already absent). Remove the key `experiment_id`. Replace `tasks` by the
  same list sorted by `task_id` and `conditions` by the same list sorted by `condition_id`.
  Then `suite_rule_sha256 = hash_record({"domain": "arci-suite/1 rule", "content": payload})`.
  Two manifests that differ only in the order of tasks or conditions, in `created_at`, in
  `experiment_id` or in `record_sha256` have the same digest. Any other difference changes it.
- **Experiment id.** `suite_experiment_id(m) = f"{m.suite_id}@{suite_rule_sha256(m)}"`.
- **`create_suite_manifest(**fields)`** builds the manifest with the right `experiment_id`
  and seals it. Passing `experiment_id` or `record_sha256` is a `TypeError`.
- **Seed.** With `key = bytes.fromhex(rule_sha256)` (32 bytes) and `r = 0` when
  `scenario_seeds == "fixed"`, else `r = round`:
  `seed = int.from_bytes(sha256(b"arci-suite/1 seed" + key + cell_index.to_bytes(4, "big") + r.to_bytes(4, "big")).digest()[:8], "big") & (2**53 - 1)`.
  53 bits, so the seed survives JSON readers that use doubles. `ValueError` for a bad key,
  a negative index, `round < 1` or an unknown mode. Both arms of a pair share the seed.
  Domains for `cell_seed` and `arm_order`: `rule_sha256` is 64 lowercase hex characters;
  `0 <= cell_index < 2**32`; `1 <= round < 2**32`. Anything else is a `ValueError`.
- **Arm order.** `bit = sha256(b"arci-suite/1 order" + key + cell_index.to_bytes(4, "big") + round.to_bytes(4, "big")).digest()[0] & 1`;
  `("baseline", "candidate")` when `bit == 0`, else `("candidate", "baseline")`. The real
  round is always used here, in both seed modes.
- **Ids.** `suite_pair_id(r, t, c) = f"r{r:06d}:{t}:{c}"`. `trial_id = f"{pair_id}:{arm}"`.
  `pair_round` accepts exactly the strings matching `^r([0-9]{6}):[^:]+:[^:]+$` whose
  number is at least 1 (the whole string, no trailing newline), returns that number, and
  raises `ValueError` for any other string.
- **`build_suite_round(manifest, round)`** returns `2 * N` specs: cells in cell order, and
  for each cell the baseline spec then the candidate spec. `ValueError` unless
  `1 <= round <= max_rounds`, and `ValueError("seed collision")` if two cells of the round
  share a seed. Each `TrialSpec` is:
  `experiment_id=manifest.experiment_id` (as stored, not recomputed), `trial_id`, `pair_id`,
  `arm`, `variant=<arm spec>.label`, `agent`, `command`, `toolset`, `mcp_server`,
  `decisions=None`, `task_id`, `task`, `condition`, `seed`, `budgets`,
  `alpha=float(Fraction(alpha))`, `delta=float(Fraction(delta))`, and the defaults for
  `interval_method`, `looks`, `tool_mode`, `recording`, `replay_final_state`. The seed is
  derived from `suite_rule_sha256(manifest)`, recomputed from content.
- **`build_suite_schedule`** is the rounds 1 to `max_rounds` concatenated.

Trial identity is `arci.schedule.spec_sha256(spec)`, unchanged.

## 4. `src/arci/suite_stats.py` (not frozen; pinned by acceptance tests)

Standard library only, plus `arci.suite_schema` for `rule_of` and `check_suite_plan`.
Every comparison that decides is exact: `Fraction` or integers. No `float`, `math.log`,
`math.sqrt` or `random` on any path that reaches a verdict.

```python
@dataclass(frozen=True)
class SuiteRule:
    alpha: Fraction
    delta: Fraction
    stakes: tuple[Fraction, ...]
    n_cells: int
    max_rounds: int
    max_errored_pairs: int = 0
    @property
    def threshold(self) -> Fraction: ...          # 2 / alpha

class SuitePlanError(ValueError): ...

def rule_of(manifest: SuiteManifest) -> SuiteRule
def wealth(minus: int, zero: int, plus: int, rule: SuiteRule) -> tuple[Fraction, Fraction]
def scored_wealth(minus: int, zero: int, plus: int, errored: int, rule: SuiteRule) -> tuple[Fraction, Fraction]
def crossed(value: Fraction, rule: SuiteRule) -> bool
def wealth_text(value: Fraction) -> str
def earliest_pass_round(rule: SuiteRule) -> int | None
def earliest_block_round(rule: SuiteRule) -> int | None
def never_differs_pass_round(rule: SuiteRule) -> int | None
def default_max_rounds(n_cells: int) -> int
def default_max_errored_pairs(n_cells: int, max_rounds: int) -> int
def check_suite_plan(manifest: SuiteManifest) -> tuple[str, ...]

@dataclass(frozen=True)
class OperatingCharacteristics:
    p_pass: Fraction
    p_block: Fraction
    p_inconclusive: Fraction
    expected_pairs: Fraction

def operating_characteristics(
    laws: Sequence[tuple[Fraction, Fraction, Fraction]], rule: SuiteRule
) -> OperatingCharacteristics
```

- **Domains.** `SuiteRule` validates itself on construction and raises `ValueError`:
  `alpha`, `delta` and stakes are `Fraction` instances in the ranges of section 2 rule 4
  (stakes non-empty, at most 8, strictly increasing); `n_cells >= 1`; `max_rounds >= 1`;
  `0 <= max_errored_pairs <= n_cells * max_rounds`. Counts passed to `wealth` and
  `scored_wealth` are non-negative `int`s, else `ValueError`. Each law passed to
  `operating_characteristics` is three `Fraction`s, each at least 0, summing to exactly 1,
  and there is one law per cell, else `ValueError`.
- **`wealth(minus, zero, plus, rule)`** returns `(PASS wealth, BLOCK wealth)` for a stream
  holding those counts of d = -1, 0, +1. With `x = d + delta`:
  PASS wealth = mean over stakes `q` of the product over pairs of `1 + q / (1 - delta) * x`;
  BLOCK wealth = mean over `q` of the product of `1 - q / (1 + delta) * x`.
  Equal weights. Order of pairs does not matter. Must be computed from the counts with
  integer powers, not pair by pair: `wealth(0, 100_000, 0, rule)` returns promptly.
- **`scored_wealth`** applies the errored-pair rule: PASS wealth is
  `wealth(minus + errored, zero, plus, rule)[0]`; BLOCK wealth is
  `wealth(minus, zero, plus + errored, rule)[1]`.
- **`crossed(value, rule)`** is `value >= rule.threshold`, inclusive, by integer comparison.
- **`wealth_text(value)`** for `value > 0`: let `e` be the integer with
  `10**e <= value < 10**(e + 1)` and `m = floor(value / 10**(e - 5))` (a six-digit integer).
  The text is `f"{m // 100000}.{m % 100000:05d}e{e:+03d}"`. Verified example: the PASS
  wealth of 80 pairs all `0` at the defaults is `"4.22732e+01"`.
  Truncated, never rounded, by integer arithmetic. `ValueError` for `value <= 0`.
- **`earliest_pass_round`**: the first round `r <= max_rounds` at which a stream of
  `r * n_cells` pairs all `+1` has PASS wealth crossed; `None` if there is none.
  **`earliest_block_round`**: the same with all `-1` and the BLOCK wealth.
  **`never_differs_pass_round`**: the same with all `0` and the PASS wealth.
- **Defaults.** `default_max_rounds(N) = ceil(400 / N)` (so 1 for `N >= 400`).
  `default_max_errored_pairs(N, R) = ceil(N * R / 100)`. Integer arithmetic.
- **`check_suite_plan(manifest)`** raises `SuitePlanError` when
  (a) `never_differs_pass_round(rule)` is `None`: the budget is below the first round end
  at which a candidate that never differs from the baseline could PASS; or
  (b) with `E = max_errored_pairs`, `scored_wealth(0, 0, registered_pairs - E, E, rule)[0]`
  has not crossed: PASS is unreachable once the tolerance is used.
  Otherwise it returns warnings, exactly `("max_rounds below 3: few looks",)` when
  `max_rounds < 3`, else `()`.
- **`operating_characteristics(laws, rule)`**: `laws[i]` is `(P(d=-1), P(d=0), P(d=+1))` for
  cell `i`, exact, summing to 1; `len(laws) == rule.n_cells`. Cells are independent, every
  round has the same laws, there are no errored pairs and no hard violations. Returns the
  exact probabilities of each verdict under the stopping rule of section 5 and the exact
  expected number of pairs run. The three probabilities sum to 1 exactly. It must handle
  20 cells and 400 registered pairs with different laws per cell.

Known exact facts at the defaults (alpha 1/20, delta 1/10, stakes 1/4 and 1/2):

- All-zero PASS wealth first crosses 40 at 79 pairs. So `never_differs_pass_round` is 4 for
  20 cells and 8 for 10 cells, and a 20-cell plan with `max_rounds = 3` is refused.
- All `+1` first crosses the PASS threshold at 9 pairs; all `-1` first crosses the BLOCK
  threshold at 13 pairs. For 20 cells both earliest rounds are 1.
- 20 cells, 4 rounds, `max_errored_pairs = 1` passes `check_suite_plan`. With one errored
  pair and 79 pairs of `0` the PASS wealth is about 21.17, so that run is INCONCLUSIVE.
- 20 cells, 20 rounds, identical independent arms at 0.95: PASS 0.999462 (rounded), expected
  pairs 125.863. 0.95 against 0.75: BLOCK 0.928342, expected pairs 202.522. The exact
  fractions are the two matching Table C records in `spikes/s1c/results.json`
  (`RESULTS.md` holds the rounded table).
- For every law with suite mean difference exactly `-delta`, `p_pass <= alpha / 2` and
  `p_block <= alpha / 2`.

## 5. `src/arci/suite_gate.py` (not frozen; pinned by acceptance tests)

```python
def evaluate_rounds(manifest: SuiteManifest, trials: Sequence[TrialEnvelope]) -> tuple[SuiteRoundDecision, ...]
def decide_suite(manifest: SuiteManifest, trials: Sequence[TrialEnvelope]) -> SuiteDecision
def replay_suite_decision(decision: SuiteDecision, manifest: SuiteManifest, trials: Sequence[TrialEnvelope]) -> bool
```

**Round verdict.** For the cumulative counts through round `r` and the cumulative number of
hard violations (hard-severity entries in `trial.contract.violations` over candidate trials;
a trial with no contract result has none), in this order:

1. `counts.errored > max_errored_pairs`: ERROR, reasons `("errored pairs exceed max_errored_pairs",)`.
2. hard violations `> 0`: BLOCK, `("candidate hard violation",)`.
3. Both wealths crossed: ERROR, `("both tests crossed",)`.
4. PASS wealth crossed: PASS, `("non-inferiority established",)`.
5. BLOCK wealth crossed: BLOCK, `("regression established",)`.
6. Otherwise INCONCLUSIVE, `("no test crossed",)`.

The wealths are `scored_wealth` of the cumulative counts. `pass_crossed` and `block_crossed`
are always the true crossings, whatever the verdict.

**`evaluate_rounds`** assumes a valid manifest and trials that match the schedule. It
returns one `SuiteRoundDecision` for each complete round present, walking from round 1 and
stopping after the first round whose verdict is not INCONCLUSIVE. A trailing partial round
is ignored: it is no look, neither a verdict nor an exception. The runner uses this to
decide whether to run another round.

**`decide_suite`** is pure and never raises, for any `SuiteManifest` instance and any
sequence of `TrialEnvelope` instances, including instances built with `model_construct` or
`model_copy` that hold invalid values. Same inputs, same sealed decision, on every platform.

**Normalise first.** A record built with `model_copy(update=...)` can hold a value of the
wrong type (the string `"ERROR"` where `Outcome.ERROR` belongs) under a seal that still
verifies. So the gate never reads the supplied instances directly. It rebuilds the manifest
with `SuiteManifest.model_validate(manifest.model_dump(mode="python"))` and every trial with
`TrialEnvelope.model_validate(trial.model_dump(mode="python"))`, and every later check and
all scoring use only the rebuilt instances.

It then collects every failing check below, in this order, into `reasons`. An exception
raised inside a check counts as that check failing.

| # | Check | Reason |
|---|---|---|
| 1 | The manifest rebuilds, and `canonical_json` of its `model_dump(mode="json")` succeeds | `manifest values invalid` |
| 2 | `manifest.validate_seal()` | `manifest seal invalid` |
| 3 | `manifest.experiment_id == suite_experiment_id(manifest)` | `suite rule digest mismatch` |
| 4 | `check_suite_plan(manifest)` does not raise | `suite plan invalid` |
| 5 | Every trial rebuilds, and `canonical_json` of its `model_dump(mode="json")` succeeds | `trial values invalid` |
| 6 | No duplicate trial id; every id is in `build_suite_schedule(manifest)`; every trial matches its spec on `experiment_id`, `trial_id`, `pair_id`, `arm`, `task_id`, `condition_id`, `seed` and `spec_sha256` (as `gate.py:41-50`) | `trial schedule mismatch` |
| 7 | Every `trial.validate_seal()` | `trial seal invalid` |
| 8 | The trial ids are exactly rounds 1 to `r` of the schedule for some `1 <= r <= max_rounds` (not empty, no partial round) | `trial set is not a whole number of rounds` |

If check 1 fails, checks 2 to 8 are skipped. If check 5 fails, checks 6 to 8 are skipped.
Check 8 is skipped when check 6 fails. If any check failed, the decision is ERROR with
`history = ()` and `cells = ()`. Otherwise the rounds are walked as in `evaluate_rounds`,
giving a history that ends at round `k`:

| Situation | Result |
|---|---|
| `k < r` (a round before the last stored one was decisive or ERROR) | ERROR, `trials stored after the stopping round` |
| `k == r`, round verdict INCONCLUSIVE, `r < max_rounds` | ERROR, `stopped without a decision` |
| `k == r`, round verdict ERROR | ERROR, that round's reasons |
| `k == r`, round verdict PASS or BLOCK | that verdict and that round's reasons, `stopped_at_round = r` |
| `k == r == max_rounds`, round verdict INCONCLUSIVE | INCONCLUSIVE, `("no test crossed",)`, `stopped_at_round = r` |

In these five rows `history` is the walked rounds and `cells` is the per-cell table over all
supplied trials, in cell order. Every ERROR decision has `stopped_at_round = 0` and
`exit_code = 3`. If anything is raised outside the eight checks (in the walk, the cell
table or sealing), the result is a sealed ERROR decision with reasons
`("gate computation failed",)`, `history = ()` and `cells = ()`.

**Fields of every decision.**
- When check 1 passed: `experiment_id`, `alpha`, `delta`, `stakes`, `scenario_seeds`,
  `max_rounds`, `max_errored_pairs` and `prior_runs` mirror the rebuilt manifest;
  `n_cells` is its cell count; `threshold = format_rational(2 / alpha)`;
  `manifest_sha256 = manifest.record_sha256`.
- When check 1 failed, one fixed template: every string field above is `""`, every tuple
  `()`, every integer `0`, and `manifest_sha256` is `""`.
- `trials_sha256` is `hash_record({"trials": sorted(record_sha256 of the supplied trials)})`,
  taken from the supplied instances. It is `""` if any supplied `record_sha256` is not a
  `str`, or if computing it raises for any reason (a string that cannot be encoded as
  UTF-8, such as a lone surrogate).
  Round digests use the same formula over the trials of rounds 1 to that round.
- **Last resort.** A Python string can hold text that cannot be encoded (`"\ud800"`), and
  Pydantic accepts it. Checks 1 and 5 turn that into a named failure. If, despite
  everything above, building or sealing the decision itself raises, the result is the fixed
  template of the previous bullet with `trials_sha256 = ""`, `history = ()`, `cells = ()`
  and reasons exactly `("gate computation failed",)`. That decision always seals.

**`replay_suite_decision`** is true if and only if the decision's seal is valid and
`decide_suite(manifest, trials) == decision`. It never raises.

## 6. `bench/selfcheck_suite.py` and `docs/STATISTICS_SUITE.md` (task P1b)

- `python -m bench.selfcheck_suite` exits 0 only if every check holds; follow the shape of
  `bench/selfcheck.py`. Checks, all exact: both directional errors are at most `alpha / 2`
  on the margin for grids of 1, 2, 5, 10 and 20 cells, including laws that differ strongly
  between cells; the operating-characteristics rows of ADR 0011 reproduce as exact
  fractions; the floors (79 pairs) reproduce; power for 50, 100, 200 and 400 cells under the
  default budget is tabulated (ADR 0011 open point 3; report, do not assert a threshold).
- `docs/STATISTICS_SUITE.md` states the estimand, the rule, the proof in full (from
  `PROOF.md`), every assumption of ADR 0011 item 6, the seed modes of item 7 with the exact
  per-round condition, the errored-pair rule, the limits, and the "may say / must not say"
  list. It does not change or contradict `docs/STATISTICS.md`.

## 7. Clarifications after the blind acceptance tests were written (2026-11-11)

The test authors listed where this contract was silent. These answers bind both sides.

- The order in which trials are supplied never matters: `decide_suite` and
  `evaluate_rounds` give the same result for any permutation.
- `earliest_pass_round`, `earliest_block_round` and `never_differs_pass_round` describe
  streams with no errored pair; `max_errored_pairs` does not change them.
- Model fields are not strict, as written in section 2. A value that Pydantic coerces when
  the record is rebuilt (the string `"20"` for an `int`) is judged after rebuilding.
- "Check 8 is skipped when check 6 fails" means exactly that: check 7 still runs.
- Round-verdict rule 3 (`both tests crossed`) and the `gate computation failed` paths are
  guards. No valid input is known to reach them and they have no acceptance test.
- Left unspecified on purpose, and not tested: non-string arguments to `pair_round`,
  `cell_seed` and `arm_order` beyond the stated domains; `bool` passed where an `int` is
  expected; lists passed where tuples are declared; the text of `SuitePlanError`; which of
  (a) or (b) is reported when both fail; `evaluate_rounds` on inputs that break its stated
  assumptions; consistency between fields of a hand-built decision record.
