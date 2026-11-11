"""Offline model fixture, not part of the adapter or a hosted-model claim."""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from typing import Any, cast

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import BaseTool


class ScriptedModel(FakeMessagesListChatModel):
    def bind_tools(
        self,
        tools: Sequence[dict[str, Any] | type | Callable[..., Any] | BaseTool],
        *,
        tool_choice: str | None = None,
        **kwargs: Any,
    ) -> ScriptedModel:
        del tools, tool_choice, kwargs
        return self

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        del stop, run_manager, kwargs
        prompt = next(m for m in messages if isinstance(m, HumanMessage))
        task = cast(dict[str, Any], json.loads(str(prompt.content)))
        observed = [m for m in messages if isinstance(m, ToolMessage)]
        if not observed:
            count = 2 if task.get("multi") else 1
            response = AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "lookup",
                        "args": {"key": 123 if task.get("bad_argument") else f"key-{i}"},
                        "id": f"call-{i}",
                    }
                    for i in range(count)
                ],
            )
        else:
            text = "unavailable" if observed[-1].status == "error" else observed[-1].text
            text = str(task.get("final_answer", text))
            content: str | list[str | dict[str, Any]] = text
            if task.get("list_final"):
                content = [{"type": "text", "text": text}]
            response = AIMessage(content=content)
        return ChatResult(generations=[ChatGeneration(message=response)])
