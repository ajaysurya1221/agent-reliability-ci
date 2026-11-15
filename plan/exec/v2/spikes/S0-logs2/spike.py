"""Scratch-only S0: seeded setting-change simulations using the product decision path."""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import subprocess
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, replace
from datetime import UTC, date, timedelta
from fractions import Fraction as F
from pathlib import Path
from time import perf_counter

sys.path.insert(0, "/Users/ajay/Developer/.arci-worktrees/wt-v2-logs")
sys.path.insert(0, "/Users/ajay/Developer/.arci-worktrees/wt-v2-logs/src")
from arci.logs import decide, measures
from arci.logs.records import EditResult, ReaderCounters, ReadResult, Response
from arci.logs.schema import ContextCounts, DayValue, Period
from bench.selfcheck_logs import START, day_records, history_days

ROOT = Path("/Users/ajay/Developer/.arci-worktrees/wt-v2-logs")
HERE = Path(__file__).resolve().parent
BASE = 17112026
MODELS = ("claude-opus-4", "claude-sonnet-4", "claude-haiku-4")
DESIGNS = ((5, 10), (7, 21), (14, 16), (14, 42))
NOW = START + timedelta(days=98)
SPLIT = (START + timedelta(days=84)).date()


@dataclass(frozen=True)
class Day:
    index: int
    model: int
    value: int
    zero: int
    known: int
    unknown: int
    failed: int
    edits: int

    @property
    def responses(self) -> int:
        return self.known + self.unknown


@dataclass(frozen=True)
class Job:
    id: int
    gate: str
    a: int
    b: int
    mode: str
    sigma: float = 0.45
    drop: F = F(0)

    @property
    def seed(self) -> int:
        return BASE + self.id


def jobs() -> list[Job]:
    result: list[Job] = []
    for a, b in DESIGNS:
        for mode in ("null", "token-margin", "share-margin"):
            result.append(Job(len(result), "G1", a, b, mode))
    for mode in ("busy", "new-model"):
        for a, b in ((14, 16), (7, 21)):
            result.append(Job(len(result), "G2", a, b, mode))
    for a, b in ((5, 10), (14, 16), (14, 42)):
        for sigma in (0.40, 0.45):
            for drop in (F(33, 100), F(45, 100), F(55, 100)):
                result.append(Job(len(result), "G3", a, b, "power", sigma, drop))
    return result


def override_names(
    values: tuple[str | None, ...], order: tuple[int, ...], prefix: str
) -> dict[int, str]:
    """Match the existing override aliases without exposing unknown raw log strings."""
    names: dict[int, str] = {}
    unknown = 0
    for index in order:
        name = values[index]
        if name is None:
            unknown += 1
            name = f"{prefix}-{unknown}"
        names[index] = name
    return names


def choose_m2(result: ReadResult, first_after: date, newest: date) -> tuple[str, str] | None:
    """Count all identities, including opaque names; reader orders preserve raw lexical ties."""
    counts: Counter[tuple[int, int]] = Counter()
    for response in result.responses:
        if not response.main_thread or not response.in_project:
            continue
        if response.when.tzinfo is None or response.when > NOW:
            continue
        day = response.when.astimezone(UTC).date()
        if first_after <= day <= newest:
            counts[response.model, response.effort] += 1
    if not counts:
        return None
    model_ranks = {value: i for i, value in enumerate(result.model_order)}
    effort_ranks = {value: i for i, value in enumerate(result.effort_order)}
    chosen = min(
        counts, key=lambda pair: (-counts[pair], model_ranks[pair[0]], effort_ranks[pair[1]])
    )
    return (
        override_names(result.models, result.model_order, "model")[chosen[0]],
        override_names(result.efforts, result.effort_order, "effort")[chosen[1]],
    )


def generate(rng: random.Random, job: Job, history_index: int) -> list[Day]:
    """Independent latent day values, with exact representable changes and fixed usability."""
    current = history_days(rng, job.a, job.b, job.sigma, F(0))
    indices = list(range(84 - job.b, 84)) + list(range(98 - job.a, 98))
    days: list[Day] = []
    for i, (index, raw) in enumerate(zip(indices, current, strict=True)):
        value, zeros, _, failed, edits = raw
        known = rng.choice((20, 40, 60, 80, 100))
        unknown = rng.randrange(21)
        # Coarsen the latent share BEFORE applying any shift. This makes its
        # distribution independent of the random response count, even conditionally.
        zero_tenths = round(zeros / 10)
        zero = zero_tenths * known // 10
        if job.mode == "busy":
            # Same mechanism in both periods; all days remain usable.
            value = 100 * max(1, round(value * math.exp(-0.012 * (known + unknown - 70)) / 100))
        if job.mode == "new-model" and i < 5:
            value = int(F(115, 100) * value)
        if i >= job.b:
            drop = F(1, 4) if job.mode == "token-margin" else job.drop
            moved = value * (1 - drop)
            assert moved.denominator == 1
            value = int(moved)
            if job.mode == "share-margin":
                zero += known // 10
        days.append(Day(index, 1, value, zero, known, unknown, failed, edits))
    old_days = history_days(rng, 0, 84 - job.b, job.sigma, F(0))
    for index, (value, zero, _, failed, edits) in enumerate(old_days):
        known = rng.choice((60, 80, 100))
        days.append(
            Day(
                index,
                0,
                2 * value,
                (round(zero / 10) - 1) * known // 10,
                known,
                rng.randrange(21),
                failed,
                edits,
            )
        )
    if history_index % 2 == 0:
        for index in sorted(rng.sample(range(84, 98), 6)):
            value = 50 * max(1, round(100 * math.exp(job.sigma * rng.gauss(0, 1))))
            days.append(Day(index, 2, value, 2, 4, 2, 0, 0))
    return sorted(days, key=lambda d: (d.index, d.model))


def expand(days: list[Day]) -> ReadResult:
    responses: list[Response] = []
    edits: list[EditResult] = []
    for d in days:
        rows, results = day_records(d.index, d.value, d.zero, d.known, d.failed, d.edits, d.model)
        responses.extend(rows)
        responses.extend(
            [
                Response(
                    "claude-code",
                    START + timedelta(days=d.index),
                    d.model,
                    0,
                    True,
                    None,
                    0,
                    0,
                    True,
                )
            ]
            * d.unknown
        )
        edits.extend(results)
    return ReadResult(
        "claude-code",
        tuple(responses),
        tuple(edits),
        MODELS,
        ("high",),
        tuple(sorted(range(3), key=lambda i: MODELS[i])),
        (0,),
        ReaderCounters(
            files_read=1,
            responses=len(responses),
            responses_without_reasoning=sum(d.unknown for d in days),
        ),
    )


def fast_table(days: list[Day]) -> measures.ToolTable:
    chosen = [d for d in days if d.model == 1]
    tables: list[measures.MeasureTable] = []
    for name in ("reasoning_tokens", "no_reasoning_share", "edit_failure_share"):
        values: list[DayValue] = []
        for d in chosen:
            if name == "reasoning_tokens":
                value, count = F(d.value), d.known - d.zero
            elif name == "no_reasoning_share":
                value, count = F(d.zero, d.known), d.known
            else:
                value, count = F(d.failed, d.edits), d.edits
            values.append(
                DayValue(
                    day=(START + timedelta(days=d.index)).date().isoformat(),
                    count=count,
                    value=measures.fraction_str(value),
                )
            )
        tables.append(
            measures.MeasureTable(
                name,
                tuple(v for v in values if v.day < SPLIT.isoformat()),
                tuple(v for v in values if v.day >= SPLIT.isoformat()),
            )
        )
    positive: Counter[int] = Counter()
    for d in chosen:
        positive[d.value] += d.known - d.zero
    return measures.ToolTable(
        "claude-code",
        MODELS[1],
        "high",
        len({d.model for d in days}) - 1,
        SPLIT.isoformat(),
        Period(
            first_day=START.date().isoformat(),
            last_day=(START + timedelta(days=83)).date().isoformat(),
        ),
        Period(
            first_day=SPLIT.isoformat(), last_day=(START + timedelta(days=97)).date().isoformat()
        ),
        tuple(tables),
        ContextCounts(
            client_versions_before=1,
            client_versions_after=1,
            client_versions_both=1,
            workdirs_before=1,
            workdirs_after=1,
            subagent_share_before="0/1",
            subagent_share_after="0/1",
        ),
        min(positive, key=lambda x: (-positive[x], x)),
    )


def edge_checks() -> None:
    # Equal after counts: lexical raw model wins, not numeric identity nor known counts.
    r = Response("claude-code", START + timedelta(days=97), 1, 0, True, 1, 0, 0, True)
    rr = ReadResult(
        "claude-code",
        (r, replace(r, model=0, reasoning=None)),
        (),
        MODELS,
        ("high",),
        (2, 0, 1),
        (0,),
        ReaderCounters(),
    )
    assert choose_m2(rr, SPLIT, r.when.date()) == (MODELS[0], "high")
    rr = replace(rr, responses=(*rr.responses, replace(r, model=0, reasoning=None)))
    assert choose_m2(rr, SPLIT, r.when.date()) == (MODELS[0], "high")
    extras = (
        replace(r, main_thread=False),
        replace(r, in_project=False),
        replace(r, when=START),
        replace(r, when=NOW + timedelta(days=1)),
    ) * 20
    assert choose_m2(replace(rr, responses=rr.responses + extras), SPLIT, r.when.date()) == (
        MODELS[0],
        "high",
    )
    opaque = replace(rr, models=(None, None, None), efforts=(None,))
    assert choose_m2(opaque, SPLIT, r.when.date()) == ("model-2", "effort-1")
    selected_opaque = choose_m2(opaque, SPLIT, r.when.date())
    assert selected_opaque is not None
    opaque_table = measures.build(
        opaque,
        utc_offset=timedelta(),
        now=NOW,
        since=SPLIT,
        model=selected_opaque[0],
        effort=selected_opaque[1],
    )
    assert (opaque_table.model, opaque_table.effort) == selected_opaque
    assert choose_m2(replace(rr, responses=()), SPLIT, r.when.date()) is None
    assert choose_m2(rr, r.when.date() + timedelta(days=1), r.when.date()) is None
    # Effort is the second element of the raw lexical tie break.
    effort_rr = replace(
        rr, responses=(r, replace(r, effort=1)), efforts=("high", "low"), effort_order=(0, 1)
    )
    assert choose_m2(effort_rr, SPLIT, r.when.date()) == (MODELS[1], "high")


def run_cell(job: Job, count: int | None = None) -> dict[str, int | float | str]:
    start = perf_counter()
    rng = random.Random(job.seed)
    wanted = count if count is not None else (2000 if job.gate == "G3" else 20000)
    real = none = tested = generated = old = verified = 0
    while (tested if job.gate == "G3" else generated) < wanted:
        days = generate(rng, job, generated)
        table = fast_table(days)
        counts = ReaderCounters(
            files_read=1,
            responses=sum(d.responses for d in days),
            responses_without_reasoning=sum(d.unknown for d in days),
        )
        decision = decide.decide_tool(table, counts)
        assert all(
            len(m.before_days) == job.b and len(m.after_days) == job.a for m in table.measures
        )
        pooled: Counter[int] = Counter()
        after: Counter[int] = Counter()
        for d in days:
            pooled[d.model] += d.responses
            if d.index >= 84:
                after[d.model] += d.responses
        assert min(after, key=lambda m: (-after[m], MODELS[m])) == 1
        old += min(pooled, key=lambda m: (-pooled[m], MODELS[m])) == 0
        if generated < 500 and job.gate == "G1":
            records = expand(days)
            selected = choose_m2(records, SPLIT, (START + timedelta(days=97)).date())
            assert selected is not None
            assert selected == (MODELS[1], "high")
            actual = measures.build(
                records,
                utc_offset=timedelta(),
                now=NOW,
                since=SPLIT,
                model=selected[0],
                effort=selected[1],
            )
            assert actual == table, ("day table differs", job.id, generated)
            assert decide.decide_tool(actual, records.counters) == decision
            assert (
                measures.build(records, utc_offset=timedelta(), now=NOW, since=SPLIT).model
                == MODELS[min(pooled, key=lambda m: (-pooled[m], MODELS[m]))]
            )
            verified += 1
        real += decision.result == "REAL_DROP"
        none += decision.result == "NO_DROP"
        tested += decision.reason != "streaky_days"
        generated += 1
    result: dict[str, int | float | str] = {
        "id": job.id,
        "gate": job.gate,
        "design": f"{job.a}/{job.b}",
        "mode": job.mode,
        "sigma": job.sigma,
        "drop": str(job.drop),
        "seed": job.seed,
        "generated": generated,
        "tested": tested,
        "real": real,
        "none": none,
        "old": old,
        "verified": verified,
        "seconds": round(perf_counter() - start, 3),
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cell", type=int)
    parser.add_argument("--gate", choices=("G1", "G2", "G3", "all"), default="all")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--verify-records", action="store_true")
    args = parser.parse_args()
    edge_checks()
    if args.verify_records:
        started = perf_counter()
        for job in jobs():
            if job.gate == "G1":
                result = run_cell(job, 500)
                assert result["verified"] == 500
                print(json.dumps(result), flush=True)
        print(f"RECORD PATH PASS: 6000/6000; seconds={perf_counter() - started:.3f}")
        return
    if args.smoke:
        for job in jobs():
            print(json.dumps(run_cell(job, 2)), flush=True)
        print("SMOKE PASS: all 34 cell shapes and M2 edge checks")
        return
    if args.cell is not None:
        result = run_cell(jobs()[args.cell])
        (HERE / f"cell-{args.cell:02d}.json").write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result), flush=True)
        return
    started = perf_counter()
    selected = [j for j in jobs() if args.gate == "all" or j.gate == args.gate]

    def execute(job: Job) -> str:
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        completed = subprocess.run(
            [sys.executable, "-B", str(Path(__file__)), "--cell", str(job.id)],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode:
            raise RuntimeError(f"cell {job.id}: {completed.stdout}\n{completed.stderr}")
        return completed.stdout.strip()

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(execute, j) for j in selected]
        for future in as_completed(futures):
            print(future.result(), flush=True)
    elapsed = perf_counter() - started
    (HERE / f"timing-{args.gate}.json").write_text(
        json.dumps({"seconds": elapsed, "workers": args.workers}) + "\n"
    )
    print(f"COMPLETE {args.gate}: {len(selected)} cells in {elapsed:.3f}s", flush=True)


if __name__ == "__main__":
    main()
