#!/usr/bin/env python3
"""The signal-side counts of both halves, from `signal.tsv` alone.

The registration's implementation record names counts that were not looked at before the text
was written: "how many distinct model names a repository shows, and the weight of the third
block definition. Both are counted from the signal side alone, before any pairing". This program
prints them, with the signal-side check counts of each half beside the figures the registration
fixes.

It reads the private signal table with `analyze.py`'s strict reader and opens nothing else: no
outcome table, no transcript, no manifest. It never reads an outcome value and cannot reach
`describe`, `aggregate`, `rho_of_block` or `read_outcome`. Nothing it prints is per session, per
repository or per user: no path, no key, no model name, only integers and fixed words.

Run it as `.venv/bin/python -m bench.logsignals.signal_counts` from the repository root, since it
imports a sibling of this package. Importing this module has no side effects.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import NoReturn

from bench.logsignals.analyze import (
    DEFINITIONS,
    HALVES,
    MEASURES,
    REGISTERED_CHECKS,
    SIGNAL_SIDE_CHECKS,
    UNKNOWN,
    SignalRow,
    TableInvalid,
    block_keys,
    read_signal,
    signal_side_counts,
)

MINIMUM_BLOCK = 2


class _ArgumentParser(argparse.ArgumentParser):
    """Prints the single word ``arguments-invalid`` (no usage text) and exits 2."""

    def error(self, message: str) -> NoReturn:  # argparse override: it never returns
        print("arguments-invalid", file=sys.stderr)
        raise SystemExit(2)


def registered_signal_side(rows: list[SignalRow], half: str) -> dict[str, object]:
    """Each signal-side check of one half as {found, registered, verdict}, plus `all_same`.

    The figures are the ones `analyze.REGISTERED_CHECKS` holds; the names are the sessions, the
    repositories, the sessions with a first measure of exactly 0 and the six month counts. A
    month outside the six appears under its own name, so it cannot pass for one of them.
    """
    found = signal_side_counts(rows)
    registered = REGISTERED_CHECKS[half]
    checks: dict[str, object] = {}
    all_same = True
    for name in sorted(set(found) | set(SIGNAL_SIDE_CHECKS)):
        number, figure = found.get(name, 0), registered.get(name, 0)
        same = number == figure
        all_same = all_same and same
        checks[name] = {
            "found": number,
            "registered": figure,
            "verdict": "same" if same else "different",
        }
    return {"all_same": all_same, "checks": checks}


def model_names_per_repository(rows: list[SignalRow]) -> dict[str, int]:
    """Repositories by how many distinct session model names they show, `unknown` among them."""
    names: dict[str, set[str]] = {}
    for row in rows:
        names.setdefault(row.repo_key, set()).add(row.model)
    counted = {"one": 0, "two": 0, "three_or_more": 0}
    for distinct in names.values():
        if len(distinct) == 1:
            counted["one"] += 1
        elif len(distinct) == 2:
            counted["two"] += 1
        else:
            counted["three_or_more"] += 1
    return counted


def user_ids(rows: list[SignalRow], other: list[SignalRow]) -> dict[str, int]:
    """How many sessions carry a user id, how many ids that is, and how many the other half
    shows too. No id is printed."""
    mine = {row.user_key for row in rows if row.user_key != ""}
    theirs = {row.user_key for row in other if row.user_key != ""}
    return {
        "sessions_with_user_id": sum(1 for row in rows if row.user_key != ""),
        "distinct_user_ids": len(mine),
        "shared_user_ids": len(mine & theirs),
    }


def _weight_and_repositories(blocks: dict[tuple[str, ...], list[SignalRow]]) -> dict[str, int]:
    weight = 0
    repositories: set[str] = set()
    for key, members in blocks.items():
        if len(members) < MINIMUM_BLOCK:
            continue
        weight += len(members) - 1
        repositories.add(key[0])
    return {"weight": weight, "repositories": len(repositories)}


def potential_weight(rows: list[SignalRow]) -> dict[str, object]:
    """The weight the blocks of each definition could carry, before any outcome is consulted.

    `blocks_of_two_or_more` sums `n_b - 1` over the blocks of at least 2 sessions and counts the
    repositories holding such a block. For each measure, `signal_not_constant` is the same sum
    over the blocks where that measure is also not constant (the values compared exactly).

    Both are upper bounds on the registered `W` and `m`: a block carries weight only when
    neither the signal nor the outcome is constant inside it, and no outcome is read here, so a
    constant outcome or a missing outcome value can only take weight away.
    """
    found: dict[str, object] = {}
    for definition in DEFINITIONS:
        keys = block_keys(rows, definition)
        blocks: dict[tuple[str, ...], list[SignalRow]] = {}
        for row in rows:
            blocks.setdefault(keys[row.path], []).append(row)
        not_constant: dict[str, object] = {}
        for measure in MEASURES:
            kept = {
                key: members
                for key, members in blocks.items()
                if len({member.value(measure) for member in members}) > 1
            }
            not_constant[measure] = _weight_and_repositories(kept)
        found[definition] = {
            "blocks_of_two_or_more": _weight_and_repositories(blocks),
            "signal_not_constant": not_constant,
        }
    return found


def counts_of_half(rows: list[SignalRow], half: str) -> dict[str, object]:
    """Every count of one half. No outcome is read and nothing per session is printed."""
    mine = [row for row in rows if row.half == half]
    other = [row for row in rows if row.half != half]
    return {
        "registered_signal_side": registered_signal_side(mine, half),
        "month_unknown": sum(1 for row in mine if row.month == ""),
        "model_unknown": sum(1 for row in mine if row.model == UNKNOWN),
        "model_names_per_repository": model_names_per_repository(mine),
        "user_ids": user_ids(mine, other),
        "potential_weight": potential_weight(mine),
    }


def counts(signal_path: Path) -> dict[str, object]:
    """The counts of both halves, from the signal table alone."""
    rows = read_signal(signal_path)
    return {half: counts_of_half(rows, half) for half in HALVES}


def all_registered_same(found: dict[str, object]) -> bool:
    for half in HALVES:
        half_counts = found[half]
        if not isinstance(half_counts, dict):  # pragma: no cover - built just above
            return False
        side = half_counts["registered_signal_side"]
        if not isinstance(side, dict) or side["all_same"] is not True:
            return False
    return True


def main(argv: list[str] | None = None) -> int:
    parser = _ArgumentParser(add_help=False, allow_abbrev=False)
    _ = parser.add_argument("--signal", required=True)
    try:
        args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    except SystemExit:
        return 2

    try:
        found = counts(Path(str(args.signal)))
    except TableInvalid:
        print("table-invalid", file=sys.stderr)
        return 2

    print(json.dumps(found, indent=2, sort_keys=True, ensure_ascii=True))
    return 0 if all_registered_same(found) else 3


if __name__ == "__main__":
    raise SystemExit(main())
