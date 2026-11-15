"""The quick self-check runs in-process and must meet every gate."""

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
