"""Seed variation changes business data, never the planted offline outcome law."""

from __future__ import annotations

import importlib
import importlib.util
import json
import os
import random
from pathlib import Path
from typing import Any

import pytest

if importlib.util.find_spec("langchain") is None:
    if os.environ.get("ARCI_REQUIRE_ADAPTERS") == "1":
        raise ImportError("ARCI_REQUIRE_ADAPTERS=1 requires LangChain")
    pytest.skip("optional LangChain extra is absent", allow_module_level=True)

from pydantic import JsonValue

from arci.adapters.langchain import make_adapter
from arci.perturb import build
from arci.schema import Bucket, Budgets, FaultSpec
from arci.toolbox import ToolBox
from examples.langchain_quickstart.check import check
from examples.langchain_quickstart.tools import make_tools

EXAMPLE = Path(__file__).resolve().parents[3] / "examples" / "langchain_quickstart"


def test_seeded_business_data_and_independent_check() -> None:
    task: dict[str, JsonValue] = {"order_id": "ORD-101", "action": "refund"}
    first = make_tools(task, 0)
    second = make_tools(task, 1)
    assert first.snapshot is not None and second.snapshot is not None
    assert first.snapshot() != second.snapshot()
    assert not check(task, {"final_output": "Done", "state": first.snapshot()})
    lookup = first.tools[0].invoke({"order_id": "ORD-101"})
    first.tools[2].invoke({"order_id": "ORD-101", "amount_cents": lookup["total_cents"]})
    assert check(task, {"final_output": "Failed", "state": first.snapshot()})
    assert not check(task, {"final_output": "Done", "state": second.snapshot()})


@pytest.mark.parametrize("seed", [0, 7, 2**64 - 1])
def test_all_tasks_have_the_same_fault_law(monkeypatch: pytest.MonkeyPatch, seed: int) -> None:
    monkeypatch.syspath_prepend(str(EXAMPLE))
    monkeypatch.delenv("ARCI_QUICKSTART_BASELINE", raising=False)
    monkeypatch.delenv("ARCI_QUICKSTART_CANDIDATE", raising=False)
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    monkeypatch.setenv("LANGSMITH_TRACING_V2", "false")
    agent = importlib.import_module("agent")
    tasks = [json.loads(line) for line in (EXAMPLE / "tasks.jsonl").read_text().splitlines()]
    assert len({t["id"] for t in tasks}) == 24
    for task in tasks:
        for fault in (None, "tool_timeout", "tool_error_once", "empty_result"):
            for candidate in (False, True):
                adapter = make_adapter(
                    make_tools,
                    agent.baseline_settings,
                    agent.candidate_settings,
                    fault_exceptions={"timeout": TimeoutError, "error": RuntimeError},
                )
                world = adapter.toolset(task, seed)
                box = ToolBox(
                    world.tools,
                    Budgets(max_tool_calls=6, max_model_steps=6),
                    lambda _kind, _payload: None,
                    perturbations=()
                    if fault is None
                    else (
                        build(
                            FaultSpec(
                                name=fault,
                                bucket=Bucket.FALSIFY,
                                tool="lookup_order",
                                at_occurrence=0,
                            )
                        ),
                    ),
                )
                (adapter.candidate if candidate else adapter.baseline)(task, box, random.Random(0))
                assert check(task, world.snapshot()) == (
                    not candidate or fault in (None, "empty_result")
                ), (task["id"], fault, candidate)
                if fault is None:
                    assert 1 <= len(box.recording) <= 4


def test_real_model_settings_match(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.syspath_prepend(str(EXAMPLE))
    agent = importlib.import_module("agent")
    calls: list[tuple[str, dict[str, Any]]] = []

    def model(identifier: str, **kwargs: Any) -> object:
        calls.append((identifier, kwargs))
        return object()

    monkeypatch.setattr(agent, "init_chat_model", model)
    monkeypatch.setenv("ARCI_QUICKSTART_BASELINE", "ollama:baseline")
    monkeypatch.setenv("ARCI_QUICKSTART_CANDIDATE", "ollama:candidate")
    agent.baseline_settings()
    agent.candidate_settings()
    assert calls == [
        ("ollama:baseline", {"temperature": 0, "reasoning": False}),
        ("ollama:candidate", {"temperature": 0, "reasoning": False}),
    ]


def test_offline_environment_disables_inherited_v2_tracing(monkeypatch: pytest.MonkeyPatch) -> None:
    import subprocess
    import sys

    from tests.unit.examples.test_langchain_quickstart import offline_env

    monkeypatch.setenv("LANGSMITH_TRACING_V2", "true")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from langsmith.utils import tracing_is_enabled; print(tracing_is_enabled())",
        ],
        env=offline_env(),
        text=True,
        capture_output=True,
        check=True,
        timeout=10,
    )
    assert result.stdout == "False\n"
