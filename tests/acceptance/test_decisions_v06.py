"""v0.6: ready for Jev day one. FROZEN. Offline; a fake upstream shaped like the real one.

The fake speaks the TypeSafe wire format the way Vercel AI Gateway does (path prefix, its own model
id, an extra `provider_metadata` object, a request-id header, probability sums that are only
approximately 1). Every test here is a thing that would otherwise fail the first real run.
"""

from __future__ import annotations

import gzip
import json
import os
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, cast

import pytest
from pydantic import JsonValue, ValidationError

from arci.schema import (
    DECISION_MODELS_TOOL,
    DECISION_TOOL,
    DecisionSpec,
    Event,
    Manifest,
    Outcome,
    Termination,
    TrialEnvelope,
    Verdict,
)
from tests.acceptance.decision_fixtures import (
    COND_LOW_CONFIDENCE,
    COND_NOISY_DECISIONS,
    GATEWAY_MODEL,
    decision_contract,
    decision_manifest,
    decision_spec,
    decisions,
    fixture,
    gateway_decisions,
)
from tests.acceptance.helpers import COND_CLEAN

pytestmark = pytest.mark.acceptance
REPO = Path(__file__).resolve().parents[2]


def _run(variant: str, **kw: object) -> TrialEnvelope:
    from arci.runner import run_trial

    return run_trial(decision_spec(variant, **kw), lambda _e: None, decision_contract())  # pyright: ignore[reportArgumentType]


def _starts(env: TrialEnvelope) -> list[str]:
    return [cast(str, e.payload["tool"]) for e in env.events if e.kind == "tool_start"]


def _finish(env: TrialEnvelope) -> Event:
    (event,) = [
        e for e in env.events if e.kind == "tool_finish" and e.payload.get("tool") == DECISION_TOOL
    ]
    return event


# --- a fake upstream shaped like the gateway ------------------------------------------------


class _Gateway(ThreadingHTTPServer):
    """Modes: ok, 429-once, 529-once, 429-always, slow-retry, gzip, text, nopin."""

    def __init__(self, mode: str) -> None:
        super().__init__(("127.0.0.1", 0), _Handler)
        self.mode = mode
        self.lock = threading.Lock()
        self.posts = 0
        self.paths: list[str] = []
        self.bearers: list[str] = []
        self.models: list[str] = []
        self.started: list[float] = []


class _Handler(BaseHTTPRequestHandler):
    server: _Gateway  # pyright: ignore[reportIncompatibleVariableOverride]

    def log_message(self, format: str, *args: object) -> None:
        del format, args

    def _send(self, status: int, body: bytes, headers: dict[str, str]) -> None:
        self.send_response(status)
        for name, value in headers.items():
            self.send_header(name, value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, body: dict[str, Any], extra: dict[str, str] | None = None) -> None:
        with self.server.lock:
            request_id = f"req-{len(self.server.paths):04d}"
        headers = {"Content-Type": "application/json", "x-typesafe-request-id": request_id}
        headers.update(extra or {})
        self._send(status, json.dumps(body).encode("utf-8"), headers)

    def do_GET(self) -> None:
        with self.server.lock:
            self.server.paths.append(self.path)
            self.server.bearers.append(self.headers.get("Authorization", ""))
        if self.path != "/typesafe/v1/models":
            self._json(404, {"message": "not found", "error_type": "not_found"})
            return
        name = "typesafe-ai/jev-2" if self.server.mode == "nopin" else GATEWAY_MODEL
        self._json(
            200,
            {
                "models": [
                    {
                        "name": name,
                        "description": "fake",
                        "release_date": "2026-09-15",
                        "context_window": 32000,
                    }
                ],
                "object": "list",
            },
        )

    def do_POST(self) -> None:
        with self.server.lock:
            self.server.paths.append(self.path)
            self.server.bearers.append(self.headers.get("Authorization", ""))
            self.server.started.append(time.monotonic())
            self.server.posts += 1
            attempt = self.server.posts
        length = int(self.headers.get("Content-Length", "0"))
        body = cast(dict[str, JsonValue], json.loads(self.rfile.read(length)))
        with self.server.lock:
            self.server.models.append(cast(str, body.get("model")))
        mode = self.server.mode
        if self.path != "/typesafe/v1/systemone":
            self._json(404, {"message": "not found", "error_type": "not_found"})
        elif self.headers.get("Authorization") != "Bearer real-secret":
            self._json(401, {"message": "invalid api key", "error_type": "authentication"})
        elif mode == "429-always" or (mode == "429-once" and attempt == 1):
            self._json(
                429,
                {"message": "rate limited", "error_type": "rate_limit"},
                {"retry-after-ms": "200"},
            )
        elif mode == "529-once" and attempt == 1:
            self._json(
                529, {"message": "overloaded", "error_type": "overloaded"}, {"retry-after": "1"}
            )
        elif mode == "slow-retry":
            self._json(
                429, {"message": "rate limited", "error_type": "rate_limit"}, {"retry-after": "30"}
            )
        elif mode == "gzip":
            raw = gzip.compress(json.dumps(self._answer(body)).encode("utf-8"))
            self._send(200, raw, {"Content-Type": "application/json", "Content-Encoding": "gzip"})
        elif mode == "text":
            self._send(200, b"<html>maintenance</html>", {"Content-Type": "text/html"})
        else:
            self._json(200, self._answer(body))

    def _answer(self, body: dict[str, JsonValue]) -> dict[str, Any]:
        answer = cast(dict[str, Any], fixture(body, 0, 0))
        department = answer["answers"]["department"]
        # The real service rounds: sums land within 1e-4 of 1, not within 1e-6.
        department["probabilities"] = {
            k: round(v, 4) + (0.0002 if k == department["choice"] else 0.0)
            for k, v in department["probabilities"].items()
        }
        answer["model"] = GATEWAY_MODEL
        answer["usage"] = {"input_tokens": 275, "output_tokens": 20, "cached_input_tokens": 0}
        answer["provider_metadata"] = {
            "gateway": {"routing": {"canonicalSlug": GATEWAY_MODEL}, "cost": "0.00001155"}
        }
        return answer


@pytest.fixture
def gateway() -> Any:
    servers: list[_Gateway] = []

    def start(mode: str = "ok") -> _Gateway:
        server = _Gateway(mode)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        servers.append(server)
        return server

    yield start
    for server in servers:
        server.shutdown()
        server.server_close()


@pytest.fixture
def real_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TYPESAFE_API_KEY", "real-secret")


# --- schema -----------------------------------------------------------------------------------


def test_base_url_may_carry_a_path_prefix_and_new_defaults() -> None:
    assert DecisionSpec(upstream="http", base_url="https://ai-gateway.vercel.sh/typesafe").model
    assert DecisionSpec(upstream="http").request_seconds == 5.0  # below the SDKs' 10 s timeout
    assert DecisionSpec(upstream="http").max_requests_per_minute == 600
    for bad in (
        "https://ai-gateway.vercel.sh/typesafe/",
        "https://x.y/a/../b",
        "https://x.y//a",
        "https://x.y/a?x=1",
        "http://api.typesafe.ai/typesafe",
    ):
        with pytest.raises(ValidationError):
            DecisionSpec(upstream="http", base_url=bad)
    with pytest.raises(ValidationError):
        DecisionSpec(upstream="http", max_requests_per_minute=-1)


# --- A1 + A2 + A3: the gateway shape ----------------------------------------------------------


def test_a_gateway_shaped_upstream_is_accepted_recorded_and_served(
    gateway: Any, real_key: None
) -> None:
    server = gateway()
    env = _run("keys", spec=gateway_decisions(server.server_port))
    assert env.outcome is Outcome.PASS, env.failure_detail
    assert env.final_state == {
        "stored": "refund",
        "log": ["start", "keys=answers,model,provider_metadata,usage"],
    }
    assert server.paths == ["/typesafe/v1/systemone"]  # the prefix is joined, nothing else
    assert server.models == [GATEWAY_MODEL] and server.bearers == ["Bearer real-secret"]
    finish = _finish(env)
    value = cast(dict[str, Any], finish.payload["value"])
    assert value["status"] == 200 and value["body"]["model"] == GATEWAY_MODEL
    assert value["headers"] == {"x-typesafe-request-id": "req-0000"}
    assert value["body"]["provider_metadata"]["gateway"]["cost"] == "0.00001155"
    assert value["upstream"]["body"] == value["body"]  # nothing injected: raw equals served
    assert value["upstream"]["attempts"] == 1 and value["upstream"]["first_status"] is None
    (recorded,) = [r for r in env.recording if r.tool == DECISION_TOOL]
    assert recorded.result.value == value


def test_models_discovery_through_the_prefix(gateway: Any, real_key: None) -> None:
    server = gateway()
    env = _run("models", spec=gateway_decisions(server.server_port))
    assert env.outcome is Outcome.PASS, env.failure_detail
    assert server.paths[0] == "/typesafe/v1/models"
    (models,) = [r for r in env.recording if r.tool == DECISION_MODELS_TOOL]
    body = cast(dict[str, Any], cast(dict[str, Any], models.result.value)["body"])
    assert (
        body["models"][0]["name"] == GATEWAY_MODEL and body["models"][0]["context_window"] == 32000
    )


def test_one_bounded_wait_on_429_or_529_then_one_recorded_attempt(
    gateway: Any, real_key: None
) -> None:
    for mode in ("429-once", "529-once"):
        server = gateway(mode)
        env = _run("gated", spec=gateway_decisions(server.server_port))
        assert env.outcome is Outcome.PASS, (mode, env.failure_detail)
        assert server.posts == 2, mode  # one wait, one retry, upstream side
        assert _starts(env).count(DECISION_TOOL) == 1, mode  # one admitted attempt, agent side
        value = cast(dict[str, Any], _finish(env).payload["value"])
        assert value["status"] == 200 and _finish(env).payload["injected_by"] is None
        # The wait is not hidden: the raw snapshot says how many sends it took and what came first.
        assert value["upstream"]["attempts"] == 2
        assert value["upstream"]["first_status"] == (429 if mode == "429-once" else 529)
    always = gateway("429-always")
    env = _run("gated", spec=gateway_decisions(always.server_port))
    assert env.outcome is Outcome.ERROR and env.termination is Termination.HARNESS_ERROR
    assert always.posts == 2  # exactly one retry, never more
    slow = gateway("slow-retry")
    before = time.monotonic()
    env = _run("gated", spec=gateway_decisions(slow.server_port, request_seconds=2.0))
    assert env.outcome is Outcome.ERROR and env.termination is Termination.HARNESS_ERROR
    assert time.monotonic() - before < 15.0  # a 30 s retry-after is capped by request_seconds
    assert slow.posts == 1


def test_encoding_and_non_json_and_tls_are_one_clear_harness_message(
    gateway: Any, real_key: None
) -> None:
    zipped = _run("gated", spec=gateway_decisions(gateway("gzip").server_port))
    assert zipped.outcome is Outcome.ERROR and zipped.termination is Termination.HARNESS_ERROR
    assert "content-encoding" in cast(str, zipped.failure_detail).lower()
    text = _run("gated", spec=gateway_decisions(gateway("text").server_port))
    assert text.outcome is Outcome.ERROR and "non-JSON" in cast(str, text.failure_detail)
    plain = gateway()
    tls = _run(
        "gated",
        spec=decisions(
            upstream="http",
            fixture_name=None,
            base_url=f"https://127.0.0.1:{plain.server_port}/typesafe",
            model=GATEWAY_MODEL,
        ),
    )
    assert tls.outcome is Outcome.ERROR and tls.termination is Termination.HARNESS_ERROR
    detail = cast(str, tls.failure_detail)
    assert detail.startswith("TLS") and "Traceback" not in detail and len(detail) < 300


# --- B5: pacing ---------------------------------------------------------------------------


def test_the_parent_paces_trial_starts_for_http_upstreams(
    gateway: Any, real_key: None, tmp_path: Path
) -> None:
    from arci.runner import run_experiment

    server = gateway()
    m = decision_manifest(
        baseline="gated",
        candidate="gated",
        conditions=(COND_CLEAN,),
        n_per_arm=10,
        spec=gateway_decisions(server.server_port, max_requests_per_minute=120),
    )
    before = time.monotonic()
    trials = run_experiment(m, tmp_path, max_workers=8)
    elapsed = time.monotonic() - before
    assert all(t.outcome is Outcome.PASS for t in trials), [t.failure_detail for t in trials]
    assert server.posts == 20
    assert elapsed >= 9.0, elapsed  # 20 starts at 2 per second: at least 19 gaps of 0.5 s


# --- B6: tokens and cost -------------------------------------------------------------------------


def test_the_report_lists_decision_tokens_and_cost(
    gateway: Any, real_key: None, tmp_path: Path
) -> None:
    from arci.gate import decide
    from arci.report import render_markdown
    from arci.runner import run_experiment

    server = gateway()
    m = decision_manifest(
        baseline="gated",
        candidate="gated",
        conditions=(COND_CLEAN,),
        n_per_arm=2,
        spec=gateway_decisions(server.server_port),
    )
    trials = run_experiment(m, tmp_path, max_workers=4)
    report = render_markdown(m, decide(m, trials), trials)
    assert "## Decisions" in report
    section = report.split("## Decisions", 1)[1]
    assert "4" in section and "1100" in section and "80" in section  # attempts, input, output
    assert "USD" in section and f"{1100 * 0.042 / 1e6:.7f}" in section


# --- C9: the raw upstream answer ---------------------------------------------------------------


def test_the_raw_upstream_answer_is_recorded_but_never_served() -> None:
    env = _run("keys", condition=COND_LOW_CONFIDENCE)
    assert env.outcome is Outcome.PASS
    assert env.final_state == {"stored": "escalate", "log": ["start", "keys=answers,model,usage"]}
    value = cast(dict[str, Any], _finish(env).payload["value"])
    served = value["body"]["answers"]["department"]
    raw = value["upstream"]["body"]["answers"]["department"]
    assert served["confidence"] == pytest.approx(0.4, abs=1e-9)
    assert raw["confidence"] > 0.8 and raw["choice"] == served["choice"]
    assert value["upstream"]["status"] == 200


def test_no_upstream_means_a_null_snapshot() -> None:
    from tests.acceptance.decision_fixtures import COND_UNAVAILABLE

    env = _run("gated", condition=COND_UNAVAILABLE)
    assert env.outcome is Outcome.PASS
    for event in env.events:
        if event.kind == "tool_finish" and event.payload.get("tool") == DECISION_TOOL:
            value = cast(dict[str, Any], event.payload["value"])
            assert value["status"] == 529 and value["upstream"] is None


def test_an_error_on_removal_never_establishes_minimality() -> None:
    """Removing a fault and getting ERROR (not PASS) says nothing about that fault."""
    from arci.minimize import minimize_faults
    from arci.runner import run_trial

    noisy = _run("abandon", condition=COND_NOISY_DECISIONS)
    assert noisy.outcome is Outcome.FAIL
    manifest = decision_manifest(conditions=(COND_NOISY_DECISIONS,))
    spec = decision_spec("abandon", condition=COND_NOISY_DECISIONS)

    def flaky_runner(candidate: Any, emit: Any, contract: Any) -> TrialEnvelope:
        names = tuple(f.name for f in candidate.condition.faults)
        if names == ("empty_result",):  # the decision fault removed: the harness breaks instead
            broken = candidate.model_copy(
                update={"decisions": decisions(fixture_name="broken_fixture")}
            )
            return run_trial(broken, emit, contract)
        return run_trial(candidate, emit, contract)

    result = minimize_faults(manifest, noisy, spec, run=flaky_runner)  # pyright: ignore[reportArgumentType]
    assert "decision_low_confidence" in result.kept
    assert result.minimality != "1-minimal"


def test_minimality_is_never_claimed_for_a_live_upstream(gateway: Any, real_key: None) -> None:
    from arci.minimize import minimize_faults

    server = gateway()
    spec = gateway_decisions(server.server_port)
    noisy = _run("abandon", condition=COND_NOISY_DECISIONS, spec=spec)
    assert noisy.outcome is Outcome.FAIL
    result = minimize_faults(
        decision_manifest(conditions=(COND_NOISY_DECISIONS,), spec=spec),
        noisy,
        decision_spec("abandon", condition=COND_NOISY_DECISIONS, spec=spec),
    )
    assert result.kept == ("decision_low_confidence",)
    assert result.minimality == "reduced"  # live answers are sampled; 1-minimal is not claimable

    offline = _run("abandon", condition=COND_NOISY_DECISIONS)
    result = minimize_faults(
        decision_manifest(conditions=(COND_NOISY_DECISIONS,)),
        offline,
        decision_spec("abandon", condition=COND_NOISY_DECISIONS),
    )
    assert result.minimality == "1-minimal"  # the seeded fixture still earns the claim


# --- B4: preflight ------------------------------------------------------------------------


def _preflight(tmp_path: Path, m: Manifest, key: str | None) -> subprocess.CompletedProcess[str]:
    path = tmp_path / "manifest.json"
    path.write_text(m.model_dump_json())
    env = {k: v for k, v in os.environ.items() if k != "TYPESAFE_API_KEY"}
    if key is not None:
        env["TYPESAFE_API_KEY"] = key
    env["PYTHONPATH"] = str(REPO)
    return subprocess.run(
        [sys.executable, "-m", "arci.cli", "preflight", str(path)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


def test_preflight_reports_ready_missing_pin_and_unreachable(gateway: Any, tmp_path: Path) -> None:
    ok = gateway()
    done = _preflight(
        tmp_path, decision_manifest(spec=gateway_decisions(ok.server_port)), "real-secret"
    )
    assert done.returncode == 0, done.stdout + done.stderr
    assert GATEWAY_MODEL in done.stdout and "req-" in done.stdout and "275" in done.stdout
    assert ok.posts == 1 and not (tmp_path / "runs").exists()  # one smoke request, no run store

    nopin = gateway("nopin")
    done = _preflight(
        tmp_path, decision_manifest(spec=gateway_decisions(nopin.server_port)), "real-secret"
    )
    assert done.returncode == 2 and "typesafe-ai/jev-2" in done.stdout and nopin.posts == 0

    done = _preflight(tmp_path, decision_manifest(spec=gateway_decisions(ok.server_port)), None)
    assert done.returncode == 3 and "TYPESAFE_API_KEY" in done.stdout + done.stderr

    closed = gateway()
    port = closed.server_port
    closed.shutdown()
    closed.server_close()
    done = _preflight(tmp_path, decision_manifest(spec=gateway_decisions(port)), "real-secret")
    assert done.returncode == 3

    done = _preflight(tmp_path, decision_manifest(), "real-secret")  # fixture upstream
    assert done.returncode == 3 and "http" in done.stdout + done.stderr


def test_the_gate_and_the_hero_story_hold_through_the_gateway(
    gateway: Any, real_key: None, tmp_path: Path
) -> None:
    from arci.gate import decide
    from arci.runner import run_experiment

    server = gateway()
    m = decision_manifest(n_per_arm=12, spec=gateway_decisions(server.server_port))
    trials = run_experiment(m, tmp_path, max_workers=6)
    d = decide(m, trials)
    assert d.verdict is Verdict.BLOCK and all(t.outcome is not Outcome.ERROR for t in trials)
    assert all(
        any(
            r.tool == DECISION_TOOL and "upstream" in cast(dict[str, Any], r.result.value)
            for r in t.recording
        )
        for t in trials
    )
