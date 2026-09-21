"""Canonical JSON hashing. FROZEN (orchestrator-owned).

Hashes here are integrity checks, not signed provenance: they detect accidental
or careless modification, they do not authenticate who produced a record.

`canonical_json` and `hash_record` are adapted from evalopt-graph
(src/evalopt_graph/attestation.py), MIT License, (c) 2026 Ajay Surya Senthilrajan.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from hashlib import sha256
from typing import Any

# Timing and self-referential fields never enter a digest, so the same logical
# record hashes identically across machines and reruns.
VOLATILE_FIELDS: frozenset[str] = frozenset(
    {"record_sha256", "at_ms", "duration_ms", "wall_seconds", "created_at"}
)


def canonical_json(value: object) -> bytes:
    """Sorted keys, no whitespace, UTF-8, non-finite floats rejected."""
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode()


def hash_record(value: Mapping[str, object]) -> str:
    return sha256(canonical_json(value)).hexdigest()


def hash_bytes(data: bytes) -> str:
    return sha256(data).hexdigest()


def strip_volatile(value: Any, excluded: frozenset[str] = VOLATILE_FIELDS) -> Any:
    """Recursively drop volatile keys from mappings; leave everything else intact."""
    if isinstance(value, Mapping):
        return {
            str(k): strip_volatile(v, excluded)
            for k, v in value.items()  # pyright: ignore[reportUnknownVariableType]
            if k not in excluded
        }
    if isinstance(value, (list, tuple)):
        return [strip_volatile(v, excluded) for v in value]  # pyright: ignore[reportUnknownVariableType]
    return value


def seal_digest(payload: Mapping[str, object]) -> str:
    """Digest of a record with volatile fields (including its own seal) removed."""
    return hash_record(strip_volatile(payload))
