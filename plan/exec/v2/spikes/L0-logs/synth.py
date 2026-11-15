"""Seeded synthetic logs. Canary-bearing input fixtures are intentionally private inputs.

Only this generator writes raw synthetic strings; reader/CLI outputs never copy them.
"""

from __future__ import annotations

import importlib
import json
import random
import sys
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import cast

from records import JSON, Tool


@dataclass(frozen=True)
class Parameters:
    date: date
    scale: float = 1.0
    log_sd: float = 0.40


@dataclass
class Generated:
    claude_root: Path
    codex_root: Path
    cwd: Path
    expected: dict[Tool, dict[str, int]]
    seed: int


def schedule(
    before: int = 42, after: int = 14, drop: float = 0.0, sd: float = 0.4
) -> list[Parameters]:
    start = date(2026, 1, 1)
    return [
        Parameters(start + timedelta(days=i), 1.0 if i < before else 1 - drop, sd)
        for i in range(before + after)
    ]


def generate(root: Path, seed: int, days: list[Parameters], compressed: bool = True) -> Generated:
    rng = random.Random(seed)
    sequence = 0

    def canary() -> str:
        nonlocal sequence
        sequence += 1
        return f"CANARY-{seed * 1000000 + sequence}"

    claude_root, codex_root = root / "claude", root / "codex"
    cwd = root / canary()
    expected: dict[Tool, dict[str, int]] = {
        tool: {
            "files": 0,
            "lines": 0,
            "responses": 0,
            "duplicate_responses": 0,
            "unparseable_lines": 0,
            "skipped_line_types": 0,
            "edit_results": 0,
            "denied_edits": 0,
            "lacking_reasoning": 0,
            "unread_compressed": 0,
            "skipped_api_errors": 0,
        }
        for tool in ("claude", "codex")
    }

    def write(path: Path, rows: list[dict[str, JSON] | str], tool: Tool) -> bytes:
        path.parent.mkdir(parents=True, exist_ok=True)
        text = "\n".join(json.dumps(r) if isinstance(r, dict) else r for r in rows) + "\n"
        path.write_text(text, encoding="utf-8")
        expected[tool]["files"] += 1
        expected[tool]["lines"] += len(rows)
        return text.encode()

    sub_codex: list[dict[str, JSON] | str] = [
        {
            "type": "session_meta",
            "payload": {
                "cwd": str(cwd),
                "cli_version": canary(),
                "thread_source": "subagent",
            },
        },
        {"type": "turn_context", "payload": {"model": "gpt-synth", "effort": "high"}},
    ]
    sub_claude: list[dict[str, JSON] | str] = []
    for cumulative_sub, parameter in enumerate(days, 1):
        for tool in ("claude", "codex"):
            day_value = max(
                1, round(10000 * parameter.scale * rng.lognormvariate(0, parameter.log_sd))
            )
            for session in range(2):
                stamp = datetime.combine(parameter.date, time(12 + session), UTC).isoformat()
                rows: list[dict[str, JSON] | str] = []
                if tool == "codex":
                    rows.extend(
                        [
                            {
                                "timestamp": stamp,
                                "type": "session_meta",
                                "payload": {
                                    "cwd": str(cwd),
                                    "cli_version": canary(),
                                    "thread_source": "user",
                                },
                            },
                            {
                                "timestamp": stamp,
                                "type": "turn_context",
                                "payload": {
                                    "model": "gpt-synth",
                                    "effort": "high",
                                },
                            },
                        ]
                    )
                for i in range(12):
                    value = 0 if rng.random() < 0.08 else max(1, day_value + rng.randint(-50, 50))
                    missing = i == 0 and session == 0
                    expected[tool]["responses"] += 1
                    expected[tool]["lacking_reasoning"] += missing
                    expected[tool]["duplicate_responses"] += 1
                    if tool == "claude":
                        identity, tool_id = canary(), canary()
                        usage: dict[str, JSON] = {
                            "output_tokens_details": None
                            if missing
                            else {"thinking_tokens": value},
                        }
                        blocks: tuple[dict[str, JSON], ...] = (
                            {"type": "thinking", "thinking": canary(), "signature": canary()},
                            {"type": "tool_use", "id": tool_id, "name": "Edit", "input": canary()},
                        )
                        for block in blocks:
                            rows.append(
                                {
                                    "type": "assistant",
                                    "timestamp": stamp,
                                    "effort": "high",
                                    "version": canary(),
                                    "message": {
                                        "id": identity,
                                        "model": "claude-synth",
                                        "content": [block],
                                        "usage": usage,
                                        "stop_reason": "tool_use",
                                    },
                                }
                            )
                        denied = i == 1
                        user: dict[str, JSON] = {
                            "type": "user",
                            "timestamp": stamp,
                            "message": {
                                "content": [
                                    {
                                        "type": "tool_result",
                                        "tool_use_id": tool_id,
                                        "is_error": denied or rng.random() < 0.04,
                                        "content": canary(),
                                    }
                                ]
                            },
                        }
                        if denied:
                            user["permissionDecision"] = {"decision": "reject"}
                        rows.append(user)
                        expected[tool]["denied_edits"] += denied
                        expected[tool]["edit_results"] += not denied
                    else:
                        event: dict[str, JSON] = {
                            "type": "event_msg",
                            "timestamp": stamp,
                            "payload": {
                                "type": "token_count",
                                "info": {
                                    "last_token_usage": {}
                                    if missing
                                    else {"reasoning_output_tokens": value},
                                    "total_token_usage": {"total_tokens": (i + 1) * 100000},
                                },
                            },
                        }
                        rows.extend([event, event])
                rows.extend([{"type": "attachment", "unknown": canary()}, "{" + canary()])
                expected[tool]["unparseable_lines"] += 1
                expected[tool]["skipped_line_types"] += 1
                if tool == "claude":
                    rows.append(
                        {
                            "type": "assistant",
                            "isApiErrorMessage": True,
                            "message": {"content": canary()},
                        }
                    )
                    expected[tool]["skipped_api_errors"] += 1
                    path = claude_root / "project" / f"{parameter.date}-{session}.jsonl"
                else:
                    rows.append(
                        {"type": "event_msg", "payload": {"type": "token_count", "info": None}}
                    )
                    expected[tool]["skipped_line_types"] += 1
                    path = (
                        codex_root
                        / "sessions"
                        / parameter.date.strftime("%Y/%m/%d")
                        / f"rollout-{session}.jsonl"
                    )
                write(path, rows, tool)
        stamp = datetime.combine(parameter.date, time(12), UTC).isoformat()
        sub_claude.append(
            {
                "type": "assistant",
                "timestamp": stamp,
                "isSidechain": True,
                "message": {
                    "id": canary(),
                    "model": "claude-synth",
                    "content": [{"type": "text", "text": canary()}],
                    "usage": {"output_tokens_details": {"thinking_tokens": 1}},
                },
            }
        )
        sub_codex.append(
            {
                "type": "event_msg",
                "timestamp": stamp,
                "payload": {
                    "type": "token_count",
                    "info": {
                        "last_token_usage": {"reasoning_output_tokens": 1},
                        "total_token_usage": {"total_tokens": cumulative_sub},
                    },
                },
            }
        )
    write(
        claude_root / "project" / "session" / "subagents" / "nested" / "agent-synth.jsonl",
        sub_claude,
        "claude",
    )
    encoded = write(codex_root / "archived_sessions" / "subagent.jsonl", sub_codex, "codex")
    for tool in ("claude", "codex"):
        expected[tool]["responses"] += len(days)
    # Journal is intentionally not part of expected reader counts.
    journal = claude_root / "project" / "journal.jsonl"
    journal.write_text(canary(), encoding="utf-8")
    if compressed and sys.version_info >= (3, 14):
        module = importlib.import_module("compression.zstd")
        compressed_bytes = cast(bytes, module.compress(encoded))
        (codex_root / "archived_sessions" / "subagent-copy.jsonl.zst").write_bytes(compressed_bytes)
        expected["codex"]["files"] += 1
        expected["codex"]["lines"] += len(sub_codex)
        expected["codex"]["responses"] += len(days)
    return Generated(claude_root, codex_root, cwd, expected, seed)
