"""Summarise reference-machine demo timings (docs/measurement/reference-machines/).

    python plan/exec/scripts/reference_stats.py reference-ubuntu-latest.json [more.json ...]

For each file (one OS per file, written by .github/workflows/ttfv-reference.yml) it prints the
five `total` values (command_start -> all_steps_held, whole seconds), p50 and p95 by nearest
rank, and whether each is within the memo target (p50 <= 120 s, p95 <= 180 s). A sample that
exited non-zero or never printed "All six steps held" has no total: it is shown as failed and
ranks above every finished sample, so it can only push a percentile up. It reports; it does not
gate: the exit status is always 0.
"""

from __future__ import annotations

import datetime as dt
import json
import math
import sys
from pathlib import Path
from typing import Any

TARGETS = {50: 120.0, 95: 180.0}  # percentile -> memo target in seconds
STAMP = "%Y-%m-%dT%H:%M:%SZ"


def parse(stamp: object) -> dt.datetime | None:
    if not isinstance(stamp, str):
        return None
    try:
        return dt.datetime.strptime(stamp, STAMP)
    except ValueError:
        return None


def total(sample: dict[str, Any]) -> float | None:
    """Seconds from command_start to all_steps_held; None if the sample did not hold."""
    if sample.get("exit_code") != 0:
        return None
    start, held = parse(sample.get("command_start")), parse(sample.get("all_steps_held"))
    if start is None or held is None:
        return None
    return (held - start).total_seconds()


def nearest_rank(values: list[float | None], p: int) -> float | None:
    """Nearest-rank percentile; None (a failed sample) ranks above every number."""
    if not values:
        return None
    ranked = sorted(values, key=lambda v: math.inf if v is None else v)
    return ranked[max(1, math.ceil(p / 100 * len(ranked))) - 1]


def fmt(value: float | None) -> str:
    return "failed" if value is None else f"{value:g} s"


def report(path: Path) -> list[str]:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
        samples: list[dict[str, Any]] = list(doc["samples"])
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return [f"{path.name}: unreadable ({exc.__class__.__name__}: {exc})"]
    runner = doc.get("runner") or {}
    where = " ".join(str(runner.get(k)) for k in ("os", "arch", "label") if runner.get(k))
    lines = [f"{path.name}: {where or 'unknown runner'}, {doc.get('package', '?')}"]
    if not samples:
        return [*lines, "  no samples"]
    totals = [total(s) for s in samples]
    shown = [
        f"{fmt(t)}{' (cold)' if s.get('uv_cache') == 'cold' else ''}"
        for s, t in zip(samples, totals, strict=True)
    ]
    lines.append(f"  totals ({len(samples)}): {', '.join(shown)}")
    for p, target in TARGETS.items():
        value = nearest_rank(totals, p)
        within = value is not None and value <= target
        verdict = "within" if within else "NOT within"
        lines.append(f"  p{p} = {fmt(value)}  ({verdict} target <= {target:g} s)")
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
