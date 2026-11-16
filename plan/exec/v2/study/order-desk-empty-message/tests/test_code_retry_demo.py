"""A code retry records two lookups during a single model-requested tool call."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from langchain_core.messages import ToolMessage

from arci.adapters.langchain import make_adapter

sys.path.insert(0, str(Path(__file__).resolve().parent))

from code_retry_demo import RetryEmptyLookupOnce
from test_end_to_end import (
    agent,
    model_inputs,
    observed_settings,
    read_trials,
    run_proof,
)


def retry_settings() -> dict[str, Any]:
    result = observed_settings(True)
    result["middleware"].append(RetryEmptyLookupOnce())
    return result


toolset, baseline, candidate = make_adapter(
    agent.registered_tools,
    retry_settings,
    retry_settings,
    fault_exceptions={"timeout": TimeoutError, "error": RuntimeError},
)


def test_code_retry_returns_second_result_without_recursing() -> None:
    first = ToolMessage(content=" \nnull\t", tool_call_id="first", name="lookup_order")
    second = ToolMessage(content="null", tool_call_id="second", name="lookup_order")
    cases: list[tuple[str, object, int]] = [
        ("lookup_order", first, 2),
        ("check_stock", first, 1),
        ("lookup_order", object(), 1),
        ("lookup_order", ToolMessage(content="null", status="error", tool_call_id="e"), 1),
        ("lookup_order", ToolMessage(content='{"sku": "SKU-1"}', tool_call_id="o"), 1),
    ]
    for tool, initial, expected_calls in cases:
        request = SimpleNamespace(tool_call={"name": tool})
        requests: list[object] = []

        def handler(
            received: object, requests: list[object] = requests, initial: object = initial
        ) -> object:
            requests.append(received)
            return initial if len(requests) == 1 else second

        result = RetryEmptyLookupOnce().wrap_tool_call(request, handler)
        assert requests == [request] * expected_calls
        assert result is (second if expected_calls == 2 else initial)


def test_code_retry_is_recorded_without_an_intervening_model_step() -> None:
    output = run_proof("test_code_retry_demo", all_tasks=False)
    trials = read_trials(output)
    assert len(trials) == 2
    for directory, trial in trials:
        lookups = [call for call in trial.recording if call.tool == "lookup_order"]
        assert len(lookups) == 2
        first, second = lookups
        assert first.occurrence == 0 and first.result.ok
        assert first.result.injected_by == "empty_result" and first.result.value is None
        assert second.occurrence == 1 and second.result.ok
        assert second.result.injected_by is None and isinstance(second.result.value, dict)
        assert first.arguments_sha256 == second.arguments_sha256
        starts = [
            event.seq
            for event in trial.events
            if event.kind == "tool_start" and event.payload.get("tool") == "lookup_order"
        ]
        assert len(starts) == 2
        between = [event for event in trial.events if starts[0] < event.seq < starts[1]]
        assert [event.kind for event in between] == ["tool_finish"]
        assert between[0].payload.get("injected_by") == "empty_result"
        inputs = model_inputs(directory, trial.arm)
        assert len(inputs) == trial.usage.model_steps == 4
        observed = [message for message in inputs[1] if message["type"] == "tool"]
        assert len(observed) == 1
        assert observed[0]["name"] == "lookup_order"
        assert observed[0]["status"] == "success"
        assert json.loads(observed[0]["content"]) == second.result.value
        assert "sku" in second.result.value
        assert not (directory / f"{trial.arm}-audit.jsonl").exists()
    (output / "summary.json").write_text(
        json.dumps(
            {
                "kind": "offline code-retry demonstration; not used by study agent",
                "trials": 2,
                "lookups_per_trial": 2,
                "model_steps_between_lookups": 0,
                "model_receives_order": True,
            },
            indent=2,
        )
        + "\n"
    )
    print(f"2 offline trials verified; code retry delivers the order; stores: {output}")


def main() -> None:
    test_code_retry_returns_second_result_without_recursing()
    test_code_retry_is_recorded_without_an_intervening_model_step()
    print("2 code-retry tests passed")


if __name__ == "__main__":
    main()
