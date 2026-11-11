"""Exercise the executable suite bench and its independent verification paths."""

from __future__ import annotations

from fractions import Fraction as F

import pytest

from bench import selfcheck_suite as bench


def test_quick_bench(capsys: pytest.CaptureFixture[str]) -> None:
    assert bench.main(["--quick"]) == 0
    output = capsys.readouterr().out
    for marker in (
        "Directional errors",
        "Table C receipts",
        "Exact floors",
        "Brute-force gate paths",
        "Large-grid power",
        "Run time:",
        "All suite checks PASS",
    ):
        assert marker in output
    assert "729" in output


def test_bench_returns_nonzero_for_failed_assertion(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def fail(quick: bool = False) -> None:
        raise AssertionError("deliberate failed check")

    monkeypatch.setattr(bench, "check_calibration", fail)
    assert bench.main(["--quick"]) == 1
    assert "FAIL: deliberate failed check" in capsys.readouterr().out


@pytest.mark.parametrize("n", [1, 2, 5, 10, 20])
def test_full_calibration_grid_has_margin_near_nulls_and_heterogeneity(n: int) -> None:
    cases = bench.calibration_cases(n)
    means = {sum((p - m for m, _, p in laws), F(0)) / n for _, laws in cases}
    assert means == {F(-11, 100), F(-1, 10), F(-9, 100)}
    assert {name.split("/")[1] for name, _ in cases} == {"positive", "independent", "negative"}
    for name, laws in cases:
        assert len(laws) == n
        assert all(sum(law) == 1 and min(law) >= 0 for law in laws)
        if name.startswith("heterogeneous"):
            cell_means = [p - m for m, _, p in laws]
            assert min(cell_means) < F(-1, 2)
            assert max(cell_means) > F(1, 5)
    assert any(name.startswith("heterogeneous") for name, _ in cases) is (n > 1)


def test_joint_laws_cover_both_dependence_extremes() -> None:
    a, b = F(11, 20), F(9, 20)
    assert bench.joint_law(a, b, "positive") == (F(1, 10), F(9, 10), F(0))
    assert bench.joint_law(a, b, "negative") == (a, F(0), b)
    assert bench.joint_law(a, b, "independent") == (
        a * (1 - b),
        (1 - a) * (1 - b) + a * b,
        (1 - a) * b,
    )
    with pytest.raises(ValueError, match="unknown coupling"):
        bench.joint_law(a, b, "invalid")
