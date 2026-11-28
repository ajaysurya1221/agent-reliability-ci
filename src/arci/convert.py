"""Convert a captured evaluation export into neutral, source-bound JSONL rows."""

from __future__ import annotations

import os
import sys
import tempfile
from collections import Counter
from contextlib import suppress
from pathlib import Path
from typing import TextIO

from arci.hashing import canonical_json, hash_bytes
from arci.importers.promptfoo import READER, TESTED_VERSIONS, PromptfooError, PromptfooResult, read
from arci.outcome_report import escape_terminal

_EXISTING_RESULTS = (
    "These are existing results: use arci verdict-rule and arci verdict for a descriptive verdict; "
    "the error bound needs fresh runs (arci check-change)."
)


def neutral_jsonl(result: PromptfooResult, source_sha256: str) -> bytes:
    lines: list[bytes] = []
    for row in result.rows:
        record: dict[str, object] = {
            "task_id": row.task_id,
            "outcome": row.outcome,
            "reader": READER,
            "source_sha256": source_sha256,
        }
        if row.round is not None:
            record["round"] = row.round
        lines.append(canonical_json(record) + b"\n")
    return b"".join(lines)


def _remove_temporary(path: str) -> str | None:
    for _ in range(3):
        try:
            os.unlink(path)
        except FileNotFoundError:
            return None
        except OSError:
            continue
        return None
    return path


def _write_new(out: Path, content: bytes) -> str | None:
    try:
        fd, temporary = tempfile.mkstemp(dir=out.parent)
    except OSError as exc:
        raise PromptfooError("cannot create output file") from exc
    try:
        with os.fdopen(fd, "wb") as stream:
            if stream.write(content) != len(content):
                raise OSError("short write")
        os.link(temporary, out)
    except FileExistsError as exc:
        raise PromptfooError("output already exists") from exc
    except OSError as exc:
        raise PromptfooError("cannot write output file") from exc
    finally:
        leftover = _remove_temporary(temporary)
    return leftover


def stream_text(text: str, stream: TextIO) -> str:
    """Preserve printable Unicode when the destination encoding supports it."""
    encoding = getattr(stream, "encoding", None) or "utf-8"
    return text.encode(encoding, errors="backslashreplace").decode(encoding)


def convert(
    source: Path, out: Path, *, prompt: int | None = None, provider: str | None = None
) -> int:
    try:
        if not out.name.endswith(".jsonl"):
            raise PromptfooError("output must end in .jsonl")
        if out.resolve() == source.resolve():
            raise PromptfooError("output must differ from the source")
        if not out.parent.is_dir():
            raise PromptfooError("output folder must exist")
        try:
            raw = source.read_bytes()
        except OSError as exc:
            raise PromptfooError("cannot read source file") from exc
        result = read(raw, prompt=prompt, provider=provider)
        digest = hash_bytes(raw)
        leftover = _write_new(out, neutral_jsonl(result, digest))
    except (PromptfooError, OSError) as exc:
        print(stream_text(f"convert: {escape_terminal(str(exc))}", sys.stderr), file=sys.stderr)
        return 3

    version = escape_terminal(result.tool_version or "unknown")
    counts = Counter(row.outcome for row in result.rows)
    lines = [
        f"reader: {READER}",
        f"tool version: {version}",
        f"source_sha256: {digest}",
        f"selected cell: {escape_terminal(str(result.selected_cell))}",
        f"rows: {len(result.rows)}, rounds: {len({row.round for row in result.rows})}",
        f"pass: {counts['pass']}, fail: {counts['fail']}, error: {counts['error']}",
    ]
    if result.tool_version not in TESTED_VERSIONS:
        lines.append(f"Notice: {READER} was not tested with promptfoo version {version}.")
    if result.cache is True:
        lines.append(
            "Notice: the cache was on, so answers may come from earlier runs "
            "that the file cannot show."
        )
    lines.append(_EXISTING_RESULTS)
    if leftover is not None:
        lines.append(f"Notice: could not remove temporary file {escape_terminal(leftover)}")
    try:
        print(stream_text("\n".join(lines), sys.stdout), flush=True)
    except Exception:
        # Publication succeeded. Keep the interpreter's shutdown flush from
        # retrying a failed write to the process's stdout (which would exit 120).
        if sys.stdout is sys.__stdout__:
            with suppress(OSError, ValueError):
                sys.stdout.close()
    return 0
