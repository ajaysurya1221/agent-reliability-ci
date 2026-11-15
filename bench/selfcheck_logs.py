"""Exact checks and seeded final-rule simulations on synthetic in-memory records.

Run: .venv/bin/python -m bench.selfcheck_logs --date YYYY-MM-DD
A short pilot fixes each cell's count before collecting it, to bound laptop runtime.
"""

from __future__ import annotations

import argparse
import io
import math
import random
import sys
from collections import Counter
from collections.abc import Sequence
from contextlib import redirect_stdout
from datetime import UTC, date, datetime, timedelta
from fractions import Fraction as F
from itertools import combinations
from pathlib import Path
from statistics import NormalDist
from time import perf_counter

from arci.logs import decide, measures, rank_test
from arci.logs.records import EditResult, ReaderCounters, ReadResult, Response
from arci.logs.schema import ContextCounts, DayValue, Period, ToolDecision

DESIGNS = ((5, 10), (7, 21), (14, 42), (28, 84))
START = datetime(2026, 1, 1, 12, tzinfo=UTC)
SEED = 16112026
LIMIT = F(283, 10000)


def rate(k: int, n: int) -> str:
    """Display-only Wilson 95% interval, always with its numerator/denominator."""
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
        # A second setting and unusable records exercise pooled selection and filtering.
        responses.append(
            Response("claude-code", START + timedelta(days=i), 1, 0, True, None, 0, 0, True)
        )
    return read_result(responses, edits)


def streak_table(
    rng: random.Random, m: int, n: int, sigma: float, drop: F, rho: float
) -> measures.ToolTable:
    """Section 4 only: exactly the same synthetic days, without expanding responses."""
    days = history_days(rng, m, n, sigma, drop, rho=rho)
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
        context=ContextCounts(
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
) -> tuple[int, int, int, int, int]:
    def trial(rng: random.Random) -> tuple[ToolDecision, str]:
        result = history(rng, m, n, sigma, drop, shared, rho)
        table = table_of(result, n)
        assert table.model == "model-1" and table.other_settings == 1
        assert all(len(row.before_days) == n and len(row.after_days) == m for row in table.measures)
        decision = decide.decide_tool(table, result.counters)
        unguarded = without_streak(table) if rho else decision.result
        return decision, unguarded

    # Separate pilot seed; count is fixed before the measured stream starts.
    started = perf_counter()
    pilot = random.Random(f"{seed}:timing-only")
    for _ in range(3):
        trial(pilot)
    seconds = (perf_counter() - started) / 3
    count = requested if not budget else max(30, min(requested, int(budget / seconds)))
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
    # Move the split; pooled winner must stay the fixed lexical-first identity.
    for n in (10, 9, 8):
        assert table_of(result, n).model == "model-1"
    print(
        "Demonstration outside A2: 15 days / 3,003 models; after-count selection "
        "rejects in 3003/3003 labelings, p_real=1/3003 every time. "
        "Product pooled counts are all 305 and select model-1 for every checked split."
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


def run(quick: bool, stamp: str) -> int:
    started = perf_counter()
    print("# Session-log self-check\n")
    print(f"Date: {stamp}; seed base: {SEED}; mode: {'quick' if quick else 'full'}.")
    print(
        "Command: `.venv/bin/python -m bench.selfcheck_logs "
        f"{'--quick ' if quick else ''}--date {stamp}`"
    )
    print(
        "\nAll simulated rates include counts and Wilson 95% intervals. Claude Code's three "
        "measures are generated through Response/EditResult -> measures.build -> decide_tool. "
        "Reasoning: log-normal, quantized to multiples of 100 before exact changes. "
        "Independent shares: rounded (0.10+0.25 Phi(Z)) and (0.05+0.25 Phi(Z)), denominator 100. "
        "Shared ranks: both shares 10/(20+pooled reasoning rank), oriented alike. "
        "AR(1): stationary Gaussian innovations on all three independent latent streams. "
        "Pilot-based count reductions use timing only, never measured outcomes; "
        "requested and actual counts are printed. "
        "Simulation gates are implementation checks, not proofs."
    )
    gates: list[tuple[str, bool]] = []
    exact(12 if quick else 14)
    gates.append(("exact enumeration and rejection levels", True))
    usable_days()
    gates.append(("selected-setting usable-day boundaries", True))
    print("\n## Null and exact reasoning-margin boundary\n")
    print(
        "| after/before | dependence | drop | seed | requested | "
        "REAL DROP (95% CI) | NO DROP (95% CI) | seconds |"
    )
    print("|---|---|---|---:|---:|---|---|---:|")
    cell = 0
    for m, n in ((7, 21),) if quick else DESIGNS:
        for shared in (False, True):
            for drop in (F(0), F(1, 4)):
                seed = SEED + cell
                cell += 1
                start = perf_counter()
                requested = 300 if quick else 20000
                real, none, _, _, count = simulate(
                    m, n, 0.45, drop, seed, requested, 0 if quick else 25, shared
                )
                dependence = "shared" if shared else "independent"
                name = f"{'null REAL' if not drop else 'margin NO'} {m}/{n} {dependence}"
                gates.append((name, F(none if drop else real, count) <= LIMIT))
                print(
                    f"| {m}/{n} | {dependence} | {drop} | {seed} | {requested} | "
                    f"{rate(real, count)} | {rate(none, count)} | {perf_counter() - start:.2f} |",
                    flush=True,
                )
    print("\n## Power (report only)\n")
    print(
        "| after/before | log SD | drop | seed | requested | "
        "REAL DROP (95% CI) | NO DROP (95% CI) | seconds |"
    )
    print("|---|---|---|---:|---:|---|---|---:|")
    if quick:
        print("Skipped in quick mode.")
    else:
        cells = [
            (m, n, sd, drop)
            for m, n in DESIGNS
            for sd in (0.35, 0.45, 0.55)
            for drop in (F(0), F(33, 100), F(45, 100), F(1, 2), F(55, 100))
        ]
        cells.append((14, 42, 0.40, F(45, 100)))
        for m, n, sd, drop in cells:
            seed = SEED + 1000 + cell
            cell += 1
            start = perf_counter()
            real, none, _, _, count = simulate(m, n, sd, drop, seed, 2000, 4)
            print(
                f"| {m}/{n} | {sd} | {drop} | {seed} | 2000 | "
                f"{rate(real, count)} | {rate(none, count)} | "
                f"{perf_counter() - start:.2f} |",
                flush=True,
            )
    print("\n## Days that come in streaks (report only)\n")
    print(
        "rho=0 has independent days; positive rho breaks A1. At drop=0, REAL DROP is "
        "the directional error; at drop=1/4, NO DROP is the directional error. "
        "The power row reports REAL DROP at a 45% drop and log SD 0.40. "
        "Section 4 builds day tables directly from the same generator (unit-checked "
        "against full Response/EditResult reduction); the production exact tests and "
        "decide_tool still run. No timing-based count reductions in this section.\n"
    )
    print(
        "| after/before | rho | log SD | drop | metric | seed | histories | "
        "no check (95% CI) | per-measure check (95% CI) | as built (95% CI) | seconds |"
    )
    print("|---|---|---|---|---|---:|---:|---|---|---|---:|")
    if quick:
        print("Skipped in quick mode.")
    else:
        streak_cells = [
            (m, n, rho, 0.45, drop)
            for m, n in DESIGNS
            for rho in (0.0, 0.3, 0.5, 0.7)
            for drop in (F(), F(1, 4))
        ]
        streak_cells.append((14, 42, 0.0, 0.40, F(45, 100)))
        for m, n, rho, sd, drop in streak_cells:
            seed = SEED + 2000 + cell
            cell += 1
            count = 1000 if (m, n) == (28, 84) else 2000
            start = perf_counter()
            variants = simulate_streaks(m, n, sd, drop, seed, count, rho)
            metric = (
                "wrong NO DROP"
                if drop == F(1, 4)
                else "wrong REAL DROP"
                if not drop
                else "REAL DROP"
            )
            index = int(drop == F(1, 4))
            rates = " | ".join(rate(tally[index], count) for tally in variants)
            print(
                f"| {m}/{n} | {rho} | {sd} | {drop} | {metric} | {seed} | {count} | "
                f"{rates} | {perf_counter() - start:.2f} |",
                flush=True,
            )
    print("\n## Assumption counterexamples (demonstrations, not valid product claims)\n")
    selection_demo()
    usability_demo()
    gates.append(("both assumption counterexamples exceed 1/40", True))
    print("\n## Gates\n\n| gate | result |\n|---|---|")
    for name, passed in gates:
        print(f"| {name} | {'PASS' if passed else 'FAIL'} |")
    print(f"\nElapsed: {perf_counter() - started:.3f} seconds.")
    return 0 if all(passed for _, passed in gates) else 1


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
    args = parser.parse_args(argv)
    if not args.quick and args.date is None:
        parser.error("full mode requires --date YYYY-MM-DD")
    output = Transcript()
    with redirect_stdout(output):
        try:
            code = run(bool(args.quick), str(args.date or date(2026, 11, 15)))
        except AssertionError as exc:
            print(f"\n| gate | result |\n|---|---|\n| assertion {exc} | FAIL |")
            code = 1
    text = output.getvalue()
    if not args.quick:
        target = Path(__file__).resolve().parents[1] / "docs/results/logs-selfcheck.md"
        target.write_text(text, encoding="utf-8")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
