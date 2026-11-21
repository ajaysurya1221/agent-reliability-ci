"""Compare explicit and neutral text after a successful empty lookup."""

from __future__ import annotations

import json
import os
from typing import Any, Literal

from configuration import resolve_settings, validate_registration
from langchain.agents.middleware import AgentMiddleware, ToolRetryMiddleware
from langchain.chat_models import init_chat_model
from langchain_core.messages import ToolMessage
from offline_model import OfflineModel
from pydantic import JsonValue
from tools import make_tools

from arci.adapters.langchain import ToolEnv, make_adapter


class ReturnToolErrors(AgentMiddleware):
    """Run 2's one change: show a tool's ValueError to the model instead of crashing.

    No retry. The same instance behaviour in both arms. Timeouts and runtime errors are
    still handled by the retry middleware, as in run 1.
    """

    def wrap_tool_call(self, request: Any, handler: Any) -> Any:
        try:
            return handler(request)
        except ValueError as exc:
            call = request.tool_call
            return ToolMessage(
                content=f"Error: {exc}",
                tool_call_id=call["id"],
                name=call["name"],
                status="error",
            )


EXPLICIT_TEXT: str = (
    "lookup_order returned an empty result. Call lookup_order again with the same order_id."
)
NEUTRAL_TEXT: str = (
    "lookup_order returned an empty result. This lookup_order result is for the supplied order_id."
)


class ReplaceEmptyLookup(AgentMiddleware):
    """Replace only a successful null lookup; leave the recorded tool call intact."""

    def __init__(self, text: str, arm: Literal["baseline", "candidate"]) -> None:
        self.text = text
        self.arm = arm

    def wrap_tool_call(self, request: Any, handler: Any) -> Any:
        result = handler(request)
        if (
            request.tool_call["name"] != "lookup_order"
            or not isinstance(result, ToolMessage)
            or result.status == "error"
            or str(result.content).strip() != "null"
        ):
            return result
        replacement = ToolMessage(
            content=self.text,
            tool_call_id=result.tool_call_id,
            name=result.name,
            status=result.status,
        )
        audit = os.environ.get("ORDER_DESK_EMPTY_TEXT_AUDIT")
        if audit:
            try:
                with open(audit, "a", encoding="utf-8") as stream:
                    record = {
                        "tool": "lookup_order",
                        "tool_call_id": result.tool_call_id,
                        "arm": self.arm,
                    }
                    stream.write(json.dumps(record) + "\n")
            except Exception:
                pass  # Supporting evidence must never change the model's input.
        return replacement


def settings(candidate: bool) -> dict[str, Any]:
    registered = resolve_settings()
    arm = "candidate" if candidate else "baseline"
    model_id = str(registered[arm])
    # Keep inference settings identical. Ollama's optional reasoning mode is disabled
    # for both arms; other providers keep their default reasoning mode in both arms.
    inference: dict[str, Any] = {"temperature": registered["temperature"]}
    if registered[f"{arm}_reasoning"] is False:
        inference["reasoning"] = False
    model = (
        init_chat_model(model_id, **inference)
        if model_id != "offline:scripted"
        else OfflineModel(responses=[])
    )
    # The same retry in both arms, as in run 2: one retry of a timeout or a runtime error.
    retry = ToolRetryMiddleware(
        max_retries=1,
        initial_delay=0,
        jitter=False,
        retry_on=(TimeoutError, RuntimeError),
        on_failure="continue",
    )
    return {
        "model": model,
        "middleware": [
            retry,
            ReturnToolErrors(),
            ReplaceEmptyLookup(NEUTRAL_TEXT if candidate else EXPLICIT_TEXT, arm),
        ],
        "system_prompt": (
            "Use the order desk tools. Read the order first. Refund exactly its total_cents. "
            "For stock notes, read its SKU stock and write exactly 'stock: N'. "
            "Only add a note when the task asks for one. For refund notes write exactly "
            "'refunded'. A plain refund needs no note. Retry an empty lookup once."
        ),
    }


def baseline_settings() -> dict[str, Any]:
    return settings(False)


def candidate_settings() -> dict[str, Any]:
    return settings(True)


def registered_tools(task: dict[str, JsonValue], seed: int) -> ToolEnv:
    registered = validate_registration(task)
    if registered["baseline"] == "offline:scripted":
        OfflineModel.validate_prompt(task.get("input"))
    return make_tools(task, seed)


toolset, baseline, candidate = make_adapter(
    registered_tools,
    baseline_settings,
    candidate_settings,
    # Keys are fault kinds, not perturbation names such as 'tool_timeout'.
    fault_exceptions={"timeout": TimeoutError, "error": RuntimeError},
)
