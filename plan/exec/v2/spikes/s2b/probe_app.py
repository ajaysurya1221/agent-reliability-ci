"""Adversarial fixtures kept separate from the user's minimal application."""

from __future__ import annotations

import asyncio
from typing import Any, cast

from arci_langchain import Graph, Middleware, make_adapter
from langchain.agents import create_agent
from langchain.agents.middleware import ToolErrorMiddleware, ToolRetryMiddleware
from langchain_core.tools import BaseTool, StructuredTool
from langgraph.types import Command
from pydantic import JsonValue
from scripted_model import ScriptedModel
from user_app import make_tools as user_make_tools


def make_tools(task: dict[str, JsonValue], seed: int) -> list[BaseTool]:
    tools: list[BaseTool] = user_make_tools(task, seed)
    shape = task.get("shape")
    if shape == "artifact":
        tools[0].response_format = "content_and_artifact"
    elif shape == "return_direct":
        tools[0].return_direct = True
    elif shape in ("command", "message-dict"):
        state: dict[str, JsonValue] = {"body_calls": 0}

        def lookup(key: str) -> Any:
            """Return a literal whose key order is independent of task transport."""
            del key
            state["body_calls"] = int(str(state["body_calls"])) + 1
            if shape == "message-dict":
                return {"z": "café", "a": [1, True]}
            return Command(update={"unexpected": "mutation"})

        tools = [StructuredTool.from_function(lookup, metadata={"task": task, "user_state": state})]
    return tools


class AsyncGraph:
    def __init__(self, graph: Graph) -> None:
        self.graph = graph

    def invoke(self, *args: Any, **kwargs: Any) -> Any:
        return asyncio.run(self.ainvoke(*args, **kwargs))

    async def ainvoke(self, *args: Any, **kwargs: Any) -> Any:
        return await self.graph.ainvoke(*args, **kwargs)


def build_agent(tools: list[BaseTool], middleware: list[Middleware]) -> Graph:
    task = cast(dict[str, Any], (tools[0].metadata or {}).get("task", {}))
    policy = task.get("policy", "none")
    user: list[Middleware] = []
    if policy == "retry":
        user.append(
            ToolRetryMiddleware(max_retries=1, initial_delay=0, jitter=False, on_failure="error")
        )
    elif policy == "error":
        user.append(ToolErrorMiddleware(on_error=lambda _exc, _request: "unavailable"))
    graph = create_agent(
        ScriptedModel(responses=[]),
        tools=tools,
        middleware=[*middleware[:1], *user, *middleware[1:]],
    )
    return AsyncGraph(graph) if task.get("shape") == "async" else graph


toolset, baseline, candidate = make_adapter(make_tools, build_agent, build_agent)
