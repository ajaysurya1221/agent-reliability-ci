"""Summarise reference-machine demo timings (docs/measurement/reference-machines/).

    python plan/exec/scripts/reference_stats.py reference-ubuntu-latest.json [more.json ...]

For each file (one OS per file, written by .github/workflows/ttfv-reference.yml) it first
validates the structure and the timestamps. An invalid file is reported as INVALID with its
problems and no figures. A valid file gets two blocks, never pooled:

- cold (each sample with its own empty uv cache, a first-time user): the `total` values
  (command_start -> all_steps_held, whole seconds), then p50 and p95 by nearest rank, each
  within or over the memo target (p50 <= 120 s, p95 <= 180 s). Fewer than five cold samples:
  raw values only, no percentile claim (protocol section 8.3).
- warm (cache already filled): the same figures, never compared with the memo target.

A sample that exited non-zero, timed out or never printed "All six steps held" has no total: it
is shown as failed and ranks above every finished sample, so it can only push a percentile up;
a percentile that lands on it is "not reached". It reports; it does not gate: the exit status
is always 0.
"""

from __future__ import annotations

import datetime as dt
import itertools
import json
import math
import sys
from pathlib import Path
from typing import Any, cast

TARGETS = {50: 120.0, 95: 180.0}  # percentile -> memo target in seconds
MIN_FOR_PERCENTILES = 5
STAMP = "%Y-%m-%dT%H:%M:%SZ"
CACHES = ("cold", "warm")
# Stamps a sample may carry, in the order they must occur.
ORDERED_STAMPS = ("command_start", "demo_banner", "demo_verdict", "all_steps_held")


def parse(stamp: object) -> dt.datetime | None:
    if not isinstance(stamp, str):
        return None
    try:
        return dt.datetime.strptime(stamp, STAMP)
    except ValueError:
        return None


def is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def sample_problems(where: str, sample: dict[str, Any]) -> list[str]:
    out: list[str] = []
    if not is_int(sample.get("sample")):
        out.append(f"{where}: 'sample' is not an integer")
    if sample.get("uv_cache") not in CACHES:
        out.append(f"{where}: 'uv_cache' is {sample.get('uv_cache')!r}, not cold or warm")
    timed_out = sample.get("timed_out", False)
    if not isinstance(timed_out, bool):
        out.append(f"{where}: 'timed_out' is not true or false")
    code = sample.get("exit_code", "missing")
    if not (is_int(code) or (code is None and timed_out is True)):
        out.append(f"{where}: 'exit_code' is {code!r} (null only for a timed-out sample)")
    if timed_out is True and sample.get("all_steps_held") is not None:
        out.append(f"{where}: timed out but 'all_steps_held' is set")
    if "all_steps_held" not in sample:
        out.append(f"{where}: 'all_steps_held' is missing")
    stamps: list[tuple[str, dt.datetime]] = []
    for key in ORDERED_STAMPS:
        value = sample.get(key)
        if value is None:
            if key == "command_start":
                out.append(f"{where}: 'command_start' is missing")
            continue
        when = parse(value)
        if when is None:
            out.append(f"{where}: {key!r} is {value!r}, not a UTC timestamp")
            continue
        stamps.append((key, when))
    for (k1, t1), (k2, t2) in itertools.pairwise(stamps):
        if t2 < t1:
            seconds = (t2 - t1).total_seconds()
            out.append(f"{where}: {k2} is before {k1} ({seconds:g} s, out of order)")
    return out


def problems(doc: object) -> list[str]:
    """Everything wrong with a reference JSON; empty when it can be summarised."""
    if not isinstance(doc, dict):
        return ["the top level is not an object"]
    samples = cast("dict[str, Any]", doc).get("samples")
    if not isinstance(samples, list):
        return ["'samples' is missing or not a list"]
    out: list[str] = []
    seen: set[int] = set()
    for i, sample in enumerate(cast("list[Any]", samples)):
        where = f"samples[{i}]"
        if not isinstance(sample, dict):
            out.append(f"{where} is {json.dumps(sample)}, not an object")
            continue
        typed = cast("dict[str, Any]", sample)
        out.extend(sample_problems(where, typed))
        n = typed.get("sample")
        if isinstance(n, int) and not isinstance(n, bool):
            if n in seen:
                out.append(f"{where}: sample number {n} appears twice")
            seen.add(n)
    return out


def total(sample: dict[str, Any]) -> float | None:
    """Seconds from command_start to all_steps_held; None if the sample did not hold."""
    if sample.get("timed_out") is True or sample.get("exit_code") != 0:
        return None
    start, held = parse(sample.get("command_start")), parse(sample.get("all_steps_held"))
    if start is None or held is None or held < start:
        return None
    return (held - start).total_seconds()


def nearest_rank(values: list[float | None], p: int) -> float | None:
    """Nearest-rank percentile; None (a failed sample) ranks above every number."""
    if not values:
        return None
    ranked = sorted(values, key=lambda v: math.inf if v is None else v)
    return ranked[max(1, math.ceil(p / 100 * len(ranked))) - 1]


def shown(sample: dict[str, Any], value: float | None) -> str:
    if value is not None:
        return f"{value:g} s"
    return "timed out" if sample.get("timed_out") is True else "failed"


def block(name: str, samples: list[dict[str, Any]], *, compare: bool) -> list[str]:
    totals = [total(s) for s in samples]
    raw = ", ".join(shown(s, t) for s, t in zip(samples, totals, strict=True)) or "none"
    lines = [f"  {name} totals ({len(samples)}): {raw}"]
    if len(samples) < MIN_FOR_PERCENTILES:
        claim = f"fewer than {MIN_FOR_PERCENTILES} samples, raw values only, no percentile claim"
    else:
        parts: list[str] = []
        for p, target in TARGETS.items():
            value = nearest_rank(totals, p)
            figure = "not reached" if value is None else f"{value:g} s"
            if compare:
                within = value is not None and value <= target
                figure += f" {'within' if within else 'over'} target (<= {target:g} s)"
            parts.append(f"p{p} {figure}")
        claim = "; ".join(parts)
        if len(samples) < 20:
            claim += f"; p95 of {len(samples)} is the maximum"
    if not compare:
        claim += "; warm samples are never compared with the memo target"
    return [*lines, f"  {name}: {claim}"]


def report(path: Path) -> list[str]:
    try:
        doc: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [f"{path.name}: unreadable ({exc.__class__.__name__}: {exc})"]
    found = problems(doc)
    if found:
        return [f"{path.name}: INVALID, no figures reported", *(f"  - {p}" for p in found)]
    data = cast("dict[str, Any]", doc)  # validated by problems()
    runner = data.get("runner")
    info = cast("dict[str, Any]", runner) if isinstance(runner, dict) else {}
    where = " ".join(str(info.get(k)) for k in ("os", "arch", "label") if info.get(k))
    lines = [f"{path.name}: {where or 'unknown runner'}, {data.get('package', '?')}"]
    samples: list[dict[str, Any]] = data["samples"]
    for cache in CACHES:
        chosen = [s for s in samples if s["uv_cache"] == cache]
        lines.extend(block(cache, chosen, compare=cache == "cold"))
    return lines


def main(argv: list[str]) -> int:
    if not argv:
        print((__doc__ or "").strip())
        return 0
    for arg in argv:
        print("\n".join(report(Path(arg))))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
