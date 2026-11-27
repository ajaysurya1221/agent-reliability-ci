"""Run two honest failures through the released worker and all three recounts."""

import json
import os
import shutil
import sys
from pathlib import Path

from arci.descriptor import compile_run_descriptor
from arci.runner import run_trial
from arci.schema import Event
from arci.suite_schedule import build_suite_round
from arci.suite_schema import SuiteManifest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import count_a  # noqa: E402
import count_b  # noqa: E402
from check_evidence import observation, receipt_map  # noqa: E402
from descriptors import models, read  # noqa: E402


def run(root: Path, work: Path) -> None:
    work.mkdir()
    agent = work / "agent"
    shutil.copytree(root / "agent", agent)
    (agent / "standin.py").rename(agent / "normal_standin.py")
    (agent / "standin.py").write_text("""
import httpx,json,os
from normal_standin import respond

def transport():
    def exchange(request):
        if os.environ["CASE"] == "worker_loss":
            os._exit(7)
        if json.loads(request.content)["messages"][-1]["content"] == "saved":
            raise RuntimeError("fixture crash after writing the note")
        return respond(request)
    return httpx.MockTransport(exchange)
""")
    run_name = "size0-d1-q2-null"
    path = root / "prepared" / (run_name + ".assignments.json")
    bound = read(path)
    manifest = compile_run_descriptor(root / "prepared" / (run_name + ".yaml"))
    assert isinstance(manifest, SuiteManifest)
    (work / "manifest.json").write_text(manifest.model_dump_json())
    receipts = work / "receipts"
    receipts.mkdir()
    tag = models(root)["q2"]["tag"]
    audit = work / "replacement.jsonl"
    audit.touch()
    os.environ.update(
        SIZE0_RUN=run_name,
        SIZE0_TAG=tag,
        SIZE0_TRANSPORT="offline",
        SIZE0_CONDITION="null",
        SIZE0_ASSIGNMENTS=str(path),
        ORDER_DESK_FIRST_EXCHANGE_AUDIT=str(receipts),
        LANGSMITH_TRACING="false",
        LANGCHAIN_TRACING_V2="false",
        PYTHONDONTWRITEBYTECODE="1",
    )
    schedule = build_suite_round(manifest, 1)
    with (work / "events.jsonl").open("w") as events, (work / "trials.jsonl").open("w") as trials:

        def save_event(event: Event) -> None:
            events.write(event.model_dump_json() + "\n")

        for scenario, spec in zip(("worker_loss", "after_note"), schedule[:2], strict=True):
            os.environ["CASE"] = scenario
            trial = run_trial(
                spec,
                save_event,
                manifest.contract,
                extra_pythonpath=(str(agent),),
            )
            assert trial.validate_seal() and trial.outcome.value == "FAIL", trial.failure_detail
            assert trial.termination.value == "crash"
            if scenario == "worker_loss":
                assert not trial.recording and trial.final_state is None
            else:
                from check import check

                assert trial.final_state is not None and check(spec.task, trial.final_state)
            row = trial.model_dump(mode="json")
            counts = observation(row, str(spec.task["order_id"]), scenario == "after_note")
            assert counts["final_state_passes"] == 0 and counts["exposed"] == int(
                scenario == "after_note"
            )
            trials.write(trial.model_dump_json() + "\n")
    exchanges = [read(p) for p in receipts.glob("*.json")]
    assert receipt_map(exchanges, bound[:2], tag) == {
        spec.trial_id: i == 1 for i, spec in enumerate(schedule[:2])
    }
    (work / "exchanges.jsonl").write_text("".join(json.dumps(r) + "\n" for r in exchanges))
    counts = count_a.count(work, audit)
    assert counts == count_b.count(work, audit)
    totals = counts["pooled"]
    assert (
        totals["delivered"],
        totals["exposed"],
        totals["unexposed"],
        totals["final_state_passes"],
    ) == (2, 1, 1, 0)
    assert totals["terminations"] == {"crash": 2}


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT / "agent"))
    run(Path(sys.argv[1]), Path(sys.argv[2]))
