"""Exercise first-exchange failures through a released ARCI worker with no socket."""

import os
import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch

import httpx

from arci.descriptor import compile_run_descriptor
from arci.runner import run_trial
from arci.suite_schedule import build_suite_round
from arci.suite_schema import SuiteManifest


def transport() -> httpx.MockTransport:
    from exposure import FirstExchange
    from standin import respond

    publish = FirstExchange.publish

    def persist(self: FirstExchange, *, create: bool) -> None:
        if self.row["stream_completed"]:
            raise OSError("injected completion write failure")
        publish(self, create=create)

    def send(request: httpx.Request) -> httpx.Response:
        if os.environ["RECEIPT_CASE"] == "timeout":
            raise httpx.ReadTimeout("before headers", request=request)
        return respond(request)

    if os.environ["RECEIPT_CASE"] == "lost":
        FirstExchange.publish = persist
    return httpx.MockTransport(send)


def candidate(*args: Any) -> Any:
    import agent

    with patch("standin.transport", transport):
        return agent.candidate(*args)


def main(root: Path, work: Path, case: str) -> None:
    from descriptors import models, read

    name = "size0-d1-q2-null"
    manifest = compile_run_descriptor(root / "prepared" / f"{name}.yaml")
    assert isinstance(manifest, SuiteManifest)
    spec = build_suite_round(manifest, 1)[1].model_copy(update={"agent": "receipt_probe:candidate"})
    receipts = work / "receipts"
    receipts.mkdir()
    os.environ.update(
        SIZE0_RUN=name,
        SIZE0_TAG=models(root)["q2"]["tag"],
        SIZE0_TRANSPORT="offline",
        SIZE0_CONDITION="null",
        SIZE0_ASSIGNMENTS=str(root / "prepared" / f"{name}.assignments.json"),
        ORDER_DESK_FIRST_EXCHANGE_AUDIT=str(receipts),
        RECEIPT_CASE=case,
        LANGSMITH_TRACING="false",
        LANGCHAIN_TRACING_V2="false",
    )
    trial = run_trial(
        spec,
        lambda _: None,
        manifest.contract,
        extra_pythonpath=(str(root / "agent"), str(Path(__file__).resolve().parent)),
    )
    assert trial.validate_seal()
    (work / "manifest.json").write_text(manifest.model_dump_json())
    (work / "trials.jsonl").write_text(trial.model_dump_json() + "\n")
    (work / "events.jsonl").write_text("".join(e.model_dump_json() + "\n" for e in trial.events))
    (receipt,) = receipts.glob("*.json")
    (work / "exchanges.jsonl").write_bytes(receipt.read_bytes() + b"\n")
    assert read(receipt)["stream_completed"] is False
    assert trial.outcome.value == "ERROR" and trial.termination.value == "harness_error", (
        trial.failure_detail
    )


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    main(Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3])
