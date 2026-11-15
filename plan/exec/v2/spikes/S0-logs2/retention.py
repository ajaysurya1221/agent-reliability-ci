"""Pure M4 row operations and seeded retention properties; no persisted user data."""

from __future__ import annotations

import json
import random
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

sys.path.insert(0, "/Users/ajay/Developer/.arci-worktrees/wt-v2-logs")
sys.path.insert(0, "/Users/ajay/Developer/.arci-worktrees/wt-v2-logs/src")
from arci.logs.records import EFFORTS, render_model
from bench.selfcheck_logs import rate

ROOT = Path("/Users/ajay/Developer/.arci-worktrees/wt-v2-logs")
HERE = Path(__file__).resolve().parent
BASE = 17112026
Setting = tuple[str, str]
Key = tuple[str, int, Setting, int]


@dataclass(frozen=True)
class Counts:
    responses: int
    histogram: tuple[tuple[int, int], ...]
    unknown: int
    edits: int
    failed: int


Rows = dict[Key, Counts]


@dataclass(frozen=True)
class Batch:
    hour: int
    tool: str
    setting: Setting
    counts: Counts


def combine(values: list[Counts]) -> Counts:
    histogram: Counter[int] = Counter()
    for value in values:
        histogram.update(dict(value.histogram))
    return Counts(
        sum(v.responses for v in values),
        tuple(sorted(histogram.items())),
        sum(v.unknown for v in values),
        sum(v.edits for v in values),
        sum(v.failed for v in values),
    )


def write_rows(kept: Rows, logs: Rows, newest: int) -> tuple[Rows, int, int]:
    """Replace on >= response count; bounded-setting and distinct-count admission; age cap."""
    merged = {k: v for k, v in kept.items() if k[3] >= newest - 180}
    rejected_names = rejected_counts = 0
    for key, row in logs.items():
        if key[3] < newest - 180:
            continue
        if render_model(key[2][0]) is None or key[2][1] not in EFFORTS:
            rejected_names += 1
            continue
        if len(row.histogram) > 5000:
            rejected_counts += 1
            continue
        if key not in merged or row.responses >= merged[key].responses:
            merged[key] = row
    return merged, rejected_names, rejected_counts


def use_rows(
    kept: Rows, logs: Rows, offset: int, first: int, newest: int
) -> tuple[Rows, dict[Key, str], int]:
    used = {k: v for k, v in logs.items() if k[1] == offset and first <= k[3] <= newest}
    sources = {k: "logs" for k in used}
    ignored = 0
    for key, row in kept.items():
        if key[1] != offset:
            ignored += 1
            continue
        if not first <= key[3] <= newest:
            continue
        if key not in used or row.responses > used[key].responses:
            used[key] = row
            sources[key] = "kept"
    return used, sources, ignored


def reduce_batches(batches: list[Batch], now: int, offset: int = 0) -> Rows:
    grouped: dict[Key, list[Counts]] = defaultdict(list)
    for batch in batches:
        if batch.hour <= now:
            key = (batch.tool, offset, batch.setting, (batch.hour * 60 + offset) // 1440)
            grouped[key].append(batch.counts)
    return {key: combine(values) for key, values in grouped.items()}


def generate(rng: random.Random) -> list[Batch]:
    batches: list[Batch] = []
    for day in range(98):
        for tool in ("claude-code", "codex"):
            setting = (
                rng.choice(("claude-opus-4", "claude-sonnet-4", "gpt-5")),
                rng.choice(("high", "low")),
            )
            for hour in (0, 6, 12, 18):
                known = rng.randrange(5, 31)
                zero = rng.randrange(known + 1)
                unknown = rng.randrange(5)
                value = rng.randrange(1, 2000)
                edits = rng.randrange(20) if tool == "claude-code" else 0
                failed = rng.randrange(edits + 1)
                histogram = tuple((k, v) for k, v in ((0, zero), (value, known - zero)) if v)
                batches.append(
                    Batch(
                        day * 24 + hour,
                        tool,
                        setting,
                        Counts(known + unknown, histogram, unknown, edits, failed),
                    )
                )
    return batches


def trial(rng: random.Random, long_gap: bool) -> dict[str, int]:
    full = generate(rng)
    first_hour = rng.randrange(0, 10 * 24)
    final_hour = 97 * 24 + rng.randrange(24)
    runs = [first_hour]
    while runs[-1] < final_hour:
        gap = rng.randrange(31 * 24, 45 * 24 + 1) if long_gap else rng.randrange(1, 29 * 24 + 1)
        runs.append(min(final_hour, runs[-1] + gap))
    disk = full.copy()
    kept: Rows = {}
    expected: Rows = {}
    actual: Rows = {}
    whole = partial = refreshed = 0
    for now in runs:
        # Delete only batches older than 30 exact 24-hour days. Some days are
        # wholly deleted; others lose selected 6-hour batches, so histograms change.
        modes = {day: rng.randrange(3) for day in range(now // 24 - 29)}
        remaining: list[Batch] = []
        for batch in disk:
            mode = modes.get(batch.hour // 24, 0)
            remove = batch.hour < now - 30 * 24 and (
                mode == 1 or (mode == 2 and rng.random() < 0.5)
            )
            if remove:
                whole += mode == 1
                partial += mode == 2
            else:
                remaining.append(batch)
        disk = remaining
        logs = reduce_batches(disk, now)
        refreshed += sum(k in kept and v.responses > kept[k].responses for k, v in logs.items())
        used, _, ignored = use_rows(kept, logs, 0, now // 24 - 97, now // 24)
        assert ignored == 0
        expected = {
            k: v
            for k, v in reduce_batches(full, now).items()
            if first_hour // 24 <= k[3] <= now // 24
        }
        actual = {k: v for k, v in used.items() if k[3] >= first_hour // 24}
        if not long_gap:
            assert actual == expected, ("short-gap mismatch", runs, now)
        kept, bad_name, bad_count = write_rows(kept, logs, now // 24)
        assert bad_name == bad_count == 0
    missing = sum(k not in actual for k in expected)
    different = sum(k in actual and actual[k] != v for k, v in expected.items())
    deficit = sum(
        v.responses - actual[k].responses if k in actual else v.responses
        for k, v in expected.items()
    )
    # At changed offset, compare with fresh logs reduced in that offset, never
    # with rows whose date bins were computed in the previous offset.
    new_offset = rng.choice((-480, 330, 345))
    fresh = reduce_batches(disk, final_hour, new_offset)
    newest = (final_hour * 60 + new_offset) // 1440
    mixed, sources, ignored = use_rows(kept, fresh, new_offset, newest - 97, newest)
    expected_fresh = {k: v for k, v in fresh.items() if newest - 97 <= k[3] <= newest}
    assert mixed == expected_fresh and ignored == len(kept)
    assert set(sources.values()) <= {"logs"}
    # Writing new-offset rows preserves independent old-offset keys.
    updated, _, _ = write_rows(kept, fresh, newest)
    assert all(updated[k] == v for k, v in kept.items())
    return {
        "mismatch": int(bool(missing or different)),
        "missing_rows": missing,
        "partial_rows": different,
        "response_deficit": deficit,
        "ignored": ignored,
        "whole_deleted_batches": whole,
        "partial_deleted_batches": partial,
        "refreshed": refreshed,
        "runs": len(runs),
    }


def edge_checks() -> dict[str, int]:
    key: Key = ("claude-code", 0, ("claude-sonnet-4", "high"), 10)
    a = Counts(20, ((0, 2), (100, 18)), 0, 12, 1)
    fewer = Counts(10, ((100, 10),), 0, 5, 0)
    equal = Counts(20, ((100, 20),), 0, 15, 2)
    more = Counts(21, ((100, 21),), 0, 15, 2)
    for logs, expected in ((fewer, a), (equal, equal), (more, more)):
        kept: Rows = {key: a}
        original = kept.copy()
        written, _, _ = write_rows(kept, {key: logs}, 10)
        used, sources, _ = use_rows(kept, {key: logs}, 0, 0, 10)
        assert written[key] == used[key] == expected
        assert sources[key] == ("kept" if logs.responses < 20 else "logs")
        assert kept == original
    assert write_rows({key: a}, {}, 190)[0] == {key: a}
    assert write_rows({key: a}, {}, 191)[0] == {}
    invalid: Key = ("claude-code", 0, ("secret arbitrary log string", "high"), 10)
    oversized = Counts(5001, tuple((i, 1) for i in range(5001)), 0, 0, 0)
    assert write_rows({}, {invalid: a, key: oversized}, 10) == ({}, 1, 1)
    limit = Counts(5000, tuple((i, 1) for i in range(5000)), 0, 0, 0)
    assert write_rows({}, {key: limit}, 10)[0] == {key: limit}
    # Limits of the literal rule, outside the gated fixed-offset, 98-day property.
    # Edited equal-size logs replace, and a new-day response count cannot recover
    # older rows dropped by the 180-day cap.
    return {
        "tie_replace": 1,
        "smaller_preserved": 1,
        "larger_replace": 1,
        "180_day_cap": 1,
        "names_and_histogram_cap": 1,
    }


def main() -> None:
    edge_checks()
    results: list[dict[str, int | float | str]] = []
    for long_gap in (False, True):
        seed = BASE + 4000 + int(long_gap)
        rng = random.Random(seed)
        start = perf_counter()
        totals: Counter[str] = Counter()
        maximum = 0
        for _ in range(500):
            row = trial(rng, long_gap)
            totals.update(row)
            maximum = max(maximum, row["response_deficit"])
        result: dict[str, int | float | str] = dict(totals)
        result.update(
            seed=seed,
            mode="31-45 days" if long_gap else "at most 29 days",
            histories=500,
            seconds=round(perf_counter() - start, 3),
            max_response_deficit=maximum,
        )
        results.append(result)
        print(json.dumps(result), flush=True)
        print("mismatching histories: " + rate(totals["mismatch"], 500), flush=True)
    (HERE / "retention.json").write_text(json.dumps(results, indent=2) + "\n")
    print(
        "G4 PASS: 500 short-gap histories, 500 long-gap controls, 1000 offset checks, edge checks"
    )


if __name__ == "__main__":
    main()
