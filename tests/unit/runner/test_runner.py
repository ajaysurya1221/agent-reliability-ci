from __future__ import annotations

import contextlib
import random

from pydantic import JsonValue

from arci.interfaces import BudgetExceeded, ToolBoxProtocol
from arci.runner import run_trial
from arci.schema import Budgets, Outcome, Termination
from tests.acceptance.helpers import COND_CLEAN, contract, spec


def model_budget_agent(
    task: dict[str, JsonValue], tools: ToolBoxProtocol, rng: random.Random
) -> dict[str, JsonValue]:
    del task, rng
    tools.note_model_step("first")
    with contextlib.suppress(BudgetExceeded):
        tools.note_model_step("over")
    tools.call("store", value=42)
    return {"success": True}


def test_same_spec_has_stable_seal() -> None:
    trial_spec = spec("fragile_agent")
    left = run_trial(trial_spec, lambda _event: None, contract())
    right = run_trial(trial_spec, lambda _event: None, contract())
    assert left.record_sha256 == right.record_sha256


def test_oracle_not_agent_claim_decides_outcome() -> None:
    trial = run_trial(spec("liar_agent", condition=COND_CLEAN), lambda _event: None, contract())
    assert trial.agent_claimed_success is True
    assert trial.outcome is Outcome.FAIL
    assert trial.termination is Termination.COMPLETED


def test_caught_model_step_budget_is_still_a_budget_failure() -> None:
    trial_spec = spec("good_agent", condition=COND_CLEAN).model_copy(
        update={
            "agent": "tests.unit.runner.test_runner:model_budget_agent",
            "budgets": Budgets(max_model_steps=1),
        }
    )
    trial = run_trial(trial_spec, lambda _event: None, contract())
    assert trial.final_state is not None and trial.final_state["stored"] == 42
    assert trial.outcome is Outcome.FAIL
    assert trial.termination is Termination.BUDGET
