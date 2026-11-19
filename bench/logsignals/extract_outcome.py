#!/usr/bin/env python3
"""Program 2 of the log-signals study: the private outcome table.

Reads two columns of the dataset's sessions table -- `transcript_path` and `agent_percentage` --
and writes one row of `outcome.tsv` for every manifest path found in the table. It knows no
signal, opens no transcript and never imports `arci`.

It runs in an environment that has `pyarrow`; this repository's environment has not, so the
import happens inside `main`. Importing this module has no side effects.
"""

from __future__ import annotations

import argparse
import importlib
import json
import math
import os
import re
import sys
from pathlib import Path
from typing import Any, NoReturn

COLUMNS: tuple[str, ...] = ("transcript_path", "agent_percentage")
HEADER: tuple[str, ...] = ("path", "agent_percentage")

_TRANSCRIPT_PATH_RE = re.compile(r"\Atranscripts[0-9]*/[^/\\\x00-\x1f]{1,480}\.jsonl\Z")
_HEX16_RE = re.compile(r"\A[0-9a-f]{16}\Z")
_MONTH_RE = re.compile(r"\A20[0-9]{2}-(0[1-9]|1[0-2])\Z")
_VALID_GROUPS = frozenset({"claude_code", "codex"})
_VALID_HALVES = frozenset({"discovery", "confirmation"})


class ManifestInvalid(Exception):
    """Raised for any manifest content violation. Carries no detail."""


class SchemaInvalid(Exception):
    """Raised when a needed column is absent or carries another type."""


class OutputRefused(Exception):
    """Raised when the output file exists already. Carries no detail."""


class _ArgumentParser(argparse.ArgumentParser):
    """Prints the single word ``arguments-invalid`` (no usage text) and exits 2."""

    def error(self, message: str) -> NoReturn:  # argparse override: it never returns
        print("arguments-invalid", file=sys.stderr)
        raise SystemExit(2)


def manifest_paths(text: str) -> list[str]:
    """The manifest paths in manifest order. Validation is that of the signal side: six fields,
    a valid path, no path twice. Raises ManifestInvalid and leaks no value."""
    raw_lines = text.split("\n")
    if raw_lines and raw_lines[-1] == "":
        raw_lines = raw_lines[:-1]
    paths: list[str] = []
    seen: set[str] = set()
    for raw in raw_lines:
        if raw == "":
            continue
        parts = raw.split("\t")
        if len(parts) != 6:
            raise ManifestInvalid
        path, group, repo_key, half, month, user_key = parts
        if not _TRANSCRIPT_PATH_RE.match(path) or path in seen:
            raise ManifestInvalid
        if group not in _VALID_GROUPS or not _HEX16_RE.match(repo_key):
            raise ManifestInvalid
        if half not in _VALID_HALVES:
            raise ManifestInvalid
        if month != "" and not _MONTH_RE.match(month):
            raise ManifestInvalid
        if user_key != "" and not _HEX16_RE.match(user_key):
            raise ManifestInvalid
        seen.add(path)
        paths.append(path)
    return paths


def read_manifest(manifest_path: Path) -> list[str]:
    try:
        data = manifest_path.read_bytes()
    except OSError:
        raise ManifestInvalid from None
    try:
        text = data.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        raise ManifestInvalid from None
    return manifest_paths(text)


def is_missing(value: object) -> bool:
    if value is None:
        return True
    return isinstance(value, float) and math.isnan(value)


def validate_schema(parquet: Any, arrow: Any, sessions: str) -> None:
    schema: Any = parquet.ParquetFile(sessions).schema_arrow
    names: set[str] = set(schema.names)
    for column in COLUMNS:
        if column not in names:
            raise SchemaInvalid
    path_type: Any = schema.field("transcript_path").type
    if not (arrow.types.is_string(path_type) or arrow.types.is_large_string(path_type)):
        raise SchemaInvalid
    value_type: Any = schema.field("agent_percentage").type
    if not (arrow.types.is_floating(value_type) or arrow.types.is_integer(value_type)):
        raise SchemaInvalid


def read_columns(parquet: Any, arrow: Any, sessions: str) -> list[tuple[object, object]]:
    """The two columns as a list of (transcript_path, agent_percentage) pairs."""
    validate_schema(parquet, arrow, sessions)
    table: Any = parquet.read_table(sessions, columns=list(COLUMNS))
    paths: list[object] = list(table.column("transcript_path").to_pylist())
    values: list[object] = list(table.column("agent_percentage").to_pylist())
    if len(paths) != len(values):
        raise SchemaInvalid
    return list(zip(paths, values, strict=True))


def build_rows(
    paths: list[str], pairs: list[tuple[object, object]]
) -> tuple[list[str], dict[str, int]]:
    """One row per manifest path that is the path of exactly one table row, in manifest order."""
    by_path: dict[str, list[object]] = {}
    for raw_path, value in pairs:
        if not isinstance(raw_path, str):
            continue
        key = raw_path.strip()
        if key == "":
            continue
        by_path.setdefault(key, []).append(value)

    counts = {
        "manifest_paths": len(paths),
        "table_rows": len(pairs),
        "not_in_table": 0,
        "ambiguous": 0,
        "missing_value": 0,
        "rows_written": 0,
    }
    rows: list[str] = []
    for path in paths:
        matches = by_path.get(path, [])
        if len(matches) != 1:
            if matches:
                counts["ambiguous"] += 1
            else:
                counts["not_in_table"] += 1
            continue
        value = matches[0]
        if is_missing(value):
            counts["missing_value"] += 1
            written = ""
        elif isinstance(value, bool) or not isinstance(value, (int, float)):
            raise SchemaInvalid
        else:
            written = repr(float(value))
        rows.append(f"{path}\t{written}")
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


def main(argv: list[str] | None = None) -> int:
    parser = _ArgumentParser(add_help=False, allow_abbrev=False)
    _ = parser.add_argument("--sessions", required=True)
    _ = parser.add_argument("--manifest", required=True)
    _ = parser.add_argument("--out", required=True)
    try:
        args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    except SystemExit:
        return 2

    out_path = Path(str(args.out))
    if os.path.lexists(str(out_path)):
        print("output-exists", file=sys.stderr)
        return 2

    try:
        paths = read_manifest(Path(str(args.manifest)))
    except ManifestInvalid:
        print("manifest-invalid", file=sys.stderr)
        return 2

    # pyarrow lives only in the environment that holds the dataset, so it is imported here and
    # never at module level. Both modules are typed `Any`: no stubs are installed for them.
    try:
        arrow: Any = importlib.import_module("pyarrow")
        parquet: Any = importlib.import_module("pyarrow.parquet")
    except ImportError as exc:
        print(f"import: {type(exc).__name__}", file=sys.stderr)
        return 1

    try:
        pairs = read_columns(parquet, arrow, str(args.sessions))
        rows, counts = build_rows(paths, pairs)
    except SchemaInvalid:
        print("schema-invalid", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"sessions: {type(exc).__name__}", file=sys.stderr)
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
    raise SystemExit(main())
