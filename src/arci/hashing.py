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


def canonical_json(value: object) -> bytes:
    """Sorted keys, no whitespace, UTF-8, non-finite floats rejected."""
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode()


def hash_record(value: Mapping[str, object]) -> str:
    return sha256(canonical_json(value)).hexdigest()


def hash_bytes(data: bytes) -> str:
    return sha256(data).hexdigest()
