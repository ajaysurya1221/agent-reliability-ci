"""In-process /api/chat stand-in for rehearsals. Uses no sockets."""

import json
from typing import Any

import httpx


def respond(request: httpx.Request) -> httpx.Response:
    body = json.loads(request.content)
    messages = body["messages"]
    order_id = messages[4]["tool_calls"][0]["function"]["arguments"]["order_id"]
    last = messages[-1]["content"]
    call: tuple[str, dict[str, Any]] | None
    if last == "null":
        call = "lookup_order", {"order_id": order_id}
    elif last.startswith("{"):
        call = "check_stock", {"sku": json.loads(last)["sku"]}
    elif last.isdecimal():
        call = "add_note", {"order_id": order_id, "note": f"stock: {last}"}
    else:
        call = None
    message: dict[str, Any] = {"role": "assistant", "content": "" if call else "Done"}
    if call:
        message["tool_calls"] = [{"function": {"name": call[0], "arguments": call[1]}}]
    return httpx.Response(
        200, json={"model": body["model"], "done": True, "message": message, "done_reason": "stop"}
    )


def transport() -> httpx.MockTransport:
    return httpx.MockTransport(respond)
