"""Observe the registered first Ollama exchange and reconcile receipts with the store."""

from __future__ import annotations

import json
import sys
from collections import Counter
from collections.abc import Iterator
from contextlib import suppress
from pathlib import Path
from typing import Any

import httpx
from pydantic import JsonValue


class FirstExchange:
    def __init__(
        self, path: str, arm: str, task: dict[str, JsonValue], seed: int, prompt: str, reply: str
    ) -> None:
        self.path = Path(path)
        self.arm = arm
        self.seed = seed
        self.order_id = task["order_id"]
        self.messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": task["input"]},
            self.tool_call("check_stock", {"sku": self.order_id}),
            {"role": "tool", "content": "Error: unknown SKU"},
            self.tool_call("lookup_order", {"order_id": self.order_id}),
            {"role": "tool", "content": reply},
        ]
        self.first: httpx.Request | None = None
        self.matches = False
        self.assistant = False

    @staticmethod
    def tool_call(name: str, arguments: dict[str, JsonValue]) -> dict[str, Any]:
        return {
            "role": "assistant",
            "tool_calls": [{"function": {"name": name, "arguments": arguments}}],
        }

    def on_request(self, request: httpx.Request) -> None:
        if self.first is not None:
            return
        self.first = request
        with suppress(KeyError, ValueError, TypeError, httpx.RequestNotRead):
            self.matches = (
                request.method == "POST"
                and request.url.path == "/api/chat"
                and json.loads(request.content)["messages"] == self.messages
            )

    def on_response(self, response: httpx.Response) -> None:
        if response.request is not self.first or not response.is_success:
            return
        # The pinned synchronous Ollama client consumes decoded NDJSON with iter_lines.
        # Observe that same iterator without buffering, replacing or swallowing its data.
        original = response.iter_lines

        def observed_lines() -> Iterator[str]:
            for line in original():
                try:
                    frame = json.loads(line)
                    if (
                        frame["done"] is True
                        and frame["message"]["role"] == "assistant"
                        and frame.get("done_reason") != "load"
                        and not frame.get("error")
                    ):
                        self.assistant = True
                except (ValueError, KeyError, TypeError):
                    pass
                yield line

        response.iter_lines = observed_lines

    def record(self) -> None:
        # ARCI strips the descriptor id from the worker task. Its order_id uniquely
        # identifies the task in the registered file. Evidence I/O must not decide a trial.
        try:
            rows = Path(__file__).with_name("tasks.jsonl").read_text().splitlines()
            (task_id,) = (t["id"] for t in map(json.loads, rows) if t["order_id"] == self.order_id)
            row = {
                "arm": self.arm,
                "task_id": task_id,
                "seed": self.seed,
                "first_request_matches": self.matches,
                "assistant_response": self.assistant,
            }
            with self.path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(row) + "\n")
        except (OSError, KeyError, TypeError, ValueError):
            pass


def verify(trials: Path, receipts: Path) -> str:
    def key(row: dict[str, Any]) -> tuple[str, str, int]:
        if type(row["seed"]) is not int:
            raise ValueError("invalid scenario seed")
        return row["arm"], row["task_id"], row["seed"]

    with trials.open(encoding="utf-8") as stream:
        expected = Counter(key(row) for row in map(json.loads, stream))
    seen: Counter[tuple[str, str, int]] = Counter()
    with receipts.open(encoding="utf-8") as stream:
        for row in map(json.loads, stream):
            assignment = key(row)
            if row["first_request_matches"] is not True or row["assistant_response"] is not True:
                raise ValueError(f"unconfirmed first exchange for {assignment}")
            seen[assignment] += 1
    if not expected or seen != expected or any(n != 1 for n in expected.values()):
        raise ValueError("first-exchange receipts must match every assignment exactly once")
    return f"{len(expected)} assignments with a matching first request and assistant response"


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("expected one trials.jsonl and one first-exchange file")
    try:
        print(verify(Path(sys.argv[1]), Path(sys.argv[2])))
    except (OSError, KeyError, ValueError, TypeError) as exc:
        sys.exit(f"live exposure unverified: {exc}")
