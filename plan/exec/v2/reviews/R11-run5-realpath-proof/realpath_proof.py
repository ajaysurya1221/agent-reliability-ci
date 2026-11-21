"""In-process HTTP capture, with one fixed five-turn policy for both run 5 arms."""

from __future__ import annotations

import json
import socket
import sys
from collections import Counter
from collections.abc import Generator
from contextlib import contextmanager
from itertools import count
from typing import Any, TextIO
from unittest.mock import patch

BLOCKED: Counter[str] = Counter()
URL = "http://127.0.0.1:9/api/chat"


def refuse_network(event: str, args: tuple[Any, ...]) -> None:
    internet_socket = event == "socket.__new__" and args[1] in (socket.AF_INET, socket.AF_INET6)
    if internet_socket or event in {
        "socket.connect",
        "socket.sendto",
        "socket.sendmsg",
        "socket.getaddrinfo",
        "socket.gethostbyname",
        "socket.gethostbyaddr",
        "socket.getnameinfo",
    }:
        BLOCKED[event] += 1
        raise RuntimeError(f"network disabled for proof ({event})")


sys.addaudithook(refuse_network)

import httpx  # noqa: E402 -- install the socket guard before importing client code


def _call(name: str, **arguments: str) -> dict[str, Any]:
    return {"function": {"name": name, "arguments": arguments}}


def _policy(messages: list[dict[str, Any]], order_id: str) -> list[dict[str, Any]]:
    tools = [m for m in messages if m["role"] == "tool"]
    if len(tools) < 2:
        return [_call("lookup_order", order_id=order_id)]
    if len(tools) == 2:
        return [_call("check_stock", sku=json.loads(tools[-1]["content"])["sku"])]
    if len(tools) == 3:
        return [_call("add_note", order_id=order_id, note=f"stock: {tools[-1]['content']}")]
    if len(tools) == 4:
        return []
    raise ValueError("unexpected number of tool replies")


@contextmanager
def capture(
    stream: TextIO, round_number: int, task: str, arm: str, seed: int, order_id: str
) -> Generator[None, None, None]:
    turns = count(1)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method != "POST" or str(request.url) != URL:
            raise ValueError(f"unexpected HTTP request: {request.method} {request.url}")
        raw = request.content.decode("utf-8")
        stream.write(
            json.dumps(
                {
                    "round": round_number,
                    "task": task,
                    "seed": seed,
                    "arm": arm,
                    "turn": next(turns),
                    "url": str(request.url),
                    "body": raw,
                }
            )
            + "\n"
        )
        body = json.loads(raw)
        calls = _policy(body["messages"], order_id)
        head = {"model": body["model"], "created_at": "2026-11-16T00:00:00Z"}
        lines = []
        if calls:
            lines.append(
                {
                    **head,
                    "message": {"role": "assistant", "content": "", "tool_calls": calls},
                    "done": False,
                }
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
        return httpx.Response(200, content="".join(json.dumps(line) + "\n" for line in lines))

    mock = httpx.MockTransport(handler)
    with patch.object(httpx.Client, "_transport_for_url", return_value=mock):
        yield
    total = next(turns) - 1
    if total != 5:
        raise ValueError(f"{task}/{arm} captured {total} requests")
