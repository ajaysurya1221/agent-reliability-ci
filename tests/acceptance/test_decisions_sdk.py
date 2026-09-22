"""v0.5: the official TypeSafe Python SDK against the boundary, unmodified. FROZEN.

Skipped when `typesafe-sdk` is not installed (it is a dev dependency, never a runtime one). Proves
the zero-change claim: `TypeSafeClient()` reads the endpoint and token from the environment.
"""

from __future__ import annotations

import importlib.util
from typing import cast

import pytest

from arci.schema import DECISION_TOOL, Outcome, Termination, TrialEnvelope
from tests.acceptance.decision_fixtures import COND_UNAVAILABLE, decision_contract, decision_spec
from tests.acceptance.helpers import COND_CLEAN

pytestmark = [
    pytest.mark.acceptance,
    pytest.mark.skipif(
        importlib.util.find_spec("typesafe_sdk") is None, reason="typesafe-sdk absent"
    ),
]


def _run(variant: str, **kw: object) -> TrialEnvelope:
    from arci.runner import run_trial

    return run_trial(decision_spec(variant, **kw), lambda _e: None, decision_contract())  # pyright: ignore[reportArgumentType]


def _starts(env: TrialEnvelope) -> list[str]:
    return [cast(str, e.payload["tool"]) for e in env.events if e.kind == "tool_start"]


def test_the_official_sdk_needs_no_change() -> None:
    env = _run("sdk", condition=COND_CLEAN)
    assert env.outcome is Outcome.PASS, env.failure_detail
    assert env.final_state == {"stored": "refund", "log": ["start"]}
    assert _starts(env) == ["log", DECISION_TOOL, "store"]


def test_the_sdk_retries_twice_then_the_agent_degrades() -> None:
    env = _run("sdk", condition=COND_UNAVAILABLE, max_seconds=40.0)
    assert env.outcome is Outcome.PASS and env.termination is Termination.COMPLETED
    assert env.final_state == {"stored": "escalate", "log": ["start"]}
    assert _starts(env).count(DECISION_TOOL) == 3  # one attempt plus the SDK's default two retries
