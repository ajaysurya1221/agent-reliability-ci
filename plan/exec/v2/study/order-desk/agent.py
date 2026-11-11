"""Swap the two model ids to compare real agents with identical inference settings."""

from __future__ import annotations

from typing import Any

from configuration import resolve_settings, validate_registration
from langchain.agents.middleware import ToolRetryMiddleware
from langchain.chat_models import init_chat_model
from offline_model import OfflineModel
from pydantic import JsonValue
from tools import make_tools

from arci.adapters.langchain import ToolEnv, make_adapter


def settings(candidate: bool) -> dict[str, Any]:
    registered = resolve_settings()
    arm = "candidate" if candidate else "baseline"
    model_id = str(registered[arm])
    # Keep inference settings identical. Ollama's optional reasoning mode is disabled
    # for both arms; other providers keep their default reasoning mode in both arms.
    inference: dict[str, Any] = {"temperature": registered["temperature"]}
    if registered[f"{arm}_reasoning"] is False:
        inference["reasoning"] = False
    model = (
        init_chat_model(model_id, **inference)
        if model_id != "offline:scripted"
        else OfflineModel(responses=[])
    )
    # Baseline retries a transient read failure inside the recorded tool boundary.
    # Candidate removes that retry: clean tests pass, injected exceptions expose it.
    retry = ToolRetryMiddleware(
        max_retries=1,  # study: identical in both arms; only the model differs
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
            "Only add a note when the task asks for one. For refund notes write exactly "
            "'refunded'. A plain refund needs no note. Retry an empty lookup once."
        ),
    }


def baseline_settings() -> dict[str, Any]:
    return settings(False)


def candidate_settings() -> dict[str, Any]:
    return settings(True)


def registered_tools(task: dict[str, JsonValue], seed: int) -> ToolEnv:
    registered = validate_registration(task)
    if registered["baseline"] == "offline:scripted":
        OfflineModel.validate_prompt(task.get("input"))
    return make_tools(task, seed)


toolset, baseline, candidate = make_adapter(
    registered_tools,
    baseline_settings,
    candidate_settings,
    # Keys are fault kinds, not perturbation names such as 'tool_timeout'.
    fault_exceptions={"timeout": TimeoutError, "error": RuntimeError},
)
