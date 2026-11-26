"""Build the registered board from the two families. No model access."""

import argparse
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PROMPT = (
    "You answer questions by using the tools you are given. Call a tool when you need "
    "information. Never invent a tool result. When you know the answer, reply with the answer."
)
STOCK = "The lookup returned no data. Repeat the same call with the same arguments."


def orders() -> list[dict[str, Any]]:
    result = []
    for i in range(1, 9):
        oid = f"ORD-{100 + 3 * i}"
        result.append(
            {
                "id": f"O-o{i}",
                "family": "orders",
                "ask": f"How many cents were paid in total for order {oid}?",
                "opening": {"name": "lookup_order", "arguments": {"order_id": oid}},
                "source": {"kind": "world_state", "field": "order.total_cents"},
                "answer_type": "integer",
                "task": {"order_id": oid},
            }
        )
    return result


def build(root: Path) -> dict[str, Any]:
    data = json.loads((root / "calendardesk/tasks.json").read_bytes())
    calendar = data["tasks"] if isinstance(data, dict) else data
    if not isinstance(calendar, list) or len(calendar) != 8:
        raise ValueError("expected eight calendar tasks")
    rows = orders() + calendar
    ids = set()
    for n, row in enumerate(rows):
        if (
            set(row) != {"id", "family", "ask", "opening", "source", "answer_type", "task"}
            or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]{0,63}", row["id"])
            or row["id"] in ids
            or row["family"] != ("orders" if n < 8 else "calendar")
            or row["answer_type"] not in ("integer", "string")
            or not isinstance(row["ask"], str)
            or not row["ask"]
            or not isinstance(row["task"], dict)
            or set(row["opening"]) != {"name", "arguments"}
            or not isinstance(row["opening"]["arguments"], dict)
            or row["opening"]["name"] == "board_opening"
            or row["source"]["kind"] != "world_state"
            or not row["source"]["field"]
        ):
            raise ValueError(f"invalid board row {n + 1}")
        ids.add(row["id"])
    return {"system_prompt": PROMPT, "stock_sentence": STOCK, "tasks": rows}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    root = parser.parse_args().root
    (root / "tasks/tasks.json").write_text(
        json.dumps(build(root), indent=2, ensure_ascii=False) + "\n"
    )
