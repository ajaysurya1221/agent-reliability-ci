"""P3a2 public tool-shape and provider-definition parity."""

from __future__ import annotations

import importlib.util
import os
import random
from functools import partial
from typing import Annotated, Any

import pytest

if importlib.util.find_spec("langchain") is None:
    if os.environ.get("ARCI_REQUIRE_ADAPTERS") == "1":
        raise ImportError("ARCI_REQUIRE_ADAPTERS=1 requires LangChain")
    pytest.skip("optional LangChain extra is absent", allow_module_level=True)
from langchain.agents import create_agent
from langchain.agents.middleware import AgentMiddleware
from langchain_core.callbacks import CallbackManagerForRetrieverRun, CallbackManagerForToolRun
from langchain_core.documents import Document
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.retrievers import BaseRetriever
from langchain_core.runnables import RunnableConfig, RunnableLambda
from langchain_core.tools import (
    BaseTool,
    InjectedToolArg,
    StructuredTool,
    Tool,
    create_retriever_tool,
)
from langchain_core.utils.function_calling import convert_to_openai_tool
from pydantic import BaseModel, Field

from arci.adapters.langchain import make_adapter
from arci.schema import Budgets, ToolMode
from arci.toolbox import HarnessError, ToolBox
from tests.unit.adapters.fixtures import Input, ScriptedModel, call_message, model
from tests.unit.adapters.test_core import boundary, observations


class Retriever(BaseRetriever):
    def _get_relevant_documents(
        self, query: str, *, run_manager: CallbackManagerForRetrieverRun
    ) -> list[Document]:
        return [Document(page_content="found:" + query)]


def prefixed(key: str, prefix: str) -> str:
    return prefix + key


def plain(key: str) -> str:
    return key


def extract_key(value: dict[str, Any]) -> str:
    return str(value["key"])


@pytest.mark.parametrize("kind", ["Tool", "retriever", "runnable", "partial"])
def test_stock_sync_tools_have_native_observations(kind: str) -> None:
    """Findings 13, 34: stock sync wrappers and partials are valid without user injection."""
    if kind == "Tool":
        target: BaseTool = Tool(name="lookup", description="Lookup.", func=plain)
        args = {"tool_input": "x"}
    elif kind == "retriever":
        target = create_retriever_tool(Retriever(), "lookup", "Lookup.")
        args = {"query": "x"}
    elif kind == "runnable":
        target = RunnableLambda(extract_key).as_tool(name="lookup", arg_types={"key": str})
        args = {"key": "x"}
    else:
        target = StructuredTool(
            name="lookup",
            description="Lookup.",
            args_schema=Input,
            func=partial(prefixed, prefix="found:"),
        )
        args = {"key": "x"}
    native = model(call_message(args), AIMessage(content="done"))
    expected_partial: Any = None
    if kind == "partial":
        # Installed ToolNode cannot inspect a bare partial; the public body path can.
        expected_partial = target.run(args)
    else:
        create_agent(native, tools=[target]).invoke({"messages": [HumanMessage(content="x")]})
    wrapped = model(call_message(args), AIMessage(content="done"))

    def spec() -> dict[str, Any]:
        return {"model": wrapped}

    adapter = make_adapter(lambda _t, _s: [target], spec, spec)
    _, box, _ = boundary(adapter)
    adapter.baseline({"input": "x"}, box, random.Random())
    if kind == "partial":
        assert wrapped.seen[-1][-1].content == expected_partial == "found:x"
    else:
        assert observations(wrapped) == observations(native)
    assert box.tool_calls == 1


class ConfigTool(BaseTool):
    name: str = "lookup"
    description: str = "Lookup."
    args_schema: Any = Input

    def _run(self, key: str, config: RunnableConfig) -> str:
        return str(config) + key


class ManagerTool(BaseTool):
    name: str = "lookup"
    description: str = "Lookup."
    args_schema: Any = Input

    def _run(self, key: str, run_manager: CallbackManagerForToolRun | None = None) -> str:
        return str(run_manager) + key


@pytest.mark.parametrize("target", [ConfigTool(), ManagerTool()])
@pytest.mark.parametrize("replaying", [False, True])
def test_subclass_injection_rejected(target: BaseTool, replaying: bool) -> None:
    """Findings 13, 34: a user implementation's hidden config/run-manager injection rejects."""
    adapter = make_adapter(lambda _t, _s: [target], lambda: {}, lambda: {})
    with pytest.raises(HarnessError, match="injected tool arguments"):
        if replaying:
            adapter.baseline(
                {},
                ToolBox({}, Budgets(), lambda _kind, _payload: None, mode=ToolMode.REPLAY),
                random.Random(),
            )
        else:
            adapter.toolset({}, 7)


@pytest.mark.parametrize("name", ["tool", "self"])
@pytest.mark.parametrize("schema_kind", ["dict", "inferred"])
def test_reserved_names_rejected_at_registration(name: str, schema_kind: str) -> None:
    """Finding 5: reserved boundary fields must reject before model invocation."""

    def tool_arg(tool: str) -> str:
        return tool

    def self_arg(self: str) -> str:
        return self

    body = tool_arg if name == "tool" else self_arg
    target = (
        StructuredTool.from_function(body, name="lookup", description="Lookup.")
        if schema_kind == "inferred"
        else StructuredTool(
            name="lookup",
            description="Lookup.",
            args_schema={"type": "object", "properties": {name: {"type": "string"}}},
            func=body,
        )
    )
    adapter = make_adapter(lambda _t, _s: [target], lambda: {}, lambda: {})
    with pytest.raises(HarnessError, match="reserved boundary argument name"):
        adapter.toolset({}, 7)


class HiddenSchema(BaseModel):
    key: Annotated[str, InjectedToolArg()]


def test_schema_only_injection_is_rejected() -> None:
    """Finding 31a: dropping the schema source must expose this injected argument."""
    target = StructuredTool(
        name="lookup", description="Lookup.", args_schema=HiddenSchema, func=plain
    )
    adapter = make_adapter(lambda _t, _s: [target], lambda: {}, lambda: {})
    with pytest.raises(HarnessError, match="injected tool arguments"):
        adapter.toolset({}, 7)


class BoundModel(ScriptedModel):
    definitions: list[Any] = Field(default_factory=list)

    def bind_tools(self, tools: Any, **kwargs: Any) -> Any:
        self.definitions.append(
            [
                {
                    "definition": convert_to_openai_tool(t),
                    "extras": t.extras,
                    "metadata": t.metadata,
                    "tags": t.tags,
                }
                for t in tools
            ]
        )
        return self


@pytest.mark.parametrize("simple", [False, True])
def test_proxy_definitions_and_tool_policy_metadata_match_native(simple: bool) -> None:
    """Findings 10, 34: both proxy layers retain provider extras and policy metadata."""
    target: BaseTool = StructuredTool.from_function(
        plain,
        name="lookup",
        description="Lookup.",
        extras={"cache_control": {"type": "ephemeral"}},
        metadata={"team": "a"},
        tags=["tag"],
    )
    if simple:
        target = Tool(
            name="lookup",
            description="Lookup.",
            func=plain,
            extras=target.extras,
            metadata=target.metadata,
            tags=target.tags,
        )
    seen: list[Any] = []

    class Observe(AgentMiddleware[Any, Any, Any]):
        def wrap_tool_call(self, request: Any, handler: Any) -> Any:
            seen.append((request.tool.extras, request.tool.metadata, request.tool.tags))
            return handler(request)

    native = BoundModel(
        responses=[], script=[call_message({"key": "x"}), AIMessage(content="done")]
    )
    create_agent(native, tools=[target], middleware=[Observe()]).invoke(
        {"messages": [HumanMessage(content="x")]}
    )
    wrapped = BoundModel(
        responses=[], script=[call_message({"key": "x"}), AIMessage(content="done")]
    )

    def spec() -> dict[str, Any]:
        return {"model": wrapped, "middleware": [Observe()]}

    adapter = make_adapter(lambda _t, _s: [target], spec, spec)
    _, box, _ = boundary(adapter)
    adapter.baseline({"input": "x"}, box, random.Random())
    assert wrapped.definitions == native.definitions
    assert seen == [(target.extras, target.metadata, target.tags)] * 2
