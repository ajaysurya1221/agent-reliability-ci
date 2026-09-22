"""v0.5: the decision boundary. FROZEN. Offline, no model calls, no API key.

The acceptance story: an agent that asks a System One endpoint (Jev-style) is tested like any
other command agent. Its decisions are recorded, budgeted, perturbed and replayed through the
harness-owned boundary; the real key never enters the agent's process; a regression in how the
agent handles low confidence becomes a reduced, replayable failure case.
"""

from __future__ import annotations

import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, cast

import pytest
from pydantic import JsonValue, ValidationError

from arci.schedule import build_schedule, spec_sha256
from arci.schema import (
    DECISION_MODELS_TOOL,
    DECISION_TOOL,
    SCHEMA_VERSION,
    ArmSpec,
    Bucket,
    Condition,
    DecisionSpec,
    Event,
    FaultSpec,
    Manifest,
    Outcome,
    ReplayBundle,
    ReplayStatus,
    Termination,
    ToolMode,
    TrialEnvelope,
    Verdict,
)
from tests.acceptance.decision_fixtures import (
    COND_LOW_CONFIDENCE,
    COND_NOISY_DECISIONS,
    COND_UNAVAILABLE,
    PINNED_MODEL,
    STATE_MARKER,
    TASK,
    decision_client,
    decision_contract,
    decision_manifest,
    decision_spec,
    decisions,
    fixture,
)
from tests.acceptance.helpers import COND_CLEAN, manifest

pytestmark = pytest.mark.acceptance


def _run(variant: str, **kw: object) -> TrialEnvelope:
    from arci.runner import run_trial

    return run_trial(decision_spec(variant, **kw), lambda _e: None, decision_contract())  # pyright: ignore[reportArgumentType]


def _starts(env: TrialEnvelope) -> list[str]:
    return [cast(str, e.payload["tool"]) for e in env.events if e.kind == "tool_start"]


def _finishes(env: TrialEnvelope, tool: str) -> list[Event]:
    return [e for e in env.events if e.kind == "tool_finish" and e.payload.get("tool") == tool]


def _answers(event: Event) -> dict[str, Any]:
    value = cast(dict[str, Any], event.payload["value"])
    return cast(dict[str, Any], value["body"]["answers"])


def _rebundle(bundle: ReplayBundle, **spec_update: object) -> ReplayBundle:
    data = bundle.model_dump(exclude={"record_sha256"})
    return ReplayBundle.create(**{**data, "spec": bundle.spec.model_copy(update=spec_update)})


# --- schema -----------------------------------------------------------------------------


def test_schema_version_moved_because_defaults_enter_seals() -> None:
    assert SCHEMA_VERSION == "arci/0.5"
    assert decision_manifest().schema_version == "arci/0.5"


def test_decision_spec_validation() -> None:
    assert DecisionSpec(upstream="http").base_url == "https://api.typesafe.ai"
    assert DecisionSpec(upstream="http", base_url="http://127.0.0.1:8080").model == "jev-1.13.0"
    for bad in (
        {"upstream": "fixture"},  # fixture required
        {"upstream": "http", "fixture": "a.b:c"},  # fixture forbidden
        {"upstream": "http", "base_url": "http://api.typesafe.ai"},  # plaintext off loopback
        {"upstream": "http", "base_url": "https://api.typesafe.ai/v1"},  # path
        {"upstream": "http", "base_url": "https://user:pw@api.typesafe.ai"},  # credentials
        {"upstream": "http", "base_url": "https://api.typesafe.ai?x=1"},  # query
        {"upstream": "http", "model": "jev latest"},
        {"upstream": "http", "model": ""},
        {"upstream": "http", "max_decisions": 1001},
        {"upstream": "http", "request_seconds": 0},
        {"upstream": "http", "max_body_bytes": 2_000_000},
        {"upstream": "http", "extra": 1},
    ):
        with pytest.raises(ValidationError):
            DecisionSpec(**bad)  # pyright: ignore[reportArgumentType]


def test_manifest_rules_for_decisions() -> None:
    base = decision_manifest().model_dump(exclude={"record_sha256"})
    Manifest.create(**base)
    python_agents = manifest().model_dump(exclude={"record_sha256"})
    with pytest.raises(ValidationError):  # python agents cannot have decisions
        Manifest.create(**{**python_agents, "decisions": decisions().model_dump()})
    low = FaultSpec(name="decision_low_confidence", bucket=Bucket.FALSIFY, tool=DECISION_TOOL)
    with pytest.raises(ValidationError):  # decision faults need `decisions`
        Manifest.create(
            **{
                **base,
                "decisions": None,
                "conditions": (Condition(condition_id="c", faults=(low,)),),
            }
        )
    harness_owned = decision_manifest().model_dump(exclude={"record_sha256"})
    harness_owned["mcp_server"]["env"] = {"TYPESAFE_API_KEY": "sk-leak"}
    with pytest.raises(ValidationError):  # would seal a key into every record and bundle
        Manifest.create(**harness_owned)
    harness_owned = decision_manifest().model_dump(exclude={"record_sha256"})
    harness_owned["candidate"]["command"]["env"] = {"TYPESAFE_BASE_URL": "http://example.invalid"}
    with pytest.raises(ValidationError):
        Manifest.create(**harness_owned)
    for fault in (
        low.model_copy(update={"tool": "fetch"}),  # wrong target
        low.model_copy(update={"tool": None}),  # no wildcard
        low.model_copy(update={"params": {"confidence_max": 1.5}}),
        low.model_copy(update={"params": {"confidence_max": True}}),
        low.model_copy(update={"params": {"cap": 0.4}}),  # unknown parameter
        FaultSpec(
            name="decision_unavailable", bucket=Bucket.FALSIFY, tool=DECISION_TOOL, params={"x": 1}
        ),
        FaultSpec(name="tool_timeout", bucket=Bucket.FALSIFY, tool=DECISION_TOOL),  # generic
        FaultSpec(name="empty_result", bucket=Bucket.BENIGN, tool=DECISION_MODELS_TOOL),
    ):
        with pytest.raises(ValidationError):
            Manifest.create(
                **{**base, "conditions": (Condition(condition_id="c", faults=(fault,)),)}
            )


def test_decisions_are_bound_into_every_trial_spec() -> None:
    with_decisions = decision_manifest(n_per_arm=2)
    without = Manifest.create(
        **{
            **with_decisions.model_dump(exclude={"record_sha256"}),
            "decisions": None,
            "conditions": (COND_CLEAN,),
        }
    )
    a = build_schedule(with_decisions)[0]
    b = build_schedule(without)[0]
    assert a.decisions == with_decisions.decisions and b.decisions is None
    assert spec_sha256(a) != spec_sha256(b.model_copy(update={"condition": a.condition}))


# --- the boundary: record --------------------------------------------------------------------


def test_a_gated_agent_decides_then_acts_and_everything_is_recorded() -> None:
    env = _run("gated")
    assert env.outcome is Outcome.PASS and env.termination is Termination.COMPLETED
    assert env.validate_seal()
    assert env.final_state == {"stored": "refund", "log": ["start"]}
    assert _starts(env) == ["log", DECISION_TOOL, "store"]
    assert env.usage.tool_calls == 3  # a decision attempt counts toward max_tool_calls
    start = next(
        e for e in env.events if e.kind == "tool_start" and e.payload["tool"] == DECISION_TOOL
    )
    request = cast(dict[str, Any], start.payload["arguments"])
    assert request["model"] == "jev-latest" and request["state"] == {"ticket": TASK}
    assert set(request["questions"]) == {
        "department",
        "refund_requested",
        "policy_supports",
        "frustration",
    }
    assert start.payload["occurrence"] == 0
    (finish,) = _finishes(env, DECISION_TOOL)
    assert finish.payload["ok"] is True and finish.payload["injected_by"] is None
    value = cast(dict[str, Any], finish.payload["value"])
    assert value["status"] == 200 and value["headers"] == {}
    assert value["body"]["model"] == PINNED_MODEL  # pinned, whatever the agent asked for
    assert set(value["body"]["answers"]) == set(request["questions"])
    recorded = [r for r in env.recording if r.tool == DECISION_TOOL]
    assert len(recorded) == 1 and recorded[0].occurrence == 0
    assert recorded[0].result.value == value
    from arci.hashing import hash_record

    assert recorded[0].arguments_sha256 == hash_record(request)


def test_records_are_deterministic_and_carry_no_token() -> None:
    a, b = _run("gated"), _run("gated")
    assert a.record_sha256 == b.record_sha256
    assert "Bearer" not in a.model_dump_json() and "127.0.0.1" not in a.model_dump_json()


def test_the_real_key_never_enters_the_agent_process(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TYPESAFE_API_KEY", "real-secret")
    monkeypatch.setenv("TYPESAFE_BASE_URL", "https://api.typesafe.ai")
    spec = decision_spec("leak")
    spec = spec.model_copy(
        update={
            "command": spec.command.model_copy(  # pyright: ignore[reportOptionalMemberAccess]
                update={
                    "env": {
                        "TYPESAFE_API_KEY": "agent-override",
                        "TYPESAFE_BASE_URL": "http://example.invalid",
                    }
                }
            )
        }
    )
    from arci.runner import run_trial

    env = run_trial(spec, lambda _e: None, decision_contract())
    assert env.outcome is Outcome.PASS
    log = cast(list[str], cast(dict[str, Any], env.final_state)["log"])
    base, key = log[1].split(" ")
    assert base.startswith("base=http://127.0.0.1:")
    token = key.removeprefix("key=")
    assert token not in {"real-secret", "agent-override", ""} and len(token) >= 16


def test_local_rejections_are_the_agents_problem_not_the_harness() -> None:
    wrong = _run("wrongkey")
    assert wrong.outcome is Outcome.FAIL and wrong.termination is Termination.COMPLETED
    assert wrong.final_state == {"stored": "unauthorized", "log": ["start"]}
    assert DECISION_TOOL not in _starts(wrong)  # not recorded, not budgeted

    huge = _run("huge")
    assert huge.outcome is Outcome.FAIL and huge.termination is Termination.COMPLETED
    assert huge.final_state == {"stored": "too-large", "log": ["start"]}
    assert DECISION_TOOL not in _starts(huge)

    bad = _run("badreq")  # an empty question map is 422, then the agent carries on
    assert bad.outcome is Outcome.PASS and _starts(bad).count(DECISION_TOOL) == 1


def test_models_discovery_is_recorded_but_is_not_a_tool_event() -> None:
    env = _run("models")
    assert env.outcome is Outcome.PASS
    assert _starts(env) == ["log", DECISION_TOOL, "store"]
    (models,) = [r for r in env.recording if r.tool == DECISION_MODELS_TOOL]
    body = cast(dict[str, Any], cast(dict[str, Any], models.result.value)["body"])
    assert body["models"][0]["name"] == PINNED_MODEL
    assert env.usage.tool_calls == 3


def test_decisions_after_the_mcp_session_closed_are_still_served_and_recorded() -> None:
    env = _run("late")
    assert env.outcome is Outcome.PASS, env.failure_detail
    assert _starts(env) == ["log", "store", DECISION_TOOL]


def test_budgets_cover_decision_attempts() -> None:
    env = _run("double", spec=decisions(max_decisions=1))
    assert env.outcome is Outcome.FAIL and env.termination is Termination.BUDGET
    assert _starts(env).count(DECISION_TOOL) == 1  # the attempt over budget emits no tool_start

    env = _run("gated", max_tool_calls=2)  # log, decision, then store is one too many
    assert env.outcome is Outcome.FAIL and env.termination is Termination.BUDGET


def test_concurrent_decision_requests_are_a_harness_fault() -> None:
    env = _run("concurrent")
    assert env.outcome is Outcome.ERROR and env.termination is Termination.HARNESS_ERROR


def test_a_broken_or_lying_fixture_is_a_harness_fault_never_an_agent_failure() -> None:
    for name in (
        "broken_fixture",
        "malformed_fixture",
        "wrong_model_fixture",
        "unnormalised_fixture",
        "infinite_fixture",
    ):
        env = _run("gated", spec=decisions(fixture_name=name))
        assert env.outcome is Outcome.ERROR, name
        assert env.termination is Termination.HARNESS_ERROR, name


def test_an_mcp_server_cannot_advertise_a_reserved_tool_name() -> None:
    for name in ("decision:systemone", "decision:x", "rpc:ping"):
        env = _run("gated", server_args=("--extra-tool", name))
        assert env.outcome is Outcome.ERROR and env.termination is Termination.HARNESS_ERROR, name


# --- perturbations ----------------------------------------------------------------------------


def test_low_confidence_flattens_choices_but_keeps_the_winner() -> None:
    clean = _run("gated")
    env = _run("gated", condition=COND_LOW_CONFIDENCE)
    assert env.outcome is Outcome.PASS
    assert env.final_state == {"stored": "escalate", "log": ["start"]}
    (finish,) = _finishes(env, DECISION_TOOL)
    assert (
        finish.payload["ok"] is True and finish.payload["injected_by"] == "decision_low_confidence"
    )
    answers, before = _answers(finish), _answers(_finishes(clean, DECISION_TOOL)[0])
    department = answers["department"]
    assert department["choice"] == "billing" == before["department"]["choice"]
    assert department["confidence"] == pytest.approx(0.4, abs=1e-9)
    probabilities = cast(dict[str, float], department["probabilities"])
    assert sum(probabilities.values()) == pytest.approx(1.0, abs=1e-9)
    assert max(probabilities.items(), key=lambda kv: kv[1])[0] == "billing"
    ranked = sorted(probabilities, key=lambda k: probabilities[k])
    earlier = cast(dict[str, float], before["department"]["probabilities"])
    ranked_before = sorted(earlier, key=lambda k: earlier[k])
    assert ranked == ranked_before
    n = len(probabilities)
    assert (n * max(probabilities.values()) - 1) / (n - 1) == pytest.approx(0.4, abs=1e-9)
    # Nouls and scores are untouched; the fixture noise is seeded so they match the clean run.
    assert answers["refund_requested"] == before["refund_requested"]
    assert answers["policy_supports"] == before["policy_supports"]
    assert answers["frustration"] == before["frustration"]

    abandoned = _run("abandon", condition=COND_LOW_CONFIDENCE)
    assert abandoned.outcome is Outcome.FAIL and abandoned.termination is Termination.COMPLETED
    assert abandoned.final_state == {"stored": None, "log": ["start"]}
    assert abandoned.failure_fingerprint is not None and "none" in cast(
        str, abandoned.failure_detail
    )

    blind = _run("blind", condition=COND_LOW_CONFIDENCE)
    assert blind.outcome is Outcome.PASS  # mixing never reverses the ranking


def test_low_confidence_leaves_an_already_uncertain_answer_alone() -> None:
    cap = decisions()
    high = COND_LOW_CONFIDENCE.model_copy(
        update={
            "condition_id": "cap_high",
            "faults": (
                COND_LOW_CONFIDENCE.faults[0].model_copy(
                    update={"params": {"confidence_max": 0.95}}
                ),
            ),
        }
    )
    env = _run("gated", condition=high, spec=cap)
    (finish,) = _finishes(env, DECISION_TOOL)
    before = _answers(_finishes(_run("gated"), DECISION_TOOL)[0])
    assert _answers(finish)["department"] == before["department"]
    assert finish.payload["injected_by"] == "decision_low_confidence"


def test_provider_unavailable_is_529_for_the_rest_of_the_trial() -> None:
    env = _run("gated", condition=COND_UNAVAILABLE)
    assert env.outcome is Outcome.PASS and env.final_state == {
        "stored": "escalate",
        "log": ["start"],
    }
    assert _starts(env) == ["log", DECISION_TOOL, DECISION_TOOL, DECISION_TOOL, "store"]
    finishes = _finishes(env, DECISION_TOOL)
    assert [cast(dict[str, Any], f.payload["value"])["status"] for f in finishes] == [529, 529, 529]
    assert all(f.payload["ok"] is False and f.payload["error_kind"] == "http_529" for f in finishes)
    assert all(f.payload["injected_by"] == "decision_unavailable" for f in finishes)
    assert [r.occurrence for r in env.recording if r.tool == DECISION_TOOL] == [0, 1, 2]
    for variant in ("abandon", "blind"):
        env = _run(variant, condition=COND_UNAVAILABLE)
        assert env.outcome is Outcome.FAIL and env.termination is Termination.COMPLETED, variant
        assert "http_529" in cast(str, env.failure_detail)


# --- replay -----------------------------------------------------------------------------------


def test_replay_serves_recorded_decisions_and_never_runs_the_fixture() -> None:
    from arci.replay import make_bundle, replay

    env = _run("abandon", condition=COND_LOW_CONFIDENCE)
    m = decision_manifest()
    bundle = make_bundle(m, env, decision_spec("abandon", condition=COND_LOW_CONFIDENCE))
    assert bundle.validate_seal() and bundle.spec.tool_mode is ToolMode.REPLAY
    assert any(r.tool == DECISION_TOOL for r in bundle.spec.recording)
    never = _rebundle(bundle, decisions=decisions(fixture_name="broken_fixture"))
    result = replay(never)
    assert result.status is ReplayStatus.REPRODUCED, result.detail

    tampered = tuple(
        r.model_copy(update={"arguments_sha256": "0" * 64}) if r.tool == DECISION_TOOL else r
        for r in bundle.spec.recording
    )
    assert replay(_rebundle(bundle, recording=tampered)).status is ReplayStatus.INVALID
    other = _rebundle(bundle, command=decision_client("blind"))  # acts: an extra `store`
    assert replay(other).status is ReplayStatus.INVALID

    live = _rebundle(
        bundle,
        command=decision_client("gated"),
        tool_mode=ToolMode.RECORD,
        recording=(),
        replay_final_state=None,
    )
    repaired = replay(live)
    assert repaired.status is ReplayStatus.NOT_REPRODUCED
    assert repaired.observed_outcome is Outcome.PASS


# --- the whole loop -----------------------------------------------------------------------------


def test_the_gate_blocks_the_abandoning_agent(tmp_path: Path) -> None:
    from arci.gate import decide
    from arci.runner import run_experiment

    m = decision_manifest(n_per_arm=20)
    trials = run_experiment(m, tmp_path, max_workers=6)
    d = decide(m, trials)
    assert (d.conditions[0].baseline.successes, d.conditions[0].candidate.successes) == (20, 0)
    assert d.verdict is Verdict.BLOCK
    assert all(t.outcome is not Outcome.ERROR for t in trials)


def test_diff_hides_the_state_and_still_locates_the_divergence() -> None:
    from arci.diff import first_divergence, step_signature

    gated = _run("gated", condition=COND_LOW_CONFIDENCE, arm="baseline")
    abandoned = _run("abandon", condition=COND_LOW_CONFIDENCE)
    d = first_divergence(gated, abandoned)
    assert d.after_injection == "decision_low_confidence"
    assert d.left is not None and "store" in d.left
    for trial in (gated, abandoned):
        assert all(STATE_MARKER not in step_signature(e) for e in trial.events)
    start = next(
        e for e in gated.events if e.kind == "tool_start" and e.payload["tool"] == DECISION_TOOL
    )
    other_state = json.loads(json.dumps(start.payload))
    other_state["arguments"]["state"]["ticket"]["text"] = "something else entirely"
    assert step_signature(start) != step_signature(
        start.model_copy(update={"payload": other_state})
    )
    assert DECISION_TOOL in step_signature(start)


def test_minimisation_keeps_only_the_decision_fault() -> None:
    from arci.minimize import minimize_faults

    noisy = _run("abandon", condition=COND_NOISY_DECISIONS)
    assert noisy.outcome is Outcome.FAIL
    result = minimize_faults(
        decision_manifest(conditions=(COND_NOISY_DECISIONS,)),
        noisy,
        decision_spec("abandon", condition=COND_NOISY_DECISIONS),
    )
    assert result.kept == ("decision_low_confidence",) and result.minimality == "1-minimal"


# --- http upstream ----------------------------------------------------------------------------


class _Upstream(ThreadingHTTPServer):
    def __init__(self, mode: str) -> None:
        super().__init__(("127.0.0.1", 0), _Handler)
        self.mode = mode
        self.bearers: list[str] = []
        self.models: list[str] = []


class _Handler(BaseHTTPRequestHandler):
    server: _Upstream  # pyright: ignore[reportIncompatibleVariableOverride]

    def log_message(self, format: str, *args: object) -> None:
        del format, args

    def _send(self, status: int, body: dict[str, Any]) -> None:
        raw = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:
        self.server.bearers.append(self.headers.get("Authorization", ""))
        if self.path != "/v1/models":
            self._send(404, {"detail": "not found"})
            return
        self._send(
            200,
            {
                "models": [
                    {"name": PINNED_MODEL, "description": "fake", "release_date": "2026-09-15"}
                ]
            },
        )

    def do_POST(self) -> None:
        self.server.bearers.append(self.headers.get("Authorization", ""))
        length = int(self.headers.get("Content-Length", "0"))
        body = cast(dict[str, JsonValue], json.loads(self.rfile.read(length)))
        self.server.models.append(cast(str, body.get("model")))
        if self.path != "/v1/systemone":
            self._send(404, {"detail": "not found"})
        elif self.headers.get("Authorization") != "Bearer real-secret":
            self._send(401, {"detail": "invalid api key"})
        elif self.server.mode == "529":
            self._send(529, {"detail": "overloaded"})
        elif self.server.mode == "422":
            self._send(
                422, {"detail": [{"loc": ["body", "state"], "msg": "no", "type": "value_error"}]}
            )
        else:
            self._send(200, fixture(body, 0, 0))


@pytest.fixture
def upstream() -> Any:
    servers: list[_Upstream] = []

    def start(mode: str = "ok") -> _Upstream:
        server = _Upstream(mode)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        servers.append(server)
        return server

    yield start
    for server in servers:
        server.shutdown()
        server.server_close()


def _http_spec(server: _Upstream, **kw: object) -> DecisionSpec:
    return decisions(
        upstream="http", fixture_name=None, base_url=f"http://127.0.0.1:{server.server_port}", **kw
    )


def test_http_upstream_gets_the_real_key_and_the_pinned_model(
    monkeypatch: pytest.MonkeyPatch, upstream: Any
) -> None:
    monkeypatch.setenv("TYPESAFE_API_KEY", "real-secret")
    server = upstream()
    env = _run("models", spec=_http_spec(server))
    assert env.outcome is Outcome.PASS, env.failure_detail
    assert server.bearers and all(b == "Bearer real-secret" for b in server.bearers)
    assert server.models == [PINNED_MODEL]  # the agent asked for jev-latest; the boundary pinned it
    start = next(
        e for e in env.events if e.kind == "tool_start" and e.payload["tool"] == DECISION_TOOL
    )
    assert (
        cast(dict[str, Any], start.payload["arguments"])["model"] == "jev-latest"
    )  # recorded as sent
    (models,) = [r for r in env.recording if r.tool == DECISION_MODELS_TOOL]
    assert (
        cast(dict[str, Any], cast(dict[str, Any], models.result.value)["body"])["models"][0]["name"]
        == PINNED_MODEL
    )


def test_a_real_provider_failure_is_a_harness_fault_and_a_422_is_passed_through(
    monkeypatch: pytest.MonkeyPatch, upstream: Any
) -> None:
    monkeypatch.setenv("TYPESAFE_API_KEY", "real-secret")
    down = _run("gated", spec=_http_spec(upstream("529")))
    assert down.outcome is Outcome.ERROR and down.termination is Termination.HARNESS_ERROR

    rejected = _run("gated", spec=_http_spec(upstream("422")))
    assert rejected.outcome is Outcome.PASS and rejected.final_state == {
        "stored": "escalate",
        "log": ["start"],
    }
    (finish,) = _finishes(rejected, DECISION_TOOL)
    assert finish.payload["ok"] is False and finish.payload["error_kind"] == "http_422"
    assert finish.payload["injected_by"] is None

    monkeypatch.setenv("TYPESAFE_API_KEY", "wrong-secret")
    unauthorised = _run("gated", spec=_http_spec(upstream()))
    assert (
        unauthorised.outcome is Outcome.ERROR
        and unauthorised.termination is Termination.HARNESS_ERROR
    )

    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    assert "TYPESAFE_API_KEY" not in os.environ
    missing = _run("gated", spec=_http_spec(upstream()))
    assert missing.outcome is Outcome.ERROR and missing.termination is Termination.HARNESS_ERROR


def test_an_arm_spec_with_decisions_round_trips_through_the_cli_manifest(tmp_path: Path) -> None:
    path = tmp_path / "manifest.json"
    m = decision_manifest(n_per_arm=2)
    path.write_text(m.model_dump_json())
    loaded = Manifest.model_validate_json(path.read_text())
    assert loaded.validate_seal() and loaded.decisions == m.decisions
    assert isinstance(loaded.baseline, ArmSpec)
