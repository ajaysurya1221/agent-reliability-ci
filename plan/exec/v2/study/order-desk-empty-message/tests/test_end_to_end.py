"""Offline integration proof using real ARCI workers, injection, adapter and stores.

The scripted policy records its actual input before interpreting it. These trials
prove plumbing only: they are not the registered suite or evidence of model benefit.
Run directly with the supplied run3-env Python; pytest is optional.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from tempfile import mkdtemp
from typing import Any
from unittest.mock import patch

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import JsonValue

from arci.adapters.langchain import make_adapter
from arci.runner import run_trial
from arci.schedule import build_schedule
from arci.schema import (
    ArmSpec,
    Bucket,
    Budgets,
    Condition,
    ContractSpec,
    FaultSpec,
    Manifest,
    Outcome,
    TrialEnvelope,
)
from arci.storage import ExperimentStore

STUDY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(STUDY))

import agent  # noqa: E402 -- also importable in the isolated ARCI worker.
from configuration import resolve_settings  # noqa: E402
from offline_model import OfflineModel  # noqa: E402


class ObservingModel(OfflineModel):
    """A deterministic stock-note policy, explicitly handling either empty message."""

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        with Path(os.environ["ORDER_DESK_TEST_MESSAGES"]).open("a", encoding="utf-8") as stream:
            stream.write(json.dumps([m.model_dump(mode="json") for m in messages]) + "\n")
        prompt = self.validate_prompt(next(m.text for m in messages if isinstance(m, HumanMessage)))
        match = re.search(r"ORD-\d+", prompt)
        assert match is not None
        order_id = match.group()
        replies = [m for m in messages if isinstance(m, ToolMessage)]
        latest = replies[-1] if replies else None
        arguments: dict[str, Any]
        if latest is None or (
            latest.name == "lookup_order" and latest.text in ("null", agent.EMPTY_LOOKUP_TEXT)
        ):
            name, arguments = "lookup_order", {"order_id": order_id}
        elif latest.name == "lookup_order":
            order = json.loads(latest.text)
            assert isinstance(order, dict)
            name, arguments = "check_stock", {"sku": order["sku"]}
        elif latest.name == "check_stock":
            stock = json.loads(latest.text)
            assert isinstance(stock, int)
            name, arguments = "add_note", {"order_id": order_id, "note": f"stock: {stock}"}
        else:
            assert latest.name == "add_note"
            return ChatResult(generations=[ChatGeneration(message=AIMessage(content="Done"))])
        response = AIMessage(
            content="",
            tool_calls=[{"name": name, "args": arguments, "id": f"call-{len(replies)}"}],
        )
        return ChatResult(generations=[ChatGeneration(message=response)])


def observed_settings(candidate: bool) -> dict[str, Any]:
    # Refuse real model configuration before settings() can construct a provider.
    registered = resolve_settings()
    assert registered["baseline"] == registered["candidate"] == "offline:scripted"
    result = agent.settings(candidate)
    result["model"] = ObservingModel(responses=[])
    return result


def baseline_settings() -> dict[str, Any]:
    return observed_settings(False)


def candidate_settings() -> dict[str, Any]:
    return observed_settings(True)


toolset, baseline, candidate = make_adapter(
    agent.registered_tools,
    baseline_settings,
    candidate_settings,
    fault_exceptions={"timeout": TimeoutError, "error": RuntimeError},
)


def run_proof(module: str, *, all_tasks: bool) -> Path:
    """Keep real worker envelopes, events and model observations for every proof run."""
    parent = STUDY / "_offline"
    parent.mkdir(exist_ok=True)
    output = Path(mkdtemp(prefix=f"{module}-", dir=parent))
    tasks: list[dict[str, JsonValue]] = [
        json.loads(line) for line in (STUDY / "tasks.jsonl").read_text().splitlines()
    ]
    if not all_tasks:
        tasks = tasks[:1]
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("ARCI_QUICKSTART_")
        and not key.startswith("LANGCHAIN_")
        and not key.startswith("LANGSMITH_")
    }
    environment.update(
        PYTHONDONTWRITEBYTECODE="1", LANGCHAIN_TRACING_V2="false", LANGSMITH_TRACING="false"
    )
    with patch.dict(os.environ, environment, clear=True):
        for task in tasks:
            task["quickstart_settings"] = resolve_settings()
            manifest = Manifest.create(
                experiment_id=f"offline-plumbing-{task['id']}",
                task_id=str(task["id"]),
                task=task,
                toolset=f"{module}:toolset",
                baseline=ArmSpec(label="baseline", agent=f"{module}:baseline"),
                candidate=ArmSpec(label="candidate", agent=f"{module}:candidate"),
                contract=ContractSpec(oracle="check:check"),
                conditions=(
                    Condition(
                        condition_id="empty_result",
                        faults=(
                            FaultSpec(
                                name="empty_result",
                                bucket=Bucket.FALSIFY,
                                tool="lookup_order",
                                at_occurrence=0,
                            ),
                        ),
                    ),
                ),
                n_per_arm=1,
                budgets=Budgets(
                    max_tool_calls=12, max_model_steps=12, max_seconds=120, grader_seconds=20
                ),
            )
            store = ExperimentStore(output, manifest)
            for spec in build_schedule(manifest):
                audit = store.run_dir / f"{spec.arm}-audit.jsonl"
                messages = store.run_dir / f"{spec.arm}-messages.jsonl"
                with patch.dict(
                    os.environ,
                    {
                        "ORDER_DESK_EMPTY_TEXT_AUDIT": str(audit),
                        "ORDER_DESK_TEST_MESSAGES": str(messages),
                    },
                ):
                    trial = run_trial(
                        spec,
                        store.append_event,
                        manifest.contract,
                        extra_pythonpath=(str(STUDY / "tests"), str(STUDY)),
                    )
                store.append_trial(trial)
                assert trial.outcome == Outcome.PASS, (
                    trial.termination,
                    trial.failure_detail,
                    store.run_dir,
                )
    return output


def read_trials(output: Path) -> list[tuple[Path, TrialEnvelope]]:
    result: list[tuple[Path, TrialEnvelope]] = []
    for path in sorted(output.glob("*/trials.jsonl")):
        for line in path.read_text().splitlines():
            trial = TrialEnvelope.model_validate_json(line)
            assert trial.validate_seal()
            result.append((path.parent, trial))
    return result


def model_inputs(directory: Path, arm: str) -> list[list[dict[str, Any]]]:
    return [
        json.loads(line) for line in (directory / f"{arm}-messages.jsonl").read_text().splitlines()
    ]


def test_injected_empty_lookup_reaches_model_and_remains_recorded() -> None:
    output = run_proof("test_end_to_end", all_tasks=True)
    trials = read_trials(output)
    assert len(trials) == 16
    audits = 0
    for directory, trial in trials:
        lookups = [call for call in trial.recording if call.tool == "lookup_order"]
        assert len(lookups) == 2
        first, second = lookups
        assert first.occurrence == 0 and first.result.ok
        assert first.result.injected_by == "empty_result" and first.result.value is None
        assert second.occurrence == 1 and second.result.injected_by is None
        assert isinstance(second.result.value, dict) and "sku" in second.result.value
        assert first.arguments_sha256 == second.arguments_sha256
        assert any(
            event.kind == "tool_finish" and event.payload.get("injected_by") == "empty_result"
            for event in trial.events
        )
        inputs = model_inputs(directory, trial.arm)
        assert len(inputs) == trial.usage.model_steps == 5
        # This is the first model invocation AFTER the first recorded tool call.
        observed = [message for message in inputs[1] if message["type"] == "tool"]
        assert len(observed) == 1
        message = observed[0]
        expected = agent.EMPTY_LOOKUP_TEXT if trial.arm == "baseline" else "null"
        assert message["content"] == expected
        assert message["name"] == "lookup_order" and message["status"] == "success"
        audit = directory / f"{trial.arm}-audit.jsonl"
        if trial.arm == "baseline":
            records = [json.loads(line) for line in audit.read_text().splitlines()]
            assert records == [{"tool": "lookup_order", "tool_call_id": message["tool_call_id"]}]
            audits += len(records)
        else:
            assert not audit.exists()
        # The next lookup follows another model step, unlike the code retry demo.
        starts = [
            event.seq
            for event in trial.events
            if event.kind == "tool_start" and event.payload.get("tool") == "lookup_order"
        ]
        assert len(starts) == 2
        assert any(
            event.kind == "model_step" and starts[0] < event.seq < starts[1]
            for event in trial.events
        )
    assert audits == 8
    summary = {
        "kind": "offline plumbing proof; not model-effect evidence",
        "trials": len(trials),
        "baseline_messages": agent.EMPTY_LOOKUP_TEXT,
        "candidate_messages": "null",
        "injected_empty_results": 16,
        "baseline_audit_lines": audits,
        "candidate_audit_lines": 0,
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(f"16 offline trials verified; 8 baseline messages, 8 candidate nulls; stores: {output}")


def main() -> None:
    test_injected_empty_lookup_reaches_model_and_remains_recorded()
    print("1 end-to-end test passed")


if __name__ == "__main__":
    main()
