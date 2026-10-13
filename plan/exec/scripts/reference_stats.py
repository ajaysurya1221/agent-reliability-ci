"""Summarise reference-machine demo timings (docs/measurement/reference-machines/).

    python plan/exec/scripts/reference_stats.py reference-ubuntu-latest.json [more.json ...]

For each file (one OS per file, written by .github/workflows/ttfv-reference.yml) it first
validates the structure, the timestamps and that no sample contradicts itself. An invalid file
is reported as INVALID with its problems and no figures. A valid file gets two blocks, never
pooled:

- cold (each sample with its own empty uv cache, a first-time user): the `total` values
  (command_start -> all_steps_held, whole seconds), then p50 and p95 by nearest rank, each
  within or over the memo target (p50 <= 120 s, p95 <= 180 s). Fewer than five cold samples:
  raw values only, no percentile claim (protocol section 8.3).
- warm (cache already filled): the same figures, never compared with the memo target.

A sample succeeds only if it started, did not time out, exited 0 and carries all four stamps
(command_start, demo_banner, demo_verdict, all_steps_held) in order. Every other sample has no
total and is shown by what happened to it: "failed" (non-zero exit), "timed out (hang)" (killed
at the per-sample limit, timeout_reason "sample"), "cut off by budget" (killed early by the
loop's deadline, timeout_reason "budget"), "not started" (no time left) or "missing" (no
complete journal row). Each ranks above every successful sample, so it can only push a
percentile up; a percentile that lands on it is "not reached". Incomplete journal lines are
listed, not counted (their sample is counted as missing). A sample whose fields contradict each
other (exit 0 without a stamp, a timeout without a reason, a cold cache that was not empty, not
started yet not timed out, ...) makes the whole file INVALID. It reports; it does not gate: the
exit status is always 0.
"""

from __future__ import annotations

import datetime as dt
import itertools
import json
import math
import sys
from pathlib import Path
from typing import Any, TypeGuard, cast

TARGETS = {50: 120.0, 95: 180.0}  # percentile -> memo target in seconds
MIN_FOR_PERCENTILES = 5
STAMP = "%Y-%m-%dT%H:%M:%SZ"
CACHES = ("cold", "warm")
REASONS = ("sample", "budget")  # timeout_reason of a timed-out sample
# Stamps a sample may carry, in the order they must occur.
ORDERED_STAMPS = ("command_start", "demo_banner", "demo_verdict", "all_steps_held")
DEMO_STAMPS = ORDERED_STAMPS[1:]


def parse(stamp: object) -> dt.datetime | None:
    if not isinstance(stamp, str):
        return None
    try:
        return dt.datetime.strptime(stamp, STAMP)
    except ValueError:
        return None


def is_int(value: object) -> TypeGuard[int]:
    return isinstance(value, int) and not isinstance(value, bool)


def flag(sample: dict[str, Any], key: str, where: str, out: list[str]) -> bool | None:
    """The sample's true/false field `key` (`missing` defaults to false); None if malformed."""
    value = sample.get(key, False if key == "missing" else None)
    if isinstance(value, bool):
        return value
    out.append(f"{where}: {key!r} is {value!r}, not true or false")
    return None


def reason_problems(
    where: str, sample: dict[str, Any], timed_out: bool | None, limit: int | None
) -> list[str]:
    """`timeout_reason` against `timed_out`, `started` and the per-sample limit `limit`."""
    reason = sample.get("timeout_reason")
    if reason is not None and reason not in REASONS:
        return [f"{where}: 'timeout_reason' is {reason!r}, not 'sample', 'budget' or null"]
    out: list[str] = []
    if timed_out and reason is None:
        out.append(f"{where}: timed out but 'timeout_reason' is null")
    if timed_out is False and reason is not None:
        out.append(f"{where}: not timed out but 'timeout_reason' is {reason!r}")
    if sample.get("started") is False and reason == "sample":
        out.append(f"{where}: not started but 'timeout_reason' is 'sample'")
    seconds = sample.get("timeout_seconds")
    if seconds is not None and (not is_int(seconds) or seconds < 0):
        out.append(f"{where}: 'timeout_seconds' is {seconds!r}, not a whole number of seconds")
    elif is_int(seconds) and limit is not None and reason is not None:
        if reason == "sample" and seconds < limit:
            out.append(
                f"{where}: 'timeout_reason' is 'sample' but its limit {seconds} s < {limit} s"
            )
        if reason == "budget" and seconds >= limit:
            out.append(
                f"{where}: 'timeout_reason' is 'budget' but its limit {seconds} s >= {limit} s"
            )
    return out


def contradictions(where: str, sample: dict[str, Any], limit: int | None = None) -> list[str]:
    """Fields of one sample that cannot all be true at once.

    `limit` is the design's per-sample timeout in seconds, when the file records it.
    """
    out: list[str] = []
    started = flag(sample, "started", where, out)
    timed_out = flag(sample, "timed_out", where, out)
    missing = flag(sample, "missing", where, out)
    out.extend(reason_problems(where, sample, timed_out, limit))
    code = sample.get("exit_code", "missing")
    present = {key: sample.get(key) is not None for key in ORDERED_STAMPS}
    if code is None:
        if not (timed_out or started is False or missing):
            out.append(
                f"{where}: 'exit_code' is None"
                " (null only for a timed-out, not-started or missing sample)"
            )
    elif not is_int(code):
        out.append(f"{where}: 'exit_code' is {code!r}, not an integer or null")
    else:
        if timed_out:
            out.append(f"{where}: timed out but 'exit_code' is {code}")
        if started is False:
            out.append(f"{where}: not started but 'exit_code' is {code}")
        if code == 0:
            out.extend(
                f"{where}: exit 0 but {k!r} is missing" for k in DEMO_STAMPS if not present[k]
            )
    if missing:
        if started:
            out.append(f"{where}: missing from the journal but 'started' is true")
        if timed_out:
            out.append(f"{where}: missing from the journal but 'timed_out' is true")
        out.extend(
            f"{where}: missing from the journal but {k!r} is set"
            for k in ORDERED_STAMPS
            if present[k]
        )
        return out
    if not present["command_start"]:
        out.append(f"{where}: 'command_start' is missing")
    if started is False:
        if timed_out is False:
            # The loop leaves a sample unstarted only when its budget is used up, and records it
            # as timed out (timeout_reason "budget"); only a missing sample has neither.
            out.append(f"{where}: not started but 'timed_out' is false (and not missing)")
        out.extend(f"{where}: not started but {k!r} is set" for k in DEMO_STAMPS if present[k])
    if timed_out and present["all_steps_held"]:
        out.append(f"{where}: timed out but 'all_steps_held' is set")
    entries = sample.get("uv_cache_entries_at_start")
    if entries is not None:
        if not is_int(entries) or entries < 0:
            out.append(f"{where}: 'uv_cache_entries_at_start' is {entries!r}, not a count")
        elif sample.get("uv_cache") == "cold" and entries > 0:
            out.append(f"{where}: cold sample but its uv cache had {entries} entries at start")
    return out


def sample_problems(where: str, sample: dict[str, Any], limit: int | None = None) -> list[str]:
    out: list[str] = []
    if not is_int(sample.get("sample")):
        out.append(f"{where}: 'sample' is not an integer")
    if sample.get("uv_cache") not in CACHES:
        out.append(f"{where}: 'uv_cache' is {sample.get('uv_cache')!r}, not cold or warm")
    if "all_steps_held" not in sample:
        out.append(f"{where}: 'all_steps_held' is missing")
    out.extend(contradictions(where, sample, limit))
    stamps: list[tuple[str, dt.datetime]] = []
    for key in ORDERED_STAMPS:
        value = sample.get(key)
        if value is None:
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


def incomplete_problems(where: str, entry: dict[str, Any]) -> list[str]:
    out: list[str] = []
    if entry.get("sample") is not None:
        out.append(f"{where}: incomplete journal line but 'sample' is {entry.get('sample')!r}")
    if not isinstance(entry.get("raw_prefix"), str):
        out.append(f"{where}: incomplete journal line without a 'raw_prefix'")
    return out


def is_incomplete(sample: dict[str, Any]) -> bool:
    return sample.get("incomplete") is True


def problems(doc: object) -> list[str]:
    """Everything wrong with a reference JSON; empty when it can be summarised."""
    if not isinstance(doc, dict):
        return ["the top level is not an object"]
    top = cast("dict[str, Any]", doc)
    samples = top.get("samples")
    if not isinstance(samples, list):
        return ["'samples' is missing or not a list"]
    out: list[str] = []
    design = top.get("design")
    limit = (
        cast("dict[str, Any]", design).get("sample_timeout_seconds")
        if isinstance(design, dict)
        else None
    )
    limit = limit if is_int(limit) and limit > 0 else None
    journal_incomplete = top.get("journal_incomplete", False)
    if not isinstance(journal_incomplete, bool):
        out.append(f"'journal_incomplete' is {journal_incomplete!r}, not true or false")
    seen: set[int] = set()
    lines = 0
    for i, sample in enumerate(cast("list[Any]", samples)):
        where = f"samples[{i}]"
        if not isinstance(sample, dict):
            out.append(f"{where} is {json.dumps(sample)}, not an object")
            continue
        typed = cast("dict[str, Any]", sample)
        if not isinstance(typed.get("incomplete", False), bool):
            out.append(f"{where}: 'incomplete' is {typed.get('incomplete')!r}, not true or false")
            continue
        if is_incomplete(typed):
            lines += 1
            out.extend(incomplete_problems(where, typed))
            continue
        out.extend(sample_problems(where, typed, limit))
        n = typed.get("sample")
        if isinstance(n, int) and not isinstance(n, bool):
            if n in seen:
                out.append(f"{where}: sample number {n} appears twice")
            seen.add(n)
    if lines and journal_incomplete is not True:
        out.append(f"{lines} incomplete journal line(s) but 'journal_incomplete' is not true")
    if journal_incomplete is True and not lines:
        out.append("'journal_incomplete' is true but no entry is an incomplete journal line")
    return out


def total(sample: dict[str, Any]) -> float | None:
    """Seconds from command_start to all_steps_held for a successful sample, else None.

    Successful: started, not timed out, not missing, exit 0, all four stamps present and ordered.
    """
    if sample.get("started") is not True or sample.get("timed_out") is not False:
        return None
    if sample.get("missing", False) is not False or is_incomplete(sample):
        return None
    code = sample.get("exit_code")
    if not is_int(code) or code != 0:
        return None
    stamps = [parse(sample.get(key)) for key in ORDERED_STAMPS]
    ordered: list[dt.datetime] = [t for t in stamps if t is not None]
    if len(ordered) != len(ORDERED_STAMPS):
        return None
    if any(t2 < t1 for t1, t2 in itertools.pairwise(ordered)):
        return None
    return (ordered[-1] - ordered[0]).total_seconds()


def nearest_rank(values: list[float | None], p: int) -> float | None:
    """Nearest-rank percentile; None (a failed sample) ranks above every number."""
    if not values:
        return None
    ranked = sorted(values, key=lambda v: math.inf if v is None else v)
    return ranked[max(1, math.ceil(p / 100 * len(ranked))) - 1]


def shown(sample: dict[str, Any], value: float | None) -> str:
    if value is not None:
        return f"{value:g} s"
    if sample.get("missing") is True:
        return "missing"
    if sample.get("started") is False:
        return "not started"
    if sample.get("timed_out") is True:
        return (
            "cut off by budget" if sample.get("timeout_reason") == "budget" else "timed out (hang)"
        )
    return "failed"


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
    entries: list[dict[str, Any]] = data["samples"]
    samples = [s for s in entries if not is_incomplete(s)]
    for cache in CACHES:
        chosen = [s for s in samples if s["uv_cache"] == cache]
        lines.extend(block(cache, chosen, compare=cache == "cold"))
    cut = len(entries) - len(samples)
    if cut:
        lines.append(
            f"  journal: {cut} incomplete line(s), not counted;"
            " a sample with no complete journal row is counted as missing"
        )
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
