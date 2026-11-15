"""Generate small synthetic histories; seed 7 was chosen for REAL DROP / NO DROP.

Claude Code has a planted 45% reasoning-count drop in the final 14 of 56 days;
Codex is unchanged. There are 21 main-thread replies per day (about 24),
keeping the uncompressed files below 400 KB. This illustrative seed was selected
for those two results, not as statistical calibration evidence. No private session data are used.
"""

from __future__ import annotations

import argparse
import json
import random
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "src/arci/logs/example"


def generate() -> dict[str, bytes]:
    rng = random.Random(7)
    claude: list[dict[str, object]] = []
    codex: list[dict[str, object]] = [
        {
            "type": "session_meta",
            "payload": {
                "id": "example",
                "cwd": "/example",
                "cli_version": "1",
                "filler": "synthetic",
            },
        },
        {"type": "turn_context", "payload": {"model": "codex-example-1", "effort": "high"}},
    ]
    sub: list[dict[str, object]] = [
        {"type": "session_meta", "payload": {"id": "sub", "thread_source": "subagent"}},
        codex[1],
    ]
    start = datetime(2026, 9, 20, 12, tzinfo=UTC)
    for day in range(56):
        base = rng.randrange(900, 1101)
        for response in range(21):
            stamp = (
                (start + timedelta(days=day, minutes=response)).isoformat().replace("+00:00", "Z")
            )
            count = base + rng.randrange(-40, 41)
            identity = str(day * 21 + response)
            message: dict[str, object] = {
                "id": identity,
                "model": "claude-example-1",
                "usage": {
                    "output_tokens_details": {
                        "thinking_tokens": count * 55 // 100 if day >= 42 else count
                    }
                },
            }
            if response == 0 and day % 7 == 0:
                message["content"] = [{"type": "tool_use", "id": identity, "name": "Edit"}]
            claude.append(
                {"type": "assistant", "timestamp": stamp, "effort": "high", "message": message}
            )
            if response == 0 and day % 7 == 0:
                claude.append(
                    {
                        "type": "user",
                        "timestamp": stamp,
                        "message": {"content": [{"type": "tool_result", "tool_use_id": identity}]},
                    }
                )
            event: dict[str, object] = {
                "type": "event_msg",
                "timestamp": stamp,
                "payload": {
                    "type": "token_count",
                    "info": {"last_token_usage": {"reasoning_output_tokens": count}},
                },
            }
            codex.append(event)
        stamp = str(codex[-1]["timestamp"])
        event = codex[-1]
        if day % 7 == 0:
            claude.append(
                {
                    "type": "assistant",
                    "timestamp": stamp,
                    "effort": "high",
                    "isSidechain": True,
                    "filler": "synthetic",
                    "message": {
                        "id": f"sub-{day}",
                        "model": "claude-example-1",
                        "usage": {"output_tokens_details": {"thinking_tokens": 100}},
                    },
                }
            )
            sub.append(event)
    return {
        **{
            name: ("\n".join(json.dumps(row, separators=(",", ":")) for row in rows) + "\n").encode(
                "utf-8"
            )
            for name, rows in (
                ("claude/history.jsonl", claude),
                ("codex/sessions/rollout-example.jsonl", codex),
                ("codex/archived_sessions/rollout-subagent.jsonl", sub),
            )
        },
        "now.txt": b"2026-11-15T00:00:00+00:00\n",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    generated = generate()
    if args.check:
        matches = all(
            (ROOT / name).is_file() and (ROOT / name).read_bytes() == data
            for name, data in generated.items()
        )
        print("Example bytes match." if matches else "Example bytes differ.")
        return 0 if matches else 1
    for name, data in generated.items():
        target = ROOT / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    print(f"Generated {sum(map(len, generated.values()))} bytes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
