"""Offline integration proof using real ARCI workers, injection, adapter and stores.

The scripted policy records its actual input before interpreting it. These trials
prove plumbing only: they are not the registered suite or evidence of model benefit.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch

import yaml
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.messages import BaseMessage
from langchain_core.outputs import ChatResult

from arci.adapters.langchain import make_adapter
from arci.descriptor import loads_suite_descriptor
from arci.runner import run_trial
from arci.schema import Outcome
from arci.suite_schedule import build_suite_round
from arci.suite_storage import SuiteStore, load_suite_run

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
        return super()._generate(messages, stop, run_manager, **kwargs)


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
    task_to_input=agent.task_input,
    fault_exceptions={"timeout": TimeoutError, "error": RuntimeError},
)


def run_proof(output: Path) -> Path:
    """One round in a temporary suite store with scripted settings sealed in every task."""
    descriptor = yaml.safe_load((STUDY / "arci.yaml").read_text())
    assert isinstance(descriptor, dict)
    tasks = [json.loads(line) for line in (STUDY / "tasks.jsonl").read_text().splitlines()]
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("ARCI_QUICKSTART_", "LANGCHAIN_", "LANGSMITH_"))
    }
    environment.update(
        PYTHONDONTWRITEBYTECODE="1", LANGCHAIN_TRACING_V2="false", LANGSMITH_TRACING="false"
    )
    with patch.dict(os.environ, environment, clear=True):
        for task in tasks:
            task["quickstart_settings"] = resolve_settings()
        descriptor.update(
            suite_id="offline-compound-test",
            toolset="test_end_to_end:toolset",
            tasks=tasks,
            prior_runs=[],
        )
        for arm in ("baseline", "candidate"):
            descriptor[arm].update(agent=f"test_end_to_end:{arm}", candidate_id=f"offline-{arm}")
        suite = loads_suite_descriptor(json.dumps(descriptor))
        store = SuiteStore(output, suite)
        for spec in build_suite_round(suite, 1):
            with patch.dict(
                os.environ,
                {
                    "ORDER_DESK_EMPTY_TEXT_AUDIT": str(store.run_dir / "audit.jsonl"),
                    "ORDER_DESK_TEST_MESSAGES": str(
                        store.run_dir / f"{spec.trial_id}-messages.jsonl"
                    ),
                },
            ):
                trial = run_trial(
                    spec,
                    store.append_event,
                    suite.contract,
                    extra_pythonpath=(str(STUDY / "tests"), str(STUDY)),
                )
            store.append_trial(trial)
            assert trial.outcome == Outcome.PASS, (trial.termination, trial.failure_detail)
    return store.run_dir


def model_inputs(directory: Path, arm: str) -> list[list[dict[str, Any]]]:
    return [
        json.loads(line) for line in (directory / f"{arm}-messages.jsonl").read_text().splitlines()
    ]


def test_injected_empty_lookup_reaches_model_and_remains_recorded(tmp_path: Path) -> None:
    directory = run_proof(tmp_path)
    _, trials = load_suite_run(directory)
    assert len(trials) == 16
    audits = {"baseline": 0, "candidate": 0}
    records = [json.loads(line) for line in (directory / "audit.jsonl").read_text().splitlines()]
    for trial in trials:
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
        inputs = model_inputs(directory, trial.trial_id)
        assert len(inputs) == trial.usage.model_steps == 4
        expected = "null" if trial.arm == "candidate" else agent.GENERIC_TEXT
        assert [m["type"] for m in inputs[0]] == ["system", "human", "ai", "tool", "ai", "tool"]
        assert inputs[0][3]["content"] == "Error: unknown SKU"
        assert inputs[0][5]["content"] == expected
        assert [call.tool for call in trial.recording] == [
            "check_stock",
            "lookup_order",
            "lookup_order",
            "check_stock",
            "add_note",
        ]
        audit_id = inputs[0][5]["tool_call_id"]
        matches = [r for r in records if r["tool_call_id"] == audit_id]
        if trial.arm == "baseline":
            assert matches == [
                {"tool": "lookup_order", "arm": "baseline", "tool_call_id": audit_id}
            ]
        else:
            assert not matches
        audits[trial.arm] += len(matches)
        # The two scripted turns consumed tool budget only. The stand-in retried.
        assert [e.kind for e in trial.events[1:7]] == [
            "tool_start",
            "tool_finish",
            "tool_start",
            "tool_finish",
            "model_step",
            "tool_start",
        ]
    assert audits == {"baseline": 8, "candidate": 0}
    assert len(records) == 8
    results = [
        subprocess.check_output(
            [
                sys.executable,
                str(STUDY.parent / "counts-run-6" / name),
                str(directory),
                "--audit",
                str(directory / "audit.jsonl"),
            ]
        )
        for name in ("count_a.py", "count_b.py")
    ]
    assert results[0] == results[1]
    summary = json.loads(results[0])
    for arm, counts in summary["arms"].items():
        assert counts["trials"] == counts["passed"] == counts["scripted_opening_recorded"] == 8
        assert counts["model_step_after_opening"] == counts["empty_result_delivered_ok"] == 8
        assert counts["after_empty_result"]["read_again"] == {"trials": 8, "passed": 8}
        assert summary["audit"]["by_arm"][arm]["distinct_tool_call_ids"] == audits[arm]
