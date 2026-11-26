"""Board file formats and fixed design."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
Row = dict[str, Any]
OLLAMA = "0.32.14"
SIDES = ("baseline", "candidate")
LABELS = ("stock-sentence", "empty-as-given")
REG = "PREREGISTRATION-board-0.draft.md"
LIST = "board0-digests.sha256"
NOTE = "descriptor-digests.sha256"
EXPORTS = (
    "descriptor.yaml",
    "manifest.json",
    "trials.jsonl",
    "events.jsonl",
    "decision.json",
    "ledger.jsonl",
    "receipts.jsonl",
    "audit.json",
    "count_a.json",
    "count_b.json",
    "run.log",
)
RULE = {
    "alpha": "1/20",
    "delta": "1/10",
    "stakes": ["1/4", "1/2"],
    "scenario_seeds": "per_round",
    "max_rounds": 26,
    "max_errored_pairs": 4,
}


def need(ok: object, message: str) -> None:
    if not ok:
        raise ValueError(message)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read(path: Path) -> Any:
    return json.loads(path.read_bytes())


def lines(path: Path) -> list[Row]:
    return [json.loads(line) for line in path.read_bytes().splitlines()]


def dump(value: object) -> bytes:
    return (
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    ).encode()


def write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = dump(value)
    if path.is_file():
        need(path.read_bytes() == data, f"conflicting {path.name}")
    else:
        with path.open("xb") as f:
            f.write(data)


SPARES = ("S1", "S2")


def pin_name(slot: str) -> str:
    return f"board0-pin2-{slot}"


def registry(path: Path, *, offline: bool = False) -> Row:
    config = read(path)
    need(
        isinstance(config, dict)
        and set(config) == {"ollama", "slots", "spares"}
        and config["ollama"] == OLLAMA,
        "registered Ollama version",
    )
    slots, spares = config["slots"], config["spares"]
    size = 2 if offline else 5
    need(isinstance(slots, list) and len(slots) == size, f"expected {size} model slots")
    need(isinstance(spares, list) and len(spares) == 2, "expected two spares")
    fields = {"slot", "tag", "digest", "family", "size", "pin"}
    ids = [*(f"M{i + 1}" for i in range(size)), *SPARES]
    for slot, row in zip(ids, [*slots, *spares], strict=True):
        need(
            isinstance(row, dict)
            and fields <= row.keys() <= fields | ({"vacant"} if slot.startswith("M") else set())
            and isinstance(row.get("vacant", False), bool)
            and all(isinstance(row[k], str) and row[k].strip() == row[k] and row[k] for k in fields)
            and row["slot"] == slot
            and re.fullmatch(r"[a-zA-Z0-9][\w./:-]*", row["tag"])
            and re.fullmatch("[a-f0-9]{64}", row["digest"]),
            f"invalid model {slot}",
        )
    for row in spares:
        need(row["pin"] == pin_name(row["slot"]), f"invalid spare pin {row['slot']}")
    originals = []
    for row in slots:
        if row["pin"] == pin_name(row["slot"]):
            originals.append(row)
        else:
            need(
                any(row == spare | {"slot": row["slot"]} for spare in spares),
                f"invalid substitute for {row['slot']}",
            )
    registered = originals + spares
    for field in ("tag", "digest"):
        need(len({m[field] for m in registered}) == len(registered), f"duplicate model {field}")
        need(len({m[field] for m in slots}) == size, f"duplicate slot {field}")
    return config


def models(path: Path, *, offline: bool = False) -> list[Row]:
    return registry(path, offline=offline)["slots"]


def schedule(slots: list[Row]) -> list[str]:
    names = [s["slot"] for s in slots]
    return [pin_name(s) for s in [*names, *SPARES]] + [
        f"board0-d{d}-{s}-{phase}"
        for d, order in [(1, names), (2, list(reversed(names)))]
        for s in order
        for phase in ("clean", "E")
    ]


def descriptor(doc: Row, model: Row, run: str, *, offline: bool, task_id: str | None = None) -> Row:
    clean = run.endswith("-clean")
    cfg: Row = {
        "suite_id": run,
        "tasks": [
            {
                "id": r["id"],
                "key_id": r["id"],
                **{k: r[k] for k in ("family", "ask", "opening", "task")},
            }
            for r in doc["tasks"]
        ],
        "conditions": [
            {
                "id": "E",
                **(
                    {}
                    if clean
                    else {
                        "faults": [
                            {"name": "empty_result", "tool": name, "occurrence": 0}
                            for name in sorted({r["opening"]["name"] for r in doc["tasks"]})
                        ]
                    }
                ),
            }
        ],
        "rule": RULE.copy(),
        "budgets": {"max_tool_calls": 12, "max_seconds": 120, "grader_seconds": 20},
        "oracle": "board_oracle:passed",
        "mcp_server": {
            "name": "env",
            "argv": ["python", "-P", "-m", "board_relay"],
            "snapshot": "board_oracle:snapshot",
        },
    }
    for side, label in zip(SIDES, LABELS, strict=True):
        label = "clean" if clean else label
        cfg[side] = {
            "label": label,
            "command": {
                "argv": [
                    "python",
                    "-P",
                    "-m",
                    "agent",
                    "--task-file",
                    "{task_file}",
                    "--mcp-config",
                    "{mcp_config}",
                    "--arm",
                    label,
                    "--model",
                    model["tag"],
                    "--run-id",
                    run,
                    *(["--offline"] if offline else []),
                ],
                "infra_exit_codes": [70, 75],
                "env": {"BOARD0_ARCI_ARM": side},
            },
        }
    if clean:
        row = next(r for r in cfg.pop("tasks") if r["id"] == task_id)
        cfg.pop("suite_id")
        cfg.pop("rule")
        cfg.update(
            experiment_id=run + "-" + str(task_id),
            task_id=row.pop("id"),
            task=row,
            n_per_arm=1,
            base_seed=int(sha((run + "/" + str(task_id)).encode())[:12], 16),
        )
    return cfg


def check_deadline(trial: Row, receipt: Row) -> None:
    for event in trial["events"]:
        if event["kind"] in ("tool_start", "tool_finish"):
            need(0 <= event["at_ms"] <= 120_000, "tool deadline")
    if trial["termination"] == "completed":
        need(0 <= receipt["agent_seconds"] <= 120, "agent deadline")


def require_infra(trial: Row, receipt: Row, exchange: Row) -> None:
    need(
        exchange is receipt["exchanges"][-1]
        and not receipt["complete"]
        and trial["outcome"] == "ERROR"
        and trial["termination"] == "harness_error"
        and receipt.get("agent_exit") == 75
        and trial["agent_claimed_success"] is False
        and trial["failure_detail"] == "agent reported an infrastructure failure (exit <n>)",
        "backend failure differs from recorded exit",
    )


def assistant(raw: bytes, tag: str) -> Row:
    response = json.loads(raw)
    json.dumps(response, ensure_ascii=False, allow_nan=False).encode("utf-8")
    need(
        isinstance(response, dict)
        and response.get("model") == tag
        and response.get("done") is True
        and response.get("done_reason") != "length",
        "model or done",
    )
    msg = response.get("message")
    if not isinstance(msg, dict) or msg.get("role") != "assistant":
        raise ValueError("response role")
    calls = msg.get("tool_calls", [])
    need(
        isinstance(calls, list) and (calls or isinstance(msg.get("content"), str)),
        "assistant content",
    )
    return msg


def function(wrapper: object) -> Row:
    fn = wrapper.get("function") if isinstance(wrapper, dict) else None
    if not isinstance(fn, dict):
        raise ValueError("assistant tool call")
    need(
        isinstance(fn.get("name"), str) and isinstance(fn.get("arguments", {}), dict),
        "assistant tool call",
    )
    return fn
