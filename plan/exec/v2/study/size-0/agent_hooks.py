"""Capture preflight metadata before Ollama or LangChain parses tool arguments."""

import sys
from collections.abc import Callable
from pathlib import Path
from time import monotonic

import httpx
from descriptors import Row

# Use the same observer that is copied into the isolated worker import path.
sys.path.insert(0, str(Path(__file__).resolve().parent / "agent"))
from wire import observe

sys.path.pop(0)


def probe_capture(capture: Row) -> dict[str, list[Callable[..., None]]]:
    first_start: float | None = None

    def sent(request: httpx.Request) -> None:
        nonlocal first_start
        if first_start is None:
            first_start = monotonic()

    def frame_seen(frame: Row) -> None:
        if frame.get("model") is not None:
            capture["models"].append(frame.get("model"))
        capture["thinking"] |= bool(frame.get("message", {}).get("thinking"))
        if (
            frame.get("done") is True
            and capture["load_duration"] is None
            and frame.get("load_duration") is not None
        ):
            capture["load_duration"] = frame["load_duration"] / 1e9

    def hook(response: httpx.Response) -> None:
        before = len(capture["models"])
        if observe(response, frame_seen) is None:
            capture["completed"] += 1
        if capture["load_duration"] is None:
            assert first_start is not None
            capture["load_duration"] = monotonic() - first_start
            capture["load_duration_missing"] = True
        if len(capture["models"]) == before:
            capture["models"].append(None)

    return {"request": [sent], "response": [hook]}
