"""Honesty under misbehaviour: findings from the checkpoint-2 adversarial review. FROZEN.

Trust model (docs/TRUST_MODEL.md): the agent is the user's own code, not an adversary, but it
may be buggy in any of these ways. None of them may turn into a wrong verdict.
"""

from __future__ import annotations

import base64
import subprocess
import sys
import time
from pathlib import Path

import pytest

from arci.hashing import hash_bytes
from arci.schema import (
    Bucket,
    Condition,
    Event,
    FaultSpec,
    Outcome,
    ReplayBundle,
    ReplayStatus,
    Termination,
    ToolMode,
    TrialEnvelope,
)
from tests.acceptance.helpers import COND_CLEAN, MOD, contract, manifest, spec

pytestmark = pytest.mark.acceptance
REPO = Path(__file__).resolve().parents[2]


def _run(agent: str, **kw: object) -> tuple[TrialEnvelope, list[Event]]:
    from arci.runner import run_trial

    seen: list[Event] = []
    oracle = str(kw.pop("oracle", "oracle"))
    env = run_trial(spec(agent, **kw), seen.append, contract(oracle))  # pyright: ignore[reportArgumentType]
    return env, seen


def _terminated(pid: int) -> bool:
    stat = subprocess.run(
        ["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True, check=False
    ).stdout.strip()
    return stat == "" or stat.startswith("Z")


def _shape(events: tuple[Event, ...] | list[Event]) -> list[tuple[int, str]]:
    return [(e.seq, e.kind) for e in events]


# --- harness faults are ERROR, whatever the agent does about them ---------------


def test_a_broken_injector_is_a_harness_error_even_if_the_agent_swallows_it() -> None:
    broken = Condition(
        condition_id="broken",
        faults=(FaultSpec(name=f"{MOD}:broken_perturbation", bucket=Bucket.FALSIFY, tool="fetch"),),
    )
    env, _ = _run("swallowing_agent", condition=broken)
    assert env.final_state is not None and env.final_state.get("stored") == 42  # it "worked"
    assert env.outcome is Outcome.ERROR and env.termination is Termination.HARNESS_ERROR


def test_a_failing_event_sink_is_a_harness_error_not_a_silent_pass() -> None:
    from arci.runner import run_trial

    def sink(event: Event) -> None:
        raise OSError("disk full")

    env = run_trial(spec("good_agent", condition=COND_CLEAN), sink, contract())
    assert env.outcome is Outcome.ERROR and env.termination is Termination.HARNESS_ERROR
    assert env.validate_seal()


def test_junk_on_the_protocol_channel_yields_a_sealed_error_envelope() -> None:
    env, _ = _run("garbage_agent", condition=COND_CLEAN)
    assert env.validate_seal()
    assert env.outcome is Outcome.ERROR and env.termination is Termination.HARNESS_ERROR
    kinds = [e.kind for e in env.events]
    assert "tool_finish" in kinds  # the valid events before the junk are kept
    assert kinds.count("trial_end") == 1 and kinds[-1] == "trial_end"


def test_a_hanging_grader_is_a_bounded_grader_error() -> None:
    started = time.monotonic()
    env, _ = _run("good_agent", condition=COND_CLEAN, oracle="hanging_oracle", grader_seconds=2.0)
    assert time.monotonic() - started < 30
    assert env.outcome is Outcome.ERROR and env.termination is Termination.GRADER_ERROR


def test_grader_noise_does_not_leak_into_the_seal() -> None:
    a, _ = _run("good_agent", condition=COND_CLEAN, oracle="noisy_oracle")
    b, _ = _run("good_agent", condition=COND_CLEAN, oracle="noisy_oracle")
    assert a.outcome is Outcome.ERROR and a.record_sha256 == b.record_sha256


# --- the agent cannot hide its own misbehaviour ----------------------------------


def test_swallowed_budget_exhaustion_is_still_a_failure() -> None:
    env, _ = _run("budget_swallower", condition=COND_CLEAN, max_tool_calls=5)
    assert env.final_state is not None and env.final_state.get("stored") == 42
    assert env.outcome is Outcome.FAIL and env.termination is Termination.BUDGET


def test_mutating_a_returned_value_cannot_rewrite_the_record() -> None:
    env, _ = _run("mutating_agent", condition=COND_CLEAN)
    fetched = next(r for r in env.recording if r.tool == "fetch")
    assert fetched.result.value == {"key": "answer", "value": 42}
    finish = next(
        e for e in env.events if e.kind == "tool_finish" and e.payload.get("tool") == "fetch"
    )
    assert finish.payload.get("value") == {"key": "answer", "value": 42}
    assert env.outcome is Outcome.PASS


def test_a_nonzero_exit_after_completion_is_a_crash() -> None:
    env, _ = _run("atexit_exit_agent", condition=COND_CLEAN)
    assert env.outcome is Outcome.FAIL and env.termination is Termination.CRASH


def test_a_worker_that_will_not_exit_times_out_with_one_terminal_event() -> None:
    env, seen = _run("atexit_hang_agent", condition=COND_CLEAN, max_seconds=3.0)
    assert env.outcome is Outcome.FAIL and env.termination is Termination.TIMEOUT
    assert _shape(seen) == _shape(env.events)  # what was persisted is what was sealed
    assert [k for _, k in _shape(seen)].count("trial_end") == 1
    assert [s for s, _ in _shape(seen)] == list(range(len(seen)))


def test_descendants_are_cleaned_up_after_a_successful_trial(tmp_path: Path) -> None:
    pid_file = tmp_path / "orphan.pid"
    env, _ = _run("orphan_agent", condition=COND_CLEAN, task={"pid_file": str(pid_file)})
    assert env.outcome is Outcome.PASS
    orphan = int(pid_file.read_text())
    deadline = time.monotonic() + 10
    while not _terminated(orphan) and time.monotonic() < deadline:
        time.sleep(0.1)
    assert _terminated(orphan), "a successful trial left a process behind"


# --- replay ------------------------------------------------------------------------


def test_leftover_recording_is_invalid_even_when_the_agent_raises() -> None:
    from arci.replay import make_bundle, replay

    env, _ = _run("uncaught_agent")
    assert env.outcome is Outcome.FAIL
    bundle = make_bundle(manifest(candidate="uncaught_agent"), env, spec("uncaught_agent"))
    assert replay(bundle).status is ReplayStatus.REPRODUCED
    padded = bundle.spec.model_copy(
        update={"recording": (*bundle.spec.recording, bundle.spec.recording[-1])}
    )
    data = bundle.model_dump(exclude={"record_sha256"})
    assert replay(ReplayBundle.create(**{**data, "spec": padded})).status is ReplayStatus.INVALID


def _embedded_variant(source: str) -> ReplayBundle:
    """A live-mode bundle for the fragile agent whose EMBEDDED fixture module is `source`."""
    from arci.replay import make_bundle

    env, _ = _run("fragile_agent")
    base = make_bundle(
        manifest(),
        env,
        spec("fragile_agent"),
        root=REPO,
        include=(
            "tests/__init__.py",
            "tests/acceptance/__init__.py",
            "tests/acceptance/fixture_agents.py",
        ),
    )
    path = "tests/acceptance/fixture_agents.py"
    raw = source.encode()
    data = base.model_dump(exclude={"record_sha256"})
    live = base.spec.model_copy(
        update={"tool_mode": ToolMode.RECORD, "recording": (), "replay_final_state": None}
    )
    return ReplayBundle.create(
        **{
            **data,
            "spec": live,
            "files": {**base.files, path: base64.b64encode(raw).decode()},
            "fixtures": {**base.fixtures, path: hash_bytes(raw)},
        }
    )


def test_embedded_code_wins_over_the_checkout_on_the_import_path() -> None:
    """Replayed from inside the checkout, where a module of the same name exists."""
    from arci.replay import replay

    original = (REPO / "tests/acceptance/fixture_agents.py").read_text()
    assert replay(_embedded_variant(original)).status is ReplayStatus.REPRODUCED
    repaired = (
        original + "\\n\\nfragile_agent = good_agent  # the embedded copy is the repaired one\\n"
    )
    result = replay(_embedded_variant(repaired))
    assert result.status is ReplayStatus.NOT_REPRODUCED
    assert result.observed_outcome is Outcome.PASS


def test_replay_leaves_the_callers_import_state_alone() -> None:
    from arci.replay import replay

    before_path, before_modules = list(sys.path), set(sys.modules)
    original = (REPO / "tests/acceptance/fixture_agents.py").read_text()
    marker = original + "\\n\\nimport json as zz_bundle_only_marker  # noqa: F401\\n"
    assert replay(_embedded_variant(marker)).status is ReplayStatus.REPRODUCED
    assert sys.path == before_path
    leaked = {m for m in set(sys.modules) - before_modules if not m.startswith(("arci", "_"))}
    assert not {m for m in leaked if "fixture_agents" in m}


def test_bundle_paths_cannot_escape_the_payload_directory() -> None:
    from arci.replay import replay

    bundle = _embedded_variant((REPO / "tests/acceptance/fixture_agents.py").read_text())
    data = bundle.model_dump(exclude={"record_sha256"})
    raw = b"print('escaped')\\n"
    for evil in ("../escape.py", "/tmp/arci-escape.py", "a/../../escape.py"):
        forged = ReplayBundle.create(
            **{
                **data,
                "files": {**bundle.files, evil: base64.b64encode(raw).decode()},
                "fixtures": {**bundle.fixtures, evil: hash_bytes(raw)},
            }
        )
        assert replay(forged).status is ReplayStatus.INVALID


# --- statistics at the edge of the supported range --------------------------------

CP_EDGE = [  # alpha = 1e-6, K = 1: per-arm tail 2.5e-7, confidence 0.9999995
    (10000, 10000, 0.998480974397, 1.0),
    (9990, 10000, 0.996371411368, 0.999890624362),
    (0, 10000, 0.0, 0.001519025603),
    (190, 200, 0.829920472982, 0.994422498826),
    (5, 10, 0.016037872750, 0.983962127250),
]


@pytest.mark.parametrize(("x", "n", "low", "high"), CP_EDGE)
def test_clopper_pearson_is_exact_at_the_smallest_supported_alpha(
    x: int, n: int, low: float, high: float
) -> None:
    from arci.stats import clopper_pearson_tail

    got_low, got_high = clopper_pearson_tail(x, n, 2.5e-7)
    assert got_low == pytest.approx(low, rel=0, abs=1e-9)
    assert got_high == pytest.approx(high, rel=0, abs=1e-9)


def test_alpha_outside_the_supported_range_is_rejected_at_the_manifest() -> None:
    from pydantic import ValidationError

    from arci.schema import Manifest

    data = manifest().model_dump(exclude={"record_sha256"})
    for bad in (1e-20, 0.0, 0.75):
        with pytest.raises(ValidationError):
            Manifest.create(**{**data, "alpha": bad})
    assert Manifest.create(**{**data, "alpha": 1e-6}).validate_seal()


def test_the_gate_uses_the_tail_directly_at_the_smallest_alpha() -> None:
    from arci.gate import decide
    from tests.acceptance.helpers import synthetic_trials

    m = manifest(alpha=1e-6)
    d = decide(
        m,
        synthetic_trials(
            m, condition_id="fetch_timeout", baseline_successes=190, candidate_successes=190
        ),
    )
    c = d.conditions[0]
    assert c.baseline.cp_low == pytest.approx(0.829920472982, rel=0, abs=1e-9)
    assert c.delta_low == pytest.approx(0.829920472982 - 0.994422498826, rel=0, abs=1e-8)
