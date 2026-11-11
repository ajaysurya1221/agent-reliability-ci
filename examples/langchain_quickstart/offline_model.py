"""A small scripted stand-in, not an LLM: read tool results instead of memorising seeds."""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Sequence
from typing import Any, cast

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import LanguageModelInput
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool


class OfflineModel(FakeMessagesListChatModel):
    """One policy for both arms: abandon on a tool error that middleware did not recover."""

    @staticmethod
    def validate_prompt(prompt: object) -> str:
        if (
            not isinstance(prompt, str)
            or re.fullmatch(
                r"(?:Refund order ORD-\d+(?: and add a refunded note)?|"
                r"Check stock for order ORD-\d+ and add a stock note)\.",
                prompt,
            )
            is None
        ):
            raise ValueError(
                "offline model only solves the shipped task wording; "
                "replace the offline model when replacing tasks"
            )
        return prompt

    def bind_tools(
        self,
        tools: Sequence[dict[str, Any] | type | Callable[..., Any] | BaseTool],
        *,
        tool_choice: str | None = None,
        **kwargs: Any,
    ) -> Runnable[LanguageModelInput, AIMessage]:
        return cast(Runnable[LanguageModelInput, AIMessage], self)

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        prompt = self.validate_prompt(next(m.text for m in messages if isinstance(m, HumanMessage)))
        match = re.search(r"ORD-\d+", prompt)
        if match is None:
            raise ValueError("expected an order id")
        order_id = match.group()
        replies = [m for m in messages if isinstance(m, ToolMessage)]
        results: dict[str, Any] = {}
        for reply in replies:
            if reply.status == "error":
                return ChatResult(generations=[ChatGeneration(message=AIMessage(content="Done"))])
            try:
                results[str(reply.name)] = json.loads(reply.text)
            except ValueError:
                results[str(reply.name)] = reply.text
        name, args = "", {}
        order = results.get("lookup_order")
        if not order:
            # An empty read is not proof of success: both arms retry it.
            name, args = "lookup_order", {"order_id": order_id}
        elif prompt.startswith("Refund") and "issue_refund" not in results:
            name, args = (
                "issue_refund",
                {"order_id": order_id, "amount_cents": order["total_cents"]},
            )
        elif prompt.startswith("Check") and "check_stock" not in results:
            name, args = "check_stock", {"sku": order["sku"]}
        elif "note" in prompt and "add_note" not in results:
            note = "refunded" if prompt.startswith("Refund") else f"stock: {results['check_stock']}"
            name, args = "add_note", {"order_id": order_id, "note": note}
        response = (
            AIMessage(content="Done")
            if not name
            else AIMessage(
                content="", tool_calls=[{"name": name, "args": args, "id": f"call-{len(replies)}"}]
            )
        )
        return ChatResult(generations=[ChatGeneration(message=response)])
