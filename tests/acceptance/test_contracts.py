"""Contract evaluation. FROZEN."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import JsonValue

from arci.interfaces import ContractRejected
from arci.schema import Event
from tests.acceptance.helpers import contract

pytestmark = pytest.mark.acceptance
TASK: dict[str, JsonValue] = {"goal": "store 42"}


def _calls(*tools: str) -> list[Event]:
    events: list[Event] = []
    for i, tool in enumerate(tools):
        events.append(Event(trial_id="t", seq=2 * i, kind="tool_start", payload={"tool": tool}))
        events.append(
            Event(
                trial_id="t", seq=2 * i + 1, kind="tool_finish", payload={"tool": tool, "ok": True}
            )
        )
    return events


def test_success_comes_only_from_the_oracle_over_final_state() -> None:
    from arci.contracts import evaluate_contract

    ok = evaluate_contract(contract(), _calls("fetch", "store"), TASK, {"stored": 42, "log": []})
    bad = evaluate_contract(contract(), _calls("fetch", "store"), TASK, {"stored": None, "log": []})
    assert ok.success and not ok.violations and ok.grader_error is None
    assert not bad.success and bad.grader_error is None


def test_missing_final_state_is_not_success() -> None:
    from arci.contracts import evaluate_contract

    assert not evaluate_contract(contract(), [], TASK, None).success


def test_oracle_exception_is_a_grader_error_not_an_agent_failure() -> None:
    from arci.contracts import evaluate_contract

    r = evaluate_contract(contract("raising_oracle"), [], TASK, {"stored": 42})
    assert r.grader_error is not None and "grader exploded" in r.grader_error
    assert not r.success


def test_unresolvable_oracle_is_a_grader_error() -> None:
    from arci.contracts import evaluate_contract

    r = evaluate_contract(contract("no_such_function"), [], TASK, {"stored": 42})
    assert r.grader_error is not None


def test_boundary_invariants_produce_hard_violations() -> None:
    from arci.contracts import evaluate_contract

    spec = contract(
        max_tool_calls=2,
        forbidden_tools=("log",),
        required_tools=("store",),
        max_calls_per_tool={"fetch": 1},
    )
    r = evaluate_contract(spec, _calls("log", "fetch", "fetch"), TASK, {"stored": 42})
    names = {v.invariant for v in r.violations}
    assert names == {"max_tool_calls", "forbidden_tools", "required_tools", "max_calls_per_tool"}
    assert all(v.severity == "hard" for v in r.violations)
    assert r.success  # the oracle still says the goal state holds; the gate blocks on violations


def test_unobservable_invariants_are_rejected_up_front() -> None:
    from arci.contracts import validate_contract

    validate_contract(contract())
    with pytest.raises(ContractRejected):
        validate_contract(contract(unobservable=("must_not_modify: billing/**",)))


def test_contract_loads_from_yaml(tmp_path: Path) -> None:
    from arci.contracts import load_contract

    path = tmp_path / "contract.yaml"
    path.write_text(
        "oracle: tests.acceptance.fixture_agents:oracle\nmax_tool_calls: 5\nforbidden_tools: [rm]\n"
    )
    spec = load_contract(path)
    assert spec.max_tool_calls == 5 and spec.forbidden_tools == ("rm",)
