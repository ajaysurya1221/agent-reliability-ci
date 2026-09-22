"""Deterministic Jev-shaped answers for the offline triage experiment."""

from __future__ import annotations

import random
from typing import TypeAlias, cast

from .world import JsonValue, scenario_for_seed

JsonObject: TypeAlias = dict[str, JsonValue]


def _object(value: JsonValue | None, label: str) -> JsonObject:
    if not isinstance(value, dict):
        raise TypeError(f"{label} must be an object")
    return cast(JsonObject, value)


def _choice_answer(question: JsonObject, correct: str, rng: random.Random) -> JsonObject:
    criteria = _object(question.get("criteria"), "choice criteria")
    options = sorted(criteria)
    if correct not in options or len(options) < 2:
        raise ValueError("choice fixture does not contain the correct option")
    top = (0.92, 0.93, 0.94)[rng.randrange(3)]
    other = [option for option in options if option != correct]
    weights = [rng.uniform(0.8, 1.2) for _ in other]
    remainder = 1.0 - top
    weight_total = sum(weights)
    probabilities: JsonObject = {
        option: remainder * weight / weight_total
        for option, weight in zip(other, weights, strict=True)
    }
    probabilities[correct] = top
    n = len(options)
    return {
        "type": "choice",
        "choice": correct,
        "probabilities": probabilities,
        "confidence": (n * top - 1.0) / (n - 1),
    }


def _calibration(ticket: JsonObject) -> tuple[float, float] | None:
    raw = ticket.get("calibration")
    if raw is None:
        return None
    values = _object(raw, "ticket calibration")
    share = values.get("ambiguous_share")
    confidence = values.get("confidence")
    if (
        isinstance(share, bool)
        or not isinstance(share, int | float)
        or not 0.0 <= share <= 1.0
        or isinstance(confidence, bool)
        or not isinstance(confidence, int | float)
        or not 0.0 <= confidence <= 1.0
    ):
        raise ValueError("calibration values must be numbers in [0, 1]")
    return float(share), float(confidence)


def _calibrated_choice_answer(
    question: JsonObject,
    correct: str,
    confidence: float,
    seed: int,
    occurrence: int,
) -> JsonObject:
    criteria = _object(question.get("criteria"), "choice criteria")
    options = sorted(criteria)
    if correct not in options or len(options) < 2:
        raise ValueError("choice fixture does not contain the correct option")
    rng = random.Random(f"{seed}:calibration:{occurrence}")
    winner = correct
    if rng.random() >= confidence:
        wrong = [option for option in options if option != correct]
        winner = wrong[rng.randrange(len(wrong))]
    top = (1.0 + (len(options) - 1.0) * confidence) / len(options)
    remainder = (1.0 - top) / (len(options) - 1)
    probabilities: JsonObject = {
        option: (top if option == winner else remainder) for option in options
    }
    return {
        "type": "choice",
        "choice": winner,
        "probabilities": probabilities,
        "confidence": confidence,
    }


def _noul_answer(value: bool, rng: random.Random) -> JsonObject:
    jitter = rng.uniform(-0.01, 0.01)
    probability = (0.94 if value else 0.06) + jitter
    return {"type": "noul", "noul": probability}


def _score_answer(question: JsonObject, level: int, rng: random.Random) -> JsonObject:
    criteria = question.get("criteria")
    if not isinstance(criteria, list) or not 0 <= level < len(criteria):
        raise ValueError("score fixture level is outside its criteria")
    top = (0.88, 0.89, 0.90)[rng.randrange(3)]
    other = [index for index in range(len(criteria)) if index != level]
    remainder = 1.0 - top
    share = remainder / len(other)
    numeric_probabilities = {
        str(index): (top if index == level else share) for index in range(len(criteria))
    }
    score = sum(int(index) * probability for index, probability in numeric_probabilities.items())
    probabilities: JsonObject = dict(numeric_probabilities)
    return {
        "type": "score",
        "score": score,
        "legend": {str(index): criteria[index] for index in range(len(criteria))},
        "probabilities": probabilities,
        "confidence": (len(criteria) * top - 1.0) / (len(criteria) - 1),
    }


def fixture(request: JsonObject, seed: int, occurrence: int) -> JsonObject:
    """Return confident, correct answers in the System One response wire shape."""
    scenario = scenario_for_seed(seed)
    questions = _object(request.get("questions"), "questions")
    state = _object(request.get("state"), "state")
    ticket = _object(state.get("ticket"), "state.ticket")
    if ticket.get("ticket_id") != scenario.ticket_id:
        raise ValueError("decision request contains the wrong seeded ticket")
    rng = random.Random(f"{seed}:decision:{occurrence}")
    calibration = _calibration(ticket)
    ambiguous = (
        calibration is not None
        and random.Random(f"{seed}:calibration:ambiguous").random() < calibration[0]
    )
    truth: dict[str, str | bool | int] = {
        "department": scenario.department,
        "refund_requested": scenario.refund_requested,
        "policy_supports": scenario.policy_supports,
        "frustration": scenario.frustration,
    }
    answers: JsonObject = {}
    for name, raw_question in questions.items():
        question = _object(raw_question, f"question {name}")
        kind = question.get("type")
        value = truth.get(name)
        if kind == "choice" and isinstance(value, str):
            if ambiguous and calibration is not None:
                answers[name] = _calibrated_choice_answer(
                    question, value, calibration[1], seed, occurrence
                )
            else:
                answers[name] = _choice_answer(question, value, rng)
        elif kind == "noul" and isinstance(value, bool):
            answers[name] = _noul_answer(value, rng)
        elif kind == "score" and isinstance(value, int) and not isinstance(value, bool):
            answers[name] = _score_answer(question, value, rng)
        else:
            raise ValueError(f"unsupported triage question {name!r}")
    model = request.get("model")
    if not isinstance(model, str):
        raise TypeError("model must be a string")
    return {
        "model": model,
        "answers": answers,
        "usage": {"input_tokens": 96 + rng.randrange(8), "output_tokens": 0},
    }
