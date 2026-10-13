"""Seeded inventory scenarios for the retry example.

The implementation lives in :mod:`arci.demo.world` so that ``arci demo`` runs from an
installed wheel; this module re-exports it, so ``examples.retry_agent.world:make_world``
and ``arci.demo.world:make_world`` resolve to the same objects and the same scenarios.
"""

from __future__ import annotations

from arci.demo.world import (
    CONFIRM_TRANSIENT_FAILURES,
    FLAKY_CONFIRM_SHARE,
    PREEXISTING_RESERVATION_SHARE,
    InventoryWorld,
    Scenario,
    Task,
    make_world,
    oracle,
    scenario_for_seed,
)

__all__ = [
    "CONFIRM_TRANSIENT_FAILURES",
    "FLAKY_CONFIRM_SHARE",
    "PREEXISTING_RESERVATION_SHARE",
    "InventoryWorld",
    "Scenario",
    "Task",
    "make_world",
    "oracle",
    "scenario_for_seed",
]
