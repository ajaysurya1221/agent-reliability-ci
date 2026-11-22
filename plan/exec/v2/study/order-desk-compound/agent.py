"""Compare generic guidance with raw null after a shared two-call opening."""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from typing import Any, Literal, cast
from uuid import uuid4

from configuration import resolve_settings, validate_registration
from exposure import FirstExchange
from langchain.agents.middleware import (
    AgentMiddleware,
    AgentState,
    ModelRequest,
    ModelResponse,
    ToolRetryMiddleware,
)
from langchain.chat_models import init_chat_model
from langchain_core.messages import AIMessage, ToolMessage
from offline_model import OfflineModel
from pydantic import JsonValue
from tools import make_tools

from arci.adapters.langchain import ToolEnv, make_adapter


class OpeningState(AgentState[Any]):
    order_id: str


def task_input(task: dict[str, JsonValue]) -> dict[str, Any]:
    """Carry the registered id in graph state without adding a word to the prompt."""
    return {"order_id": task["order_id"], "messages": [{"role": "user", "content": task["input"]}]}


class ScriptedOpening(AgentMiddleware[OpeningState]):
    """Emit one call per graph turn. Only the real tool node supplies its reply."""

    state_schema = OpeningState

    def __init__(self, exchange: FirstExchange | None = None) -> None:
        self.exchange = exchange

    def wrap_model_call(
        self,
        request: ModelRequest[None],
        handler: Callable[[ModelRequest[None]], ModelResponse[Any]],
    ) -> AIMessage | ModelResponse[Any]:
        # Initially only the user is present. Each single call adds one AI/tool pair.
        length = len(request.messages)
        if length not in (1, 3):
            exchange, self.exchange = self.exchange, None
            try:
                return handler(request)
            finally:
                if exchange is not None:
                    exchange.record()
        order_id = cast(OpeningState, request.state)["order_id"]
        tool, argument = ("check_stock", "sku") if length == 1 else ("lookup_order", "order_id")
        return AIMessage(
            content="",
            tool_calls=[{"name": tool, "args": {argument: order_id}, "id": str(uuid4())}],
        )


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


GENERIC_TEXT: str = (
    "The previous tool call returned an empty result. Repeat that call with the same input."
)
SYSTEM_PROMPT = (
    "Use the order desk tools. Read the order first. Refund exactly its total_cents. "
    "For stock notes, read its SKU stock and write exactly 'stock: N'. "
    "Only add a note when the task asks for one. For refund notes write exactly "
    "'refunded'. A plain refund needs no note. Retry an empty lookup once."
)
# Each ARCI worker creates one registered toolset before it builds its arm's model.
_worker_trial: tuple[dict[str, JsonValue], int] | None = None


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
    exchange = None
    receipt_path = os.environ.get("ORDER_DESK_FIRST_EXCHANGE_AUDIT")
    if receipt_path and _worker_trial is not None and model_id.startswith("ollama:"):
        task, seed = _worker_trial
        exchange = FirstExchange(
            receipt_path, arm, task, seed, SYSTEM_PROMPT, "null" if candidate else GENERIC_TEXT
        )
        inference["sync_client_kwargs"] = {
            "event_hooks": {"request": [exchange.on_request], "response": [exchange.on_response]}
        }
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
            ScriptedOpening(exchange),
            retry,
            ReturnToolErrors(),
            *([] if candidate else [ReplaceEmptyLookup(GENERIC_TEXT, "baseline")]),
        ],
        "system_prompt": SYSTEM_PROMPT,
    }


def baseline_settings() -> dict[str, Any]:
    return settings(False)


def candidate_settings() -> dict[str, Any]:
    return settings(True)


def registered_tools(task: dict[str, JsonValue], seed: int) -> ToolEnv:
    global _worker_trial
    registered = validate_registration(task)
    _worker_trial = (task, seed)
    if registered["baseline"] == "offline:scripted":
        OfflineModel.validate_prompt(task.get("input"))
    return make_tools(task, seed)


toolset, baseline, candidate = make_adapter(
    registered_tools,
    baseline_settings,
    candidate_settings,
    task_to_input=task_input,
    # Keys are fault kinds, not perturbation names such as 'tool_timeout'.
    fault_exceptions={"timeout": TimeoutError, "error": RuntimeError},
)
