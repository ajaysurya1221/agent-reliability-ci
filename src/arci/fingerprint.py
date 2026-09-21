"""Failure fingerprints. FROZEN (orchestrator-owned).

A fingerprint identifies "the same failure" across stochastic runs. Default mode
scrubs run-specific noise; strict mode keeps it.
"""

from __future__ import annotations

import re
from hashlib import sha256

_HEX = re.compile(r"\b(?:0x)?[0-9a-fA-F]{8,}\b")
_PATH = re.compile(r"(?:[A-Za-z]:)?(?:[\\/][\w.\-@+ ]+){2,}")
_NUM = re.compile(r"\d+(?:\.\d+)?")


def normalise(detail: str, *, strict: bool = False) -> str:
    """First line only, whitespace collapsed; paths, hex and numbers scrubbed unless strict."""
    lines = detail.splitlines()
    first = " ".join(lines[0].split()) if lines else ""
    if strict:
        return first
    first = _PATH.sub("<path>", first)
    first = _HEX.sub("<hex>", first)
    return _NUM.sub("<n>", first)


def fingerprint(kind: str, detail: str, *, strict: bool = False) -> str:
    """sha256 of `kind` plus the normalised first line of `detail`.

    `kind` namespaces the failure (for example "oracle", "tool_fault:timeout",
    "invariant:max_tool_calls", "crash"), so equal messages from different
    sources stay distinct.
    """
    return sha256(f"{kind}\n{normalise(detail, strict=strict)}".encode()).hexdigest()
