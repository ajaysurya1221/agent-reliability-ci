"""The never-cut deliverables: real example agents A/B/C and the gate's own calibration. FROZEN."""

from __future__ import annotations

from pathlib import Path

import pytest

from arci.schema import Outcome, ReplayStatus, ToolMode, Verdict

pytestmark = pytest.mark.acceptance


@pytest.mark.parametrize(
    ("candidate", "expected"),
    [("agent_b", Verdict.BLOCK), ("agent_a", Verdict.PASS), ("agent_c", Verdict.PASS)],
)
def test_frozen_experiment_blocks_the_regression_and_passes_the_repair(
    tmp_path: Path, candidate: str, expected: Verdict
) -> None:
    from arci.gate import decide
    from arci.runner import run_experiment
    from examples.retry_agent.experiment import build_manifest

    m = build_manifest(n_per_arm=200, candidate=candidate)
    assert m.n_per_arm == 200 and m.validate_seal()
    trials = run_experiment(m, tmp_path, max_workers=8)
    d = decide(m, trials)
    assert d.verdict is expected, d.reasons
    assert all(t.outcome is not Outcome.ERROR for t in trials)


def test_one_illustrative_run_hides_the_regression() -> None:
    """pass@1 on a clean run cannot tell A from B. That is the point of the tool."""
    from arci.runner import run_trial
    from arci.schedule import build_schedule
    from examples.retry_agent.experiment import build_manifest, clean_manifest

    m = clean_manifest(candidate="agent_b")
    first_pair = build_schedule(m)[:2]
    outcomes = [run_trial(s, lambda _e: None, m.contract).outcome for s in first_pair]
    assert outcomes == [Outcome.PASS, Outcome.PASS]
    assert build_manifest(n_per_arm=200, candidate="agent_b").conditions != m.conditions


def test_repaired_candidate_passes_the_reproducer() -> None:
    from arci.replay import make_bundle, replay
    from arci.runner import run_trial
    from arci.schedule import build_schedule
    from examples.retry_agent.experiment import build_manifest

    m = build_manifest(n_per_arm=200, candidate="agent_b")
    candidate_specs = [s for s in build_schedule(m) if s.arm == "candidate"]
    failing = None
    for s in candidate_specs[:40]:
        env = run_trial(s, lambda _e: None, m.contract)
        if env.outcome is Outcome.FAIL:
            failing = (s, env)
            break
    assert failing is not None, "agent_b never failed in 40 faulted trials"
    spec, env = failing
    bundle = make_bundle(m, env, spec)
    assert replay(bundle).status is ReplayStatus.REPRODUCED
    from arci.schema import ReplayBundle

    repaired_agent = build_manifest(n_per_arm=200, candidate="agent_c").candidate.agent
    data = bundle.model_dump(exclude={"record_sha256"})
    repaired = ReplayBundle.create(
        **{
            **data,
            "spec": bundle.spec.model_copy(
                update={
                    "agent": repaired_agent,
                    "tool_mode": ToolMode.RECORD,
                    "recording": (),
                    "replay_final_state": None,
                }
            ),
        }
    )
    result = replay(repaired)
    assert result.status is ReplayStatus.NOT_REPRODUCED
    assert result.observed_outcome is Outcome.PASS


def test_selfcheck_calibration_is_exact_and_honest() -> None:
    from bench.selfcheck import operating_characteristics

    def oc(p_a: float, p_b: float, n: int) -> dict[str, float]:
        out = operating_characteristics(p_a, p_b, n, alpha=0.05, delta=0.10)
        assert set(out) == {"PASS", "BLOCK", "INCONCLUSIVE"}
        assert sum(out.values()) == pytest.approx(1.0, abs=1e-9)
        return out

    assert oc(0.95, 0.65, 200)["BLOCK"] == pytest.approx(0.9849, abs=2e-3)  # power
    assert oc(0.95, 0.75, 200)["BLOCK"] == pytest.approx(0.3647, abs=2e-3)
    assert oc(0.95, 0.95, 200)["PASS"] == pytest.approx(0.8890, abs=2e-3)
    assert oc(0.80, 0.80, 200)["PASS"] == pytest.approx(0.2184, abs=2e-3)
    assert oc(0.95, 0.85, 200)["PASS"] <= 0.05  # false PASS at the margin boundary
    assert oc(0.95, 0.95, 200)["BLOCK"] <= 0.05  # false BLOCK under no change
    assert oc(0.95, 0.65, 20)["INCONCLUSIVE"] == pytest.approx(0.992345533306, abs=1e-6)
    assert oc(1.0, 0.0, 20)["BLOCK"] == pytest.approx(1.0)  # a total collapse still decides
