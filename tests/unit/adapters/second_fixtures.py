"""Offline process fixtures for P3a3 graph-entry attribution."""

from __future__ import annotations

import importlib.util
import os
from typing import Any

import pytest

if importlib.util.find_spec("langchain") is None:
    if os.environ.get("ARCI_REQUIRE_ADAPTERS") == "1":
        raise ImportError("ARCI_REQUIRE_ADAPTERS=1 requires LangChain")
    pytest.skip("optional LangChain extra is absent", allow_module_level=True)

from langchain.agents.middleware import AgentMiddleware, ModelResponse, PIIMiddleware
from langchain_core.messages import AIMessage
from langchain_core.tools import StructuredTool
from pydantic import JsonValue

from arci.adapters.langchain import make_adapter
from tests.unit.adapters.fixtures import call_message, model

_task: dict[str, JsonValue] = {}


def tools(task: dict[str, JsonValue], seed: int) -> list[StructuredTool]:
    global _task
    _task = task

    def lookup(key: str) -> str:
        return key

    return [StructuredTool.from_function(lookup, description="Lookup.")]


class Cached(AgentMiddleware[Any, Any, Any]):
    def __init__(self) -> None:
        self.calls = 0

    def wrap_model_call(self, request: Any, handler: Any) -> Any:
        self.calls += 1
        return ModelResponse(
            result=[call_message({"key": "x"}) if self.calls == 1 else AIMessage(content="done")]
        )

    def after_agent(self, state: Any, runtime: Any) -> None:
        raise RuntimeError("cached policy failed")


def settings() -> dict[str, Any]:
    kind = _task["case"]
    scripted = model(call_message({"key": "x"}), AIMessage(content="done"))
    if kind == "bound":
        return {"model": scripted.with_config(tags=["bound"])}
    if kind == "pii":
        middleware = PIIMiddleware("email", strategy="block")
    elif kind == "cached":
        middleware = Cached()
    else:

        def refuse(self: Any, *args: Any, **kwargs: Any) -> None:
            raise PermissionError("policy refused input")

        middleware = type("Guard", (AgentMiddleware,), {str(kind): refuse})()
    return {"model": scripted, "middleware": [middleware]}


toolset, baseline, candidate = make_adapter(tools, settings, settings)
