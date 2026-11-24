"""Time fixed streams only. Run as a script from the study directory."""

from __future__ import annotations

import sys
from itertools import cycle
from pathlib import Path
from random import Random
from tempfile import TemporaryFile
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gates import Counts, Decision, decisions
from simulate import Key, Tallies, draw_rounds, journal_entry, seed


def time_fixture(counts: Counts) -> float:
    # U values spell the four cell types at handmade cutoffs 95 and 42.
    values = [(99, 99), (99, 0), (0, 99), (0, 0)]
    draws = cycle(
        u for pair, count in zip(values, counts, strict=True) for _ in range(count) for u in pair
    )

    def fixed(_: int) -> int:
        return next(draws)

    def hand(key: Key) -> dict[str, Decision]:
        stream = draw_rounds(42, "I", "primary", fixed, fixed)
        assert stream == (counts,) * 20
        return decisions(stream, Random(seed(key, "bootstrap")))

    tallies = Tallies()
    start = perf_counter()
    with TemporaryFile("a+b") as journal:
        for i in range(180):
            tallies.add(journal_entry(journal, Key("primary", "I", 42, i), "hand", hand))
    return (perf_counter() - start) / 180


if __name__ == "__main__":
    for case in (Counts(6, 0, 0, 14), Counts(4, 0, 3, 13), Counts(2, 2, 4, 12)):
        print(f"{case}: {time_fixture(case) * 1000:.3f} ms per stream")
