"""Generate both days from the registered roster. JSON is valid YAML."""

import json
import re
from pathlib import Path
from typing import Any

SLOTS = ("q2", "q4", "q9", "g12")
REG = "PREREGISTRATION-size-0.draft.md"
RUNS = tuple(
    f"size0-d{day}-{slot}-{condition}"
    for day, order in ((1, SLOTS), (2, ("q9", "q4", "q2")))
    for slot in order
    for condition in ("clean", "null")
)
Row = dict[str, Any]


def read(path: Path) -> Any:
    return json.loads(path.read_bytes())


def encoded(value: object) -> bytes:
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode()


def validate_slot(root: Path, slot: str, identity: Row) -> None:
    bounds = read(root / "slots.json")[slot]
    size = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*B\s*", identity["size"], re.IGNORECASE)
    if size is None or not bounds["min_billions"] <= float(size[1]) <= bounds["max_billions"]:
        raise ValueError(f"{slot}: parameter size outside registered range")
    if bounds["family"] not in identity["family"].casefold():
        raise ValueError(f"{slot}: family differs from registered slot")


def models(root: Path) -> dict[str, Row]:
    config = read(root / "models.json")
    if (
        set(config) != {"ollama", "slots"}
        or not isinstance(config["ollama"], str)
        or not config["ollama"].strip()
    ):
        raise ValueError("invalid server version or roster")
    rows = config["slots"]
    fields = {"slot", "tag", "digest", "family", "size", "format", "quantization", "context"}
    if not isinstance(rows, list) or len(rows) != 4:
        raise ValueError("expected four model slots")
    for row in rows:
        if set(row) != fields or not (
            row["context"] == 32768
            and all(isinstance(row[k], str) and row[k].strip() for k in fields - {"context"})
        ):
            raise ValueError("invalid model record")
        if not re.fullmatch(r"[A-Za-z0-9._/-]+:[A-Za-z0-9._-]+", row["tag"]) or not re.fullmatch(
            r"[a-f0-9]{64}", row["digest"]
        ):
            raise ValueError("invalid model tag or digest")
    result = {r["slot"]: r for r in rows}
    if set(result) != set(SLOTS) or any(len({r[k] for r in rows}) != 4 for k in ("digest", "tag")):
        raise ValueError("expected four distinct digests and tags and canonical slots")
    for slot, row in result.items():
        validate_slot(root, slot, row)
    if len({result[s]["quantization"] for s in ("q2", "q4", "q9")}) != 1:
        raise ValueError("Qwen quantization levels differ")
    return result


def descriptor(root: Path, run: str, model: Row) -> Row:
    tag = "ollama:" + model["tag"]
    settings = {
        "baseline": tag,
        "candidate": tag,
        "temperature": 0.7,
        "baseline_reasoning": False,
        "candidate_reasoning": False,
    }
    tasks = [
        json.loads(line) | {"quickstart_settings": settings}
        for line in (root / "agent/tasks.jsonl").read_text().splitlines()
    ]
    null = run.endswith("-null")
    condition = (
        {
            "id": "empty_result",
            "faults": [{"name": "empty_result", "tool": "lookup_order", "occurrence": 0}],
        }
        if null
        else {"id": "clean", "faults": []}
    )
    arm = {"agent": "agent:candidate", "candidate_id": tag + "+compound-raw-null"}
    return {
        "suite_id": run,
        "tasks": tasks,
        "toolset": "agent:toolset",
        "oracle": "check:check",
        "baseline": arm | {"label": "raw-null-a", "agent": "agent:baseline"},
        "candidate": arm | {"label": "raw-null-b"},
        "conditions": [condition],
        "rule": {
            "alpha": "1/20",
            "delta": "1/10",
            "stakes": ["1/4", "1/2"],
            "max_rounds": 10,
            "max_errored_pairs": 4,
            "scenario_seeds": "per_round",
        },
        "budgets": {
            "max_tool_calls": 12,
            "max_model_steps": 12,
            "max_seconds": 120,
            "grader_seconds": 20,
        },
    }
