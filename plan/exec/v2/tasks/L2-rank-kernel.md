# L2: the exact rank kernel

Read `/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/tasks/L-CONTRACT.md` first and
follow its rules. The mathematics is in `STATISTICS_LOGS-draft.md`, sections "The tests" and
"Proof" (path in the contract).

## You own

- `src/arci/logs/__init__.py` (a one-line docstring, nothing else)
- `src/arci/logs/rank_test.py`
- `tests/unit/logs/__init__.py`, `tests/unit/logs/test_rank_test.py`

## Build

`rank_test.py` with exactly the five public functions of the contract, pure functions on
`Fraction` and `int`:

1. `p_real(before, after)`: rank the pooled values with midranks; `W` is the sum of the
   after-values' midranks; return the share, among all `C(n+m, m)` choices of which pooled
   values are "after", of choices whose midrank sum is at most `W`. Count with integer
   dynamic programming over the groups of tied values on doubled midranks (a group of `t`
   equal values contributes `C(t, j)` ways to put `j` of them in "after"). Empty `before` or
   `after` returns `Fraction(1)`.
2. `strict_count(moved_before, after)`: the number of pairs with `x' < y`, strictly.
3. `g_tail(n, m, u)`: the probability that the count of pairs `x < y` is at least `u` when
   `n` x-values and `m` y-values, all distinct, are arranged uniformly at random. This is the
   Mann-Whitney distribution; compute the counts for all `u` at once (for example with the
   standard recurrence or the product form of the Gaussian binomial coefficient) and cache by
   `(n, m)`. `u ≤ 0` returns 1; `u > n*m` returns 0.
4. `p_none(moved_before, after)`: `g_tail(len(moved_before), len(after), strict_count(...))`.
5. `p_streak(before_in_date_order)`: median `M` of the values (even count: the mean of the
   two middle ones); drop values equal to `M`; mark the rest above or below; `R` runs, `a`
   above, `b` below; return the probability of `R` or fewer runs under a uniformly random
   arrangement of the marks, from the exact runs distribution
   (`P(R = 2k) = 2·C(a−1, k−1)·C(b−1, k−1) / C(a+b, a)`,
   `P(R = 2k+1) = [C(a−1, k)·C(b−1, k−1) + C(a−1, k−1)·C(b−1, k)] / C(a+b, a)`).
   Return `Fraction(1)` when `a` or `b` is 0.

Requirements: no float; no global mutable state except bounded caches; any call with both
groups at most 84 values returns in well under two seconds cold; inputs are not mutated;
non-`Fraction` numbers (`int`) are accepted.

## Tests (`tests/unit/logs/test_rank_test.py`)

- Brute force by enumeration, written independently in the test file, equals each of
  `p_real`, `g_tail` and `p_streak` for every case with at most 12 values in total: `p_real`
  on three tie patterns (all distinct; values from three levels; all equal), `g_tail` for
  every `u`, `p_streak` for every arrangement of every `a + b ≤ 12`.
- For those cases, the share of labelings on which `p_real ≤ α` is at most `α` for
  `α` in `{1/40, 1/120}`; the same for `p_none` with distinct values and with ties (the
  share of arrangements on which `g_tail(n, m, strict_count) ≤ α` is at most `α`).
- Monotonicity: making one after-value smaller never raises `strict_count`.
- The reviewer's example: before eight `200`s and two `100`s, after five `100`s gives
  `p_real == Fraction(1, 143)`.
- Edge cases: empty groups, one value, all equal, `u` out of range, 84 and 84 values (runs,
  returns a `Fraction`, completes).

## Done when

`.venv/bin/pytest tests/unit/logs/test_rank_test.py -q` passes; ruff format, ruff check and
basedpyright are clean on your files; `shasum -a 256 -c FROZEN.sha256` still passes.
