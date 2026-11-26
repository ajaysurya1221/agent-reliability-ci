"""Count B reads exported bytes, seeded keys and sealed recordings independently of Count A."""

import base64
import hashlib
import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from common import SIDES, Row, assistant, check_deadline, function, lines, need, require_infra
from worlds import check_opening, record_id, world


def terminal(receipt: Row, tag: str, trial: Row, known: set[str]) -> str | None:
    remaining = 11  # the opening already consumed one call
    exchanges = receipt["exchanges"]
    need(1 <= len(exchanges) == receipt["steps"] <= 8, "Count B chat budget")
    for x in exchanges:
        raw = base64.b64decode(x["request_b64"], validate=True)
        need(
            hashlib.sha256(raw).hexdigest() == x["sha256"] and json.loads(raw)["model"] == tag,
            "Count B request bytes",
        )
        if x["status"] != 200 or x["response_b64"] is None or x.get("incomplete_body"):
            if trial["termination"] != "timeout":
                require_infra(trial, receipt, x)
            break
        body = base64.b64decode(x["response_b64"], validate=True)
        try:
            msg = assistant(body, tag)
            answer = msg["content"] if not msg.get("tool_calls") else None
            for call in msg.get("tool_calls", []):
                fn = function(call)
                if fn["name"] in known:
                    if not remaining:
                        need(x is exchanges[-1], "Count B request after budget")
                        return None
                    remaining -= 1
        except ValueError:
            require_infra(trial, receipt, x)
            break
        if answer is not None:
            need(x is exchanges[-1], "Count B request after final text")
            return answer
    need(len(exchanges) == 8 or not receipt["complete"], "Count B premature completion")
    return None


def grade(text: str | None, key: int | str, snapshot: object, row_id: str) -> tuple[bool, bool]:
    if not text:
        return False, False
    terminal = text.strip()
    if terminal.endswith("."):
        terminal = terminal[:-1]
    exact = terminal == str(key)
    text = text.replace(row_id, "")
    pending: list[Any] = [snapshot]
    candidates: set[Any] = {key}
    while pending:
        item = pending.pop()
        if isinstance(item, dict):
            pending.extend(item.values())
        elif isinstance(item, list):
            pending.extend(item)
        elif type(item) is type(key):
            candidates.add(item)
    if isinstance(key, int):
        tokens = re.findall(r"(?<![\d.,])(?:\d{1,3}(?:,\d{3})+|\d+)(?![\d]|[.,]\d)", text)
        numerals = {
            "".join(str(unicodedata.decimal(c)) for c in token if c != ",").lstrip("0") or "0"
            for token in tokens
        }
        return {str(v) for v in candidates} & numerals == {str(key)}, exact
    found = set()
    pos = 0
    words = sorted(filter(None, candidates), key=len, reverse=True)
    while pos < len(text):
        if pos == 0 or not text[pos - 1].isalnum():
            for word in words:
                end = pos + len(word)
                if text.startswith(word, pos) and (end == len(text) or not text[end].isalnum()):
                    found.add(word)
                    pos = end
                    break
            else:
                pos += 1
        else:
            pos += 1
    return found == {key}, exact


def count(store: Path, rows: dict[str, Row], tag: str) -> Row:
    run = store.parent.name if store.parent.name.endswith("-clean") else store.name
    receipts = lines(store / "receipts.jsonl")
    index = {(r["run"], r["key_id"], r["seed"], r["arci_arm"]): r for r in receipts}
    need(len(index) == len(receipts), "duplicate receipt")
    arms = {
        s: {
            f: dict.fromkeys(
                (
                    "passed",
                    "trials",
                    "retrieved",
                    "exact",
                    "errored",
                ),
                0,
            )
            for f in ("orders", "calendar", "all")
        }
        for s in SIDES
    }
    signs = Counter(dict.fromkeys(("minus", "zero", "plus", "errored"), 0))
    pairs: dict[str, dict[str, str]] = defaultdict(dict)
    for t in lines(store / "trials.jsonl"):
        side = t["arm"]
        row = rows[t["task_id"]]
        r = index.pop((run, t["task_id"], t["seed"], side))
        ledger = t["final_state"]["ledger"]
        check_opening(row, t["seed"], ledger[2]["server_reply"])
        check_deadline(t, r)
        text = terminal(r, tag, t, {tool["name"] for tool in ledger[1]["tools"]})
        group, field = row["source"]["field"].split(".")
        snapshot = world(row, t["seed"]).snapshot()
        key = snapshot[group][field]
        exact = False
        if t["termination"] == "completed":
            need(
                r["complete"] and text == r["answer"] == t["final_state"]["answer"],
                "Count B terminal receipt",
            )
            passed, exact = grade(text, key, snapshot, record_id(row))
            need(t["outcome"] == ("PASS" if passed else "FAIL"), "Count B final text grade")
        else:
            need(t["outcome"] != "PASS", "Count B noncompleted pass")
        calls = [c["result"] for c in t["recording"] if not c["tool"].startswith("rpc:")]
        record = snapshot[row["source"]["field"].split(".")[0]]

        retrieved = any(
            c["tool"] == row["opening"]["name"]
            and c["ok"]
            and any(
                b.get("type") == "text" and json.loads(b["text"]) == record
                for b in c["value"]["content"]
            )
            for c in calls[1:]
        ) and not run.endswith("-clean")
        for group in (row["family"], "all"):
            v = arms[side][group]
            v["trials"] += 1
            v["passed"] += int(t["outcome"] == "PASS")
            v["errored"] += int(t["outcome"] == "ERROR")
            v["exact"] += int(exact)
            v["retrieved"] += int(retrieved)
        need(side not in pairs[t["pair_id"]], "duplicate pair side")
        pairs[t["pair_id"]][side] = t["outcome"]
    need(not index, "extra receipt")
    for pair in pairs.values():
        a, b = pair["baseline"], pair["candidate"]
        sign = (
            "errored"
            if "ERROR" in (a, b)
            else "zero"
            if a == b
            else "plus"
            if b == "PASS"
            else "minus"
        )
        signs[sign] += 1
    return {"arms": arms, "signs": dict(signs)}
