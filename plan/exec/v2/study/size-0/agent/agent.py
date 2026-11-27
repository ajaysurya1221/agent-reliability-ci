"""Run the raw-null candidate in both ARCI arms."""

from __future__ import annotations

import os
import random
from collections.abc import Callable
from typing import Any, cast
from uuid import uuid4

from exposure import FirstExchange, ReceiptLost
from langchain.agents.middleware import (
    AgentMiddleware,
    AgentState,
    ModelRequest,
    ModelResponse,
    ToolRetryMiddleware,
)
from langchain.chat_models import init_chat_model
from langchain_core.messages import AIMessage, ToolMessage
from pydantic import JsonValue
from tools import make_tools

from arci.adapters.langchain import ToolEnv, make_adapter
from arci.interfaces import AgentFn, ToolBoxProtocol
from arci.toolbox import ToolBox


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
                # The request hook already saved no_response_headers. Preserve a
                # more specific wire reason even if the adapter raised HarnessError.
                if exchange is not None and not exchange.row["stream_completed"]:
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


SYSTEM_PROMPT = (
    "Use the order desk tools. Read the order first. Refund exactly its total_cents. "
    "For stock notes, read its SKU stock and write exactly 'stock: N'. "
    "Only add a note when the task asks for one. For refund notes write exactly "
    "'refunded'. A plain refund needs no note. Retry an empty lookup once."
)
# Each ARCI worker creates one registered toolset before it builds its arm's model.
_worker_trial: tuple[dict[str, JsonValue], int] | None = None


def candidate_settings(arm: str) -> dict[str, Any]:
    assert _worker_trial is not None
    task, seed = _worker_trial
    model_id = "ollama:" + os.environ["SIZE0_TAG"]
    registered = task["quickstart_settings"]
    if registered != {
        "baseline": model_id,
        "candidate": model_id,
        "temperature": 0.7,
        "baseline_reasoning": False,
        "candidate_reasoning": False,
    }:
        raise ValueError("model settings differ from registered task")
    exchange = FirstExchange(os.environ["ORDER_DESK_FIRST_EXCHANGE_AUDIT"], task, seed, arm)
    client: dict[str, Any] = {
        "follow_redirects": False,
        "trust_env": False,
        "event_hooks": {"request": [exchange.on_request], "response": [exchange.on_response]},
    }
    if os.environ.get("SIZE0_TRANSPORT") == "offline":
        from standin import transport

        client["transport"] = transport()
    model = init_chat_model(model_id, temperature=0.7, reasoning=False, sync_client_kwargs=client)
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
        ],
        "system_prompt": SYSTEM_PROMPT,
    }


def registered_tools(task: dict[str, JsonValue], seed: int) -> ToolEnv:
    global _worker_trial
    _worker_trial = (task, seed)
    return make_tools(task, seed)


def latch_receipt_loss(arm: AgentFn) -> AgentFn:
    def run(
        task: dict[str, JsonValue], boundary: ToolBoxProtocol, rng: random.Random
    ) -> dict[str, JsonValue]:
        try:
            return arm(task, boundary, rng)
        except ReceiptLost as exc:
            cast(ToolBox, boundary).fail_harness(str(exc))

    return run


toolset, raw_baseline, raw_candidate = make_adapter(
    registered_tools,
    lambda: candidate_settings("baseline"),
    lambda: candidate_settings("candidate"),
    task_to_input=task_input,
    fault_exceptions={"timeout": TimeoutError, "error": RuntimeError},
)
baseline = latch_receipt_loss(raw_baseline)
candidate = latch_receipt_loss(raw_candidate)
