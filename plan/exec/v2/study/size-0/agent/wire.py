"""Observe a synchronous chat exchange through EOF before the tool parser sees it."""

import json
from collections.abc import Callable
from typing import Any

import httpx


def observe(response: httpx.Response, frame_seen: Callable[[dict[str, Any]], None]) -> str | None:
    if not response.is_success:
        return f"http_{response.status_code}"
    lines: list[str] = []
    reason = None
    terminal = False
    for line in response.iter_lines():
        lines.append(line)
        try:
            frame = json.loads(line)
            if not isinstance(frame, dict):
                raise ValueError("expected frame")
            frame_seen(frame)
            if frame.get("error"):
                reason = "server_error"
            elif terminal or frame.get("message", {}).get("role") != "assistant":
                reason = reason or "invalid_stream"
            terminal = frame.get("done") is True and frame.get("done_reason") != "load"
        except (ValueError, TypeError, AttributeError):
            reason = reason or "invalid_stream"
    response.iter_lines = lambda: iter(lines)
    return reason or (None if terminal else "missing_terminal")
