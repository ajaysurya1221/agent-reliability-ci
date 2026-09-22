"""Hero demo 2: a Jev-style triage agent, offline, no key, no model. FROZEN.

Story: A gates on confidence and escalates when unsure. B is the regression: on low confidence it
returns without acting. The frozen experiment under `decision_low_confidence` BLOCKs B, a clean
illustrative run cannot tell them apart, the failure replays offline and minimises to the one
decision fault, and the repaired C passes.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from arci.schema import DECISION_TOOL, Outcome, ReplayStatus, Verdict

pytestmark = pytest.mark.acceptance


@pytest.mark.parametrize(
    ("candidate", "expected"),
    [("b", Verdict.BLOCK), ("a", Verdict.PASS), ("c", Verdict.PASS)],
)
def test_frozen_experiment_blocks_the_regression_and_passes_the_repair(
    tmp_path: Path, candidate: str, expected: Verdict
) -> None:
    from arci.gate import decide
    from arci.runner import run_experiment
    from examples.jev_triage_agent.experiment import build_manifest

    m = build_manifest(n_per_arm=50, candidate=candidate)
    assert m.n_per_arm == 50 and m.validate_seal()
    assert m.decisions is not None and m.decisions.upstream == "fixture"
    trials = run_experiment(m, tmp_path, max_workers=8)
    d = decide(m, trials)
    assert d.verdict is expected, d.reasons
    assert all(t.outcome is not Outcome.ERROR for t in trials)
    assert all(any(r.tool == DECISION_TOOL for r in t.recording) for t in trials)


def test_one_clean_run_hides_the_regression() -> None:
    from arci.runner import run_trial
    from arci.schedule import build_schedule
    from examples.jev_triage_agent.experiment import clean_manifest

    m = clean_manifest(candidate="b")
    first_pair = build_schedule(m)[:2]
    for spec in first_pair:
        env = run_trial(spec, lambda _e: None, m.contract)
        assert env.outcome is Outcome.PASS, (spec.variant, env.failure_detail)


def test_the_failure_replays_offline_minimises_and_the_repair_passes(tmp_path: Path) -> None:
    from arci.minimize import minimize_faults
    from arci.replay import make_bundle, replay
    from arci.runner import run_trial
    from arci.schedule import build_schedule
    from examples.jev_triage_agent.experiment import build_manifest, noisy_manifest

    noisy = noisy_manifest(candidate="b")
    spec = next(s for s in build_schedule(noisy) if s.arm == "candidate")
    env = run_trial(spec, lambda _e: None, noisy.contract)
    assert env.outcome is Outcome.FAIL
    reduced = minimize_faults(noisy, env, spec)
    assert reduced.kept == ("decision_low_confidence",) and reduced.minimality == "1-minimal"
    assert replay(reduced.bundle).status is ReplayStatus.REPRODUCED

    m = build_manifest(n_per_arm=1, candidate="b")
    failing = next(s for s in build_schedule(m) if s.arm == "candidate")
    env = run_trial(failing, lambda _e: None, m.contract)
    bundle = make_bundle(m, env, failing)
    (bundle_path := tmp_path / "bundle.json").write_text(bundle.model_dump_json())
    assert replay(bundle).status is ReplayStatus.REPRODUCED
    repaired = build_manifest(n_per_arm=1, candidate="c")
    fixed = next(s for s in build_schedule(repaired) if s.arm == "candidate")
    assert run_trial(fixed, lambda _e: None, repaired.contract).outcome is Outcome.PASS
    assert bundle_path.exists()
