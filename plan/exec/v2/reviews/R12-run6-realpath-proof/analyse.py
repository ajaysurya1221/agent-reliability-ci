"""Compare every complete captured JSON body, retaining every field and message position."""

from __future__ import annotations

import gzip
import json
from collections import Counter
from itertools import product
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
MESSAGES = "/messages/5/content"
MISSING = object()


def render(value: Any) -> str:
    return "<missing>" if value is MISSING else json.dumps(value, sort_keys=True)


def differences(left: Any, right: Any, path: str = "") -> list[tuple[str, str, str]]:
    if isinstance(left, dict) and isinstance(right, dict):
        keys = sorted(left.keys() | right.keys())
        return [
            diff
            for k in keys
            for diff in differences(left.get(k, MISSING), right.get(k, MISSING), f"{path}/{k}")
        ]
    if isinstance(left, list) and isinstance(right, list):
        from itertools import zip_longest

        return [
            diff
            for i, (a, b) in enumerate(zip_longest(left, right, fillvalue=MISSING))
            for diff in differences(a, b, f"{path}/{i}")
        ]
    if type(left) is not type(right) or left != right:
        return [(path, render(left), render(right))]
    return []


def main() -> None:
    tasks_file = HERE.parents[1] / "study/order-desk-compound/tasks.jsonl"
    tasks = {t["id"]: t for t in map(json.loads, tasks_file.read_text().splitlines())}
    assert len(tasks) == 8
    arms = ("baseline", "candidate")
    rounds, turns = range(1, 11), range(1, 5)
    with gzip.open(HERE / "http.jsonl.gz", "rt", encoding="utf-8") as stream:
        rows = [json.loads(line) for line in stream]
    receipt = rows.pop()
    assert receipt["verified_trials"] == 160
    assert not (receipt["blocked_network_events"].keys() - {"socket.__new__"})
    indexed = {(r["round"], r["task"], r["turn"], r["arm"]): r for r in rows}
    assert len(indexed) == len(rows) and set(indexed) == set(product(rounds, tasks, turns, arms))
    assert receipt["requests_leaving_process"] == 0
    texts = {"baseline": receipt["generic"], "candidate": "null"}
    assert texts["baseline"] == (
        "The previous tool call returned an empty result. Repeat that call with the same input."
    )
    expected_diff = (MESSAGES, render(texts["baseline"]), render(texts["candidate"]))
    first: Counter[str] = Counter()
    for n, task, turn in product(rounds, tasks, turns):
        a, b = (indexed[n, task, turn, arm] for arm in arms)
        assert a["seed"] == b["seed"]
        x, y = json.loads(a["body"]), json.loads(b["body"])
        assert differences(x, y) == [expected_diff], (n, task, turn)
        assert a["body"].replace(render(texts["baseline"]), render("null"), 1) == b["body"]
        for row, body in ((a, x), (b, y)):
            assert row["url"] == "http://127.0.0.1:9/api/chat"
            assert body["model"] == "qwen3.5:4b-mlx-ctx32k"
            assert body["think"] is False and body["options"]["temperature"] == 0.7
            assert {t["function"]["name"] for t in body["tools"]} == {
                "check_stock",
                "lookup_order",
                "add_note",
                "issue_refund",
            }
            messages = body["messages"]
            roles = ["system", "user"] + ["assistant", "tool"] * (turn + 1)
            assert [m["role"] for m in messages] == roles
            assert messages[1]["content"] == tasks[task]["input"]
            order_id = tasks[task]["order_id"]
            for i, name, arguments in (
                (2, "check_stock", {"sku": order_id}),
                (4, "lookup_order", {"order_id": order_id}),
            ):
                (call,) = messages[i]["tool_calls"]
                assert call["function"] == {"name": name, "arguments": arguments}
            assert messages[3]["content"] == "Error: unknown SKU"
            assert messages[5]["content"] == texts[row["arm"]]
            if turn == 1:
                first[row["arm"]] += 1
    assert first == Counter(baseline=80, candidate=80)
    print("Complete opening on first request:", dict(first))
    print("320/320 paired bodies byte-identical after changing only /messages/5/content.")
    print(
        "640 intercepted requests; 0 left the process. Blocked events:",
        receipt["blocked_network_events"],
    )


if __name__ == "__main__":
    main()
