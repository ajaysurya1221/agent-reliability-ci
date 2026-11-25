"""Byte-oriented stand-in for the chat transport. No model or network dependency."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def chat(plan_file: Path, key_id: str, step: int, body: bytes) -> tuple[int, bytes]:
    plan = json.loads(plan_file.read_bytes())[key_id]
    request = json.loads(body)
    script = plan["script"]
    message: dict[str, Any] = {"role": "assistant", "content": ""}
    if script == "gives-up":
        message["content"] = "I could not find it."
    elif script in ("corrected", "paste"):
        calls = plan["good"]
        if step < len(calls):
            message["tool_calls"] = [{"function": calls[step]}]
        else:
            last = request["messages"][-1]
            if last["role"] != "tool":
                raise ValueError("the stand-in needs the last good tool reply")
            if script == "paste":
                message["content"] = last["content"]
            elif plan.get("world_key") == "order.total_cents":
                message["content"] = str(json.loads(last["content"])["total_cents"])
            else:
                message["content"] = "\n".join(plan["expect"])
    else:
        raise ValueError(f"unknown offline script {script!r}")
    return 200, json.dumps(
        {
            "model": request["model"],
            "done": True,
            "done_reason": "stop",
            "message": message,
            "received_sha256": hashlib.sha256(body).hexdigest(),
        },
        ensure_ascii=False,
    ).encode()
