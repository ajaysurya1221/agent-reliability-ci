"""The frozen schedule. FROZEN."""

from __future__ import annotations

import pytest

from arci.schedule import build_schedule, spec_sha256
from tests.acceptance.helpers import COND_CLEAN, COND_TIMEOUT, manifest

pytestmark = pytest.mark.acceptance


def test_schedule_is_deterministic_paired_and_complete() -> None:
    m = manifest(n_per_arm=5, conditions=(COND_CLEAN, COND_TIMEOUT))
    schedule = build_schedule(m)
    assert schedule == build_schedule(m)
    assert len(schedule) == 2 * 2 * 5
    assert len({s.trial_id for s in schedule}) == len(schedule)
    assert len({spec_sha256(s) for s in schedule}) == len(schedule)
    by_pair: dict[str, list[int]] = {}
    for s in schedule:
        by_pair.setdefault(s.pair_id, []).append(s.seed)
    assert all(len(v) == 2 and v[0] == v[1] for v in by_pair.values())  # arms share a seed
    assert len({v[0] for v in by_pair.values()}) == len(by_pair)  # pairs do not
    first = schedule[0]
    assert (first.trial_id, first.pair_id, first.seed) == ("clean:00000:baseline", "clean:00000", 7)
    assert schedule[-1].seed == 7 + 1 * 5 + 4
    assert first.variant == "A" and schedule[1].variant == "B"
