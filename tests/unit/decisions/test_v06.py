from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

import pytest
from pydantic import JsonValue

import arci.cli as cli_module
import arci.mcp_boundary as boundary_module
import arci.runner as runner_module
from arci.gate import decide
from arci.hashing import hash_record
from arci.interfaces import EmitEvent
from arci.minimize import minimize_faults
from arci.report import render_markdown
from arci.schedule import build_schedule, spec_sha256
from arci.schema import (
    DECISION_TOOL,
    ContractResult,
    ContractSpec,
    DecisionSpec,
    Outcome,
    RecordedCall,
    Termination,
    ToolResult,
    TrialEnvelope,
    TrialSpec,
)
from tests.acceptance.decision_fixtures import (
    COND_LOW_CONFIDENCE,
    GATEWAY_MODEL,
    decision_manifest,
)
from tests.acceptance.helpers import COND_CLEAN, synthetic_trials

allowed_headers = vars(boundary_module)["_allowed_headers"]
attach_upstream = vars(boundary_module)["_attach_upstream"]
deadline_remaining = vars(boundary_module)["_deadline_remaining"]
join_upstream_path = vars(boundary_module)["_join_upstream_path"]
probabilities = vars(boundary_module)["_probabilities"]
raw_upstream_snapshot = vars(boundary_module)["_raw_upstream_snapshot"]
retry_delay = vars(boundary_module)["_retry_delay"]
retry_wait_fits = vars(boundary_module)["_retry_wait_fits"]
TokenBucket = vars(runner_module)["_TokenBucket"]
UpstreamResult = boundary_module.UpstreamResult
cmd_preflight = vars(cli_module)["_cmd_preflight"]
scrub_preflight_value = vars(cli_module)["_scrub_preflight_value"]
request_upstream = boundary_module.request_decision_upstream
upstream_diagnostic = boundary_module.upstream_diagnostic


def test_prefix_tolerance_headers_and_retry_parsing() -> None:
    assert join_upstream_path("https://gateway.example/typesafe", "/v1/systemone") == (
        "/typesafe/v1/systemone"
    )
    assert join_upstream_path("https://api.example", "/v1/models") == "/v1/models"
    assert probabilities({"a": 0.5004, "b": 0.5}, {"a", "b"}) is not None
    assert probabilities({"a": 0.502, "b": 0.5}, {"a", "b"}) is None
    assert probabilities({"a": 1.0005, "b": 0.0}, {"a", "b"}) is None
    assert allowed_headers(
        {
            "Retry-After": "3",
            "Retry-After-Ms": "250",
            "X-TypeSafe-Request-ID": "req-1",
            "Authorization": "secret",
        }
    ) == {
        "retry-after": "3",
        "retry-after-ms": "250",
        "x-typesafe-request-id": "req-1",
    }

    now = datetime(2026, 9, 22, 0, 0, tzinfo=UTC)
    later = now + timedelta(seconds=4)
    assert retry_delay({"retry-after-ms": "250", "retry-after": "9"}) == 0.25
    assert retry_delay({"retry-after": "1.5"}) == 1.5
    assert retry_delay(
        {"retry-after": later.strftime("%a, %d %b %Y %H:%M:%S GMT")},
        now=now.timestamp(),
    ) == pytest.approx(4.0)
    assert retry_delay({}) == 0.5
    assert retry_wait_fits(1.0, 0.0, 2.0)
    assert not retry_wait_fits(1.001, 0.0, 2.0)


def test_raw_snapshot_is_independent_and_null_is_explicit() -> None:
    upstream = UpstreamResult(
        200,
        {"x-typesafe-request-id": "req-1"},
        {"answer": {"confidence": 0.9}},
        attempts=2,
        first_status=429,
    )
    snapshot = raw_upstream_snapshot(upstream)
    cast(dict[str, Any], cast(dict[str, Any], snapshot["body"])["answer"])["confidence"] = 0.4
    assert cast(dict[str, Any], cast(dict[str, Any], upstream.body)["answer"])["confidence"] == 0.9
    assert snapshot["attempts"] == 2 and snapshot["first_status"] == 429

    result = ToolResult(
        call_id="c-0000",
        tool=DECISION_TOOL,
        ok=False,
        value={"status": 529, "headers": {}, "body": {"detail": "unavailable"}},
        error_kind="http_529",
    )
    attached = attach_upstream(result, None)
    assert cast(dict[str, JsonValue], attached.value)["upstream"] is None


def test_retry_sleep_and_deadline_use_one_monotonic_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = 0.0
    sends = 0

    def clock() -> float:
        return now

    def sleep(_seconds: float) -> None:
        nonlocal now
        now += 2.0

    def send_once(
        method: str,
        endpoint: str,
        body: dict[str, JsonValue] | None,
        spec: DecisionSpec,
        api_key: str,
        deadline: float,
        *,
        clock: Any,
    ) -> UpstreamResult:
        nonlocal sends
        del method, endpoint, body, spec, api_key, deadline, clock
        sends += 1
        return UpstreamResult(429, {"retry-after-ms": "200"}, {"detail": "busy"})

    monkeypatch.setattr(boundary_module, "_request_upstream_once", send_once)
    spec = DecisionSpec(
        upstream="http",
        base_url="http://127.0.0.1:8080/typesafe",
        request_seconds=2.0,
    )

    assert deadline_remaining(2.0, clock=clock) == 2.0
    with pytest.raises(RuntimeError, match="decision upstream timed out"):
        request_upstream(
            "POST", "/v1/systemone", {}, spec, api_key="secret", clock=clock, sleep=sleep
        )

    assert sends == 1


def test_a_non_200_resend_is_a_transport_fault(monkeypatch: pytest.MonkeyPatch) -> None:
    results = [
        UpstreamResult(529, {"retry-after-ms": "0"}, {"detail": "busy"}),
        UpstreamResult(422, {}, {"detail": "bad request"}),
    ]

    def send_once(
        method: str,
        endpoint: str,
        body: dict[str, JsonValue] | None,
        spec: DecisionSpec,
        api_key: str,
        deadline: float,
        *,
        clock: Any,
    ) -> UpstreamResult:
        del method, endpoint, body, spec, api_key, deadline, clock
        return results.pop(0)

    monkeypatch.setattr(boundary_module, "_request_upstream_once", send_once)
    spec = DecisionSpec(
        upstream="http",
        base_url="http://127.0.0.1:8080/typesafe",
        request_seconds=2.0,
    )

    with pytest.raises(RuntimeError, match="decision upstream failed after retry"):
        request_upstream(
            "POST",
            "/v1/systemone",
            {},
            spec,
            api_key="secret",
            clock=lambda: 0.0,
            sleep=lambda _seconds: None,
        )

    assert results == []


def test_upstream_diagnostics_are_redacted_safe_and_bounded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TYPESAFE_API_KEY", "real-secret")

    class BadStr(RuntimeError):
        def __str__(self) -> str:
            raise RuntimeError("broken string")

    assert "real-secret" not in upstream_diagnostic(RuntimeError("x" * 400 + "real-secret"))
    assert len(upstream_diagnostic(RuntimeError("x" * 400))) < 300
    assert upstream_diagnostic(BadStr()) == "<unprintable BadStr>"


def test_capacity_one_token_bucket_uses_the_fake_clock() -> None:
    now = 10.0
    sleeps: list[float] = []

    def clock() -> float:
        return now

    def sleep(seconds: float) -> None:
        nonlocal now
        sleeps.append(seconds)
        now += seconds

    bucket = TokenBucket(120, clock=clock, sleep=sleep)
    bucket.acquire()
    bucket.acquire()
    bucket.acquire()

    assert sleeps == pytest.approx([0.5, 0.5])
    assert now == pytest.approx(11.0)


def _decision_record(input_tokens: int, output_tokens: int) -> RecordedCall:
    result = ToolResult(
        call_id="c-0000",
        tool=DECISION_TOOL,
        ok=True,
        value={
            "status": 200,
            "headers": {},
            "body": {
                "model": GATEWAY_MODEL,
                "answers": {},
                "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens},
            },
            "upstream": None,
        },
    )
    return RecordedCall(
        tool=DECISION_TOOL,
        arguments_sha256=hash_record({}),
        occurrence=0,
        result=result,
    )


def _before_injected_decision_record() -> RecordedCall:
    return RecordedCall(
        tool=DECISION_TOOL,
        arguments_sha256=hash_record({"attempt": 2}),
        occurrence=1,
        result=ToolResult(
            call_id="c-0001",
            tool=DECISION_TOOL,
            ok=False,
            value={
                "status": 529,
                "headers": {},
                "body": {"detail": "arci injected unavailable"},
                "upstream": None,
            },
            error_kind="http_529",
            injected_by="decision_unavailable",
        ),
    )


def test_report_decision_section_counts_records_not_upstream_attempts() -> None:
    manifest = decision_manifest(
        conditions=(COND_CLEAN,),
        n_per_arm=1,
        spec=DecisionSpec(
            upstream="http",
            base_url="http://127.0.0.1:8080/typesafe",
            model=GATEWAY_MODEL,
        ),
    )
    trials = synthetic_trials(
        manifest,
        condition_id=COND_CLEAN.condition_id,
        baseline_successes=1,
        candidate_successes=1,
    )
    trials = [
        trial.model_copy(
            update={
                "recording": (
                    _decision_record(275, 20),
                    _before_injected_decision_record(),
                )
            }
        )
        for trial in trials
    ]

    report = render_markdown(manifest, decide(manifest, trials), trials)

    assert "## Decisions" in report
    assert "Recorded decisions" in report
    assert "| 4 | 550 | 40 | USD 0.0000231 |" in report
    assert "2026-09-22" in report and "not billed spend" in report


def _failed_envelope(spec: Any, outcome: Outcome = Outcome.FAIL) -> TrialEnvelope:
    return TrialEnvelope.create(
        spec_sha256=spec_sha256(spec),
        experiment_id=spec.experiment_id,
        trial_id=spec.trial_id,
        pair_id=spec.pair_id,
        arm=spec.arm,
        variant=spec.variant,
        task_id=spec.task_id,
        condition_id=spec.condition.condition_id,
        seed=spec.seed,
        outcome=outcome,
        termination=(
            Termination.HARNESS_ERROR if outcome is Outcome.ERROR else Termination.COMPLETED
        ),
        contract=None if outcome is Outcome.ERROR else ContractResult(success=False),
        failure_fingerprint=None if outcome is Outcome.ERROR else "f" * 64,
    )


def test_live_upstream_minimality_is_only_reduced() -> None:
    http = DecisionSpec(
        upstream="http",
        base_url="http://127.0.0.1:8080/typesafe",
        model=GATEWAY_MODEL,
    )
    manifest = decision_manifest(conditions=(COND_LOW_CONFIDENCE,), n_per_arm=1, spec=http)
    spec = next(
        item
        for item in build_schedule(manifest)
        if item.arm == "candidate"
        and item.condition.condition_id == COND_LOW_CONFIDENCE.condition_id
    )
    original = _failed_envelope(spec)

    def runner(spec: TrialSpec, emit_event: EmitEvent, contract: ContractSpec) -> TrialEnvelope:
        del emit_event, contract
        return _failed_envelope(spec, Outcome.PASS)

    result = minimize_faults(manifest, original, spec, run=runner)

    assert result.minimality == "reduced"


def _smoke_answer(request: dict[str, JsonValue], model: str) -> dict[str, JsonValue]:
    answers: dict[str, JsonValue] = {}
    for name, raw_question in cast(dict[str, JsonValue], request["questions"]).items():
        question = cast(dict[str, JsonValue], raw_question)
        if question["type"] == "noul":
            answers[name] = {"type": "noul", "noul": 0.9}
        elif question["type"] == "choice":
            options = list(cast(dict[str, JsonValue], question["criteria"]))
            answers[name] = {
                "type": "choice",
                "choice": options[0],
                "probabilities": {options[0]: 0.8, options[1]: 0.2},
                "confidence": 0.6,
            }
        else:
            answers[name] = {
                "type": "score",
                "score": 0.8,
                "legend": {"0": "Low", "1": "High"},
                "probabilities": {"0": 0.2, "1": 0.8},
                "confidence": 0.6,
            }
    return {
        "model": model,
        "answers": answers,
        "usage": {"input_tokens": 9, "output_tokens": 1},
    }


def test_preflight_exit_codes_with_injected_upstream(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    spec = DecisionSpec(
        upstream="http",
        base_url="http://127.0.0.1:8080/typesafe",
        model=GATEWAY_MODEL,
    )
    manifest = decision_manifest(n_per_arm=1, spec=spec)
    path = tmp_path / "manifest.json"
    path.write_text(manifest.model_dump_json(), encoding="utf-8")
    monkeypatch.setenv("TYPESAFE_API_KEY", "secret")
    calls: list[str] = []

    def ready(
        method: str,
        endpoint: str,
        body: dict[str, JsonValue] | None,
        spec: DecisionSpec,
        *,
        api_key: str | None = None,
    ) -> UpstreamResult:
        del method, api_key
        calls.append(endpoint)
        if body is None:
            return UpstreamResult(
                200,
                {},
                {"models": [{"name": spec.model, "description": "fake", "release_date": "x"}]},
            )
        return UpstreamResult(
            200,
            {"x-typesafe-request-id": "req-1"},
            _smoke_answer(body, spec.model),
        )

    assert cmd_preflight(str(path), upstream=ready, clock=lambda: 1.0) == 0
    assert calls == ["/v1/models", "/v1/systemone"]
    receipt = json.loads(capsys.readouterr().out.splitlines()[-1])
    assert receipt["preflight"]["request_id"] == "req-1"
    assert "secret" not in json.dumps(receipt)

    calls.clear()

    def missing_pin(
        method: str,
        endpoint: str,
        body: dict[str, JsonValue] | None,
        spec: DecisionSpec,
        *,
        api_key: str | None = None,
    ) -> UpstreamResult:
        del method, endpoint, body, spec, api_key
        calls.append("GET")
        return UpstreamResult(
            200,
            {},
            {"models": [{"name": "other", "description": "fake", "release_date": "x"}]},
        )

    assert cmd_preflight(str(path), upstream=missing_pin) == 2
    assert calls == ["GET"]
    monkeypatch.delenv("TYPESAFE_API_KEY")
    assert cmd_preflight(str(path), upstream=ready) == 3


def test_preflight_never_prints_a_key_from_an_upstream_exception(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    spec = DecisionSpec(
        upstream="http",
        base_url="http://127.0.0.1:8080/typesafe",
        model=GATEWAY_MODEL,
    )
    path = tmp_path / "manifest.json"
    path.write_text(decision_manifest(n_per_arm=1, spec=spec).model_dump_json(), encoding="utf-8")
    monkeypatch.setenv("TYPESAFE_API_KEY", "real-secret")

    def broken(
        method: str,
        endpoint: str,
        body: dict[str, JsonValue] | None,
        spec: DecisionSpec,
        *,
        api_key: str | None = None,
    ) -> UpstreamResult:
        del method, endpoint, body, spec, api_key
        raise RuntimeError("provider rejected real-secret")

    assert cmd_preflight(str(path), upstream=broken) == 3
    output = capsys.readouterr().out
    assert "real-secret" not in output and "<redacted>" in output


def test_preflight_scrubs_provider_strings_from_prints_and_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    key = "real-secret"
    spec = DecisionSpec(
        upstream="http",
        base_url=f"http://127.0.0.1:8080/{key}",
        model=f"provider-{key}",
    )
    path = tmp_path / "manifest.json"
    path.write_text(decision_manifest(n_per_arm=1, spec=spec).model_dump_json(), encoding="utf-8")
    monkeypatch.setenv("TYPESAFE_API_KEY", key)

    def echoed(
        method: str,
        endpoint: str,
        body: dict[str, JsonValue] | None,
        spec: DecisionSpec,
        *,
        api_key: str | None = None,
    ) -> UpstreamResult:
        del method, endpoint, api_key
        if body is None:
            return UpstreamResult(
                200,
                {"x-typesafe-request-id": key},
                {"models": [{"name": spec.model, "description": key, "release_date": key}]},
            )
        return UpstreamResult(
            200,
            {"x-typesafe-request-id": key},
            _smoke_answer(body, spec.model),
        )

    assert cmd_preflight(str(path), upstream=echoed, clock=lambda: 1.0) == 0
    output = capsys.readouterr().out
    assert key not in output
    assert "<redacted>" in output
    receipt = json.loads(output.splitlines()[-1])
    assert key not in json.dumps(receipt)
    assert scrub_preflight_value({key: [key, {"nested": key}]}, key) == {
        "<redacted>": ["<redacted>", {"nested": "<redacted>"}]
    }
