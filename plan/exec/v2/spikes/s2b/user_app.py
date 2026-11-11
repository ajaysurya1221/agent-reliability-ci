"""Example user's real tools and two agent builders; model is an offline fixture."""

from arci_langchain import Graph, Middleware, make_adapter
from langchain.agents import create_agent
from langchain.agents.middleware import ToolRetryMiddleware
from langchain_core.tools import BaseTool, StructuredTool
from pydantic import JsonValue
from scripted_model import ScriptedModel


def make_tools(task: dict[str, JsonValue], seed: int) -> list[BaseTool]:
    del seed
    state: dict[str, JsonValue] = {"body_calls": 0, "order": []}

    def lookup(key: str) -> JsonValue:
        """Look up the task's answer."""
        state["body_calls"] = int(str(state["body_calls"])) + 1
        order = state["order"]
        assert isinstance(order, list)
        order.append(key)
        if task.get("real_error") and state["body_calls"] == 1:
            raise ValueError("service unavailable")
        return task.get("value", "forty-two")

    return [StructuredTool.from_function(lookup, metadata={"user_state": state, "task": task})]


def build_baseline(tools: list[BaseTool], middleware: list[Middleware]) -> Graph:
    return create_agent(
        ScriptedModel(responses=[]),
        tools=tools,
        middleware=[
            *middleware[:1],
            ToolRetryMiddleware(max_retries=1, initial_delay=0, jitter=False, on_failure="error"),
            *middleware[1:],
        ],
    )


def build_candidate(tools: list[BaseTool], middleware: list[Middleware]) -> Graph:
    return create_agent(ScriptedModel(responses=[]), tools=tools, middleware=middleware)


toolset, baseline, candidate = make_adapter(make_tools, build_baseline, build_candidate)
