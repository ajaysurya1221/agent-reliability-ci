#!/usr/bin/env python3
"""The two stages of the log-signals study. Standard library only; no `arci` import.

Stage 1 prints the check counts and pairs nothing: it never puts a signal value beside an outcome
value of the same session, and it never calls `describe`. Stage 2 is the only code that does,
through the single pure function `describe`.

Neither stage refuses a table because of the *other* half's counts. The registration confines a
second-half mismatch to the second half ("Order of work" step 7: "A mismatch stops the study
before second-half pairing and is reported under step 4") and commits the first half's check
counts either way (step 4), so a stand-in of the other half cannot be caught here. The
both-halves signal-side comparison is `signal_counts.py`'s: it runs on `signal.tsv` before any
pairing and is written into the implementation record, and each stage ties itself to that one
table by its digest, which both the checks file and the result file record (`signal_sha256`).
`describe` keeps its own rule, that no row of the other half is a format violation.

Stage 2 takes no start time from its caller; it is either the first of the two runs of step 5,
which stamps the clock, or the second, which takes the first's stamp.

Every definition here comes from `PREREGISTRATION.md`; the file formats come from
`INTERFACE.md`. Importing this module has no side effects.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from fractions import Fraction
from pathlib import Path
from typing import Any, NoReturn, cast

MEASURES: tuple[str, ...] = ("no_reasoning_share", "reasoning_tokens")
DEFINITIONS: tuple[str, ...] = ("repository", "repository_month", "repository_model_length")
HALVES: tuple[str, ...] = ("confirmation", "discovery")
UNKNOWN = "unknown"

MINIMUM_REPOSITORIES = 10
MINIMUM_WEIGHT = 150
MINIMUM_REPOSITORIES_FOR_RANGE = 11

NOT_FORMED = "not formed"

SIGNAL_HEADER: tuple[str, ...] = (
    "path",
    "repo_key",
    "half",
    "month",
    "user_key",
    "model",
    "d",
    "first_time",
    "zero",
    "tokens_num",
    "tokens_den",
)
OUTCOME_HEADER: tuple[str, ...] = ("path", "agent_percentage")

# The figures the registration fixes for each half ("Printed as checks" and "Conditions for
# reading the numbers as an answer", with the month counts of "Data and population").
REGISTERED_MONTHS: tuple[str, ...] = (
    "2026-04",
    "2026-05",
    "2026-06",
    "2026-07",
    "2026-08",
    "2026-09",
)
SIGNAL_SIDE_CHECKS: tuple[str, ...] = (
    "sessions",
    "repositories",
    "first_measure_exactly_0",
    *(f"month_{month}" for month in REGISTERED_MONTHS),
)
REGISTERED_CHECKS: dict[str, dict[str, int]] = {
    "confirmation": {
        "sessions": 423,
        "repositories": 33,
        "outcome_at_0": 79,
        "outcome_at_100": 228,
        "outcome_between": 116,
        "first_measure_exactly_0": 25,
        "month_2026-04": 102,
        "month_2026-05": 76,
        "month_2026-06": 109,
        "month_2026-07": 104,
        "month_2026-08": 25,
        "month_2026-09": 7,
    },
    "discovery": {
        "sessions": 432,
        "repositories": 32,
        "outcome_at_0": 107,
        "outcome_at_100": 184,
        "outcome_between": 141,
        "first_measure_exactly_0": 18,
        "month_2026-04": 84,
        "month_2026-05": 116,
        "month_2026-06": 80,
        "month_2026-07": 40,
        "month_2026-08": 72,
        "month_2026-09": 40,
    },
}

_PATH_RE = re.compile(r"\Atranscripts[0-9]*/[^/\\\x00-\x1f]+\.jsonl\Z")
_HEX16_RE = re.compile(r"\A[0-9a-f]{16}\Z")
_MONTH_RE = re.compile(r"\A20[0-9]{2}-(0[1-9]|1[0-2])\Z")
_MODEL_RE = re.compile(r"\A[^\t\n\r\x00-\x1f]{1,120}\Z")
_INT_RE = re.compile(r"\A(0|[1-9][0-9]{0,11})\Z")
_COMMIT_RE = re.compile(r"\A[0-9a-f]{40}\Z")
# The start time as the registration's result file records it: UTC, whole seconds, ISO 8601.
START_TIME_RE = re.compile(
    r"\A20[0-9]{2}-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])"
    r"T([01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]\+00:00\Z"
)


class TableInvalid(Exception):
    """Raised for any violation of an input table's format. Carries no detail."""


class OutputRefused(Exception):
    """Raised when an output file exists already. Carries no detail."""


class _ArgumentParser(argparse.ArgumentParser):
    """Prints the single word ``arguments-invalid`` (no usage text) and exits 2."""

    def error(self, message: str) -> NoReturn:  # argparse override: it never returns
        print("arguments-invalid", file=sys.stderr)
        raise SystemExit(2)


# --- the input tables ---------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SignalRow:
    """One row of `signal.tsv`. It holds no outcome.

    `tokens` is always present: the registration says "every eligible Codex session has it", and
    the extractor stops rather than write a session without it, so an empty `tokens_num` or
    `tokens_den` is a format violation here.
    """

    path: str
    repo_key: str
    half: str
    month: str
    user_key: str
    model: str
    d: int
    first_time: datetime | None
    zero: int
    tokens: Fraction

    @property
    def no_reasoning_share(self) -> Fraction:
        return Fraction(self.zero, self.d)

    def value(self, measure: str) -> Fraction:
        if measure == "no_reasoning_share":
            return self.no_reasoning_share
        if measure == "reasoning_tokens":
            return self.tokens
        raise TableInvalid


def _read_text(path: Path) -> str:
    try:
        data = path.read_bytes()
    except OSError:
        raise TableInvalid from None
    try:
        return data.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        raise TableInvalid from None


def _body_lines(text: str, header: tuple[str, ...]) -> list[str]:
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines = lines[:-1]
    if not lines or lines[0] != "\t".join(header):
        raise TableInvalid
    return lines[1:]


def _parse_time(raw: str) -> datetime | None:
    if raw == "":
        return None
    try:
        when = datetime.fromisoformat(raw)
    except ValueError:
        raise TableInvalid from None
    if when.tzinfo is None:
        raise TableInvalid
    return when


def read_signal(signal_path: Path) -> list[SignalRow]:
    """Reads and strictly validates `signal.tsv`. Raises TableInvalid and leaks no value."""
    rows: list[SignalRow] = []
    seen: set[str] = set()
    for line in _body_lines(_read_text(signal_path), SIGNAL_HEADER):
        parts = line.split("\t")
        if len(parts) != len(SIGNAL_HEADER):
            raise TableInvalid
        path, repo_key, half, month, user_key, model, d_raw, first_raw, zero_raw, num, den = parts
        if not _PATH_RE.match(path) or path in seen:
            raise TableInvalid
        if not _HEX16_RE.match(repo_key) or half not in HALVES:
            raise TableInvalid
        if month != "" and not _MONTH_RE.match(month):
            raise TableInvalid
        if user_key != "" and not _HEX16_RE.match(user_key):
            raise TableInvalid
        if not _MODEL_RE.match(model):
            raise TableInvalid
        if not _INT_RE.match(d_raw) or not _INT_RE.match(zero_raw):
            raise TableInvalid
        # Both fields are required: the registration gives every eligible session a second
        # measure, so an empty field of the pair is a format violation.
        if not _INT_RE.match(num) or den not in {"1", "2"}:
            raise TableInvalid
        d, zero = int(d_raw), int(zero_raw)
        if d < 20 or zero > d:
            raise TableInvalid
        seen.add(path)
        rows.append(
            SignalRow(
                path=path,
                repo_key=repo_key,
                half=half,
                month=month,
                user_key=user_key,
                model=model,
                d=d,
                first_time=_parse_time(first_raw),
                zero=zero,
                tokens=Fraction(int(num), int(den)),
            )
        )
    return rows


def read_outcome(outcome_path: Path, needed: set[str]) -> dict[str, Fraction | None]:
    """The outcome value of every needed path: an exact Fraction, or None when the table has no
    value for it.

    The value column is parsed only for a needed path, so that an unusable value on a path that
    this half never reads cannot stop the run.
    """
    values: dict[str, Fraction | None] = {}
    seen: set[str] = set()
    for line in _body_lines(_read_text(outcome_path), OUTCOME_HEADER):
        parts = line.split("\t")
        if len(parts) != len(OUTCOME_HEADER):
            raise TableInvalid
        path, raw = parts
        if not _PATH_RE.match(path) or path in seen:
            raise TableInvalid
        seen.add(path)
        if path not in needed:
            continue
        if raw == "":
            values[path] = None
            continue
        try:
            number = float(raw)
        except ValueError:
            raise TableInvalid from None
        # `INTERFACE.md` fixes the column as the value written with `repr(float)`, so only that
        # exact spelling is accepted: `1_0`, ` 50 `, `5e1` and `+50` are format violations.
        if repr(number) != raw:
            raise TableInvalid
        if not math.isfinite(number) or number < 0.0 or number > 100.0:
            raise TableInvalid
        values[path] = Fraction(number)
    if set(values) != needed:
        raise TableInvalid
    return values


# --- the number of one block --------------------------------------------------


def midranks(values: list[Fraction]) -> list[Fraction]:
    """Ranks from 1, tied values all taking the mean of the ranks they span."""
    order = sorted(range(len(values)), key=lambda index: values[index])
    ranks: list[Fraction] = [Fraction(0)] * len(values)
    start = 0
    while start < len(order):
        stop = start
        while stop + 1 < len(order) and values[order[stop + 1]] == values[order[start]]:
            stop += 1
        shared = Fraction((start + 1) + (stop + 1), 2)
        for position in range(start, stop + 1):
            ranks[order[position]] = shared
        start = stop + 1
    return ranks


def rho_of_block(signal: list[Fraction], outcome: list[Fraction]) -> float | None:
    """Pearson's correlation of the two midrank vectors, or None when a side is constant.

    The sums are exact rational arithmetic; one square root in floating point at the end.
    """
    n = len(signal)
    if n < 2:
        return None
    if len(set(signal)) < 2 or len(set(outcome)) < 2:
        return None
    xs, ys = midranks(signal), midranks(outcome)
    total_x, total_y = sum(xs, Fraction(0)), sum(ys, Fraction(0))
    sum_xx = sum((x * x for x in xs), Fraction(0))
    sum_yy = sum((y * y for y in ys), Fraction(0))
    sum_xy = sum((x * y for x, y in zip(xs, ys, strict=True)), Fraction(0))
    numerator = n * sum_xy - total_x * total_y
    spread_x = n * sum_xx - total_x * total_x
    spread_y = n * sum_yy - total_y * total_y
    if spread_x == 0 or spread_y == 0:
        return None
    root = math.sqrt(float(numerator * numerator / (spread_x * spread_y)))
    if numerator > 0:
        return root
    if numerator < 0:
        return -root
    return 0.0


# --- the blocks ---------------------------------------------------------------


def _third_label(position: int, n: int) -> str:
    if position <= n // 3:
        return "low"
    if position <= (2 * n) // 3:
        return "middle"
    return "high"


def _length_sort_key(row: SignalRow) -> tuple[int, int, datetime, str]:
    absent = row.first_time is None
    when = datetime.min.replace(tzinfo=UTC) if row.first_time is None else row.first_time
    return (row.d, 1 if absent else 0, when, row.path)


def block_keys(rows: list[SignalRow], definition: str) -> dict[str, tuple[str, ...]]:
    """The block key of every session, for one block definition."""
    if definition == "repository":
        return {row.path: (row.repo_key,) for row in rows}
    if definition == "repository_month":
        return {row.path: (row.repo_key, row.month or UNKNOWN) for row in rows}
    if definition != "repository_model_length":
        raise TableInvalid

    groups: dict[tuple[str, str], list[SignalRow]] = {}
    for row in rows:
        groups.setdefault((row.repo_key, row.model), []).append(row)
    keys: dict[str, tuple[str, ...]] = {}
    for (repo_key, model), group in groups.items():
        ordered = sorted(group, key=_length_sort_key)
        n = len(ordered)
        for index, row in enumerate(ordered):
            keys[row.path] = (repo_key, model, _third_label(index + 1, n))
    return keys


@dataclass(frozen=True, slots=True)
class Aggregate:
    """The numbers of one block definition and one measure."""

    m: int
    weight: int
    sessions: int
    total: float
    per_repository: tuple[tuple[str, int, float], ...]

    @property
    def formed(self) -> bool:
        return self.m >= MINIMUM_REPOSITORIES and self.weight >= MINIMUM_WEIGHT

    @property
    def rho_bar(self) -> float | None:
        if self.weight == 0:
            return None
        return self.total / self.weight


def aggregate(
    rows: list[SignalRow],
    outcomes: dict[str, Fraction | None],
    measure: str,
    definition: str,
) -> Aggregate:
    """`rho_bar`'s parts over the weight-carrying blocks of one definition and measure.

    This is the only place where a signal value and an outcome value of the same session meet.
    """
    keys = block_keys(rows, definition)
    blocks: dict[tuple[str, ...], list[SignalRow]] = {}
    for row in rows:
        if outcomes.get(row.path) is None:
            continue
        blocks.setdefault(keys[row.path], []).append(row)

    weights: list[float] = []
    repositories: set[str] = set()
    sessions = 0
    weight = 0
    per_repository: list[tuple[str, int, float]] = []
    for key in sorted(blocks):
        members = blocks[key]
        signal: list[Fraction] = []
        outcome: list[Fraction] = []
        for member in members:
            held = member.value(measure)
            value = outcomes[member.path]
            if value is None:  # pragma: no cover - filtered above
                raise TableInvalid
            signal.append(held)
            outcome.append(value)
        rho = rho_of_block(signal, outcome)
        if rho is None:
            continue
        block_weight = len(members) - 1
        weights.append(block_weight * rho)
        weight += block_weight
        sessions += len(members)
        repositories.add(key[0])
        per_repository.append((key[0], block_weight, rho))
    return Aggregate(
        m=len(repositories),
        weight=weight,
        sessions=sessions,
        total=math.fsum(weights),
        per_repository=tuple(per_repository),
    )


# --- the full-precision description -------------------------------------------


def _measure_object(found: Aggregate) -> dict[str, object]:
    return {
        "formed": found.formed,
        "rho_bar": found.rho_bar if found.formed else None,
        "m": found.m,
        "W": found.weight,
        "sessions": found.sessions,
    }


def _null_first_measure_repository() -> dict[str, object]:
    return {
        "above": None,
        "below": None,
        "zero": None,
        "positive_weight_share": None,
        "loo_formed": False,
        "loo_min": None,
        "loo_max": None,
        "without_shared_formed": False,
        "without_shared": None,
    }


def shared_user_repositories(rows: list[SignalRow], half: str) -> set[str]:
    """The repositories of this half that hold a session whose user id also appears in an
    eligible Codex session of the other half."""
    mine = [row for row in rows if row.half == half]
    others = {row.user_key for row in rows if row.half != half and row.user_key != ""}
    shared = {row.user_key for row in mine if row.user_key != "" and row.user_key in others}
    return {row.repo_key for row in mine if row.user_key in shared and row.user_key != ""}


def _first_measure_repository(
    rows: list[SignalRow],
    mine: list[SignalRow],
    outcomes: dict[str, Fraction | None],
    half: str,
    found: Aggregate,
) -> dict[str, object]:
    if not found.formed:
        return _null_first_measure_repository()

    above = sum(1 for _repo, _weight, rho in found.per_repository if rho > 0)
    below = sum(1 for _repo, _weight, rho in found.per_repository if rho < 0)
    zero = sum(1 for _repo, _weight, rho in found.per_repository if rho == 0)
    positive_weight = sum(weight for _repo, weight, rho in found.per_repository if rho > 0)
    share = float(Fraction(positive_weight, found.weight))

    loo_formed = found.m >= MINIMUM_REPOSITORIES_FOR_RANGE
    loo_min: float | None = None
    loo_max: float | None = None
    if loo_formed:
        left_out = [
            (found.total - weight * rho) / (found.weight - weight)
            for _repo, weight, rho in found.per_repository
        ]
        loo_min, loo_max = min(left_out), max(left_out)

    excluded = shared_user_repositories(rows, half)
    kept = [row for row in mine if row.repo_key not in excluded]
    without = aggregate(kept, outcomes, "no_reasoning_share", "repository")
    without_formed = without.formed
    without_value = without.rho_bar if without_formed else None

    return {
        "above": above,
        "below": below,
        "zero": zero,
        "positive_weight_share": share,
        "loo_formed": loo_formed,
        "loo_min": loo_min,
        "loo_max": loo_max,
        "without_shared_formed": without_formed,
        "without_shared": without_value,
    }


def describe(signal_path: Path, outcome_path: Path, half: str) -> dict[str, object]:
    """The full-precision object of `INTERFACE.md` for one half.

    This is the single place where a signal value is set beside an outcome value.
    """
    if half not in HALVES:
        raise TableInvalid
    rows = read_signal(signal_path)
    mine = [row for row in rows if row.half == half]
    # `INTERFACE.md` fixes `signal.tsv` as one row per eligible session "of either half". The
    # number without shared users needs the other half's user ids: with that half absent nothing
    # would be excluded and the number would silently equal `rho_bar`.
    if not any(row.half != half for row in rows):
        raise TableInvalid
    outcomes = read_outcome(outcome_path, {row.path for row in mine})

    measures: dict[str, object] = {}
    first_repository: Aggregate | None = None
    for measure in MEASURES:
        by_definition: dict[str, object] = {}
        for definition in DEFINITIONS:
            found = aggregate(mine, outcomes, measure, definition)
            if measure == MEASURES[0] and definition == DEFINITIONS[0]:
                first_repository = found
            by_definition[definition] = _measure_object(found)
        measures[measure] = by_definition
    if first_repository is None:  # pragma: no cover - MEASURES and DEFINITIONS are not empty
        raise TableInvalid

    months: dict[str, int] = {}
    for row in mine:
        if row.month != "":
            months[row.month] = months.get(row.month, 0) + 1

    values = [outcomes[row.path] for row in mine]
    checks: dict[str, object] = {
        "outcome_at_0": sum(1 for value in values if value is not None and value == 0),
        "outcome_at_100": sum(1 for value in values if value is not None and value == 100),
        "outcome_between": sum(1 for value in values if value is not None and 0 < value < 100),
        "outcome_missing": sum(1 for value in values if value is None),
        "first_measure_exactly_0": sum(1 for row in mine if row.no_reasoning_share == 0),
        "months": {month: months[month] for month in sorted(months)},
        "month_unknown": sum(1 for row in mine if row.month == ""),
        "model_unknown": sum(1 for row in mine if row.model == UNKNOWN),
    }

    return {
        "half": half,
        "sessions": len(mine),
        "repositories": len({row.repo_key for row in mine}),
        "measures": measures,
        "first_measure_repository": _first_measure_repository(
            rows, mine, outcomes, half, first_repository
        ),
        "checks": checks,
    }


# --- stage 1: the check counts, which pair nothing ----------------------------


def digest_of(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        raise TableInvalid from None


def signal_side_counts(rows: list[SignalRow]) -> dict[str, int]:
    """The check counts of one half that come from `signal.tsv` alone.

    These are the sessions, the repositories, the sessions with a first measure of exactly 0 and
    the six month counts. A month outside the six appears as its own key, so it cannot pass for
    one of them. No outcome value is read here.
    """
    months: dict[str, int] = {}
    for row in rows:
        if row.month != "":
            months[row.month] = months.get(row.month, 0) + 1
    found: dict[str, int] = {
        "sessions": len(rows),
        "repositories": len({row.repo_key for row in rows}),
        "first_measure_exactly_0": sum(1 for row in rows if row.zero == 0),
    }
    for month in sorted(set(REGISTERED_MONTHS) | set(months)):
        found[f"month_{month}"] = months.get(month, 0)
    return found


def _check_counts(rows: list[SignalRow], values: dict[str, Fraction | None]) -> dict[str, int]:
    """The check counts of one half, from the signal rows and the outcome values of its paths.

    Every signal-side count comes from `signal.tsv` alone and every outcome count from
    `outcome.tsv`; no number here uses a signal value and an outcome value of the same session
    together.
    """
    present = [value for value in values.values() if value is not None]
    signal_side = signal_side_counts(rows)

    found: dict[str, int] = {
        "sessions": signal_side["sessions"],
        "repositories": signal_side["repositories"],
        "outcome_at_0": sum(1 for value in present if value == 0),
        "outcome_at_100": sum(1 for value in present if value == 100),
        "outcome_between": sum(1 for value in present if 0 < value < 100),
        "first_measure_exactly_0": signal_side["first_measure_exactly_0"],
    }
    for name, number in signal_side.items():
        if name.startswith("month_"):
            found[name] = number
    return found


def stage_one(signal_path: Path, outcome_path: Path, half: str) -> dict[str, object]:
    """The check counts beside the figures the registration fixes for that half.

    It takes the eligible paths and every signal-side count from `signal.tsv` alone and the
    outcome counts from `outcome.tsv` over those paths. No number here uses a signal value and
    an outcome value of the same session together, and `describe` is not called.
    """
    if half not in HALVES:
        raise TableInvalid
    rows = [row for row in read_signal(signal_path) if row.half == half]
    paths = {row.path for row in rows}
    values = read_outcome(outcome_path, paths)
    found = _check_counts(rows, values)

    registered = REGISTERED_CHECKS[half]
    checks: list[dict[str, object]] = []
    all_same = True
    for name, number in found.items():
        expected = registered.get(name, 0)
        same = number == expected
        all_same = all_same and same
        checks.append(
            {
                "name": name,
                "found": number,
                "registered": expected,
                "verdict": "same" if same else "different",
            }
        )

    return {
        "half": half,
        "all_same": all_same,
        "checks": checks,
        # The registration names these two and no other: "Also printed: how many sessions took
        # the month label `unknown` and how many the model name `unknown`."
        "also_printed": {
            "month_unknown": sum(1 for row in rows if row.month == ""),
            "model_unknown": sum(1 for row in rows if row.model == UNKNOWN),
        },
        "signal_sha256": digest_of(signal_path),
        "outcome_sha256": digest_of(outcome_path),
    }


# --- the printed forms --------------------------------------------------------


def printed_rho(value: float) -> str:
    return format(value, "+.3f")


def printed_coarse(value: float) -> str:
    return format(value, "+.2f")


def printed_share(value: float) -> str:
    """A share of weight as a whole percent: `format(100 * share, ".0f")`.

    That is Python's own rounding of a float to no decimals, which rounds a half to the even
    digit; the registration fixes the format ("Shares of weight: whole percent") and names no
    other rule.
    """
    return format(100 * value, ".0f") + "%"


def not_formed_form(m: int, weight: int) -> str:
    return f"not formed ({m} repositories, {weight} units)"


def _printed_measure(block: Any) -> dict[str, object]:
    m, weight = int(block["m"]), int(block["W"])
    if not block["formed"]:
        return {"not_formed": not_formed_form(m, weight)}
    return {
        "rho_bar": printed_rho(_as_float(block["rho_bar"])),
        "m": m,
        "W": weight,
        "sessions": int(block["sessions"]),
    }


def _as_float(value: object) -> float:
    if not isinstance(value, float):
        raise TableInvalid
    return value


def printed_result(description: dict[str, object], provenance: dict[str, str]) -> dict[str, object]:
    """The result file: exactly the printed forms the registration lists, and the provenance."""
    measures_raw: Any = description["measures"]
    measures: dict[str, object] = {}
    for measure in MEASURES:
        measures[measure] = {
            definition: _printed_measure(measures_raw[measure][definition])
            for definition in DEFINITIONS
        }

    first: Any = description["first_measure_repository"]
    repository_block: Any = measures_raw[MEASURES[0]][DEFINITIONS[0]]
    if not repository_block["formed"]:
        first_printed: dict[str, object] = {
            "not_formed": not_formed_form(int(repository_block["m"]), int(repository_block["W"]))
        }
    else:
        first_printed = {
            "above": int(first["above"]),
            "below": int(first["below"]),
            "zero": int(first["zero"]),
            "positive_weight_share": printed_share(_as_float(first["positive_weight_share"])),
            "without_shared": (
                printed_coarse(_as_float(first["without_shared"]))
                if first["without_shared_formed"]
                else NOT_FORMED
            ),
        }
        if first["loo_formed"]:
            first_printed["loo_min"] = printed_coarse(_as_float(first["loo_min"]))
            first_printed["loo_max"] = printed_coarse(_as_float(first["loo_max"]))
        else:
            first_printed["loo_range"] = NOT_FORMED

    return {
        "half": description["half"],
        "sessions": description["sessions"],
        "repositories": description["repositories"],
        "measures": measures,
        "first_measure_repository": first_printed,
        "provenance": dict(provenance),
    }


# --- output -------------------------------------------------------------------


def write_json(out_path: Path, obj: dict[str, object]) -> None:
    """Writes one output file with mode 0600 and refuses to overwrite an existing file."""
    text = json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    try:
        fd = os.open(str(out_path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        raise OutputRefused from None
    with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
        _ = handle.write(text)


def _run_stage_one(args: argparse.Namespace) -> int:
    out_dir = Path(str(args.out_dir))
    half = str(args.half)
    try:
        counts = stage_one(Path(str(args.signal)), Path(str(args.outcome)), half)
    except TableInvalid:
        print("table-invalid", file=sys.stderr)
        return 2
    try:
        write_json(out_dir / f"checks_{half}.json", counts)
    except OutputRefused:
        print("output-exists", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"write: {type(exc).__name__}", file=sys.stderr)
        return 1
    print(json.dumps(counts, indent=2, sort_keys=True, ensure_ascii=True))
    return 0 if counts["all_same"] else 3


def _integer(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _recorded_found(entries: object, registered: dict[str, int]) -> dict[str, int] | None:
    """The `found` figure of every entry of a checks file's list, or None on any fault.

    Every entry must carry the verdict `same`, a `found` equal to its own `registered` figure,
    and a `registered` figure equal to the one this text fixes; the list must hold exactly the
    registered check names, once each.
    """
    if not isinstance(entries, list):
        return None
    raw_entries = cast(list[object], entries)
    found: dict[str, int] = {}
    for entry in raw_entries:
        if not isinstance(entry, dict):
            return None
        item = {str(key): value for key, value in cast(dict[object, object], entry).items()}
        name = item.get("name")
        if not isinstance(name, str) or name in found or name not in registered:
            return None
        if item.get("verdict") != "same":
            return None
        number, expected = _integer(item.get("found")), _integer(item.get("registered"))
        if number is None or expected is None:
            return None
        if expected != registered[name] or number != expected:
            return None
        found[name] = number
    return found if found == registered else None


def _checks_allow(checks_path: Path, half: str, signal: Path, outcome: Path) -> bool:
    """Whether the checks file lets stage 2 run.

    Registration, "Order of work" step 4: "If any check count differs from the figure this text
    fixes, stage 2 does not run". The flag alone is not trusted: every entry of the file's own
    list is read, every registered figure is compared with the one this text fixes, stage 1's
    counts are recomputed from the two tables, and the file's two "also printed" counts are
    compared with the recount's own.
    """
    try:
        raw: object = json.loads(checks_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError):
        return False
    if not isinstance(raw, dict):
        return False
    recorded = {str(key): value for key, value in cast(dict[object, object], raw).items()}
    if recorded.get("half") != half or recorded.get("all_same") is not True:
        return False
    registered = REGISTERED_CHECKS[half]
    if _recorded_found(recorded.get("checks"), registered) is None:
        return False
    try:
        if recorded.get("signal_sha256") != digest_of(signal):
            return False
        if recorded.get("outcome_sha256") != digest_of(outcome):
            return False
        # The recount: stage 1's own function over the two tables, which pairs nothing.
        recount = stage_one(signal, outcome, half)
        if recount.get("all_same") is not True:
            return False
        if _recorded_found(recount.get("checks"), registered) is None:
            return False
        # The registration names two counts beside the checks; the file's copy of them is
        # compared with the recount's, so neither can be invented.
        if recorded.get("also_printed") != recount.get("also_printed"):
            return False
    except TableInvalid:
        return False
    return True


def start_time_of_first_run(path: Path) -> str | None:
    """The `provenance.start_time` of the first run's result file, or None when it is not there
    in the registered form.

    Nothing else of that file is read, and nothing of it is compared with this run's own result.
    """
    try:
        raw: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError):
        return None
    if not isinstance(raw, dict):
        return None
    provenance = cast(dict[object, object], raw).get("provenance")
    if not isinstance(provenance, dict):
        return None
    value = cast(dict[object, object], provenance).get("start_time")
    if not isinstance(value, str) or not START_TIME_RE.match(value):
        return None
    return value


def _same_folder(left: Path, right: Path) -> bool:
    try:
        return left.resolve() == right.resolve()
    except OSError:  # pragma: no cover - resolve() does not touch the file system here
        return str(left) == str(right)


def _start_time(args: argparse.Namespace, out_dir: Path) -> str | None:
    """The start time of this run, or None when the two flags do not name one.

    The time stamps the paired sequence of two executions, which the registration calls "the one
    start" ("These two runs are the one start; they are not two attempts"), not each process.
    Exactly one of the two flags is required: `--first-run` stamps the clock, and
    `--second-run-of FILE` takes the stamp of the first run's result file, so that the two files
    are byte-identical with no value passed in by hand.
    """
    first_run = bool(args.first_run)
    second_run_of = None if args.second_run_of is None else Path(str(args.second_run_of))
    if first_run == (second_run_of is not None):
        return None
    if second_run_of is None:
        start_time = started_now()
    else:
        if _same_folder(out_dir, second_run_of.parent):
            return None
        recorded = start_time_of_first_run(second_run_of)
        if recorded is None:
            return None
        start_time = recorded
    return start_time if START_TIME_RE.match(start_time) else None


def _run_stage_two(args: argparse.Namespace) -> int:
    out_dir = Path(str(args.out_dir))
    half = str(args.half)
    signal, outcome = Path(str(args.signal)), Path(str(args.outcome))
    if args.checks is None or args.registration_commit is None or args.record_commit is None:
        print("arguments-invalid", file=sys.stderr)
        return 2
    registration_commit, record_commit = str(args.registration_commit), str(args.record_commit)
    if not _COMMIT_RE.match(registration_commit) or not _COMMIT_RE.match(record_commit):
        print("arguments-invalid", file=sys.stderr)
        return 2
    start_time = _start_time(args, out_dir)
    if start_time is None:
        print("arguments-invalid", file=sys.stderr)
        return 2
    out_path = out_dir / f"result_{half}.json"
    if os.path.lexists(str(out_path)):
        print("output-exists", file=sys.stderr)
        return 2
    if not _checks_allow(Path(str(args.checks)), half, signal, outcome):
        print("checks-refused", file=sys.stderr)
        return 3

    try:
        description = describe(signal, outcome, half)
        provenance = {
            "registration_commit": registration_commit,
            "record_commit": record_commit,
            "analyze_sha256": digest_of(Path(__file__)),
            "signal_sha256": digest_of(signal),
            "outcome_sha256": digest_of(outcome),
            "start_time": start_time,
        }
        result = printed_result(description, provenance)
    except TableInvalid:
        print("table-invalid", file=sys.stderr)
        return 2

    try:
        write_json(out_path, result)
    except OutputRefused:
        print("output-exists", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"write: {type(exc).__name__}", file=sys.stderr)
        return 1
    return 0


def started_now() -> str:
    """The current time in the form the registration's result file records: UTC, whole seconds.

    It is read once, by the first of the two runs of step 5; the second run takes that run's
    stamp, because the time belongs to the paired sequence and not to one process.
    """
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def main(argv: list[str] | None = None) -> int:
    parser = _ArgumentParser(add_help=False, allow_abbrev=False)
    _ = parser.add_argument("--stage", required=True, choices=("1", "2"))
    _ = parser.add_argument("--signal", required=True)
    _ = parser.add_argument("--outcome", required=True)
    _ = parser.add_argument("--half", required=True, choices=HALVES)
    _ = parser.add_argument("--out-dir", required=True, dest="out_dir")
    _ = parser.add_argument("--checks")
    _ = parser.add_argument("--registration-commit", dest="registration_commit")
    _ = parser.add_argument("--record-commit", dest="record_commit")
    _ = parser.add_argument("--first-run", dest="first_run", action="store_true")
    _ = parser.add_argument("--second-run-of", dest="second_run_of")
    try:
        args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    except SystemExit:
        return 2

    if str(args.stage) == "1":
        return _run_stage_one(args)
    return _run_stage_two(args)


if __name__ == "__main__":
    raise SystemExit(main())
