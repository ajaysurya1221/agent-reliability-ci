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
    from fractions import Fraction

    from bench.selfcheck_logs import simulate

    assert simulate(5, 10, 0.45, Fraction(), 17, 31, 0.000001, gated=True)[-1] == 31


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

    def reduced(*args: object, **kwargs: object) -> tuple[int, int, int, int, int]:
        return 0, 0, 0, 0, 299

    monkeypatch.setattr(selfcheck_logs, "simulate", reduced)

    def no_op(*args: object) -> None:
        pass

    for name in ("exact", "usable_days", "selection_demo", "usability_demo"):
        monkeypatch.setattr(selfcheck_logs, name, no_op)
    assert selfcheck_logs.run(True, "2026-11-15") == 1
