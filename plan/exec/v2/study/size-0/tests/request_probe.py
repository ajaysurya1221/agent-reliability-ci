"""Capture the native client body from one released ARCI trial in an isolated worker."""

import json
import os
import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch


def candidate(*args: Any) -> Any:
    import agent
    import httpx

    # Both captured calls go through the same Ollama serializer. Only the final transport
    # is substituted. The first assistant reply ends the trial after the request is captured.
    init = agent.init_chat_model

    def capture(request: httpx.Request) -> httpx.Response:
        Path(os.environ["SIZE0_CAPTURE"]).write_bytes(request.content)
        return httpx.Response(
            200,
            json={
                "done": True,
                "model": json.loads(request.content)["model"],
                "message": {"role": "assistant", "content": "Done"},
            },
        )

    def build(model: str, **kwargs: Any) -> Any:
        if os.environ["SIZE0_PROBE_STUDY"] == "1":
            assert kwargs["sync_client_kwargs"]["follow_redirects"] is False
            assert kwargs["sync_client_kwargs"]["trust_env"] is False
        kwargs.setdefault("sync_client_kwargs", {})["transport"] = httpx.MockTransport(capture)
        return init(model, **kwargs)

    with patch.object(agent, "init_chat_model", build):
        return getattr(agent, os.environ["SIZE0_PROBE_ENTRY"])(*args)


def main(output: Path) -> None:
    from arci.descriptor import loads_suite_descriptor
    from arci.runner import run_trial
    from arci.suite_schedule import build_suite_round

    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    from descriptors import descriptor, read

    ref = root.parent / "order-desk-compound"
    import yaml

    original = yaml.safe_load((ref / "arci.yaml").read_text())
    original["tasks"] = [
        json.loads(line) for line in (ref / "tasks.jsonl").read_text().splitlines()
    ]
    roster = {r["slot"]: r for r in read(root / "models.example.json")["slots"]}
    cases = [("reference", original, ref, roster["q4"])]
    for name, slot in (("study", "q4"), ("baseline", "q4"), ("anchor", "g12")):
        model = roster[slot]
        cases.append(
            (name, descriptor(root, f"size0-d1-{slot}-null", model), root / "agent", model)
        )
    for name, body, folder, model in cases:
        suite = loads_suite_descriptor(json.dumps(body))
        spec = build_suite_round(suite, 1)[1].model_copy(
            update={"agent": "request_probe:candidate", "seed": 739}
        )
        receipt_path = output / (name + ".receipt")
        if name != "reference":
            receipt_path.mkdir()
        arm = "baseline" if name == "baseline" else "candidate"
        os.environ.update(
            SIZE0_PROBE_ENTRY=arm,
            SIZE0_PROBE_STUDY=str(int(name != "reference")),
            ARCI_QUICKSTART_BASELINE="ollama:" + model["tag"],
            ARCI_QUICKSTART_CANDIDATE="ollama:" + model["tag"],
            ARCI_QUICKSTART_TEMPERATURE="0.7",
            SIZE0_RUN="parity-probe",
            SIZE0_ASSIGNMENTS=str(output / "probe-assignments"),
            SIZE0_TAG=model["tag"],
            SIZE0_CONDITION="null",
            SIZE0_CAPTURE=str(output / name),
            ORDER_DESK_FIRST_EXCHANGE_AUDIT=str(output / (name + ".receipt")),
            LANGSMITH_TRACING="false",
            LANGCHAIN_TRACING_V2="false",
            PYTHONDONTWRITEBYTECODE="1",
        )
        (output / "probe-assignments").write_text(
            json.dumps(
                [
                    {
                        "seed": 739,
                        "round": 1,
                        "order_id": spec.task["order_id"],
                        "arm": arm,
                        "run": "parity-probe",
                    }
                ]
            )
        )
        trial = run_trial(
            spec,
            lambda _: None,
            suite.contract,
            extra_pythonpath=(str(folder), str(root / "tests")),
        )
        assert trial.termination.value == "completed", (trial.termination, trial.failure_detail)
        receipt = json.loads(
            (receipt_path if name == "reference" else next(receipt_path.glob("*.json"))).read_text()
        )
        assert receipt.get("stream_completed", receipt.get("first_request_matches"))


if __name__ == "__main__":
    main(Path(sys.argv[1]))
