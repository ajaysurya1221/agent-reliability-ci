"""Deterministic answers for the offline experiment: what the live model said.

`answers.jsonl` holds two passes of `jev-1.13.0` over the command set (frontier-scout,
`docs/evaluation/decision-model/`, 2026-10-03). The fixture answers each command with its
pass-1 record in the System One wire shape, so the offline experiment replays the live model's
answers instead of an invented oracle. The Choice probabilities are reconstructed from the
recorded confidence through the API's own definition, `confidence = (p_max - 1/n) / (1 - 1/n)`,
with the remainder spread evenly; that is what `decision_low_confidence` acts on.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TypeAlias, cast

from .world import BY_ID, RISK_LABELS, JsonValue

JsonObject: TypeAlias = dict[str, JsonValue]

HERE = Path(__file__).resolve().parent
ANSWERS_FILE = HERE / "answers.jsonl"


def _object(value: JsonValue | None, label: str) -> JsonObject:
    if not isinstance(value, dict):
        raise TypeError(f"{label} must be an object")
    return cast(JsonObject, value)


def _number(value: JsonValue | None, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise TypeError(f"{label} must be a number")
    return float(value)


def _load_recorded() -> dict[str, JsonObject]:
    recorded: dict[str, JsonObject] = {}
    for line in ANSWERS_FILE.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        raw = _object(cast(JsonValue, json.loads(line)), "answer record")
        if raw.get("pass") != 1 or "effect" not in raw:
            continue
        ident = raw.get("id")
        labelled = BY_ID.get(ident) if isinstance(ident, str) else None
        if labelled is None:
            raise ValueError("answer record names a command outside the labelled set")
        recorded[labelled.command] = raw
    return recorded


RECORDED: dict[str, JsonObject] = _load_recorded()


def fixture(request: JsonObject, seed: int, occurrence: int) -> JsonObject:
    """Return the recorded pass-1 answer for the command in the request state."""
    del seed, occurrence
    state = _object(request.get("state"), "state")
    command = state.get("command")
    if not isinstance(command, str):
        raise TypeError("state.command must be a string")
    record = RECORDED.get(command)
    if record is None:
        raise ValueError("no recorded answer for this command")
    questions = _object(request.get("questions"), "questions")
    criteria = _object(
        _object(questions.get("effect"), "effect question").get("criteria"), "effect criteria"
    )
    options = sorted(criteria)
    effect = _object(record.get("effect"), "recorded effect")
    choice = effect.get("choice")
    if not isinstance(choice, str) or choice not in criteria or len(options) < 2:
        raise ValueError("recorded effect is not one of the offered options")
    confidence = _number(effect.get("confidence"), "recorded confidence")
    count = len(options)
    top = (1.0 + (count - 1.0) * confidence) / count
    rest = (1.0 - top) / (count - 1)
    probabilities: JsonObject = {option: (top if option == choice else rest) for option in options}
    answers: JsonObject = {
        "effect": {
            "type": "choice",
            "choice": choice,
            "probabilities": probabilities,
            "confidence": confidence,
        }
    }
    for name in RISK_LABELS:
        answers[name] = {"type": "noul", "noul": _number(record.get(name), name)}
    model = request.get("model")
    if not isinstance(model, str):
        raise TypeError("model must be a string")
    usage = _object(record.get("usage"), "recorded usage")
    return {
        "model": model,
        "answers": answers,
        "usage": {
            "input_tokens": int(_number(usage.get("input_tokens"), "input_tokens")),
            "output_tokens": int(_number(usage.get("output_tokens"), "output_tokens")),
        },
    }
