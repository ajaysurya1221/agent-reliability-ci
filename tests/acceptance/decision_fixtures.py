"""Builders and trusted fixtures for the decision-boundary acceptance tests. FROZEN.

The scenario: a support agent asks a System One endpoint four questions about one ticket, then acts
through the MCP environment by storing the action it took (`store`), exactly like the v0.2 fixtures.
The oracle accepts the ground-truth action, or an escalation: escalating is always allowed.
"""

from __future__ import annotations

import math
import os
import random
import sys
import time
from pathlib import Path
from typing import Literal, cast

from pydantic import JsonValue

from arci.schema import (
    DECISION_TOOL,
    ArmSpec,
    Bucket,
    Budgets,
    CommandSpec,
    Condition,
    ContractSpec,
    DecisionSpec,
    FaultSpec,
    Manifest,
    TrialSpec,
)
from tests.acceptance.helpers import COND_CLEAN, EMPTY_LOG
from tests.acceptance.mcp_fixtures import server

HERE = Path(__file__).resolve().parent
CLIENT = str(HERE / "decision_fixture_client.py")
ME = "tests.acceptance.decision_fixtures"
PINNED_MODEL = "jev-1.13.0"
# Appears only inside the request state. Diff signatures must never print it.
STATE_MARKER = "STATE-MARKER-7f3a"

# Hidden ground truth, keyed by ticket id. Never inside the task the agent sees.
TICKETS: dict[str, dict[str, JsonValue]] = {
    "t-refund": {
        "department": "billing",
        "refund_requested": True,
        "policy_supports": True,
        "frustration": 1,
        "action": "refund",
    },
    "t-bug": {
        "department": "technical",
        "refund_requested": False,
        "policy_supports": False,
        "frustration": 2,
        "action": "technical",
    },
}
TASK: dict[str, JsonValue] = {
    "ticket_id": "t-refund",
    "text": f"I was charged twice for order A-104. Please refund the duplicate. {STATE_MARKER}",
}

LOW_CONFIDENCE = FaultSpec(
    name="decision_low_confidence",
    bucket=Bucket.FALSIFY,
    tool=DECISION_TOOL,
    at_occurrence=0,
    params={"confidence_max": 0.4},
)
UNAVAILABLE = FaultSpec(name="decision_unavailable", bucket=Bucket.FALSIFY, tool=DECISION_TOOL)
COND_LOW_CONFIDENCE = Condition(condition_id="low_confidence", faults=(LOW_CONFIDENCE,))
COND_UNAVAILABLE = Condition(condition_id="provider_down", faults=(UNAVAILABLE,))
COND_NOISY_DECISIONS = Condition(condition_id="noisy", faults=(EMPTY_LOG, LOW_CONFIDENCE))


def _question(request: dict[str, JsonValue], name: str) -> dict[str, JsonValue]:
    questions = cast(dict[str, JsonValue], request["questions"])
    return cast(dict[str, JsonValue], questions[name])


def _truth(request: dict[str, JsonValue]) -> dict[str, JsonValue]:
    state = cast(dict[str, JsonValue], request["state"])
    ticket = cast(dict[str, JsonValue], state["ticket"])
    return TICKETS[cast(str, ticket["ticket_id"])]


def fixture(request: dict[str, JsonValue], seed: int, occurrence: int) -> dict[str, JsonValue]:
    """Confident, correct, seeded answers in the exact wire shape of `POST /v1/systemone`."""
    rng = random.Random(f"{seed}:decision:{occurrence}")
    truth = _truth(request)
    answers: dict[str, JsonValue] = {}
    for name in cast(dict[str, JsonValue], request["questions"]):
        question = _question(request, name)
        kind = question["type"]
        noise = round(rng.uniform(-0.02, 0.02), 4)
        if kind == "choice":
            options = sorted(cast(dict[str, JsonValue], question["criteria"]))
            correct = cast(str, truth[name])
            top = round(0.95 + noise, 4)
            rest = round((1.0 - top) / (len(options) - 1), 6)
            probabilities = {o: (top if o == correct else rest) for o in options}
            total = sum(probabilities.values())
            probabilities = {o: round(p / total, 6) for o, p in probabilities.items()}
            n = len(options)
            answers[name] = cast(
                JsonValue,
                {
                    "type": "choice",
                    "choice": correct,
                    "probabilities": probabilities,
                    "confidence": round((n * max(probabilities.values()) - 1) / (n - 1), 6),
                },
            )
        elif kind == "noul":
            answers[name] = {
                "type": "noul",
                "noul": round((0.95 if truth[name] else 0.05) + noise, 4),
            }
        elif kind == "score":
            levels = cast(list[JsonValue], question["criteria"])
            level = cast(int, truth[name])
            probabilities = {
                str(i): (0.9 if i == level else 0.1 / (len(levels) - 1)) for i in range(len(levels))
            }
            answers[name] = cast(
                JsonValue,
                {
                    "type": "score",
                    "score": round(sum(int(i) * p for i, p in probabilities.items()), 6),
                    "legend": {str(i): levels[i] for i in range(len(levels))},
                    "probabilities": {i: round(p, 6) for i, p in probabilities.items()},
                    "confidence": round((len(levels) * 0.9 - 1) / (len(levels) - 1), 6),
                },
            )
        else:
            raise ValueError(f"unsupported question type {kind!r}")
    return {
        "model": cast(str, request["model"]),
        "answers": answers,
        "usage": {"input_tokens": 120, "output_tokens": 0},
    }


def broken_fixture(
    request: dict[str, JsonValue], seed: int, occurrence: int
) -> dict[str, JsonValue]:
    del request, seed, occurrence
    raise RuntimeError("the decision fixture is broken")


def malformed_fixture(
    request: dict[str, JsonValue], seed: int, occurrence: int
) -> dict[str, JsonValue]:
    body = fixture(request, seed, occurrence)
    answers = dict(cast(dict[str, JsonValue], body["answers"]))
    answers.pop("department")  # one requested answer is missing
    return {**body, "answers": answers}


def wrong_model_fixture(
    request: dict[str, JsonValue], seed: int, occurrence: int
) -> dict[str, JsonValue]:
    return {**fixture(request, seed, occurrence), "model": "jev-9.0.0"}


def unnormalised_fixture(
    request: dict[str, JsonValue], seed: int, occurrence: int
) -> dict[str, JsonValue]:
    body = fixture(request, seed, occurrence)
    answers = dict(cast(dict[str, JsonValue], body["answers"]))
    department = dict(cast(dict[str, JsonValue], answers["department"]))
    department["probabilities"] = {"billing": 0.9, "sales": 0.3, "technical": 0.3}
    answers["department"] = department
    return {**body, "answers": answers}


def infinite_fixture(
    request: dict[str, JsonValue], seed: int, occurrence: int
) -> dict[str, JsonValue]:
    body = fixture(request, seed, occurrence)
    answers = dict(cast(dict[str, JsonValue], body["answers"]))
    answers["refund_requested"] = {"type": "noul", "noul": math.inf}
    return {**body, "answers": answers}


def slow_fixture(request: dict[str, JsonValue], seed: int, occurrence: int) -> dict[str, JsonValue]:
    time.sleep(0.5)
    return fixture(request, seed, occurrence)


def leaky_fixture(
    request: dict[str, JsonValue], seed: int, occurrence: int
) -> dict[str, JsonValue]:
    """A careless fixture whose error message carries whatever key the boundary holds."""
    del request, seed, occurrence
    raise RuntimeError(f"upstream refused key {os.environ.get('TYPESAFE_API_KEY', '')}")


def oracle(task: dict[str, JsonValue], final_state: dict[str, JsonValue]) -> bool:
    """Independent: the stored action must be the ground truth, or an escalation."""
    expected = TICKETS[cast(str, task["ticket_id"])]["action"]
    stored = final_state.get("stored")
    return stored == expected or stored == "escalate"


def decision_client(variant: str, *extra: str) -> CommandSpec:
    return CommandSpec(
        argv=(
            sys.executable,
            CLIENT,
            "--mcp-config",
            "{mcp_config}",
            "--task-file",
            "{task_file}",
            "--variant",
            variant,
            *extra,
        ),
        infra_exit_codes=(),
    )


def decisions(
    upstream: Literal["fixture", "http"] = "fixture",
    fixture_name: str | None = "fixture",
    **kw: object,
) -> DecisionSpec:
    fixture_ref = None if fixture_name is None else f"{ME}:{fixture_name}"
    return DecisionSpec(upstream=upstream, fixture=fixture_ref, model=PINNED_MODEL, **kw)  # pyright: ignore[reportArgumentType]


GATEWAY_MODEL = "typesafe-ai/jev"


def gateway_decisions(port: int, **kw: object) -> DecisionSpec:
    """An `http` upstream shaped like Vercel AI Gateway: path prefix and its own model id."""
    return DecisionSpec(
        upstream="http",
        base_url=f"http://127.0.0.1:{port}/typesafe",
        model=GATEWAY_MODEL,
        **kw,  # pyright: ignore[reportArgumentType]
    )


def decision_contract() -> ContractSpec:
    return ContractSpec(oracle=f"{ME}:oracle")


def decision_spec(
    variant: str,
    *,
    condition: Condition = COND_CLEAN,
    arm: Literal["baseline", "candidate"] = "candidate",
    spec: DecisionSpec | None = None,
    max_seconds: float = 20.0,
    max_tool_calls: int = 20,
    seed: int = 11,
    server_args: tuple[str, ...] = (),
    client_args: tuple[str, ...] = (),
) -> TrialSpec:
    return TrialSpec(
        experiment_id="exp-decisions",
        trial_id=f"{condition.condition_id}:00000:{arm}",
        pair_id=f"{condition.condition_id}:00000",
        arm=arm,
        variant=variant,
        command=decision_client(variant, *client_args),
        mcp_server=server(*server_args),
        decisions=decisions() if spec is None else spec,
        task_id="triage-the-ticket",
        task=TASK,
        condition=condition,
        seed=seed,
        budgets=Budgets(max_tool_calls=max_tool_calls, max_seconds=max_seconds),
    )


def decision_manifest(
    *,
    baseline: str = "gated",
    candidate: str = "abandon",
    conditions: tuple[Condition, ...] = (COND_LOW_CONFIDENCE,),
    n_per_arm: int = 20,
    spec: DecisionSpec | None = None,
) -> Manifest:
    return Manifest.create(
        experiment_id="exp-decisions",
        task_id="triage-the-ticket",
        task=TASK,
        mcp_server=server(),
        decisions=decisions() if spec is None else spec,
        contract=decision_contract(),
        baseline=ArmSpec(label="A", command=decision_client(baseline), candidate_id="a"),
        candidate=ArmSpec(label="B", command=decision_client(candidate), candidate_id="b"),
        conditions=conditions,
        n_per_arm=n_per_arm,
        base_seed=7,
        budgets=Budgets(max_tool_calls=20, max_seconds=20.0),
    )
