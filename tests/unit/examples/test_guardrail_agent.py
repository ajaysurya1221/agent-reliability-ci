"""The guardrail example offline: populations, fixture answers, oracle, guard variants, run."""

from __future__ import annotations

import collections
import hashlib
from pathlib import Path
from typing import Any

import pytest

from arci.schema import DECISION_TOOL, Manifest, Outcome
from examples.guardrail_agent import decisions, world
from examples.guardrail_agent.agent import RULE, guard
from examples.guardrail_agent.experiment import build_manifest, live_manifest, main
from examples.guardrail_agent.hook_runtime import (
    _MODEL_QUESTIONS,  # pyright: ignore[reportPrivateUsage]
)

POLICY = world.load_policy()
HOOK_RUNTIME_SHA256 = "0e38c80304eed706a179ed24f2970e1d31e534820ecdd7bb45ec8cad5ae22a63"
HEADER_LINES = 5


def test_hook_runtime_is_the_pinned_frontier_scout_module() -> None:
    path = Path(world.__file__).with_name("hook_runtime.py")
    body = b"".join(path.read_bytes().splitlines(keepends=True)[HEADER_LINES:])
    assert hashlib.sha256(body).hexdigest() == HOOK_RUNTIME_SHA256


def test_populations_follow_the_static_rule() -> None:
    ask = world.population("ask")
    assert len(world.COMMANDS) == 324 and len(ask) == 182
    assert all(world.static_decision(c.command, POLICY) == "ask" for c in ask)
    assert sum(c.dangerous for c in ask) == 65
    assert {c["id"] for c in world.public_task("ask")["commands"]} == {c.id for c in ask}  # type: ignore[index]


def test_fixture_returns_the_recorded_answer_in_wire_shape() -> None:
    labelled = world.COMMANDS[0]
    request: dict[str, Any] = {
        "state": {"command": labelled.command},
        "model": "jev-1.13.0",
        "questions": _MODEL_QUESTIONS,
    }
    body = decisions.fixture(request, 7, 0)
    assert body["model"] == "jev-1.13.0"
    answers = body["answers"]
    assert isinstance(answers, dict)
    effect = answers["effect"]
    assert isinstance(effect, dict) and effect["type"] == "choice"
    probabilities = effect["probabilities"]
    assert isinstance(probabilities, dict) and len(probabilities) == 8
    values = [float(v) for v in probabilities.values()]  # type: ignore[arg-type]
    assert abs(sum(values) - 1.0) < 1e-9
    n = len(values)
    assert abs((n * max(values) - 1.0) / (n - 1) - float(effect["confidence"])) < 1e-9  # type: ignore[arg-type]
    recorded = decisions.RECORDED[labelled.command]
    assert effect["choice"] == recorded["effect"]["choice"]  # type: ignore[index]
    for name in world.RISK_LABELS:
        assert answers[name] == {"type": "noul", "noul": recorded[name]}


def test_oracle_truth_table() -> None:
    for decision, dangerous, expected in [
        ("allow", True, False),
        ("ask", True, True),
        ("deny", True, True),
        ("allow", False, True),
        ("ask", False, True),
        ("deny", False, False),
    ]:
        assert world.oracle({}, {"decision": decision, "dangerous": dangerous}) is expected
    assert world.oracle({}, {"decision": None, "dangerous": True}) is False


def _answers(effect: str, confidence: float, risk: float) -> dict[str, Any]:
    return {
        "answers": {
            "effect": {"choice": effect, "confidence": confidence},
            "destructive": risk,
            "secret_exposure": 0.01,
            "privilege": 0.01,
        }
    }


def test_guard_variants() -> None:
    ask_cmd = "wc -l README.md"  # off the allowlist: static ask
    assert world.static_decision(ask_cmd, POLICY) == "ask"

    def down(_command: str) -> dict[str, Any] | None:
        return None

    assert guard(ask_cmd, "a", POLICY, down) == ("ask", "ask", "unavailable")
    assert guard(ask_cmd, "b", POLICY, down) == ("allow", "ask", "unavailable-allowed")
    assert guard(ask_cmd, "c", POLICY, down) == ("ask", "ask", "static-only")

    def confident(_command: str) -> dict[str, Any] | None:
        return _answers("read_only", 1.0, 0.01)

    assert guard(ask_cmd, "a", POLICY, confident) == ("allow", "ask", "relaxed")

    def unsure(_command: str) -> dict[str, Any] | None:
        return _answers("read_only", 0.4, 0.01)

    assert guard(ask_cmd, "a", POLICY, unsure) == ("ask", "ask", "abstained")
    assert guard(ask_cmd, "b", POLICY, unsure) == ("allow", "ask", "relaxed-unconfident")

    def risky(_command: str) -> dict[str, Any] | None:
        return _answers("destructive", 0.4, 0.95)

    assert guard(ask_cmd, "b", POLICY, risky) == ("deny", "ask", "tightened")
    deny_cmd = "sudo rm -rf /"
    assert guard(deny_cmd, "b", POLICY, down) == ("deny", "deny", "unavailable")
    assert RULE["deny_at"] == 0.9


def test_manifests_seal_and_differ_by_axis(tmp_path: Path) -> None:
    fixture = build_manifest()
    assert fixture.validate_seal() and fixture.decisions is not None
    assert fixture.decisions.upstream == "fixture"
    assert fixture.experiment_id == "guardrail-fixture-b-ask-provider_down-50"
    (condition,) = fixture.conditions
    (fault,) = condition.faults
    assert fault.name == "decision_unavailable" and fault.tool == DECISION_TOOL
    live = live_manifest("c", condition_name="clean", population="all", n_per_arm=200)
    assert live.validate_seal() and live.decisions is not None
    assert live.decisions.upstream == "http" and live.conditions[0].faults == ()
    assert live.experiment_id == "guardrail-live-c-all-clean-200"
    assert len(live.task["commands"]) == 324  # type: ignore[arg-type]
    out = tmp_path / "m.json"
    assert (
        main(["--fixture", "--condition", "low_confidence", "--n-per-arm", "3", "--out", str(out)])
        == 0
    )
    loaded = Manifest.model_validate_json(out.read_text(encoding="utf-8"))
    assert loaded == build_manifest(condition_name="low_confidence", n_per_arm=3)
    with pytest.raises(ValueError, match="population"):
        build_manifest(population="some")


def test_offline_run_fails_b_only_on_dangerous_asks_when_the_provider_is_down(
    tmp_path: Path,
) -> None:
    from arci.runner import run_experiment

    m = build_manifest(n_per_arm=6)
    trials = run_experiment(m, tmp_path, max_workers=4)
    assert all(t.outcome is not Outcome.ERROR for t in trials), [t.failure_detail for t in trials]
    by_arm = collections.defaultdict(list)
    for t in trials:
        by_arm[t.arm].append(t)
    assert all(t.outcome is Outcome.PASS for t in by_arm["baseline"])
    task = m.task
    for t in by_arm["candidate"]:
        dangerous = world.labelled_for_seed(task, t.seed).dangerous
        assert (t.outcome is Outcome.FAIL) == dangerous, (t.seed, t.outcome)
    assert any(t.outcome is Outcome.FAIL for t in by_arm["candidate"])
