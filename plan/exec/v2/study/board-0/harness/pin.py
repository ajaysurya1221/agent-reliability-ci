"""Twenty non-board timing trials with the production chat options."""

from __future__ import annotations

import base64
import http.client
import json
import os
import re
import subprocess
import tempfile
import threading
import time
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from admission import active
from agent import Capture, JsonObject, JsonValue, Receipt, atomic_json
from common import OLLAMA, Row, assistant, need, pin_name
from grade import grade

TOY_PROMPT = "Use the pebble reader to answer the question."
TOY_TOOLS: list[JsonValue] = [
    {
        "type": "function",
        "function": {
            "name": "read_pebble",
            "description": "Read a pebble's token.",
            "parameters": {
                "type": "object",
                "properties": {"pebble": {"type": "string"}},
                "required": ["pebble"],
            },
        },
    }
]


def question(i: int) -> list[Row]:
    return [
        {"role": "system", "content": TOY_PROMPT},
        {"role": "user", "content": f"What token is on pebble stone-{i}?"},
    ]


def reader(i: int) -> Row:
    return {"name": "read_pebble", "arguments": {"pebble": f"stone-{i}"}}


def called(msg: Row, i: int) -> bool:
    calls = msg.get("tool_calls")
    return (
        isinstance(calls, list)
        and len(calls) == 1
        and isinstance(calls[0], dict)
        and isinstance(fn := calls[0].get("function"), dict)
        and fn.get("name") == "read_pebble"
        and fn.get("arguments") == reader(i)["arguments"]
    )


def request(
    run: str, model: Row, endpoint: str, body: bytes | None, capture: Capture | None = None
) -> tuple[int, bytes]:
    claim = active(run)
    need(
        claim["model"] == model and endpoint in {"version", "tags", "show", "ps", "chat"},
        "probe admission",
    )
    payload = json.loads(body) if body is not None else None
    if endpoint == "chat":
        need(run == pin_name(model["slot"]) and payload is not None, "pin chat claim")
        assert payload is not None
        from admission import CLAIMS

        admit_probe(CLAIMS / run, model["tag"], payload)
    else:
        need(
            payload == ({"model": model["tag"]} if endpoint == "show" else None), "metadata request"
        )
    conn = http.client.HTTPConnection("127.0.0.1", 11434, timeout=60)
    try:
        conn.putrequest("POST" if body else "GET", "/api/" + endpoint)
        conn.putheader("Content-Type", "application/json")
        if body is not None:
            conn.putheader("Content-Length", str(len(body)))
        conn.endheaders()
        if body is not None:
            if capture:
                capture(body)
            conn.send(body)
        response = conn.getresponse()
        return response.status, response.read()
    finally:
        conn.close()


def metadata(run: str, model: Row, *, loaded: bool = False) -> Row:
    def get(endpoint: str, payload: Row | None = None) -> Any:
        status, raw = request(
            run, model, endpoint, json.dumps(payload).encode() if payload is not None else None
        )
        need(status == 200, "metadata HTTP status")
        return json.loads(raw)

    actual = get("version")["version"]
    need(actual == OLLAMA, "Ollama server version differs")
    tag = model["tag"]
    if loaded:
        rows = [r for r in get("ps")["models"] if r["name"] == tag]
        need(
            len(rows) == 1
            and rows[0]["digest"] == model["digest"]
            and rows[0]["context_length"] == 32768,
            "loaded model digest or context differs",
        )
        return {"ollama": actual, **rows[0]}
    need(
        [r["digest"] for r in get("tags")["models"] if r["name"] == tag] == [model["digest"]],
        "installed model digest differs",
    )
    need(
        re.findall(r"(?m)^num_ctx\s+(\d+)\s*$", get("show", {"model": tag})["parameters"])
        == ["32768"],
        "model context differs",
    )
    return {"ollama": actual}


def admit_probe(directory: Path, tag: str, payload: Row) -> None:
    history = payload["messages"]
    need(
        payload
        == {
            "model": tag,
            "stream": False,
            "think": False,
            "options": {"temperature": 0.7},
            "tools": TOY_TOOLS,
            "messages": history,
        },
        "unexpected pin chat options",
    )
    i = next((n for n in range(1, 23) if history[:2] == question(n)), 0)
    need(i and (i == 1 or (directory / f"probe-{i - 1}-0").exists()), "unexpected pin question")
    delivery = i > 20
    step = int(len(history) == 4 and not delivery)
    if delivery or step:
        need(
            len(history) == 4 and history[2].get("role") == "assistant" and called(history[2], i),
            "unexpected pin reader",
        )
        result = history[3].get("content")
        need(
            history[3] == {"role": "tool", "tool_name": "read_pebble", "content": result}
            and (
                result == ""
                if delivery
                else isinstance(result, str) and re.fullmatch(r"[0-9a-f]{24}", result)
            ),
            "unexpected pin delivery",
        )
        if step:
            need((directory / f"probe-{i}-0").exists(), "missing native pin request")
    else:
        need(len(history) == 2, "unexpected pin opening")
    (directory / f"probe-{i}-{step}").touch(exist_ok=False)


def toy_chat(body: bytes) -> tuple[int, bytes]:
    payload = json.loads(body)
    last = payload["messages"][-1]
    msg: Row = {"role": "assistant", "content": last["content"]}
    if last["role"] == "user":
        pebble = last["content"].removesuffix("?").split()[-1]
        msg.update(
            content="",
            tool_calls=[{"function": {"name": "read_pebble", "arguments": {"pebble": pebble}}}],
        )
    return 200, json.dumps({"model": payload["model"], "done": True, "message": msg}).encode()


@contextmanager
def memory_sample(enabled: bool) -> Generator[list[int], None, None]:
    """Maximum observed aggregate RSS of local Ollama processes during this pin trial."""
    peak: list[int] = []
    stop = threading.Event()

    def sample() -> None:
        while not stop.is_set():
            try:
                raw = subprocess.check_output(
                    ["ps", "-axo", "rss=,comm="], stderr=subprocess.DEVNULL, text=True, timeout=2
                )
                total = 0
                for line in raw.splitlines():
                    size, _, exe = line.strip().partition(" ")
                    if size.isdigit() and Path(exe.strip()).name.lower().startswith("ollama"):
                        total += int(size) * 1024
                if total:
                    peak[:] = [max(total, *peak)] if peak else [total]
            except (OSError, subprocess.SubprocessError):
                return
            stop.wait(0.25)

    if not enabled:
        yield peak
        return
    worker = threading.Thread(target=sample, daemon=True)
    worker.start()
    try:
        yield peak
    finally:
        stop.set()
        worker.join()


def run_probe(run: str, model: Row, tmp: Path, i: int, offline: bool) -> Row:
    start = time.monotonic()
    delivery = i > 20
    receipt = Receipt(tmp, run, "pin", i, "baseline", "toy", "clean")
    history = question(i)

    def transport(step: int, body: bytes, capture: Capture) -> tuple[int, bytes]:
        if offline:
            capture(body)
            return toy_chat(body)
        return request(run, model, "chat", body, capture)

    def chat() -> Row:
        payload: JsonObject = {
            "model": model["tag"],
            "messages": list(history),
            "tools": TOY_TOOLS,
            "stream": False,
            "think": False,
            "options": {"temperature": 0.7},
        }
        response = receipt.request(transport, payload)
        try:
            return assistant(json.dumps(response).encode(), model["tag"])
        except ValueError as exc:
            raise ConnectionError("invalid pin response") from exc

    ok = False
    with memory_sample(not offline) as peak:
        try:
            message = (
                {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [{"function": reader(i)}],
                }
                if delivery
                else chat()
            )
            if called(message, i):
                token = "" if delivery else os.urandom(12).hex()
                need(
                    delivery or token not in json.dumps([*history, message, TOY_TOOLS]),
                    "pin token leaked",
                )
                history.extend(
                    [
                        message,
                        {"role": "tool", "tool_name": "read_pebble", "content": token},
                    ]
                )
                final = chat()
                sent = json.loads(
                    base64.b64decode(receipt.exchanges[-1]["request_b64"], validate=True)
                )
                need(sent["messages"] == history, "pin delivery bytes")
                ok = delivery or (
                    not final.get("tool_calls") and grade(final["content"], token, {}, "")[0]
                )
        except (OSError, http.client.HTTPException):
            # Transport failures and incomplete replies are unsuccessful probes.
            pass
    return {
        "passed": ok,
        "exchanges": receipt.exchanges,
        "seconds": time.monotonic() - start,
        "peak_memory_bytes": peak[0] if peak else None,
    }


class PinFailed(ValueError):
    """All probes completed and the model did not qualify."""


def execute(run: str, model: Row, path: Path, *, offline: bool) -> None:
    result: Row = {
        "run": run,
        "model": model,
        "transport": "stand-in" if offline else "Ollama",
        "ok": False,
        "peak_memory_bytes": None,
        "memory_method": "maximum sampled aggregate Ollama RSS, bytes",
        "trials": [],
        "delivery": [],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_json(path, result, create=True)
    result["ollama"] = OLLAMA if offline else metadata(run, model)["ollama"]
    atomic_json(path, result)
    with tempfile.TemporaryDirectory() as tmp:
        for i in range(1, 23):
            row = run_probe(run, model, Path(tmp), i, offline)
            result["delivery" if i > 20 else "trials"].append(row)
            if row["peak_memory_bytes"]:
                result["peak_memory_bytes"] = max(
                    result["peak_memory_bytes"] or 0, row["peak_memory_bytes"]
                )
            atomic_json(path, result)
    result["passed"] = sum(p["passed"] for p in result["trials"])
    atomic_json(path, result)
    if result["passed"] < 16 or not all(p["passed"] for p in result["delivery"]):
        raise PinFailed("pin threshold or empty delivery failed")
    if not offline:
        metadata(run, model, loaded=True)
    result["ok"] = True
    atomic_json(path, result)
