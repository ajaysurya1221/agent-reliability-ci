"""v0.6: the official JavaScript SDK against the boundary, unmodified. FROZEN.

Runs only when `node` is on PATH and `@typesafe-ai/sdk` is installed under the example directory
(`npm ci` there). Proves the zero-change claim for the second SDK the way `test_decisions_sdk.py`
does for Python: `new TypeSafeClient()` reads the endpoint and token from the environment.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from arci.schema import DECISION_TOOL, Outcome, Verdict

REPO = Path(__file__).resolve().parents[2]
SDK = (
    REPO
    / "examples"
    / "jev_triage_agent"
    / "node_modules"
    / "@typesafe-ai"
    / "sdk"
    / "package.json"
)

pytestmark = [
    pytest.mark.acceptance,
    pytest.mark.skipif(shutil.which("node") is None, reason="node absent"),
    pytest.mark.skipif(not SDK.exists(), reason="@typesafe-ai/sdk not installed in the example"),
]


def test_the_node_agent_tells_a_from_b_through_the_same_boundary(tmp_path: Path) -> None:
    from arci.gate import decide
    from arci.runner import run_experiment
    from examples.jev_triage_agent.experiment import build_manifest

    for candidate, expected in (("b", Verdict.BLOCK), ("a", Verdict.PASS)):
        m = build_manifest(
            n_per_arm=50, candidate=candidate, runtime="node"
        )  # A vs A needs 50 to PASS
        assert m.validate_seal()
        trials = run_experiment(m, tmp_path / candidate, max_workers=4)
        d = decide(m, trials)
        assert d.verdict is expected, (candidate, d.reasons, [t.failure_detail for t in trials])
        assert all(t.outcome is not Outcome.ERROR for t in trials)
        assert all(any(r.tool == DECISION_TOOL for r in t.recording) for t in trials)


def test_one_clean_pair_passes_for_the_node_agent() -> None:
    from arci.runner import run_trial
    from arci.schedule import build_schedule
    from examples.jev_triage_agent.experiment import clean_manifest

    m = clean_manifest(candidate="b", runtime="node")
    for spec in build_schedule(m)[:2]:
        env = run_trial(spec, lambda _e: None, m.contract)
        assert env.outcome is Outcome.PASS, (spec.variant, env.failure_detail)
