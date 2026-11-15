"""Exact checks and seeded final-rule simulations on synthetic in-memory records.

Run: .venv/bin/python -m bench.selfcheck_logs --date YYYY-MM-DD
Gates use fixed history counts. Power stops at a fixed number of tested histories.
"""

from __future__ import annotations

import argparse
import io
import json
import math
import random
import subprocess
import sys
from collections import Counter
from collections.abc import Iterator, Sequence
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, timedelta
from fractions import Fraction as F
from itertools import combinations
from pathlib import Path
from statistics import NormalDist
from time import perf_counter

from arci.logs import decide, kept, measures, rank_test
from arci.logs.records import EditResult, ReaderCounters, ReadResult, Response, Tool
from arci.logs.schema import ContextCounts, DayValue, Period, ToolDecision

DESIGNS = ((5, 10), (7, 21), (14, 16), (14, 42), (28, 84))
START = datetime(2026, 1, 1, 12, tzinfo=UTC)
SEED = 18112026
LIMIT = F(283, 10000)


def rate(k: int, n: int) -> str:
    """Display-only Wilson 95% interval, always with its numerator/denominator."""
    if not n:
        return "0/0 = undefined [undefined, undefined]"
    z = 1.959963984540054
    p = k / n
    scale = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / scale
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / scale
    return f"{k}/{n} = {p:.6f} [{max(0.0, centre - half):.6f}, {min(1.0, centre + half):.6f}]"


def tails(scores: Sequence[int]) -> dict[int, F]:
    counts = Counter(scores)
    running = 0
    result: dict[int, F] = {}
    for value, count in sorted(counts.items()):
        running += count
        result[value] = F(running, len(scores))
    return result


def exact(maximum: int) -> None:
    checked = 0
    for size in range(maximum + 1):
        for m in range(size + 1):
            labels = list(combinations(range(size), m))
            us = [sum(j - i for i, j in enumerate(label)) for label in labels]
            for u in range(-1, m * (size - m) + 2):
                assert rank_test.g_tail(size - m, m, u) == F(
                    sum(score >= u for score in us), len(labels)
                ), ("g_tail", size, m, u)
            for pattern in (list(range(size)), [i % 3 for i in range(size)], [0] * size):
                ranks = [
                    2 + 2 * sum(x < v for x in pattern) + pattern.count(v) - 1 for v in pattern
                ]
                scores = [sum(ranks[i] for i in label) for label in labels]
                expected = tails(scores)
                real_reject = none_reject = 0
                for label, score in zip(labels, scores, strict=True):
                    before = [v for i, v in enumerate(pattern) if i not in label]
                    after = [pattern[i] for i in label]
                    actual = rank_test.p_real(before, after)
                    assert actual == expected[score], ("p_real", size, m, pattern, label)
                    real_reject += actual <= F(1, 120)
                    none_reject += rank_test.p_none(before, after) <= F(1, 40)
                    checked += 1
                assert F(real_reject, len(labels)) <= F(1, 120)
                assert F(none_reject, len(labels)) <= F(1, 40)
            marks = [[i in label for i in range(size)] for label in labels]
            runs = [sum(i == 0 or v != row[i - 1] for i, v in enumerate(row)) for row in marks]
            expected_runs = tails(runs)
            rejected = 0
            for row, runs_count in zip(marks, runs, strict=True):
                values = [1 if v else -1 for v in row]
                # Median-zero padding exposes every (a,b), including unbalanced marks.
                values[size // 2 : size // 2] = [0] * (abs(2 * m - size) + 1)
                actual = rank_test.p_streak(values)
                assert actual == expected_runs[runs_count], ("p_streak", size, m, row)
                rejected += actual <= F(1, 10)
            assert F(rejected, len(labels)) <= F(1, 10)
    print(
        f"Exact enumeration: PASS; n+m <= {maximum}; {checked} rank labelings; "
        "distinct, three-level and equal ties; every runs (a,b) and every U threshold."
    )


def read_result(responses: list[Response], edits: list[EditResult], models: int = 2) -> ReadResult:
    return ReadResult(
        "claude-code",
        tuple(responses),
        tuple(edits),
        (None,) * models,
        ("high",),
        tuple(range(models)),
        (0,),
        ReaderCounters(files_read=1, responses=len(responses)),
    )


def day_records(
    index: int, value: int, zero: int, total: int, failed: int, edits_total: int, model: int = 0
) -> tuple[list[Response], list[EditResult]]:
    when = START + timedelta(days=index)
    positive = Response("claude-code", when, model, 0, True, value, 0, 0, True)
    empty = Response("claude-code", when, model, 0, True, 0, 0, 0, True)
    success = EditResult("claude-code", when, model, 0, True, False, True)
    failure = EditResult("claude-code", when, model, 0, True, True, True)
    return (
        [empty] * zero + [positive] * (total - zero),
        [failure] * failed + [success] * (edits_total - failed),
    )


def table_of(result: ReadResult, n: int) -> measures.ToolTable:
    return measures.build(
        result,
        utc_offset=timedelta(),
        now=START + timedelta(days=200),
        since=(START + timedelta(days=n)).date(),
    )


def history_days(
    rng: random.Random,
    m: int,
    n: int,
    sigma: float,
    drop: F,
    shared: bool = False,
    rho: float = 0.0,
) -> list[tuple[int, int, int, int, int]]:
    size = n + m
    latent: list[list[float]] = []
    for _ in range(1 if shared else 3):
        state = rng.gauss(0, 1)
        values: list[float] = []
        for _day in range(size):
            state = rho * state + math.sqrt(1 - rho * rho) * rng.gauss(0, 1)
            values.append(state)
        latent.append(values)
    base_values = [100 * max(1, round(100 * math.exp(sigma * z))) for z in latent[0]]
    ordering = {j: sum(v < base_values[j] for v in base_values) for j in range(size)}
    days: list[tuple[int, int, int, int, int]] = []
    for i in range(size):
        # Quantize BEFORE the change; all requested percentage moves stay exact integers.
        value = base_values[i]
        if i >= n:
            moved = value * (1 - drop)
            assert moved.denominator == 1
            value = int(moved)
        if shared:
            # Same oriented ranks, including no rounding ties: 10/(20+rank).
            total = edits_total = 20 + ordering[i]
            zero = failed = 10
        else:
            total = edits_total = 100
            zero = round(10 + 25 * NormalDist().cdf(latent[1][i]))
            failed = round(5 + 25 * NormalDist().cdf(latent[2][i]))
        days.append((value, zero, total, failed, edits_total))
    return days


def history(
    rng: random.Random,
    m: int,
    n: int,
    sigma: float,
    drop: F,
    shared: bool = False,
    rho: float = 0.0,
) -> ReadResult:
    responses: list[Response] = []
    edits: list[EditResult] = []
    for i, (value, zero, total, failed, edits_total) in enumerate(
        history_days(rng, m, n, sigma, drop, shared, rho)
    ):
        r, e = day_records(i, value, zero, total, failed, edits_total)
        responses.extend(r)
        edits.extend(e)
        # A second setting and unusable records exercise setting selection and filtering.
        responses.append(
            Response("claude-code", START + timedelta(days=i), 1, 0, True, None, 0, 0, True)
        )
    return read_result(responses, edits)


def streak_table(
    rng: random.Random, m: int, n: int, sigma: float, drop: F, rho: float, shared: bool = False
) -> measures.ToolTable:
    """Exactly the same synthetic days, without expanding responses."""
    days = history_days(rng, m, n, sigma, drop, shared=shared, rho=rho)
    tokens: list[DayValue] = []
    zeros: list[DayValue] = []
    edits: list[DayValue] = []
    for i, (value, zero, total, failed, edits_total) in enumerate(days):
        day = (START + timedelta(days=i)).date().isoformat()
        tokens.append(DayValue(day=day, count=total - zero, value=f"{value}/1"))
        zeros.append(DayValue(day=day, count=total, value=measures.fraction_str(F(zero, total))))
        edits.append(
            DayValue(
                day=day, count=edits_total, value=measures.fraction_str(F(failed, edits_total))
            )
        )
    positive: Counter[int] = Counter()
    for value, zero, total, _, _ in days:
        positive[value] += total - zero
    reference = min(positive, key=lambda value: (-positive[value], value))
    split = (START + timedelta(days=n)).date()
    return measures.ToolTable(
        tool="claude-code",
        model="model-1",
        effort="high",
        other_settings=1,
        split_date=split.isoformat(),
        before=Period(
            first_day=(split - timedelta(days=84)).isoformat(),
            last_day=(split - timedelta(days=1)).isoformat(),
        ),
        after=Period(first_day=split.isoformat(), last_day=tokens[-1].day),
        measures=(
            measures.MeasureTable("reasoning_tokens", tuple(tokens[:n]), tuple(tokens[n:])),
            measures.MeasureTable("no_reasoning_share", tuple(zeros[:n]), tuple(zeros[n:])),
            measures.MeasureTable("edit_failure_share", tuple(edits[:n]), tuple(edits[n:])),
        ),
        reference_value=reference,
        first_response_day=START.date().isoformat(),
        response_days_before=n,
        response_days_after=m,
        newest=(START + timedelta(days=n + m - 1)).date(),
        context=ContextCounts(
            client_versions_after_more=1,
            client_versions_before=1,
            client_versions_after=1,
            client_versions_both=1,
            workdirs_before=1,
            workdirs_after=1,
            subagent_share_before="0/1",
            subagent_share_after="0/1",
        ),
    )


def per_measure_result(decision: ToolDecision) -> str:
    """Previous rule, reconstructed from unchanged per-measure findings."""
    findings = [row.finding for row in decision.measures]
    if "real_drop" in findings:
        return "REAL_DROP"
    if all(f == "no_drop" for f in findings):
        return "NO_DROP"
    return "CANNOT_TELL"


def streak_variants(table: measures.ToolTable) -> tuple[str, str, str]:
    decision = decide.decide_tool(table, ReaderCounters(files_read=1))
    return without_streak(table, decision), per_measure_result(decision), decision.result


def simulate_streaks(
    m: int, n: int, sigma: float, drop: F, seed: int, count: int, rho: float
) -> tuple[tuple[int, int], ...]:
    rng = random.Random(seed)
    counts = [[0, 0] for _ in range(3)]
    for _ in range(count):
        results = streak_variants(streak_table(rng, m, n, sigma, drop, rho))
        for tally, result in zip(counts, results, strict=True):
            tally[0] += result == "REAL_DROP"
            tally[1] += result == "NO_DROP"
        assert results[2] != "REAL_DROP" or results[:2] == ("REAL_DROP", "REAL_DROP")
        assert results[2] != "NO_DROP" or results[:2] == ("NO_DROP", "NO_DROP")
    return tuple((real, none) for real, none in counts)


def without_streak(table: measures.ToolTable, decision: ToolDecision | None = None) -> str:
    """Independent literal ladder; no call to the product's ladder helper."""
    findings: list[str] = []
    known = {row.id: row.finding for row in decision.measures} if decision else {}
    for measure in table.measures:
        if measure.id in known and known[measure.id] != "streaky":
            findings.append(known[measure.id])
            continue
        direction = 1 if measure.id == "reasoning_tokens" else -1
        before = [direction * F(d.value) for d in measure.before_days]
        after = [direction * F(d.value) for d in measure.after_days]
        if len(before) < 10 or len(after) < 5:
            findings.append("too_few_days")
        elif rank_test.p_real(before, after) <= F(1, 120):
            findings.append("real_drop")
        else:
            margin = F(1, 10) if measure.id == "no_reasoning_share" else F(3, 100)
            moved = [x * F(3, 4) if direction == 1 else x - margin for x in before]
            findings.append(
                "no_drop" if rank_test.p_none(moved, after) <= F(1, 40) else "cannot_tell"
            )
    return (
        "REAL_DROP"
        if "real_drop" in findings
        else "NO_DROP"
        if all(f == "no_drop" for f in findings)
        else "CANNOT_TELL"
    )


def simulate(
    m: int,
    n: int,
    sigma: float,
    drop: F,
    seed: int,
    requested: int,
    budget: float,
    shared: bool = False,
    rho: float = 0.0,
    *,
    gated: bool = False,
) -> tuple[int, int, int, int, int]:
    def trial(rng: random.Random) -> tuple[ToolDecision, str]:
        table = streak_table(rng, m, n, sigma, drop, rho, shared)
        assert table.model == "model-1" and table.other_settings == 1
        assert all(len(row.before_days) == n and len(row.after_days) == m for row in table.measures)
        decision = decide.decide_tool(table, ReaderCounters(files_read=1))
        unguarded = without_streak(table) if rho else decision.result
        return decision, unguarded

    # The legacy budget argument is retained for callers; it cannot reduce a cell.
    count = requested
    rng = random.Random(seed)
    real = none = raw_real = raw_none = 0
    for _ in range(count):
        decision, raw = trial(rng)
        real += decision.result == "REAL_DROP"
        none += decision.result == "NO_DROP"
        raw_real += raw == "REAL_DROP"
        raw_none += raw == "NO_DROP"
    return real, none, raw_real, raw_none, count


def usable_days() -> None:
    """Test the selected setting's exact 20-known/10-positive/10-edit boundaries."""
    for known, positive, edits_count in ((20, 10, 10), (19, 10, 10), (20, 9, 10), (20, 10, 9)):
        responses: list[Response] = []
        edits: list[EditResult] = []
        for day in range(15):
            total, positives, edit_total = (
                (known, positive, edits_count) if day == 14 else (20, 10, 10)
            )
            rows, results = day_records(day, 10000, total - positives, total, 0, edit_total)
            responses.extend(rows)
            edits.extend(results)
        result = read_result(responses, edits, 1)
        decision = decide.decide_tool(table_of(result, 10), result.counters)
        expected = (
            5 if known >= 20 and positive >= 10 else 4,
            5 if known >= 20 else 4,
            5 if edits_count >= 10 else 4,
        )
        assert tuple(len(row.after_days) for row in decision.measures) == expected
        assert (decision.result == "NO_DROP") == (expected == (5, 5, 5))


def selection_demo() -> None:
    subsets = list(combinations(range(15), 5))
    pooled = [sum(21 if day in subset else 20 for day in range(15)) for subset in subsets]
    assert set(pooled) == {305}
    # For every labeling, its matching subset is the unique maximum after-count model.
    masks = [sum(1 << day for day in subset) for subset in subsets]
    for expected, mask in enumerate(masks):
        winner = max(range(len(masks)), key=lambda j: (masks[j] & mask).bit_count())
        assert winner == expected
        values = [100 if day in subsets[winner] else 200 for day in range(15)]
        after = [values[day] for day in subsets[expected]]
        before = [value for day, value in enumerate(values) if day not in subsets[expected]]
        assert rank_test.p_real(before, after) == F(1, 3003)
    responses: list[Response] = []
    for model, subset in enumerate(subsets):
        for day in range(15):
            rows, _ = day_records(
                day, 100 if day in subset else 200, 0, 21 if day in subset else 20, 0, 0, model
            )
            responses.extend(rows)
    result = read_result(responses, [], len(subsets))
    # Contiguous splits also run the production after-count choice.
    for n in (10, 9, 8):
        scores = [sum(21 if day in subset else 20 for day in range(n, 15)) for subset in subsets]
        winner = min(range(len(scores)), key=lambda j: (-scores[j], j))
        assert table_of(result, n).model == f"model-{winner + 1}"
    print(
        "Demonstration outside A1 (arci-logs/2): 15 days / 3,003 models; "
        "day values are tied to response counts. After-count selection rejects in "
        "3003/3003 labelings, p_real=1/3003 every time. Production selection agrees "
        "with the after-count maximum for every checked contiguous split."
    )


def usability_demo() -> None:
    probability = F()
    for high_after in range(15):
        # Within-type values are flat: permutations within the periods do not change any finding.
        high = [True] * (49 - high_after) + [False] * (35 + high_after)
        high += [True] * high_after + [False] * (14 - high_after)
        responses: list[Response] = []
        edits: list[EditResult] = []
        for i, is_high in enumerate(high):
            after = i >= 84
            value = (400 if is_high else 100) * (3 if after else 4) // 4
            total = 20 if is_high == after else 19
            rows, results = day_records(i, value, 0, total, 0, 10)
            responses.extend(rows)
            edits.extend(results)
        result = read_result(responses, edits, 1)
        decision = decide.decide_tool(table_of(result, 84), result.counters)
        assert (decision.result == "NO_DROP") == (high_after >= 5)
        if decision.result == "NO_DROP":
            probability += F(
                math.comb(49, high_after) * math.comb(49, 14 - high_after), math.comb(98, 14)
            )
    assert probability > F(1, 40)
    print(
        f"Demonstration outside A4: 98 days, 49 low/49 high, exact 25% token move "
        f"and swapped 19/20-response usability; exact NO DROP probability "
        f"{probability} = {float(probability):.6f} (hypergeometric enumeration, not simulation)."
    )


@dataclass(frozen=True)
class Cell:
    section: str
    mode: str
    m: int
    n: int
    seed: int
    count: int
    sigma: float = 0.45
    drop: F = F()
    rho: float = 0.0
    shared: bool = False


@dataclass(frozen=True)
class Counts:
    generated: int
    tested: int
    real: int
    none: int
    raw_real: int = 0
    raw_none: int = 0
    per_real: int = 0
    per_none: int = 0
    # A per-measure check admits any history with at least one unstopped measure.
    per_tested: int = 0
    choices: tuple[int, ...] = ()


MODELS = ("claude-opus-4", "claude-sonnet-4", "claude-haiku-4")
MARGIN_MODES = ("null", "reasoning_tokens", "no_reasoning_share", "edit_failure_share")


def setting_history(rng: random.Random, cell: Cell, index: int) -> ReadResult:
    """A1 gates draw daily values independently of every response/edit count.

    Shares are drawn on a common tenths grid before replication to a varying
    denominator. Unknown responses affect the setting choice, never a day value.
    Both viable settings receive the same specified single-measure margin move.
    """
    responses: list[Response] = []
    edits: list[EditResult] = []
    competitive = cell.section == "competitive"
    start = 84 - cell.n
    for model in (1, 2) if competitive else (1,):
        days = history_days(rng, cell.m, cell.n, cell.sigma, F())
        for i, (value, zeros, _, failed, edits_total) in enumerate(days):
            day = start + i
            known = 40 if competitive else rng.choice((20, 40, 60, 80, 100))
            unknown = rng.randrange(5 if competitive else 21)
            zero = round(zeros / 10) * known // 10
            if cell.mode == "busy":
                # The same per-response law, but 5x as many observations after.
                # The resulting median and share distributions depend on the counts.
                known = 100 if i >= cell.n else 20
                zero = sum(rng.random() < 0.2 for _ in range(known))
                positives = sorted(
                    100 * max(1, round(100 * math.exp(cell.sigma * rng.gauss(0, 1))))
                    for _ in range(known - zero)
                )
                value = (
                    (positives[(len(positives) - 1) // 2] + positives[len(positives) // 2]) // 2
                    if positives
                    else 100
                )
            if cell.mode == "new-model" and i < 5:
                moved = F(115, 100) * value
                assert moved.denominator == 1
                value = int(moved)
            if i >= cell.n:
                if cell.mode == "reasoning_tokens":
                    moved = F(3, 4) * value
                    assert moved.denominator == 1
                    value = int(moved)
                elif cell.mode == "no_reasoning_share":
                    zero += known // 10
                elif cell.mode == "edit_failure_share":
                    failed += 3
            r, e = day_records(day, value, zero, known, failed, edits_total, model)
            # Keep v*=1 under every margin move. With an even positive count,
            # half at 1 and half at 2*value-1 have median exactly value. An odd
            # count has one central value. The common 1 wins every modal tie.
            half, odd = divmod(known - zero, 2)
            r = (
                r[:zero]
                + [replace(r[-1], reasoning=1)] * half
                + [r[-1]] * odd
                + [replace(r[-1], reasoning=2 * value - 1)] * half
            )
            responses.extend(r)
            edits.extend(e)
            responses.extend(
                [
                    Response(
                        "claude-code", START + timedelta(days=day), model, 0, True, None, 0, 0, True
                    )
                ]
                * unknown
            )
    # Old setting stops at adoption. It has no after-period responses.
    for day in range(start):
        r, e = day_records(day, 20000, 10, 100, 5, 100, 0)
        responses.extend(r)
        edits.extend(e)
    if not competitive and index % 2 == 0:
        for day in sorted(rng.sample(range(84, 84 + cell.m), min(6, cell.m))):
            r, e = day_records(day, 5000, 2, 4, 0, 0, 2)
            responses.extend(r)
            edits.extend(e)
    return replace(read_result(responses, edits, 3), models=MODELS, model_order=(2, 0, 1))


def setting_counts(cell: Cell) -> Counts:
    rng = random.Random(cell.seed)
    real = none = tested = 0
    choices: Counter[str] = Counter()
    for index in range(cell.count):
        records = setting_history(rng, cell, index)
        table = table_of(records, 84)
        assert table.model in MODELS[1:]
        if cell.section != "assumptions":
            assert all(
                len(t.before_days) == cell.n and len(t.after_days) == cell.m for t in table.measures
            )
        choices[table.model] += 1
        decision = decide.decide_tool(table, records.counters)
        real += decision.result == "REAL_DROP"
        none += decision.result == "NO_DROP"
        tested += decision.reason != "streaky_days"
    return Counts(cell.count, tested, real, none, choices=tuple(choices[model] for model in MODELS))


def dependent_table(rng: random.Random, cell: Cell) -> measures.ToolTable:
    table = streak_table(rng, cell.m, cell.n, cell.sigma, F(), 0)
    changed: list[measures.MeasureTable] = []
    for measure in table.measures:
        phase = rng.randrange(7)
        state = rng.choice((-1, 1))
        days: list[DayValue] = []
        for i, day in enumerate((*measure.before_days, *measure.after_days)):
            if cell.mode == "weekly":
                # Random phase; a fixed seven-day cycle plus independent noise.
                effect = math.sin(2 * math.pi * (i + phase) / 7)
            else:
                # Stationary symmetric two-state chain, switch probability 0.08/day.
                if rng.random() < 0.08:
                    state = -state
                effect = float(state)
            value = F(day.value)
            if measure.id == "reasoning_tokens":
                value = F(100 * max(1, round(float(value) * math.exp(0.6 * effect) / 100)))
                if i >= cell.n:
                    value *= 1 - cell.drop
            else:
                # Original shares in [0.05, 0.35]; this addition never clips.
                value += F(round(10 * (effect + 1)), 100)
            days.append(day.model_copy(update={"value": measures.fraction_str(value)}))
        changed.append(
            replace(measure, before_days=tuple(days[: cell.n]), after_days=tuple(days[cell.n :]))
        )
    return replace(table, measures=tuple(changed))


def counted_histories(cell: Cell) -> Counts:
    rng = random.Random(cell.seed)
    generated = tested = real = none = raw_real = raw_none = per_real = per_none = per_tested = 0
    while (tested if cell.section == "power" else generated) < cell.count:
        table = (
            dependent_table(rng, cell)
            if cell.section == "cycles"
            else streak_table(rng, cell.m, cell.n, cell.sigma, cell.drop, cell.rho, cell.shared)
        )
        decision = decide.decide_tool(table, ReaderCounters(files_read=1))
        real += decision.result == "REAL_DROP"
        none += decision.result == "NO_DROP"
        tested += decision.reason != "streaky_days"
        generated += 1
        if cell.section in ("correlation", "cycles"):
            raw = without_streak(table, decision)
            per = per_measure_result(decision)
            raw_real += raw == "REAL_DROP"
            raw_none += raw == "NO_DROP"
            per_real += per == "REAL_DROP"
            per_none += per == "NO_DROP"
            per_tested += any(row.finding != "streaky" for row in decision.measures)
    return Counts(generated, tested, real, none, raw_real, raw_none, per_real, per_none, per_tested)


def cells(quick: bool = False) -> list[Cell]:
    result: list[Cell] = []

    def add(
        section: str,
        mode: str,
        m: int,
        n: int,
        count: int,
        sigma: float = 0.45,
        drop: F = F(),
        rho: float = 0.0,
        shared: bool = False,
    ) -> None:
        result.append(
            Cell(section, mode, m, n, SEED + len(result), count, sigma, drop, rho, shared)
        )

    for m, n in ((7, 21),) if quick else DESIGNS:
        for shared in (False, True):
            for drop in (F(), F(1, 4)):
                add(
                    "null",
                    "shared" if shared else "independent",
                    m,
                    n,
                    300 if quick else 20000,
                    drop=drop,
                    shared=shared,
                )
    for section in ("settings", "competitive"):
        for mode in MARGIN_MODES:
            add(
                section,
                mode,
                14,
                16,
                30 if quick else 20000,
                drop={
                    "null": F(),
                    "reasoning_tokens": F(1, 4),
                    "no_reasoning_share": F(1, 10),
                    "edit_failure_share": F(3, 100),
                }[mode],
            )
    if quick:
        return result
    for mode in ("busy", "new-model"):
        for m, n in ((14, 16), (7, 21)):
            add("assumptions", mode, m, n, 20000)
    for m, n in DESIGNS:
        for sigma in (0.35, 0.45, 0.55):
            for drop in (F(), F(33, 100), F(9, 20), F(1, 2), F(11, 20)):
                add("power", "independent", m, n, 2000, sigma, drop)
    add("power", "independent", 14, 42, 2000, 0.40, F(9, 20))
    for m, n in DESIGNS:
        for rho in (0.0, 0.3, 0.5, 0.7):
            for drop in (F(), F(1, 4)):
                add("correlation", "AR(1)", m, n, 1000 if n == 84 else 2000, drop=drop, rho=rho)
    add("correlation", "AR(1)", 14, 42, 2000, 0.40, F(9, 20))
    for m, n in DESIGNS:
        for mode in ("weekly", "regime"):
            for drop in (F(), F(1, 4)):
                add("cycles", mode, m, n, 1000 if n == 84 else 2000, drop=drop)
    return result


@dataclass(frozen=True)
class Batch:
    responses: tuple[Response, ...]
    edits: tuple[EditResult, ...]

    @property
    def last(self) -> datetime:
        return max(r.when for r in self.responses)


def retention_trial(seed: int, *, missing: bool = False, spanning: bool = False) -> tuple[int, int]:
    """Immutable synthetic files; only whole files older than 720 hours expire."""
    rng = random.Random(seed)
    offset = rng.choice((0, 330, -480))
    zone = timedelta(minutes=offset)
    batches: list[Batch] = []
    for day in range(98):
        for hour in (0, 6, 12, 18):
            when = START.replace(hour=0) + timedelta(days=day, hours=hour) - zone
            for tool in ("claude-code", "codex"):
                model = day % 2
                value = rng.randrange(1, 200) * 100
                responses = tuple(
                    Response(
                        tool,
                        when,
                        model,
                        0,
                        True,
                        None if i == 9 else 0 if i == 0 else value,
                        0,
                        0,
                        True,
                    )
                    for i in range(10)
                )
                edits = (
                    tuple(EditResult(tool, when, model, 0, True, i == 0, True) for i in range(4))
                    if tool == "claude-code"
                    else ()
                )
                batches.append(Batch(responses, edits))
    final = START.replace(hour=12) + timedelta(days=97) - zone
    cutoff = final - timedelta(days=30)
    if spanning:
        # One file carries records on both sides of the final deletion boundary.
        pieces = [
            b
            for b in batches
            if b.responses[0].tool == "claude-code"
            and b.last in (cutoff - timedelta(hours=6), cutoff + timedelta(hours=6))
        ]
        assert len(pieces) == 2
        batches = [b for b in batches if b not in pieces]
        batches.append(
            Batch(
                tuple(r for b in pieces for r in b.responses),
                tuple(e for b in pieces for e in b.edits),
            )
        )
    disk = list(batches)
    stored: tuple[kept.KeptRow, ...] = ()
    runs = [START.replace(hour=12) - zone]
    while runs[-1] < final:
        runs.append(min(final, runs[-1] + timedelta(hours=rng.randrange(24, 29 * 24 + 1))))
    if missing:
        # Day 1 was never captured whole: its files expire before the second capture.
        runs = [runs[0], START.replace(hour=12) + timedelta(days=45) - zone, final]
    comparisons = lost = 0
    captured: dict[kept.Key, kept.KeptRow] = {}
    for now in runs:
        old = [b for b in disk if b.last < now - timedelta(days=30)]
        disk = [b for b in disk if b.last >= now - timedelta(days=30)]
        assert all(b.last < now - timedelta(days=30) for b in old)
        if spanning and now == final:
            assert any(min(r.when for r in b.responses) < cutoff < b.last for b in disk)
        for tool in ("claude-code", "codex"):

            def records(
                files: list[Batch], *, tool: Tool = tool, now: datetime = now
            ) -> ReadResult:
                return ReadResult(
                    tool,
                    tuple(
                        r for b in files for r in b.responses if r.tool == tool and r.when <= now
                    ),
                    tuple(e for b in files for e in b.edits if e.tool == tool and e.when <= now),
                    MODELS[:2],
                    ("high",),
                    (0, 1),
                    (0,),
                    ReaderCounters(files_read=1),
                )

            all_records, live = records(batches), records(disk)
            expected = measures.build(all_records, utc_offset=zone, now=now, keep=True)
            actual = measures.build(live, utc_offset=zone, now=now, keep=True, kept_rows=stored)
            assert expected.newest == actual.newest and expected.split_date == actual.split_date
            # Both runs use the same instant, offset and default options/window.
            clean = tuple(
                replace(
                    t,
                    before_days=tuple(
                        d.model_copy(update={"source": "logs"}) for d in t.before_days
                    ),
                    after_days=tuple(d.model_copy(update={"source": "logs"}) for d in t.after_days),
                )
                for t in actual.measures
            )
            same = clean == expected.measures
            lost += not same
            if not missing:
                assert same, ("kept day lists", seed, now, tool)
                left = decide.decide_tool(actual, live.counters)
                right = decide.decide_tool(expected, all_records.counters)
                assert (left.result, left.reason) == (right.result, right.reason)
                assert [(r.finding, r.p_real, r.p_none, r.p_streak) for r in left.measures] == [
                    (r.finding, r.p_real, r.p_none, r.p_streak) for r in right.measures
                ]
                # Every newly deleted complete day was captured with all its counts.
                newest = expected.newest
                assert newest is not None
                for row in expected.write_rows:
                    if date.fromisoformat(row.day) < (now - timedelta(days=30) + zone).date():
                        assert captured[row.key] == row, ("not captured whole", seed, row.key)
            comparisons += 1
            assert expected.settings_not_kept == expected.days_not_kept == 0
            assert actual.newest is not None
            stored = kept.merge(stored, actual.write_rows, {tool: actual.newest})
            for row in expected.write_rows:
                if date.fromisoformat(row.day) < (now + zone).date():
                    captured[row.key] = row
    if missing:
        assert lost > 0, ("uncaptured-day control", seed)
    return comparisons, lost


def retention_checks(count: int) -> None:
    print("\n## Kept-table checks\n")
    print(
        "Immutable records, no late backdated arrivals, whole-file deletion strictly after "
        "720 hours. Captures at most 29 days apart. Both tools, admitted rows, "
        "fixed offsets 0/+330/-480, identical instant/options/window. "
        "Day lists agree after removing source; results and exact tests agree. "
        "The long-gap control names the limit: a day never captured whole stays lost.\n"
    )
    print("| case | seed | histories | comparisons | mismatching histories (95% CI) |")
    print("|---|---:|---:|---:|---|")
    for label, missing, spanning, seed in (
        ("promise", False, False, SEED + 10000),
        ("boundary-spanning file", False, True, SEED + 20000),
        ("never captured whole (outside promise)", True, False, SEED + 30000),
    ):
        comparisons = mismatches = 0
        for i in range(count):
            checked, lost = retention_trial(seed + i, missing=missing, spanning=spanning)
            comparisons += checked
            mismatches += bool(lost)
        print(f"| {label} | {seed} | {count} | {comparisons} | {rate(mismatches, count)} |")
    print("Each row uses seeds seed through seed+histories-1. No filesystem logs are read.")


SECTIONS = {
    "null": "Null and exact reasoning-margin boundary",
    "settings": "Setting changes (gate)",
    "competitive": "Competitive setting choice (gate)",
    "assumptions": "Assumption failures (report only)",
    "power": "Power (report only)",
    "correlation": "Days that come in streaks (report only)",
    "cycles": "Weekly cycles and regime switches (report only)",
}


def header(section: str) -> None:
    print(f"\n## {SECTIONS[section]}\n")
    if section == "null":
        print(
            "Legacy direct-day generators: independent or identical oriented ranks. "
            "The shared-rank response counts depend on values; this legacy table checks "
            "unconditional day-value exchangeability, not the conditional A1 of logs/2. "
            "The next two gates exercise that conditional assumption through records.\n"
        )
    if section in ("settings", "competitive"):
        print(
            "14/16 days; independent day values given all response counts. "
            "Known counts 20/40/60/80/100; shares on a tenths grid; edits denominator 100. "
            "The competitive cell uses 40 known and 0..4 unknown responses per day for "
            "each rival. Old setting ends before adoption. All histories run production "
            "selection, reduction and decision. Null gates wrong REAL DROP; each "
            "single-measure exact-margin cell gates wrong NO DROP at <= 566/20000.\n"
        )
    if section == "assumptions":
        print(
            "Both generators break A1. Busy: same per-response law, 20 before vs 100 after, "
            "so medians/shares have count-dependent spread. New-model: first five days "
            "multiplied by 1.15, no shift at the split. A low rate does not establish A1.\n"
        )
    if section == "power":
        print(
            "Each cell stops at 2000 tested histories: all measures have enough days and "
            "the whole-comparison streak check passes. Generated includes stopped histories. "
            "No timing pilot. Wilson intervals with a stopped denominator are descriptive.\n"
        )
    if section in ("correlation", "cycles"):
        print(
            "AR(1) is stationary with independent Gaussian streams. Positive rho breaks A1. "
            "Weekly: random phase, seven-day sine, log amplitude 0.6. Regime: symmetric "
            "two-state chain, switch probability 0.08, log amplitude +/-0.6. Both break A1. "
            "Shares add round(10*(effect+1))/100 without clipping. Null reports wrong REAL "
            "DROP; exact token margin reports wrong NO DROP. The 9/20 row reports power. "
            "Per-measure passed means at least one measure passes; its conditional numerator "
            "uses the per-measure ladder. As-built passed means all three pass.\n"
        )
        columns = [
            "after/before",
            "rho" if section == "correlation" else "generator",
            "log SD",
            "drop",
            "metric",
            "seed",
            "histories",
            "no check (95% CI)",
            "per-measure check (95% CI)",
            "as built (95% CI)",
            "per-measure passed",
            "as-built passed",
            "per-measure conditional (95% CI)",
            "as-built conditional (95% CI)",
            "seconds",
        ]
    else:
        columns = [
            "after/before",
            "dependence" if section == "null" else "scenario",
            "log SD",
            "drop",
            "seed",
            "requested",
            "generated",
            "tested",
            "stopped",
            "REAL DROP (95% CI)",
            "NO DROP (95% CI)",
            "REAL DROP / tested (95% CI)",
            "NO DROP / tested (95% CI)",
            "choices old/current/rival",
            "seconds",
        ]
    print("| " + " | ".join(columns) + " |")
    print("|" + "---|" * len(columns))


def print_cell(cell: Cell, counts: Counts, seconds: float) -> None:
    c = counts
    if cell.section in ("correlation", "cycles"):
        error_none = cell.drop == F(1, 4)
        metric = "wrong NO DROP" if error_none else "REAL DROP" if cell.drop else "wrong REAL DROP"
        raw, per, built = (
            (c.raw_none, c.per_none, c.none) if error_none else (c.raw_real, c.per_real, c.real)
        )
        values = [
            f"{cell.m}/{cell.n}",
            str(cell.rho) if cell.section == "correlation" else cell.mode,
            str(cell.sigma),
            str(cell.drop),
            metric,
            str(cell.seed),
            str(c.generated),
            rate(raw, c.generated),
            rate(per, c.generated),
            rate(built, c.generated),
            str(c.per_tested),
            str(c.tested),
            rate(per, c.per_tested),
            rate(built, c.tested),
        ]
    else:
        values = [
            f"{cell.m}/{cell.n}",
            cell.mode,
            str(cell.sigma),
            str(cell.drop),
            str(cell.seed),
            str(cell.count),
            str(c.generated),
            str(c.tested),
            str(c.generated - c.tested),
            rate(c.real, c.generated),
            rate(c.none, c.generated),
            rate(c.real, c.tested),
            rate(c.none, c.tested),
            "/".join(map(str, c.choices)) or "n/a",
        ]
    print("| " + " | ".join([*values, f"{seconds:.3f}"]) + " |", flush=True)


def execute_cell(cell: Cell) -> Counts:
    if cell.section in ("settings", "competitive", "assumptions"):
        return setting_counts(cell)
    return counted_histories(cell)


def process_cell(item: tuple[int, bool]) -> tuple[Counts, float]:
    index, quick = item
    command = [sys.executable, "-m", "bench.selfcheck_logs", "--cell", str(index)]
    if quick:
        command.append("--quick")
    completed = subprocess.run(command, check=True, capture_output=True, text=True)
    # Child output has a fixed numeric protocol; reject missing or malformed fields.
    data: object = json.loads(completed.stdout)
    assert isinstance(data, list) and len(data) == 2
    values, seconds = data
    assert isinstance(values, list) and len(values) == 10
    assert all(type(v) is int for v in values[:9])
    choices = values[9]
    assert isinstance(choices, list) and all(type(v) is int for v in choices)
    assert isinstance(seconds, float)
    return Counts(*values[:9], choices=tuple(choices)), seconds


def run_cells(
    all_cells: list[Cell], quick: bool, workers: int
) -> Iterator[tuple[Cell, Counts, float]]:
    if workers == 1:
        for cell in all_cells:
            start = perf_counter()
            yield cell, execute_cell(cell), perf_counter() - start
        return
    # Bounded waves: no later wave starts before its preceding gates are checked.
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for start in range(0, len(all_cells), workers):
            wave = all_cells[start : start + workers]
            results = pool.map(process_cell, ((start + i, quick) for i in range(len(wave))))
            for cell, (counts, seconds) in zip(wave, results, strict=True):
                yield cell, counts, seconds


def gate_passes(cell: Cell, counts: Counts) -> bool:
    wrong = counts.none if cell.drop or cell.mode in MARGIN_MODES[1:] else counts.real
    return (
        counts.generated == cell.count
        and F(wrong, counts.generated) <= LIMIT
        and (cell.section != "competitive" or all(v > 0 for v in counts.choices[1:]))
    )


def run(quick: bool, stamp: str, workers: int = 1) -> int:
    started = perf_counter()
    print("# Session-log self-check\n")
    print(
        f"Date: {stamp}; seed base: {SEED}; method: arci-logs/2; "
        f"mode: {'quick' if quick else 'full'}."
    )
    print(
        f"Command: `.venv/bin/python -m bench.selfcheck_logs {'--quick ' if quick else ''}"
        f"--date {stamp} --workers {workers}`"
    )
    print(
        "\nSynthetic data only. Rates are k/n with Wilson 95% intervals at six decimals, "
        "copied without further rounding. Reasoning is log-normal, quantized to multiples "
        "of 100 before exact changes; independent shares are rounded "
        "0.10+0.25 Phi(Z) and 0.05+0.25 Phi(Z), denominator 100. "
        "Every table calls production decide_tool. Simulation gates check implementation; "
        "they do not prove assumptions about user logs. Quick mode is a smoke check only."
    )
    gates: list[tuple[str, bool]] = []
    exact(12 if quick else 14)
    gates.append(("exact enumeration and rejection levels", True))
    usable_days()
    gates.append(("selected-setting usable-day boundaries", True))
    retention_checks(2 if quick else 500)
    gates.append(("kept-table promise and limits", True))
    section = ""
    for cell, counts, seconds in run_cells(cells(quick), quick, workers):
        if cell.section != section:
            section = cell.section
            header(section)
        print_cell(cell, counts, seconds)
        if cell.section in ("null", "settings", "competitive"):
            passed = gate_passes(cell, counts)
            name = f"{cell.section} {cell.mode} {cell.m}/{cell.n} drop={cell.drop} seed={cell.seed}"
            gates.append((name, passed))
            if not passed:
                print(
                    "\nStopped at failed gate. Later cells were not run; "
                    "no threshold or seed changed."
                )
                return gate_summary(gates, started)
    print("\n## Assumption counterexamples (demonstrations, not valid product claims)\n")
    selection_demo()
    usability_demo()
    gates.append(("both assumption counterexamples exceed 1/40", True))
    return gate_summary(gates, started)


def gate_summary(gates: list[tuple[str, bool]], started: float) -> int:
    print("\n## Gates\n\n| gate | result |\n|---|---|")
    for name, passed in gates:
        print(f"| {name} | {'PASS' if passed else 'FAIL'} |")
    failures = sum(not passed for _, passed in gates)
    print(f"\nGate summary: {len(gates) - failures}/{len(gates)} passed; {failures} failed.")
    print(f"Elapsed: {perf_counter() - started:.3f} seconds.")
    return int(bool(failures))


class Transcript(io.StringIO):
    def write(self, text: str) -> int:
        if sys.__stdout__ is not None:
            sys.__stdout__.write(text)
            sys.__stdout__.flush()
        return super().write(text)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--date", type=date.fromisoformat)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--cell", type=int, help="run one deterministic cell, numeric JSON output")
    args = parser.parse_args(argv)
    if args.workers < 1:
        parser.error("workers must be positive")
    if args.cell is not None:
        cell = cells(bool(args.quick))[args.cell]
        started = perf_counter()
        c = execute_cell(cell)
        print(
            json.dumps(
                [
                    [
                        c.generated,
                        c.tested,
                        c.real,
                        c.none,
                        c.raw_real,
                        c.raw_none,
                        c.per_real,
                        c.per_none,
                        c.per_tested,
                        c.choices,
                    ],
                    perf_counter() - started,
                ]
            )
        )
        return 0
    if not args.quick and args.date is None:
        parser.error("full mode requires --date YYYY-MM-DD")
    output = Transcript()
    with redirect_stdout(output):
        try:
            code = run(bool(args.quick), str(args.date or date(2026, 11, 16)), args.workers)
        except AssertionError as exc:
            print(f"\nGate summary: FAIL; assertion {exc}. Stopped; later checks not run.")
            code = 1
    if not args.quick:
        target = Path(__file__).resolve().parents[1] / "docs/results/logs-selfcheck.md"
        target.write_text(output.getvalue(), encoding="utf-8")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
