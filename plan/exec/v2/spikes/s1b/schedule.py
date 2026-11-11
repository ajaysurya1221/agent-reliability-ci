"""Portable SHA-256 schedule, version 1; no PRNG or random module."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping, Sequence
from fractions import Fraction

from suite_stats import Plan


def schedule_key(
    cells: Sequence[Mapping[str, str]],
    baseline: str,
    candidate: str,
    plan: Plan,
    prior_runs: Sequence[str] = (),
) -> bytes:
    """UTF-8 compact sorted-key JSON, ASCII escapes, domain prefix then SHA-256.

    Cell IDs and arm IDs are content identities supplied by the caller, not display
    labels; changed task/oracle/fault content must receive changed identities.
    Each cell carries string fields: task_id, condition_id and content identities.
    All fields enter except label, description, notes and created_at (cosmetic).
    Pass task/oracle/fault/fixture digests as additional fields to bind content.
    Rationals are reduced 'numerator/denominator' strings, stakes sorted numerically,
    equal weights, prior run order preserved. No floating-point numbers are encoded.
    """
    if plan.rule.name == "adaptive":
        raise ValueError("fixed stake set required")
    pairs = sorted((cell["task_id"], cell["condition_id"]) for cell in cells)
    if not pairs or len(set(pairs)) != len(pairs):
        raise ValueError("cells must be nonempty and unique")
    if not baseline or not candidate or any(not t or not c for t, c in pairs):
        raise ValueError("identities must be nonempty")
    if len(set(plan.rule.fractions)) != len(plan.rule.fractions):
        raise ValueError("duplicate stakes are not a set")

    def rational(value: Fraction) -> str:
        return f"{value.numerator}/{value.denominator}"

    content = {
        "cells": [
            {
                name: value
                for name, value in cell.items()
                if name not in {"label", "description", "notes", "created_at"}
            }
            for cell in sorted(cells, key=lambda c: (c["task_id"], c["condition_id"]))
        ],
        "baseline": baseline,
        "candidate": candidate,
        "rule": {
            "alpha": rational(plan.alpha),
            "delta": rational(plan.delta),
            "stakes": [rational(q) for q in sorted(plan.rule.fractions)],
            "batch": plan.batch,
            "max_pairs": plan.max_pairs,
        },
        "prior_runs": list(prior_runs),
    }
    encoded = json.dumps(
        content, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(b"arci-suite/1 key" + encoded).digest()


def rejection_index(draw: Callable[[int], int], n_cells: int, bits: int = 64) -> int:
    """Small bit widths permit deterministic testing of the rejection branch."""
    if not 1 <= n_cells <= 1 << bits:
        raise ValueError("cell count outside sampling range")
    limit = (1 << bits) - ((1 << bits) % n_cells)
    for attempt in range(1 << 32):
        value = draw(attempt)
        if not 0 <= value < 1 << bits:
            raise ValueError("draw outside bit range")
        if value < limit:
            return value % n_cells
    raise OverflowError("rejection attempts exhausted")


def _prefix(key: bytes, i: int) -> bytes:
    if len(key) != 32 or type(i) is not int or not 0 <= i < 1 << 64:
        raise ValueError("32-byte key and unsigned 64-bit index required")
    return key + i.to_bytes(8, "big")


def cell_index(key: bytes, i: int, n_cells: int) -> int:
    prefix = b"arci-suite/1 cell" + _prefix(key, i)
    return rejection_index(
        lambda a: int.from_bytes(hashlib.sha256(prefix + a.to_bytes(4, "big")).digest()[:8], "big"),
        n_cells,
    )


def trial_seed(key: bytes, i: int) -> int:
    """First eight digest bytes, big-endian, high bit cleared; same for both arms.

    Pair index separates repeated cell draws; 63-bit collisions remain possible.
    """
    return int.from_bytes(
        hashlib.sha256(b"arci-suite/1 seed" + _prefix(key, i)).digest()[:8], "big"
    ) & ((1 << 63) - 1)


def coverage() -> list[dict[str, int | str | float]]:
    rows: list[dict[str, int | str | float]] = []
    for cells in (20, 60, 150):
        for pairs in (70, 200, 400):
            probability = Fraction(cells - 1, cells) ** pairs
            rows.append(
                {
                    "cells": cells,
                    "pairs": pairs,
                    "probability_exact": str(probability),
                    "expected_exact": str(cells * probability),
                    "probability": float(probability),
                    "expected": float(cells * probability),
                }
            )
    return rows
