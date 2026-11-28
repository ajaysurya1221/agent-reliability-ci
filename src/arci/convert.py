"""Convert a captured evaluation export into neutral, source-bound JSONL rows."""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

from arci.hashing import canonical_json, hash_bytes
from arci.importers.promptfoo import READER, TESTED_VERSIONS, PromptfooError, PromptfooResult, read

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


def _write_new(out: Path, content: bytes) -> None:
    try:
        stream = out.open("xb")
    except FileExistsError as exc:
        raise PromptfooError("output already exists") from exc
    except OSError as exc:
        raise PromptfooError("cannot create output file") from exc
    try:
        with stream:
            stream.write(content)
    except OSError as exc:
        out.unlink(missing_ok=True)
        raise PromptfooError("cannot write output file") from exc


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
        _write_new(out, neutral_jsonl(result, digest))
    except (PromptfooError, OSError) as exc:
        print(f"convert: {exc}", file=sys.stderr)
        return 3

    version = result.tool_version or "unknown"
    counts = Counter(row.outcome for row in result.rows)
    print(f"reader: {READER}")
    print(f"tool version: {version}")
    print(f"source_sha256: {digest}")
    print(f"selected cell: {result.selected_cell}")
    print(f"rows: {len(result.rows)}, rounds: {len({row.round for row in result.rows})}")
    print(f"pass: {counts['pass']}, fail: {counts['fail']}, error: {counts['error']}")
    if result.tool_version not in TESTED_VERSIONS:
        print(f"Notice: {READER} was not tested with promptfoo version {version}.")
    if result.cache is True:
        print(
            "Notice: the cache was on, so answers may come from earlier runs "
            "that the file cannot show."
        )
    print(_EXISTING_RESULTS)
    return 0
