"""Compare every complete captured JSON body, retaining every field and message position."""

from __future__ import annotations

import gzip
import json
from collections import Counter
from itertools import product
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
MESSAGES = "/messages/3/content"
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
    tasks_file = HERE.parents[1] / "study/order-desk-control-message/tasks.jsonl"
    tasks = {t["id"]: t for t in map(json.loads, tasks_file.read_text().splitlines())}
    assert len(tasks) == 8
    arms = ("baseline", "candidate")
    rounds, turns = range(1, 11), range(1, 6)
    with gzip.open(HERE / "http.jsonl.gz", "rt", encoding="utf-8") as stream:
        rows = [json.loads(line) for line in stream]
    receipt = rows.pop()
    assert receipt["verified_trials"] == 160
    assert not (receipt["blocked_network_events"].keys() - {"socket.__new__"})
    indexed = {(r["round"], r["task"], r["turn"], r["arm"]): r for r in rows}
    assert len(indexed) == len(rows) and set(indexed) == set(product(rounds, tasks, turns, arms))
    texts = {"baseline": receipt["explicit"], "candidate": receipt["neutral"]}
    expected_diff = (MESSAGES, render(texts["baseline"]), render(texts["candidate"]))
    kinds: Counter[tuple[str, str, str]] = Counter()
    counts: Counter[str] = Counter()
    first: Counter[tuple[str, str]] = Counter()
    nulls: Counter[str] = Counter()
    check_errors: Counter[str] = Counter()
    identical = 0
    for n, task, turn in product(rounds, tasks, turns):
        a, b = (indexed[n, task, turn, arm] for arm in arms)
        assert a["seed"] == b["seed"]
        x, y = json.loads(a["body"]), json.loads(b["body"])
        diff = differences(x, y)
        kinds.update(diff)
        identical += not diff
        if diff != ([expected_diff] if turn > 1 else []):
            check_errors["unexpected difference pattern"] += 1
        # Independently check the original serialized bodies, including whitespace and key order.
        expected_raw = a["body"]
        if turn > 1:
            expected_raw = expected_raw.replace(
                render(texts["baseline"]), render(texts["candidate"]), 1
            )
        if expected_raw != b["body"]:
            check_errors["additional serialized differences"] += 1
        for row, body in ((a, x), (b, y)):
            arm = row["arm"]
            counts[arm] += 1
            assert row["url"] == "http://127.0.0.1:9/api/chat"
            messages = body["messages"]
            roles = ["system", "user"] + ["assistant", "tool"] * (turn - 1)
            assert [m["role"] for m in messages] == roles
            assert messages[1]["content"] == tasks[task]["input"]
            if turn > 1:
                calls = messages[2]["tool_calls"]
                assert len(calls) == 1 and calls[0]["function"] == {
                    "name": "lookup_order",
                    "arguments": {"order_id": tasks[task]["order_id"]},
                }
                content = messages[3]["content"]
                if turn == 2:
                    first[arm, content] += 1
                nulls[arm] += content == "null"
    print("Captured requests:", dict(counts), "Identical pairs:", identical)
    print("Field differences:", dict(kinds))
    print("First delivery:", dict(first), "Literal null across all appearances:", dict(nulls))
    print(
        "Blocked socket events:",
        receipt["blocked_network_events"],
        "Other differences:",
        dict(check_errors),
    )
    assert first == Counter({(arm, texts[arm]): 80 for arm in arms})
    assert not any(nulls.values()) and not check_errors
    assert identical == 80 and kinds == Counter({expected_diff: 320})


if __name__ == "__main__":
    main()
