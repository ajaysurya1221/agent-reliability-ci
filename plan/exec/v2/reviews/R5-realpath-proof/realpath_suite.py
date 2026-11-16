"""Review-only: production agent behind a fake in-process Ollama transport, for `arci run`.

No network, no Ollama, no model. Arm wrappers only tag the HTTP log; they change nothing.
"""

from __future__ import annotations

import json
import os
import re
import socket
from typing import Any

import httpx


def _no_network(self: Any, address: Any) -> Any:
    raise AssertionError(f"review proof attempted a network connection to {address!r}")


socket.socket.connect = _no_network  # type: ignore[method-assign]

EMPTY = "lookup_order returned an empty result. Call lookup_order again with the same order_id."
_TAG: dict[str, Any] = {}


def _call(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    return {"function": {"name": name, "arguments": arguments}}


def _policy(body: dict[str, Any]) -> list[dict[str, Any]]:
    messages = body["messages"]
    user = next(m["content"] for m in messages if m["role"] == "user")
    order_id = re.search(r"ORD-\d+", user).group()  # type: ignore[union-attr]
    tools = [m for m in messages if m["role"] == "tool"]
    if not tools:
        return [_call("lookup_order", {"order_id": order_id})]
    latest = tools[-1].get("content", "")
    if latest in ("null", EMPTY):
        return [_call("lookup_order", {"order_id": order_id})]
    try:
        value = json.loads(latest)
    except ValueError:
        value = latest
    if isinstance(value, dict):
        return [_call("check_stock", {"sku": value["sku"]})]
    if isinstance(value, int):
        return [_call("add_note", {"order_id": order_id, "note": f"stock: {value}"})]
    return []


def handler(request: httpx.Request) -> httpx.Response:
    body = json.loads(request.content)
    with open(os.environ["REVIEW_HTTP_LOG"], "a", encoding="utf-8") as stream:
        stream.write(json.dumps({**_TAG, "url": str(request.url), "body": body}) + "\n")
    calls = _policy(body)
    head = {"model": body["model"], "created_at": "2026-11-16T00:00:00Z"}
    lines = []
    if calls:
        lines.append(
            {**head, "message": {"role": "assistant", "content": "", "tool_calls": calls}, "done": False}
        )
    lines.append(
        {
            **head,
            "message": {"role": "assistant", "content": "" if calls else "Done"},
            "done": True,
            "done_reason": "stop",
            "prompt_eval_count": 1,
            "eval_count": 1,
        }
    )
    return httpx.Response(200, content="".join(json.dumps(line) + "\n" for line in lines).encode())


_MOCK = httpx.MockTransport(handler)
httpx.Client._transport_for_url = lambda self, url: _MOCK  # type: ignore[method-assign]

import agent  # noqa: E402  -- the production module, unchanged

toolset = agent.toolset


def baseline(task: Any, boundary: Any, rng: Any) -> Any:
    _TAG.update(arm="baseline", task=task.get("order_id"))
    return agent.baseline(task, boundary, rng)


def candidate(task: Any, boundary: Any, rng: Any) -> Any:
    _TAG.update(arm="candidate", task=task.get("order_id"))
    return agent.candidate(task, boundary, rng)
