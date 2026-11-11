"""Exercise the executable suite bench and its independent verification paths."""

from __future__ import annotations

from fractions import Fraction as F

import pytest

from arci.suite_schema import SuiteDecision
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
    assert {name.split("/")[1] for name, _ in cases} == {
        "positive",
        "independent",
        "negative",
        "p0",
    }
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


def test_margin_family_has_free_zero_mass() -> None:
    laws = [law[0] for name, law in bench.calibration_cases(1) if name.startswith("three-point/")]
    assert {z for _, z, _ in laws} == {*(F(i, 10) for i in range(10)), F(1, 9), F(9, 20)}
    assert all(p - m == F(-1, 10) for m, _, p in laws)


def test_default_rule_reads_manifest_defaults() -> None:
    from arci.suite_schema import SuiteManifest

    field = SuiteManifest.model_fields["stakes"]
    old = field.default
    try:
        field.default = ("1/3",)
        SuiteManifest.model_rebuild(force=True)
        assert bench.default_rule(20).stakes == (F(1, 3),)
    finally:
        field.default = old
        SuiteManifest.model_rebuild(force=True)


def test_gate_paths_reject_reversed_sign(monkeypatch: pytest.MonkeyPatch) -> None:
    original = bench.decide_suite

    def reverse(
        manifest: bench.SuiteManifest, trials: bench.Sequence[bench.TrialEnvelope]
    ) -> SuiteDecision:
        swapped = [
            bench.TrialEnvelope.create(
                **(
                    t.model_dump(exclude={"record_sha256"})
                    | {
                        "outcome": bench.Outcome.FAIL
                        if t.outcome is bench.Outcome.PASS
                        else bench.Outcome.PASS
                    }
                )
            )
            for t in trials
        ]
        return original(manifest, swapped)

    monkeypatch.setattr(bench, "decide_suite", reverse)
    with pytest.raises(AssertionError):
        bench.gate_path_characteristics(((F(1, 6), F(1, 3), F(1, 2)),))


def test_gate_paths_reject_missed_early_block(monkeypatch: pytest.MonkeyPatch) -> None:
    import arci.suite_gate as gate

    original = gate.RunningWealth.crossed

    def suppress(self: gate.RunningWealth) -> bool:
        final_denominator = len(self.rule.stakes) * self.base ** (
            self.rule.n_cells * self.rule.max_rounds
        )
        if self.sign == -1 and self.denominator < final_denominator:
            return False
        return original(self)

    monkeypatch.setattr(gate.RunningWealth, "crossed", suppress)
    with pytest.raises(AssertionError):
        bench.gate_path_characteristics(((F(1, 6), F(1, 3), F(1, 2)),))


def test_override_paths_reject_zero_scored_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    import arci.suite_gate as gate

    original = gate.RunningWealth.advance

    def zero_errors(
        self: gate.RunningWealth, minus: int, zero: int, plus: int, errored: int
    ) -> None:
        original(self, minus, zero + errored, plus, 0)

    monkeypatch.setattr(gate.RunningWealth, "advance", zero_errors)
    with pytest.raises(AssertionError):
        bench.check_gate_overrides()
