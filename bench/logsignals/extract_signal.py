#!/usr/bin/env python3
"""Program 1 of the log-signals study: the private signal table.

Reads the pool manifest and, for every Codex row whose transcript is eligible, writes one row of
`signal.tsv` (the format is fixed by `INTERFACE.md`). It calls the unchanged reader
`arci.logs.codex.read` once per transcript, exactly as the frozen count program does. It knows no
outcome, opens no table and prints nothing about any transcript: on success it prints counts
only.

The registration says of the second measure: "The tool defines it with at least 10 such
responses; every eligible Codex session has it." An eligible session with fewer than 10 counts
above 0 therefore breaks the registration, and that ends the study before any pairing: nothing
is written, the fixed word `second-measure-undefined` goes to stderr and the exit code is 5.

Importing this module has no side effects.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
import sys
from collections import Counter
from datetime import UTC, datetime
from fractions import Fraction
from pathlib import Path
from typing import Any, NoReturn

from arci.logs import codex

NOW = datetime(2100, 1, 1, tzinfo=UTC)
MINIMUM_RESPONSES = 20
# The registration defines the second measure with at least 10 counts above 0 ("The tool defines
# it with at least 10 such responses; every eligible Codex session has it"). An eligible session
# below that bound contradicts the registration and stops the extraction.
MINIMUM_POSITIVE_COUNTS = 10
UNKNOWN = "unknown"

HEADER: tuple[str, ...] = (
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

_TRANSCRIPT_PATH_RE = re.compile(r"\Atranscripts[0-9]*/[^/\\\x00-\x1f]+\.jsonl\Z")
_HEX16_RE = re.compile(r"\A[0-9a-f]{16}\Z")
_MONTH_RE = re.compile(r"\A20[0-9]{2}-(0[1-9]|1[0-2])\Z")
_SAFE_FIELD_RE = re.compile(r"\A[^\t\n\r\x00-\x1f]{1,120}\Z")
_VALID_GROUPS = frozenset({"claude_code", "codex"})
_VALID_HALVES = frozenset({"discovery", "confirmation"})


class ManifestInvalid(Exception):
    """Raised for any manifest content violation. Carries no detail."""


class FieldUnsafe(Exception):
    """Raised when a field of an eligible session would not be safe to write. Carries no detail.

    The registration says "All eligible sessions enter. No trimming, no transformation, no
    deletion", so such a session is not dropped: the whole extraction stops instead.
    """


class SecondMeasureUndefined(Exception):
    """Raised when an eligible session has fewer than 10 counts above 0. Carries no detail.

    The registration states that every eligible Codex session has the second measure. A session
    that breaks it ends the study before pairing, so there is no "undefined second measure" path:
    nothing is written and the extraction stops.
    """


class FieldsUnreadable(Exception):
    """Raised when reading the reader's result raised. Carries no detail.

    A raise of the reader itself is counted as `reader_exception` and the session is skipped, as
    the reference does. A raise inside `session_fields` is a fault of this program's own reading
    of a result it already holds, so it stops the extraction instead of being counted away.
    """


class OutputRefused(Exception):
    """Raised when the output file exists already. Carries no detail."""


class _ArgumentParser(argparse.ArgumentParser):
    """Prints the single word ``arguments-invalid`` (no usage text) and exits 2."""

    def error(self, message: str) -> NoReturn:  # argparse override: it never returns
        print("arguments-invalid", file=sys.stderr)
        raise SystemExit(2)


# --- manifest ----------------------------------------------------------------


def validate_and_parse_manifest(text: str) -> list[dict[str, str]]:
    """Strict manifest validation. Raises ManifestInvalid on any violation and never leaks a
    value in the exception."""
    raw_lines = text.split("\n")
    if raw_lines and raw_lines[-1] == "":
        raw_lines = raw_lines[:-1]

    lines: list[dict[str, str]] = []
    seen_paths: set[str] = set()
    for raw in raw_lines:
        if raw == "":
            continue
        parts = raw.split("\t")
        if len(parts) != 6:
            raise ManifestInvalid
        transcript_path, group, repo_key, half, month, user_key = parts
        if not _TRANSCRIPT_PATH_RE.match(transcript_path):
            raise ManifestInvalid
        if transcript_path in seen_paths:
            raise ManifestInvalid
        if group not in _VALID_GROUPS:
            raise ManifestInvalid
        if not _HEX16_RE.match(repo_key):
            raise ManifestInvalid
        if half not in _VALID_HALVES:
            raise ManifestInvalid
        if month != "" and not _MONTH_RE.match(month):
            raise ManifestInvalid
        if user_key != "" and not _HEX16_RE.match(user_key):
            raise ManifestInvalid
        seen_paths.add(transcript_path)
        lines.append(
            {
                "transcript_path": transcript_path,
                "group": group,
                "repo_key": repo_key,
                "half": half,
                "month": month,
                "user_key": user_key,
            }
        )
    return lines


def read_manifest(manifest_path: Path) -> list[dict[str, str]]:
    try:
        data = manifest_path.read_bytes()
    except OSError:
        raise ManifestInvalid from None
    try:
        text = data.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        raise ManifestInvalid from None
    return validate_and_parse_manifest(text)


# --- file classification -----------------------------------------------------


def classify_path(data_dir_real: str, transcript_path: str) -> str:
    """Returns "present", "absent" or "not_regular". Only present files are read."""
    first_component = transcript_path.split("/", 1)[0]
    expected_parent = os.path.join(data_dir_real, first_component)
    full = os.path.join(data_dir_real, transcript_path)
    try:
        real_parent = os.path.realpath(os.path.dirname(full))
    except (OSError, ValueError):
        return "not_regular"
    if real_parent != expected_parent:
        return "not_regular"
    try:
        st = os.lstat(full)
    except FileNotFoundError:
        return "absent"
    except OSError:
        return "not_regular"
    if not stat.S_ISREG(st.st_mode):
        return "not_regular"
    return "present"


# --- reader wrapper ----------------------------------------------------------


def safe_read(reader: Any, path: Path) -> tuple[bool, Any]:
    """Calls reader.read([path], project=None, now=NOW), catching every exception. Returns
    (ok, result); ok is False on any exception and nothing of the exception is kept."""
    try:
        return True, reader.read([path], project=None, now=NOW)
    except Exception:
        return False, None


def read_session(reader: Any, path: Path) -> tuple[bool, dict[str, str] | None]:
    """The signal-side fields of one transcript.

    Returns (ok, fields). `ok` is False only when the reader itself raised: that is counted as
    `reader_exception` and the session is skipped, as the reference does. `ok` with None fields
    means the session is not eligible.

    A raise inside `session_fields` is not counted and not skipped: it becomes
    `FieldsUnreadable` and stops the extraction. `SecondMeasureUndefined` passes through for the
    same reason.
    """
    ok, result = safe_read(reader, path)
    if not ok:
        return False, None
    try:
        return True, session_fields(result)
    except SecondMeasureUndefined:
        raise
    except Exception:
        raise FieldsUnreadable from None


# --- the measures of one session ---------------------------------------------


def median(values: list[int]) -> Fraction:
    ordered = sorted(values)
    m = len(ordered)
    mid = m // 2
    if m % 2 == 1:
        return Fraction(ordered[mid])
    return Fraction(ordered[mid - 1] + ordered[mid], 2)


def model_name(names: list[str]) -> str:
    """The most frequent name; a tie goes to the name that sorts first as a string."""
    if not names:
        return UNKNOWN
    counts: Counter[str] = Counter(names)
    return min(counts.items(), key=lambda item: (-item[1], item[0]))[0]


def session_fields(result: Any) -> dict[str, str] | None:
    """The signal-side fields of one transcript, or None when it is not eligible.

    Everything here comes from the reader's result and from nothing else.

    `first_time` is the earliest timestamp among the main-thread responses the unchanged reader
    returns in `result.responses`, including those without a known reasoning count. It is not the
    first response in file order: the reader keeps the order of the file, which need not be the
    order of the timestamps. Responses that are not on the main thread are left out before the
    minimum is taken.
    """
    responses: list[Any] = [r for r in result.responses if r.main_thread]
    models: tuple[str | None, ...] = tuple(result.models)
    known: list[Any] = [r for r in responses if r.reasoning is not None]
    d = len(known)
    if d < MINIMUM_RESPONSES:
        return None

    counts: list[int] = [int(r.reasoning) for r in known]
    zero = sum(1 for value in counts if value == 0)
    positive = [value for value in counts if value > 0]
    # The second measure is the median of the counts above 0, defined with at least 10 of them.
    # The registration says every eligible session has it, so fewer than 10 ends the extraction.
    if len(positive) < MINIMUM_POSITIVE_COUNTS:
        raise SecondMeasureUndefined
    tokens = median(positive)

    # The vote is over the names this session's counted responses carry. A response with no
    # rendered name gives no vote; the session takes `unknown` only when none carries a name.
    names: list[str] = []
    for response in known:
        index = int(response.model)
        raw = models[index] if 0 <= index < len(models) else None
        if raw:
            names.append(raw)

    first = min((r.when for r in responses), default=None)
    first_time = "" if first is None else first.astimezone(UTC).isoformat()

    return {
        "model": model_name(names),
        "d": str(d),
        "first_time": first_time,
        "zero": str(zero),
        "tokens_num": str(tokens.numerator),
        "tokens_den": str(tokens.denominator),
    }


# --- the run -----------------------------------------------------------------


def run(manifest_path: Path, data_dir: Path) -> tuple[list[str], dict[str, int]]:
    """Returns the rows of `signal.tsv` (without the header) and the counts."""
    lines = read_manifest(manifest_path)
    data_dir_real = os.path.realpath(str(data_dir))

    counts = {
        "manifest_lines": len(lines),
        "codex_rows": 0,
        "files_present": 0,
        "files_absent": 0,
        "files_not_regular": 0,
        "reader_exception": 0,
        "not_eligible": 0,
        "rows_written": 0,
    }
    rows: list[str] = []

    for line in lines:
        if line["group"] != "codex":
            continue
        counts["codex_rows"] += 1
        status = classify_path(data_dir_real, line["transcript_path"])
        if status == "present":
            counts["files_present"] += 1
        elif status == "absent":
            counts["files_absent"] += 1
            continue
        else:
            counts["files_not_regular"] += 1
            continue

        full_path = Path(data_dir_real) / line["transcript_path"]
        ok, fields = read_session(codex, full_path)
        if not ok:
            counts["reader_exception"] += 1
            counts["not_eligible"] += 1
            continue
        if fields is None:
            counts["not_eligible"] += 1
            continue

        if not _SAFE_FIELD_RE.match(fields["model"]):
            # Unreachable with the shipped reader, which only renders bounded model ids. An
            # eligible session is never dropped: the extraction stops instead.
            raise FieldUnsafe
        row = [
            line["transcript_path"],
            line["repo_key"],
            line["half"],
            line["month"],
            line["user_key"],
            fields["model"],
            fields["d"],
            fields["first_time"],
            fields["zero"],
            fields["tokens_num"],
            fields["tokens_den"],
        ]
        rows.append("\t".join(row))
        counts["rows_written"] += 1

    return rows, counts


def write_table(out_path: Path, rows: list[str]) -> None:
    """Creates the table with mode 0600 and refuses to overwrite an existing file."""
    text = "\t".join(HEADER) + "\n" + "".join(row + "\n" for row in rows)
    try:
        fd = os.open(str(out_path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        raise OutputRefused from None
    with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
        _ = handle.write(text)


def main(argv: list[str]) -> int:
    parser = _ArgumentParser(add_help=False, allow_abbrev=False)
    _ = parser.add_argument("--manifest", required=True)
    _ = parser.add_argument("--data-dir", required=True)
    _ = parser.add_argument("--out", required=True)
    try:
        args = parser.parse_args(argv)
    except SystemExit:
        return 2

    out_path = Path(str(args.out))
    if os.path.lexists(str(out_path)):
        print("output-exists", file=sys.stderr)
        return 2

    try:
        rows, counts = run(Path(str(args.manifest)), Path(str(args.data_dir)))
    except ManifestInvalid:
        print("manifest-invalid", file=sys.stderr)
        return 2
    except SecondMeasureUndefined:
        print("second-measure-undefined", file=sys.stderr)
        return 5
    except FieldUnsafe:
        print("field-unsafe", file=sys.stderr)
        return 1
    except FieldsUnreadable:
        print("fields-unreadable", file=sys.stderr)
        return 1
    except SystemExit:
        return 1
    except Exception as exc:
        print(f"run: {type(exc).__name__}", file=sys.stderr)
        return 1

    try:
        write_table(out_path, rows)
    except OutputRefused:
        print("output-exists", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"write: {type(exc).__name__}", file=sys.stderr)
        return 1

    print(json.dumps(counts, indent=2, sort_keys=True, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
