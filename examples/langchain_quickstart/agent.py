"""Swap the two model ids to compare real agents with identical inference settings."""

from __future__ import annotations

import os
from typing import Any

from langchain.agents.middleware import ToolRetryMiddleware
from langchain.chat_models import init_chat_model
from offline_model import OfflineModel
from tools import make_tools

from arci.adapters.langchain import make_adapter


def settings(candidate: bool) -> dict[str, Any]:
    variable = "ARCI_QUICKSTART_CANDIDATE" if candidate else "ARCI_QUICKSTART_BASELINE"
    model_id = os.environ.get(variable)
    # Keep inference settings identical. Ollama's optional reasoning mode is disabled
    # for both arms; other providers keep their default reasoning mode in both arms.
    inference: dict[str, Any] = {"temperature": 0}
    if model_id and model_id.startswith("ollama:"):
        inference["reasoning"] = False
    model = (
        init_chat_model(model_id, **inference)
        if model_id
        else OfflineModel(responses=[], candidate=candidate)
    )
    # Baseline retries a transient read failure inside the recorded tool boundary.
    # Candidate removes that retry: clean tests pass, injected exceptions expose it.
    retry = ToolRetryMiddleware(
        max_retries=0 if candidate else 1,
        initial_delay=0,
        jitter=False,
        retry_on=(TimeoutError, RuntimeError),
        on_failure="continue",
    )
    return {
        "model": model,
        "middleware": [retry],
        "system_prompt": (
            "Use the order desk tools. Read the order first. Refund exactly its total_cents. "
            "For stock notes, read its SKU stock and write exactly 'stock: N'. "
            "For refund notes write exactly 'refunded'. Retry an empty lookup once."
        ),
    }


def baseline_settings() -> dict[str, Any]:
    return settings(False)


def candidate_settings() -> dict[str, Any]:
    return settings(True)


toolset, baseline, candidate = make_adapter(
    make_tools,
    baseline_settings,
    candidate_settings,
    # Keys are fault kinds, not perturbation names such as 'tool_timeout'.
    fault_exceptions={"timeout": TimeoutError, "error": RuntimeError},
)
