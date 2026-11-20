#!/usr/bin/env python3
"""Checks a result file against the registered disclosure rules and formats.

Exit 0 when every rule holds, 4 when one fails; the failed rule is named on stderr and nothing
else is printed. Standard library only. Importing this module has no side effects.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import NoReturn, cast

MEASURES: tuple[str, ...] = ("no_reasoning_share", "reasoning_tokens")
DEFINITIONS: tuple[str, ...] = ("repository", "repository_month", "repository_model_length")
HALVES: tuple[str, ...] = ("confirmation", "discovery")

MINIMUM_REPOSITORIES = 10
MINIMUM_WEIGHT = 150
MINIMUM_REPOSITORIES_FOR_RANGE = 11

TOP_KEYS = frozenset(
    {"half", "sessions", "repositories", "measures", "first_measure_repository", "provenance"}
)
PROVENANCE_KEYS = frozenset(
    {
        "registration_commit",
        "record_commit",
        "analyze_sha256",
        "signal_sha256",
        "outcome_sha256",
        "start_time",
    }
)
FORMED_MEASURE_KEYS = frozenset({"rho_bar", "m", "W", "sessions"})
FIRST_MEASURE_KEYS = frozenset(
    {"above", "below", "zero", "positive_weight_share", "without_shared"}
)

RULES: tuple[str, ...] = (
    "allowed-keys",
    "value-format",
    "rho-floor",
    "range-floor",
    "without-shared-alone",
    "checks-mismatch",
)

NOT_FORMED = "not formed"
_RHO_RE = re.compile(r"\A[+-][01]\.[0-9]{3}\Z")
_COARSE_RE = re.compile(r"\A[+-][01]\.[0-9]{2}\Z")
_SHARE_RE = re.compile(r"\A(0|[1-9][0-9]?|100)%\Z")
_NOT_FORMED_RE = re.compile(
    r"\Anot formed \((0|[1-9][0-9]*) repositories, (0|[1-9][0-9]*) units\)\Z"
)
_COMMIT_RE = re.compile(r"\A[0-9a-f]{40}\Z")
_DIGEST_RE = re.compile(r"\A[0-9a-f]{64}\Z")
# The start time as the registration's result file records it: UTC, whole seconds, ISO 8601.
_START_TIME_RE = re.compile(
    r"\A20[0-9]{2}-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])"
    r"T([01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]\+00:00\Z"
)


class RuleFailed(Exception):
    """Carries the name of the failed rule and nothing from the file."""

    def __init__(self, rule: str) -> None:
        super().__init__(rule)
        self.rule = rule


def _fail(rule: str) -> NoReturn:
    raise RuleFailed(rule)


def _count(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        _fail("value-format")
    return value


def _text(value: object) -> str:
    if not isinstance(value, str):
        _fail("value-format")
    return value


def _mapping(value: object, rule: str) -> dict[str, object]:
    if not isinstance(value, dict):
        _fail(rule)
    raw = cast(dict[object, object], value)
    if any(not isinstance(key, str) for key in raw):
        _fail(rule)
    return cast(dict[str, object], value)


def _exact(value: object, allowed: frozenset[str], rule: str = "allowed-keys") -> dict[str, object]:
    mapping = _mapping(value, rule)
    if frozenset(mapping) != allowed:
        _fail(rule)
    return mapping


def _check_measure_block(block: object) -> tuple[int, int, bool]:
    """Returns (m, W, printed) for one definition and one measure."""
    mapping = _mapping(block, "allowed-keys")
    if frozenset(mapping) == frozenset({"not_formed"}):
        matched = _NOT_FORMED_RE.match(_text(mapping["not_formed"]))
        if matched is None:
            _fail("value-format")
        return int(matched.group(1)), int(matched.group(2)), False
    if frozenset(mapping) != FORMED_MEASURE_KEYS:
        _fail("allowed-keys")
    if not _RHO_RE.match(_text(mapping["rho_bar"])):
        _fail("value-format")
    m, weight = _count(mapping["m"]), _count(mapping["W"])
    _ = _count(mapping["sessions"])
    if m < MINIMUM_REPOSITORIES or weight < MINIMUM_WEIGHT:
        _fail("rho-floor")
    return m, weight, True


def _check_first_measure(block: object, first_m: int, first_printed: bool) -> None:
    mapping = _mapping(block, "allowed-keys")
    if frozenset(mapping) == frozenset({"not_formed"}):
        if first_printed:
            _fail("allowed-keys")
        if not _NOT_FORMED_RE.match(_text(mapping["not_formed"])):
            _fail("value-format")
        return
    if not first_printed:
        _fail("rho-floor")

    # Disclosure rule 4: the number without shared users is printed alone, with no weight and no
    # repository count beside it.
    for key in mapping:
        if key.startswith("without_shared") and key != "without_shared":
            _fail("without-shared-alone")

    with_range = FIRST_MEASURE_KEYS | {"loo_min", "loo_max"}
    without_range = FIRST_MEASURE_KEYS | {"loo_range"}
    if frozenset(mapping) == with_range:
        if first_m < MINIMUM_REPOSITORIES_FOR_RANGE:
            _fail("range-floor")
        for name in ("loo_min", "loo_max"):
            if not _COARSE_RE.match(_text(mapping[name])):
                _fail("value-format")
    elif frozenset(mapping) == without_range:
        if _text(mapping["loo_range"]) != NOT_FORMED:
            _fail("value-format")
    else:
        _fail("allowed-keys")

    for name in ("above", "below", "zero"):
        _ = _count(mapping[name])
    if not _SHARE_RE.match(_text(mapping["positive_weight_share"])):
        _fail("value-format")
    without = _text(mapping["without_shared"])
    if without != NOT_FORMED and not _COARSE_RE.match(without):
        _fail("value-format")


def _found_counts(checks: object) -> dict[str, int]:
    """The `found` figure of every entry of a checks file's list.

    A name that appears twice is refused rather than silently won by the last entry.
    """
    mapping = _mapping(checks, "checks-mismatch")
    entries = mapping.get("checks")
    if not isinstance(entries, list):
        _fail("checks-mismatch")
    found: dict[str, int] = {}
    for entry in cast(list[object], entries):
        item = _mapping(entry, "checks-mismatch")
        name, number = item.get("name"), item.get("found")
        if not isinstance(name, str) or isinstance(number, bool) or not isinstance(number, int):
            _fail("checks-mismatch")
        if name in found:
            _fail("checks-mismatch")
        found[name] = number
    return found


def check(result: object, checks: object | None = None) -> None:
    """Raises RuleFailed for the first rule that fails.

    With a checks file, the result file's `sessions` and `repositories` must equal the found
    counts that file carries.
    """
    top = _exact(result, TOP_KEYS)
    if _text(top["half"]) not in HALVES:
        _fail("value-format")
    sessions = _count(top["sessions"])
    repositories = _count(top["repositories"])
    if checks is not None:
        found = _found_counts(checks)
        if found.get("sessions") != sessions or found.get("repositories") != repositories:
            _fail("checks-mismatch")

    provenance = _exact(top["provenance"], PROVENANCE_KEYS)
    for name in ("registration_commit", "record_commit"):
        if not _COMMIT_RE.match(_text(provenance[name])):
            _fail("value-format")
    for name in ("analyze_sha256", "signal_sha256", "outcome_sha256"):
        if not _DIGEST_RE.match(_text(provenance[name])):
            _fail("value-format")
    if not _START_TIME_RE.match(_text(provenance["start_time"])):
        _fail("value-format")

    measures = _exact(top["measures"], frozenset(MEASURES))
    first_m = 0
    first_printed = False
    for measure in MEASURES:
        by_definition = _exact(measures[measure], frozenset(DEFINITIONS))
        for definition in DEFINITIONS:
            m, _weight, printed = _check_measure_block(by_definition[definition])
            if measure == MEASURES[0] and definition == DEFINITIONS[0]:
                first_m, first_printed = m, printed

    _check_first_measure(top["first_measure_repository"], first_m, first_printed)


class _ArgumentParser(argparse.ArgumentParser):
    """Prints the single word ``arguments-invalid`` (no usage text) and exits 2."""

    def error(self, message: str) -> NoReturn:  # argparse override: it never returns
        print("arguments-invalid", file=sys.stderr)
        raise SystemExit(2)


def main(argv: list[str] | None = None) -> int:
    parser = _ArgumentParser(add_help=False, allow_abbrev=False)
    _ = parser.add_argument("--result", required=True)
    _ = parser.add_argument("--checks")
    try:
        args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    except SystemExit:
        return 2

    try:
        raw: object = json.loads(Path(str(args.result)).read_text(encoding="utf-8"))
        checks: object | None = None
        if args.checks is not None:
            checks = json.loads(Path(str(args.checks)).read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError):
        print("unreadable", file=sys.stderr)
        return 4

    try:
        check(raw, checks)
    except RuleFailed as failure:
        print(failure.rule, file=sys.stderr)
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
