"""Synthetic Codex transcripts for the extractor tests.

Every session id, working directory and model name carries a token that no output of the study
may hold. No real transcript is ever opened.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path

CANARY = "CANARY"
BASE = datetime(2026, 5, 3, 14, 7, 9, tzinfo=UTC)


def canary(tag: str) -> str:
    return f"{CANARY}-{tag}"


def codex_rows(
    *,
    tag: str,
    reasoning: Sequence[int | None],
    models: Sequence[str] | None = None,
    subagent: bool = False,
    first_offset: int = 0,
    offsets: Sequence[int] | None = None,
) -> list[object]:
    """One Codex rollout: a session header, a turn context and one response per count.

    `reasoning` holds the recorded reasoning count of each response; None records no count.
    `models` gives a model name per response (a turn context is written before each).
    `offsets` gives each response's own second offset, so a file can hold its responses in an
    order that is not the order of their timestamps.
    """
    rows: list[object] = [
        {
            "type": "session_meta",
            "payload": {
                "id": canary(f"session-{tag}"),
                "cwd": "/" + canary(f"cwd-{tag}"),
                "cli_version": "6.7.8",
                "thread_source": "subagent" if subagent else "user",
            },
        }
    ]
    if models is None:
        rows.append({"type": "turn_context", "payload": {"model": "gpt-6-astra", "effort": "high"}})
    current = ""
    for index, value in enumerate(reasoning):
        if models is not None and models[index] != current:
            current = models[index]
            rows.append({"type": "turn_context", "payload": {"model": current, "effort": "high"}})
        step = index if offsets is None else offsets[index]
        stamp = (BASE + timedelta(seconds=first_offset + step)).isoformat()
        rows.append(
            {
                "type": "event_msg",
                "timestamp": stamp,
                "payload": {
                    "type": "token_count",
                    "info": {
                        "total_token_usage": {"total_tokens": 1000 + index},
                        "last_token_usage": {
                            "reasoning_output_tokens": (
                                canary("no-count") if value is None else value
                            )
                        },
                    },
                },
            }
        )
    return rows


def write_transcript(path: Path, rows: Sequence[object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(json.dumps(row) if isinstance(row, dict) else str(row) for row in rows) + "\n"
    _ = path.write_bytes(text.encode("utf-8"))


def response_time(index: int, *, first_offset: int = 0) -> str:
    return (BASE + timedelta(seconds=first_offset + index)).astimezone(UTC).isoformat()
