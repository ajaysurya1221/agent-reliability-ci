"""The packaged planner and bench/selfcheck.py enumerate the same operating characteristics."""

from __future__ import annotations

import pytest

import bench.selfcheck as selfcheck
from arci.planning import binomial_pmf, verdict_probabilities
from arci.schema import Verdict
from bench.selfcheck import operating_characteristics

# The bench's own scenario grid and pmf are the references, private or not.
SCENARIOS = selfcheck._SCENARIOS  # pyright: ignore[reportPrivateUsage]
bench_pmf = selfcheck._binomial_pmf  # pyright: ignore[reportPrivateUsage]

# N=400 is left to the published README cells (tests/unit/planning): enumerating it twice, once per
# implementation, would add about thirty seconds to the suite.
SAMPLE_SIZES = (20, 50, 100, 200)


@pytest.mark.parametrize("n", SAMPLE_SIZES)
@pytest.mark.parametrize(("p_a", "p_b"), SCENARIOS)
def test_planner_matches_the_selfcheck_enumeration(p_a: float, p_b: float, n: int) -> None:
    packaged = verdict_probabilities(p_a, p_b, n)
    bench = operating_characteristics(p_a, p_b, n)
    for verdict in (Verdict.PASS, Verdict.BLOCK, Verdict.INCONCLUSIVE):
        # The planner sums exact integers and rounds once; the bench sums floats and folds its
        # rounding residual into INCONCLUSIVE. They agree to within 1e-12, not bit for bit.
        assert packaged[verdict] == pytest.approx(bench[verdict.value], abs=1e-12)


@pytest.mark.parametrize("n", (1, 20, 400))
@pytest.mark.parametrize("p", (0.0, 0.25, 0.95, 1.0))
def test_binomial_pmf_matches_the_selfcheck_pmf(p: float, n: int) -> None:
    # The planner rounds exact rational masses once; the bench computes in floating point. They
    # agree to within 1e-12 per term, not bit for bit.
    packaged = binomial_pmf(p, n)
    bench = bench_pmf(p, n)
    assert len(packaged) == len(bench) == n + 1
    for packaged_term, bench_term in zip(packaged, bench, strict=True):
        assert packaged_term == pytest.approx(bench_term, abs=1e-12)
