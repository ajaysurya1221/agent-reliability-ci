"""Drive the unmodified run 4 entrypoints in one guarded process. Run from any directory."""

from __future__ import annotations

import gzip
import json
import os
import random
import sys
from importlib import import_module
from pathlib import Path
from typing import TYPE_CHECKING

from realpath_proof import BLOCKED, capture

from arci.descriptor import loads_suite_descriptor
from arci.perturb import build
from arci.suite_schedule import build_suite_round
from arci.toolbox import ToolBox

if TYPE_CHECKING:
    from pydantic import JsonValue

HERE = Path(__file__).resolve().parent
STUDY = HERE.parents[1] / "study/order-desk-control-message"
CAPTURE = HERE / "http.jsonl.gz"
ROUNDS = 10


def discard_event(_kind: str, _payload: dict[str, JsonValue]) -> None:
    pass


def main() -> None:
    registration = STUDY / "arci.yaml"
    suite = loads_suite_descriptor(registration.read_text(), str(registration))
    settings = suite.tasks[0].task["quickstart_settings"]
    assert isinstance(settings, dict)
    os.environ.update(
        ARCI_QUICKSTART_BASELINE=str(settings["baseline"]),
        ARCI_QUICKSTART_CANDIDATE=str(settings["candidate"]),
        ARCI_QUICKSTART_TEMPERATURE=str(settings["temperature"]),
        OLLAMA_HOST="http://127.0.0.1:9",
        LANGSMITH_TRACING="false",
        LANGCHAIN_TRACING_V2="false",
    )
    os.environ.pop("ORDER_DESK_EMPTY_TEXT_AUDIT", None)
    sys.path.insert(0, str(STUDY))
    agent = import_module("agent")
    oracle = import_module("check").check
    assert Path(str(agent.__file__)).resolve() == STUDY / "agent.py"
    trials = 0
    with gzip.open(CAPTURE, "wt", encoding="utf-8") as stream:
        for number in range(1, ROUNDS + 1):
            for spec in build_suite_round(suite, number):
                world = agent.toolset(spec.task, spec.seed)
                boundary = ToolBox(
                    world.tools,
                    spec.budgets,
                    discard_event,
                    seed=spec.seed,
                    perturbations=[build(f) for f in spec.condition.faults],
                )
                with capture(
                    stream, number, spec.task_id, spec.arm, spec.seed, str(spec.task["order_id"])
                ):
                    getattr(agent, spec.arm)(spec.task, boundary, random.Random(spec.seed))
                calls = boundary.recording
                assert [c.tool for c in calls] == [
                    "lookup_order",
                    "lookup_order",
                    "check_stock",
                    "add_note",
                ]
                assert calls[0].occurrence == 0 and calls[0].result.injected_by == "empty_result"
                assert calls[0].result.ok and calls[0].result.value is None
                assert all(c.result.ok and c.result.injected_by is None for c in calls[1:])
                assert oracle(spec.task, world.snapshot())
                trials += 1
        assert trials == 160
        assert not (BLOCKED.keys() - {"socket.__new__"}), BLOCKED
        stream.write(
            json.dumps(
                {
                    "verified_trials": trials,
                    "blocked_network_events": dict(BLOCKED),
                    "explicit": agent.EXPLICIT_TEXT,
                    "neutral": agent.NEUTRAL_TEXT,
                }
            )
            + "\n"
        )
    print(f"{trials} trials completed and graded; blocked socket events: {dict(BLOCKED)}")


if __name__ == "__main__":
    main()
