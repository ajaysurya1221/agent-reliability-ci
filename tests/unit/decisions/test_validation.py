from __future__ import annotations

import copy
import math
from collections.abc import Callable
from typing import Any, cast

import pytest
from pydantic import JsonValue

import arci.mcp_boundary as boundary_module

request_error = vars(boundary_module)["_decision_request_error"]
validate_response = vars(boundary_module)["_validate_decision_response"]
allowed_headers = vars(boundary_module)["_allowed_headers"]

MODEL = "jev-1.13.0"


def _request() -> dict[str, JsonValue]:
    return {
        "state": {"ticket": "example"},
        "model": "jev-latest",
        "questions": {
            "route": {
                "type": "choice",
                "criteria": {"billing": "Billing", "support": "Support"},
            },
            "safe": {"type": "noul"},
            "urgency": {"type": "score", "criteria": ["Low", "High"]},
        },
        "extra": {"forward": True},
    }


def _response() -> dict[str, JsonValue]:
    return cast(
        dict[str, JsonValue],
        {
            "model": MODEL,
            "answers": {
                "route": {
                    "type": "choice",
                    "choice": "billing",
                    "probabilities": {"billing": 0.7, "support": 0.3},
                    "confidence": 0.4,
                },
                "safe": {"type": "noul", "noul": 0.8},
                "urgency": {
                    "type": "score",
                    "score": 0.75,
                    "legend": {"0": "Low", "1": "High"},
                    "probabilities": {"0": 0.25, "1": 0.75},
                    "confidence": 0.5,
                },
            },
            "usage": {"input_tokens": 12, "output_tokens": 0},
        },
    )


def test_request_validation_accepts_extra_keys_and_all_question_types() -> None:
    assert request_error(_request()) is None


@pytest.mark.parametrize(
    "update,loc",
    [
        ([], ["body"]),
        ({"state": None}, ["body", "state"]),
        ({"model": 7}, ["body", "model"]),
        ({"questions": {}}, ["body", "questions"]),
        (
            {"questions": {"q": {"type": "other"}}},
            ["body", "questions", "q", "type"],
        ),
        (
            {"questions": {"q": {"type": "choice", "criteria": {}}}},
            ["body", "questions", "q", "criteria"],
        ),
        (
            {"questions": {"q": {"type": "score", "criteria": ["one"]}}},
            ["body", "questions", "q", "criteria"],
        ),
        (
            {"questions": {"q": {"type": "noul", "criteria": {"true": "yes"}}}},
            ["body", "questions", "q", "criteria"],
        ),
    ],
)
def test_request_validation_returns_a_stable_422_location(update: object, loc: list[str]) -> None:
    if isinstance(update, dict):
        value: object = {**_request(), **cast(dict[str, Any], update)}
    else:
        value = update
    error = request_error(value)
    assert error is not None
    assert cast(dict[str, Any], cast(list[Any], error["detail"])[0])["loc"] == loc


def test_response_validation_accepts_tied_winners_and_returns_an_independent_copy() -> None:
    response = _response()
    answers = cast(dict[str, Any], response["answers"])
    route = cast(dict[str, Any], answers["route"])
    route["probabilities"] = {"billing": 0.5, "support": 0.5}

    validated = validate_response(response, _request(), MODEL)
    cast(dict[str, Any], validated["answers"])["safe"]["noul"] = 0.1

    assert cast(dict[str, Any], response["answers"])["safe"]["noul"] == 0.8


def _wrong_model(body: dict[str, JsonValue]) -> None:
    body["model"] = "wrong"


def _missing_answer(body: dict[str, JsonValue]) -> None:
    cast(dict[str, Any], body["answers"]).pop("safe")


def _boolean_usage(body: dict[str, JsonValue]) -> None:
    cast(dict[str, Any], body["usage"])["input_tokens"] = True


def _bad_sum(body: dict[str, JsonValue]) -> None:
    cast(dict[str, Any], cast(dict[str, Any], body["answers"])["route"])["probabilities"] = {
        "billing": 0.8,
        "support": 0.8,
    }


def _not_maximal(body: dict[str, JsonValue]) -> None:
    cast(dict[str, Any], cast(dict[str, Any], body["answers"])["route"])["choice"] = "support"


def _infinite_noul(body: dict[str, JsonValue]) -> None:
    cast(dict[str, Any], cast(dict[str, Any], body["answers"])["safe"])["noul"] = math.inf


def _bad_legend(body: dict[str, JsonValue]) -> None:
    cast(dict[str, Any], cast(dict[str, Any], body["answers"])["urgency"])["legend"] = {"0": "Low"}


@pytest.mark.parametrize(
    "mutate",
    [
        _wrong_model,
        _missing_answer,
        _boolean_usage,
        _bad_sum,
        _not_maximal,
        _infinite_noul,
        _bad_legend,
    ],
)
def test_response_validation_rejects_invalid_provider_shapes(
    mutate: Callable[[dict[str, JsonValue]], None],
) -> None:
    response = copy.deepcopy(_response())
    mutate(response)
    with pytest.raises((TypeError, ValueError)):
        validate_response(response, _request(), MODEL)


def test_only_retry_after_is_forwarded() -> None:
    assert allowed_headers(
        {"Retry-After": "3", "X-Request-ID": "secret", "Authorization": "Bearer key"}
    ) == {"retry-after": "3"}
    with pytest.raises(ValueError, match="invalid header"):
        allowed_headers({"Retry-After": "3\r\nX-Leak: secret"})
