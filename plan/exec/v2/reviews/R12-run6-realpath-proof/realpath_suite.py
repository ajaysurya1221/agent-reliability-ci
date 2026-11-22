"""Drive the unmodified run 6 entrypoints in one guarded process. Run from any directory."""

from __future__ import annotations

import gzip
import json
import os
import random
import sys
from importlib import import_module
from io import TextIOWrapper
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING

from realpath_proof import BLOCKED, capture

from arci.descriptor import loads_suite_descriptor
from arci.perturb import build
from arci.suite_schedule import build_suite_round
from arci.toolbox import ToolBox

if TYPE_CHECKING:
    from pydantic import JsonValue

HERE = Path(__file__).resolve().parent
STUDY = HERE.parents[1] / "study/order-desk-compound"
CAPTURE = HERE / "http.jsonl.gz"
ROUNDS = 10


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
    with (
        TemporaryDirectory() as scratch,
        gzip.GzipFile(CAPTURE, "wb", mtime=0) as archive,
        TextIOWrapper(archive, encoding="utf-8") as stream,
    ):
        receipts = Path(scratch) / "first-exchanges.jsonl"
        os.environ["ORDER_DESK_FIRST_EXCHANGE_AUDIT"] = str(receipts)
        assignments: list[dict[str, str | int]] = []
        for number in range(1, ROUNDS + 1):
            for spec in build_suite_round(suite, number):
                world = agent.toolset(spec.task, spec.seed)
                events: list[tuple[str, dict[str, JsonValue]]] = []
                boundary = ToolBox(
                    world.tools,
                    spec.budgets,
                    lambda kind, payload: events.append((kind, payload)),  # noqa: B023
                    seed=spec.seed,
                    perturbations=[build(f) for f in spec.condition.faults],
                )
                with capture(
                    stream, number, spec.task_id, spec.arm, spec.seed, str(spec.task["order_id"])
                ):
                    getattr(agent, spec.arm)(spec.task, boundary, random.Random(spec.seed))
                calls = boundary.recording
                order_id = spec.task["order_id"]
                assert [kind for kind, _ in events[:5]] == [
                    "tool_start",
                    "tool_finish",
                    "tool_start",
                    "tool_finish",
                    "model_step",
                ]
                assert events[0][1]["arguments"] == {"sku": order_id}
                assert events[2][1]["arguments"] == {"order_id": order_id}
                assert [c.tool for c in calls] == [
                    "check_stock",
                    "lookup_order",
                    "lookup_order",
                    "check_stock",
                    "add_note",
                ]
                assert calls[0].occurrence == 0 and calls[0].result.error_kind == "error"
                assert not calls[0].result.ok and calls[0].result.injected_by is None
                assert calls[0].result.error_detail == "ValueError: unknown SKU"
                assert calls[1].occurrence == 0 and calls[1].result.injected_by == "empty_result"
                assert calls[1].result.ok and calls[1].result.value is None
                assert all(c.result.ok and c.result.injected_by is None for c in calls[2:])
                assert oracle(spec.task, world.snapshot())
                assignments.append({"arm": spec.arm, "task_id": spec.task_id, "seed": spec.seed})
                trials += 1
        assert trials == 160
        expected = Path(scratch) / "assignments.jsonl"
        expected.write_text("".join(json.dumps(row) + "\n" for row in assignments))
        print(import_module("exposure").verify(expected, receipts))
        assert not (BLOCKED.keys() - {"socket.__new__"}), BLOCKED
        stream.write(
            json.dumps(
                {
                    "verified_trials": trials,
                    "blocked_network_events": dict(BLOCKED),
                    "requests_leaving_process": 0,
                    "generic": agent.GENERIC_TEXT,
                }
            )
            + "\n"
        )
    print(f"{trials} trials completed and graded; blocked socket events: {dict(BLOCKED)}")


if __name__ == "__main__":
    main()
