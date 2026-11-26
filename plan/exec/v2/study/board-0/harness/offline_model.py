"""Deterministic plain-text backend for the FIFO rehearsal."""

import json
import os
import time

from common import ROOT, Row, read


def chat(body: bytes, task: Row) -> tuple[int, bytes]:
    payload = json.loads(body)
    messages = payload["messages"]
    last = messages[-1]["content"]
    tid = task["key_id"]
    planted = json.loads(os.environ.get("BOARD0_REHEARSAL_FAULTS", "{}")).get(tid) == int(
        os.environ["ARCI_SEED"]
    )
    calls = []
    text = ""
    if planted and last == "" and tid == "O-o5":
        # Leave the captured exchange unanswered until the released supervisor times out.
        time.sleep(121)
    if planted and last == "" and tid == "O-o2":
        return 200, b'{"message":'
    if planted and tid == "O-o1" and last == "":
        calls = [task["opening"]] * 12  # The twelfth additional call exceeds the budget.
    elif planted and tid == "K-k8" and messages[3]["content"] == "":
        calls = [task["opening"]]  # Exhaust all eight chat requests without a final message.
    elif last == "":
        if tid == "O-o4":
            text = read(ROOT / "tasks/tasks.json")["stock_sentence"]
        elif tid == "O-o5":
            text = task["task"]["order_id"]
        elif tid == "K-k2":
            text = "Unknown venue"
    elif last.startswith("The lookup returned"):
        calls = [task["opening"]]
    elif planted and tid == "O-o3" and len(messages) == 6:
        calls = [{"name": "unknown", "arguments": {}}, *([task["opening"]] * 10)]
    else:
        row = next(r for r in read(ROOT / "tasks/tasks.json")["tasks"] if r["id"] == tid)
        record = json.loads(last)
        value = record[row["source"]["field"].split(".")[1]]
        text = str(value)
        if tid in ("K-k1", "O-o2"):
            text = f"The answer is {value}."
        elif tid == "O-o4":
            text = f"{value:,}"
        elif tid == "K-k7":
            text = f"  {value}.  "
        if len(messages) > 4:
            if tid in ("K-k2", "O-o6"):
                text = last  # The complete record contains same-type decoys.
            elif tid == "K-k6":
                text = text.lower()
            elif tid == "O-o7":
                text = text[:-2] + "." + text[-2:]
            elif tid == "O-o8":
                text += "0"
    msg: Row = {"role": "assistant", "content": text}
    if calls:
        msg["tool_calls"] = [{"function": fn} for fn in calls]
    return 200, json.dumps(
        {"model": payload["model"], "done": True, "done_reason": "stop", "message": msg}
    ).encode()
