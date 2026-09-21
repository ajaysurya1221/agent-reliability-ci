"""Sealing and schema hygiene. FROZEN. Passes from Wave 0 onward."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from arci.fingerprint import fingerprint
from arci.hashing import canonical_json
from arci.schema import EXIT_CODES, Manifest, Verdict
from tests.acceptance.helpers import manifest

pytestmark = pytest.mark.acceptance


def test_manifest_is_sealed_and_tamper_evident() -> None:
    m = manifest()
    assert m.validate_seal()
    assert not m.model_copy(update={"n_per_arm": 20}).validate_seal()
    assert not m.model_copy(update={"delta": 0.5}).validate_seal()


def test_volatile_fields_do_not_change_the_seal() -> None:
    m = manifest()
    assert m.model_copy(update={"created_at": "2026-09-21T00:00:00Z"}).validate_seal()


def test_n_per_arm_range_is_validated() -> None:
    data = manifest().model_dump(exclude={"record_sha256"})
    for bad in (0, -5, 10_001):
        with pytest.raises(ValidationError):
            Manifest.create(**{**data, "n_per_arm": bad})


def test_unknown_fields_are_rejected() -> None:
    data = manifest().model_dump(exclude={"record_sha256"})
    with pytest.raises(ValidationError):
        Manifest.create(**{**data, "surprise": 1})


def test_non_finite_numbers_cannot_be_hashed() -> None:
    with pytest.raises(ValueError):
        canonical_json({"x": float("nan")})


def test_exit_codes_are_frozen() -> None:
    assert {v.value: c for v, c in EXIT_CODES.items()} == {
        "PASS": 0,
        "BLOCK": 1,
        "INCONCLUSIVE": 2,
        "ERROR": 3,
    }
    assert Verdict("BLOCK") is Verdict.BLOCK


def test_fingerprint_scrubs_run_noise_unless_strict() -> None:
    a = fingerprint("crash", "KeyError at /tmp/run-1/agent.py:41 id=0xdeadbeef01\ntraceback...")
    b = fingerprint("crash", "KeyError   at /var/x/run-22/agent.py:97 id=0xfeedface99")
    assert a == b
    assert fingerprint("crash", "x 1", strict=True) != fingerprint("crash", "x 2", strict=True)
    assert fingerprint("oracle", "same") != fingerprint("crash", "same")
