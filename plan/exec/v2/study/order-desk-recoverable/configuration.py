"""Resolve public inference settings, also stored in each sealed suite task."""

from __future__ import annotations

import math
import os

from pydantic import JsonValue


def resolve_settings() -> dict[str, JsonValue]:
    baseline = os.environ.get("ARCI_QUICKSTART_BASELINE")
    candidate = os.environ.get("ARCI_QUICKSTART_CANDIDATE")
    if (baseline is None) != (candidate is None):
        raise ValueError(
            "set both ARCI_QUICKSTART_BASELINE and ARCI_QUICKSTART_CANDIDATE, or neither"
        )
    real = baseline is not None
    if real and any(
        not value or ":" not in value or value == "offline:scripted" or value.strip() != value
        for value in (baseline, candidate)
    ):
        raise ValueError("both model ids must be nonempty provider:model identifiers")
    temperature = float(os.environ.get("ARCI_QUICKSTART_TEMPERATURE", "0.7" if real else "0"))
    if (
        not math.isfinite(temperature)
        or (real and temperature <= 0)
        or (not real and temperature != 0)
    ):
        raise ValueError(
            "temperature must be finite and above 0 for real models, exactly 0 offline"
        )
    return {
        "baseline": baseline or "offline:scripted",
        "candidate": candidate or "offline:scripted",
        "temperature": temperature,
        "baseline_reasoning": False
        if baseline and baseline.startswith("ollama:")
        else "provider_default"
        if real
        else "not_applicable",
        "candidate_reasoning": False
        if candidate and candidate.startswith("ollama:")
        else "provider_default"
        if real
        else "not_applicable",
    }


def validate_registration(task: dict[str, JsonValue]) -> dict[str, JsonValue]:
    settings = resolve_settings()
    if task.get("quickstart_settings") != settings:
        raise ValueError(
            "quickstart environment disagrees with registered settings; "
            "run python register.py before starting a new experiment"
        )
    return settings
