"""Construct expected wire bytes from a Run 6 capture, independently of the worker."""

import hashlib
import json
import random
from pathlib import Path

from descriptors import Row, read
from records import require

from arci.suite_schedule import build_suite_schedule
from arci.suite_schema import SuiteManifest


def assignments(root: Path, run: str, model: Row, manifest: SuiteManifest) -> list[Row]:
    body = read(root / "request-template.json")
    body["model"] = model["tag"]
    messages = body["messages"]
    result: list[Row] = []
    for spec in build_suite_schedule(manifest):
        order = spec.task["order_id"]
        messages[1]["content"] = spec.task["input"]
        messages[2]["tool_calls"][0]["function"]["arguments"]["sku"] = order
        messages[4]["tool_calls"][0]["function"]["arguments"]["order_id"] = order
        if run.endswith("-clean"):
            rng = random.Random(spec.seed)
            messages[5]["content"] = json.dumps(
                dict(
                    sku=f"SKU-{rng.randrange(1000, 9999)}",
                    total_cents=rng.randrange(1000, 20000),
                    refunded_cents=0,
                    notes=[],
                )
            )
        raw = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode()
        result.append(
            dict(
                run=run,
                round=int(spec.pair_id.split(":")[0][1:]),
                order_id=order,
                trial_id=spec.trial_id,
                task_id=spec.task_id,
                arm=spec.arm,
                seed=spec.seed,
                body_sha256=hashlib.sha256(raw).hexdigest(),
            )
        )
    require(
        len(result) == 160 and len({r["seed"] for r in result}) == 80, "assignment schedule differs"
    )
    return result
