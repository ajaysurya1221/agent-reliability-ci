"""Offline demonstration only: retry one empty lookup inside the tool boundary."""

from __future__ import annotations

from typing import Any

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import ToolMessage


class RetryEmptyLookupOnce(AgentMiddleware):
    """Return a single retry's result without asking the model for another step."""

    def wrap_tool_call(self, request: Any, handler: Any) -> Any:
        result = handler(request)
        if (
            request.tool_call["name"] == "lookup_order"
            and isinstance(result, ToolMessage)
            and result.status != "error"
            and str(result.content).strip() == "null"
        ):
            return handler(request)
        return result
