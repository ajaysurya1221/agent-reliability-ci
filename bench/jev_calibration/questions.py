"""The questions of the audit. These strings are the protocol; PROTOCOL.md describes them."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TypeAlias

from bench.jev_calibration.data import BANKING, CLINC

JsonValue: TypeAlias = dict[str, "JsonValue"] | list["JsonValue"] | str | int | float | bool | None
Question: TypeAlias = dict[str, JsonValue]

MODEL = "jev-1.13.0"
BASE_URL = "https://api.typesafe.ai"

CLOSED_ID = "intent_closed"
OPEN_ID = "intent_open"
NOUL_ID = "is_oos"
OOS_OPTION = "out_of_scope"

INSTRUCTION_CLOSED = "Which one of the listed intents does this request express?"
INSTRUCTION_OPEN = f"{INSTRUCTION_CLOSED} Pick {OOS_OPTION} if none of the listed intents fits."
OOS_DESCRIPTION = "the request is not about any of the other listed intents"
NOUL_QUESTION = (
    "Is this request about none of the `intents`? Answer yes only if no listed intent fits."
)
NOUL_CRITERIA: dict[str, JsonValue] = {
    "true": "no listed intent fits the request",
    "false": "at least one listed intent fits the request",
}


def describe(intent: str) -> str:
    """The one-phrase description of an intent: its name with the underscores removed."""
    return intent.replace("_", " ")


def choice_criteria(intents: Sequence[str]) -> dict[str, JsonValue]:
    return {intent: describe(intent) for intent in intents}


def closed_question(intents: Sequence[str]) -> Question:
    return {
        "type": "choice",
        "instructions": INSTRUCTION_CLOSED,
        "criteria": choice_criteria(intents),
    }


def open_question(intents: Sequence[str]) -> Question:
    criteria = choice_criteria(intents)
    criteria[OOS_OPTION] = OOS_DESCRIPTION
    return {"type": "choice", "instructions": INSTRUCTION_OPEN, "criteria": criteria}


def noul_question(intents: Sequence[str]) -> Question:
    instructions: dict[str, JsonValue] = {"intents": list(intents), "question": NOUL_QUESTION}
    return {"type": "noul", "instructions": instructions, "criteria": dict(NOUL_CRITERIA)}


def bundled_questions(dataset: str, intents: Sequence[str]) -> dict[str, Question]:
    """The questions one audit request carries: three for CLINC150, one for Banking77."""
    if dataset == CLINC:
        return {
            CLOSED_ID: closed_question(intents),
            OPEN_ID: open_question(intents),
            NOUL_ID: noul_question(intents),
        }
    if dataset == BANKING:
        return {CLOSED_ID: closed_question(intents)}
    raise ValueError(f"no questions defined for dataset {dataset!r}")


def closed_only_questions(intents: Sequence[str]) -> dict[str, Question]:
    """The independence check: the closed question on its own."""
    return {CLOSED_ID: closed_question(intents)}
