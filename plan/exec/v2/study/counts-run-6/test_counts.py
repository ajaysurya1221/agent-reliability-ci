"""Small hand-labelled counterexamples for the two descriptive counters."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

HERE = Path(__file__).resolve().parent


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        ("complete", (1, 1, 1, 1)),
        ("model chose wrong start", (0, 1, 0, 1)),
        ("wrong sku argument", (0, 1, 0, 1)),
        ("wrong error", (0, 1, 0, 1)),
        ("wrong order argument", (0, 0, 0, 0)),
        ("wrong lookup occurrence", (0, 0, 0, 0)),
        ("wrong finish id", (0, 0, 0, 0)),
        ("real null", (1, 0, 0, 0)),
        ("injected non-null", (1, 0, 0, 0)),
        ("failed injection", (1, 0, 0, 0)),
        ("queued lookup", (1, 1, 0, 0)),
        ("successful lookup before handoff", (1, 1, 0, 0)),
        ("no retry", (1, 1, 1, 0)),
    ],
)
def test_evidence_required(tmp_path: Path, change: str, expected: tuple[int, ...]) -> None:
    wrong = {"call_id": "0", "tool": "check_stock", "occurrence": 0, "arguments": {"sku": "A"}}
    error = {
        "call_id": "0",
        "tool": "check_stock",
        "ok": False,
        "injected_by": None,
        "error_kind": "error",
    }
    lookup = {
        "call_id": "1",
        "tool": "lookup_order",
        "occurrence": 0,
        "arguments": {"order_id": "A"},
    }
    reply = {
        "call_id": "1",
        "tool": "lookup_order",
        "ok": True,
        "injected_by": "empty_result",
        "value": None,
    }
    sequence: list[tuple[str, dict[str, Any]]] = [
        ("tool_start", wrong),
        ("tool_finish", error),
        ("tool_start", lookup),
        ("tool_finish", reply),
        ("model_step", {}),
        ("tool_start", {**lookup, "call_id": "2", "occurrence": 1}),
    ]
    detail = "ValueError: unknown SKU"
    if change == "model chose wrong start":
        sequence.insert(0, ("model_step", {}))
    if change == "wrong sku argument":
        wrong["arguments"] = {"sku": "B"}
    if change == "wrong error":
        detail = "ValueError: different"
    if change == "wrong order argument":
        lookup["arguments"] = {"order_id": "B"}
    if change == "wrong lookup occurrence":
        lookup["occurrence"] = 1
    if change == "wrong finish id":
        reply["call_id"] = "999"
    if change == "real null":
        reply["injected_by"] = None
    if change == "injected non-null":
        reply["value"] = "null"
    if change == "failed injection":
        reply["ok"] = False
    if change == "queued lookup":
        del sequence[4]
    if change == "successful lookup before handoff":
        again = sequence.pop()
        sequence[4:4] = [
            again,
            ("tool_finish", {**reply, "call_id": "2", "injected_by": None, "value": {"sku": "S"}}),
        ]
    if change == "no retry":
        sequence.pop()
    events = [
        {"trial_id": "t", "seq": i, "kind": kind, "payload": p}
        for i, (kind, p) in enumerate(sequence)
    ]
    trial = {
        "trial_id": "t",
        "arm": "candidate",
        "task_id": "desk",
        "condition_id": "empty",
        "termination": "completed",
        "outcome": "FAIL",
        "events": events,
        "recording": [{"result": {"error_detail": detail}}],
    }
    manifest = {
        "candidate": {"label": "raw-null"},
        "tasks": [{"task_id": "desk", "task": {"order_id": "A"}}],
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    (tmp_path / "trials.jsonl").write_text(json.dumps(trial) + "\n")
    (tmp_path / "events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in events))
    outputs = [
        subprocess.check_output([sys.executable, str(HERE / name), str(tmp_path)])
        for name in ("count_a.py", "count_b.py")
    ]
    assert outputs[0] == outputs[1]
    counts = json.loads(outputs[0])["arms"]["candidate"]
    reread = counts["after_empty_result"]["read_again"]
    assert (
        counts["scripted_opening_recorded"],
        counts["empty_result_delivered_ok"],
        counts["model_step_after_opening"],
        reread["trials"],
    ) == expected
    assert reread["passed"] == 0
