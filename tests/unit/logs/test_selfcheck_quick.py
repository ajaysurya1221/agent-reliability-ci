"""The quick self-check runs in-process and must meet every gate."""

import pytest

from bench.selfcheck_logs import main


def test_selfcheck_quick() -> None:
    assert main(["--quick"]) == 0


def test_streak_direct_tables_match_full_reduction() -> None:
    import random
    from fractions import Fraction

    from bench.selfcheck_logs import DESIGNS, history, streak_table, table_of

    for m, n in DESIGNS:
        for rho in (0.0, 0.3, 0.5, 0.7):
            for drop in (Fraction(), Fraction(1, 4), Fraction(45, 100)):
                direct = streak_table(random.Random(17), m, n, 0.4, drop, rho)
                full = table_of(history(random.Random(17), m, n, 0.4, drop, rho=rho), n)
                assert direct == full


def test_three_streak_variants_preserve_old_ladder() -> None:
    from dataclasses import replace

    from bench.selfcheck_logs import streak_variants
    from tests.unit.logs.test_measures import sample, table

    data = sample()
    rows = tuple(
        replace(
            r,
            reasoning=(10 if r.when.day < 26 else 20)
            if r.when.month == 4
            else (0 if i % 2 else 10),
        )
        for i, r in enumerate(data.responses)
    )
    source = table(replace(data, responses=rows))
    assert streak_variants(source) == ("REAL_DROP", "REAL_DROP", "CANNOT_TELL")


def test_unguarded_reuse_matches_full_recalculation() -> None:
    import random
    from fractions import Fraction

    from arci.logs.decide import decide_tool
    from arci.logs.records import ReaderCounters
    from bench.selfcheck_logs import DESIGNS, streak_table, without_streak

    for m, n in DESIGNS:
        for rho in (0.0, 0.3, 0.5, 0.7):
            source = streak_table(random.Random(17), m, n, 0.45, Fraction(), rho)
            decision = decide_tool(source, ReaderCounters(files_read=1))
            assert without_streak(source, decision) == without_streak(source)


def test_gate_count_cannot_be_reduced_by_time_budget() -> None:
    from dataclasses import replace

    from bench.selfcheck_logs import Cell, execute_cell, gate_passes

    cell = Cell("null", "independent", 5, 10, 17, 31)
    counts = execute_cell(cell)
    assert counts.generated == cell.count
    assert gate_passes(cell, counts)
    assert not gate_passes(cell, replace(counts, generated=cell.count - 1))


@pytest.mark.parametrize("seed", range(17, 27))
def test_gate_tables_match_full_path_for_both_dependence_cases(seed: int) -> None:
    import random
    from fractions import Fraction

    from arci.logs.decide import decide_tool
    from bench.selfcheck_logs import DESIGNS, history, streak_table, table_of

    for m, n in DESIGNS:
        for shared in (False, True):
            for drop in (Fraction(), Fraction(1, 4)):
                direct = streak_table(random.Random(seed), m, n, 0.45, drop, 0.0, shared=shared)
                records = history(random.Random(seed), m, n, 0.45, drop, shared=shared)
                unused = [r for r in records.responses if r.model == 1]
                assert len(unused) == m + n and all(r.reasoning is None for r in unused)
                assert not any(e.model == 1 for e in records.edits)
                full = table_of(records, n)
                assert full.other_settings == 1
                assert direct == full
                assert decide_tool(direct, records.counters) == decide_tool(full, records.counters)


def test_selfcheck_fails_when_gated_cell_has_fewer_tables(monkeypatch: pytest.MonkeyPatch) -> None:
    from bench import selfcheck_logs

    def reduced(*args: object, **kwargs: object) -> selfcheck_logs.Counts:
        return selfcheck_logs.Counts(299, 299, 0, 0)

    monkeypatch.setattr(selfcheck_logs, "execute_cell", reduced)

    def no_op(*args: object) -> None:
        pass

    for name in ("exact", "usable_days", "retention_checks", "selection_demo", "usability_demo"):
        monkeypatch.setattr(selfcheck_logs, name, no_op)
    assert selfcheck_logs.run(True, "2026-11-15") == 1


def test_new_gates_have_separate_full_cells_and_fixed_seeds() -> None:
    from fractions import Fraction

    from bench.selfcheck_logs import DESIGNS, MARGIN_MODES, SEED, cells

    planned = cells()
    assert SEED == 18112026
    assert len({cell.seed for cell in planned}) == len(planned)
    for section in ("settings", "competitive"):
        selected = [cell for cell in planned if cell.section == section]
        assert tuple(cell.mode for cell in selected) == MARGIN_MODES
        assert all(cell.count == 20000 for cell in selected)
    for section in ("null", "power", "correlation"):
        assert {(cell.m, cell.n) for cell in planned if cell.section == section} == set(DESIGNS)
    assert all(cell.count == 20000 for cell in planned if cell.section == "assumptions")
    assert {(cell.mode, cell.drop) for cell in planned if cell.section == "cycles"} == {
        (mode, drop) for mode in ("weekly", "regime") for drop in (0, Fraction(1, 4))
    }


@pytest.mark.parametrize("section", ("settings", "competitive"))
@pytest.mark.parametrize("seed", (17, 18, 19))
def test_new_margin_moves_preserve_structure_and_other_measures(section: str, seed: int) -> None:
    import random
    from dataclasses import replace
    from fractions import Fraction

    from bench.selfcheck_logs import MARGIN_MODES, Cell, setting_history, table_of

    cell = Cell(section, "null", 14, 16, seed, 1)
    records = setting_history(random.Random(seed), cell, 0)
    null = table_of(records, 84)
    for name in MARGIN_MODES[1:]:
        changed = setting_history(random.Random(seed), replace(cell, mode=name), 0)
        assert [(r.when, r.model, r.effort) for r in changed.responses] == [
            (r.when, r.model, r.effort) for r in records.responses
        ]
        assert [(e.when, e.model) for e in changed.edits] == [
            (e.when, e.model) for e in records.edits
        ]
        moved = table_of(changed, 84)
        assert moved.model == null.model
        assert moved.reference_value == null.reference_value == 1
        for before, after in zip(null.measures, moved.measures, strict=True):
            assert before.before_days == after.before_days
            assert [d.day for d in before.after_days] == [d.day for d in after.after_days]
            for left, right in zip(before.after_days, after.after_days, strict=True):
                expected = Fraction(left.value)
                if name == before.id:
                    expected = (
                        expected * Fraction(3, 4)
                        if name == "reasoning_tokens"
                        else (
                            expected
                            + (
                                Fraction(1, 10)
                                if name == "no_reasoning_share"
                                else Fraction(3, 100)
                            )
                        )
                    )
                assert Fraction(right.value) == expected


def test_competitive_choice_uses_both_settings() -> None:
    from bench.selfcheck_logs import Cell, setting_counts

    result = setting_counts(Cell("competitive", "null", 14, 16, 17, 40))
    assert result.generated == 40
    assert result.choices[0] == 0 and all(count > 0 for count in result.choices[1:])


def test_gate_uses_only_the_prespecified_direction_and_exact_bound() -> None:
    from dataclasses import replace

    from bench.selfcheck_logs import Cell, Counts, gate_passes

    null = Cell("settings", "null", 14, 16, 17, 20000)
    assert gate_passes(null, Counts(20000, 20000, 566, 19000))
    assert not gate_passes(null, Counts(20000, 20000, 567, 0))
    margin = replace(null, mode="edit_failure_share")
    assert gate_passes(margin, Counts(20000, 20000, 19000, 566))
    assert not gate_passes(margin, Counts(20000, 20000, 0, 567))
    assert not gate_passes(null, Counts(19999, 19999, 0, 0))
    assert gate_passes(margin, Counts(20000, 20000, 0, 0, moved_none=566))
    assert not gate_passes(margin, Counts(20000, 20000, 0, 0, moved_none=567))


def test_power_stops_at_tested_count() -> None:
    from fractions import Fraction

    from bench.selfcheck_logs import Cell, counted_histories

    result = counted_histories(Cell("power", "independent", 7, 21, 17, 50, drop=Fraction(9, 20)))
    assert result.tested == 50
    assert result.generated > result.tested
    assert result.real + result.none <= result.tested


def test_conditional_counts_and_zero_denominator() -> None:
    from bench.selfcheck_logs import Cell, counted_histories, rate

    result = counted_histories(Cell("correlation", "AR(1)", 7, 21, 17, 50, rho=0.7))
    assert 0 <= result.tested <= result.per_tested <= result.generated == 50
    assert result.real <= result.per_real <= result.raw_real
    assert result.none <= result.per_none <= result.raw_none
    assert "undefined" in rate(0, 0)


@pytest.mark.parametrize("mode", ("weekly", "regime"))
def test_dependence_generators_are_seeded_and_exact(mode: str) -> None:
    import random
    from dataclasses import replace
    from fractions import Fraction

    from bench.selfcheck_logs import Cell, dependent_table

    cell = Cell("cycles", mode, 14, 16, 17, 1)
    table = dependent_table(random.Random(17), cell)
    assert table == dependent_table(random.Random(17), cell)
    moved = dependent_table(random.Random(17), replace(cell, drop=Fraction(1, 4)))
    assert table.measures[0].before_days == moved.measures[0].before_days
    assert table.measures[1:] == moved.measures[1:]
    assert [Fraction(d.value) * Fraction(3, 4) for d in table.measures[0].after_days] == [
        Fraction(d.value) for d in moved.measures[0].after_days
    ]


def test_failed_gate_stops_before_next_cell(monkeypatch: pytest.MonkeyPatch) -> None:
    from bench import selfcheck_logs as check

    seen: list[str] = []

    def failure(cell: check.Cell) -> check.Counts:
        seen.append(cell.section)
        return check.Counts(cell.count, cell.count, cell.count, cell.count)

    monkeypatch.setattr(check, "execute_cell", failure)

    def no_op(*args: object) -> None:
        pass

    for name in ("exact", "usable_days", "retention_checks"):
        monkeypatch.setattr(check, name, no_op)
    assert check.run(True, "2026-11-16") == 1
    assert seen == ["null"]


@pytest.mark.parametrize("n", (1, 30, 300))
def test_quick_limit_matches_independent_binomial_sum(n: int) -> None:
    from fractions import Fraction
    from math import comb

    from bench.selfcheck_logs import quick_limit

    def tail(c: int) -> Fraction:
        return sum(
            (Fraction(comb(n, k) * 39 ** (n - k), 40**n) for k in range(c + 1, n + 1)),
            Fraction(),
        )

    limit = quick_limit(n)
    assert tail(limit) <= Fraction(1, 1000)
    assert limit == 0 or tail(limit - 1) > Fraction(1, 1000)


def test_quick_with_optimisation() -> None:
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-O", "-m", "bench.selfcheck_logs", "--quick", "--workers", "1"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "16/16 passed; 0 failed" in result.stdout
    assert "limit(30)=" in result.stdout and "limit(300)=" in result.stdout


def test_wrong_share_margin_fails_quick_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    from fractions import Fraction

    from arci.logs import decide
    from bench.selfcheck_logs import cells, execute_cell, gate_passes

    cell = next(
        c for c in cells(True) if c.section == "competitive" and c.mode == "no_reasoning_share"
    )
    monkeypatch.setitem(decide.MARGINS, "no_reasoning_share", Fraction(9, 10))
    counts = execute_cell(cell)
    assert counts.moved_none > 4 and counts.none == 0
    assert not gate_passes(cell, counts)
