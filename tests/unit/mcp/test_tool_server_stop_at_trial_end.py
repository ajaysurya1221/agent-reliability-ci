"""Stopping the MCP tool server at the end of a command trial.

Blind end-to-end tests: each one runs a single command trial through `arci.runner.run_trial`,
the same public entry point the MCP acceptance tests use, with the Python bridge
(`arci.mcp_toolset_server`) as the tool server.

The bridge writes its first `state.json` only once its toolset factory has returned. A trial's
`final_state` is read from that file after the trial. If the boundary kills the server at the end
of the trial without letting it finish starting and exit by itself, an agent that never used the
server is graded on `{}` instead of the toolset's starting state, and which of the two it gets
depends on timing. The pinned rules forbid that ("No outcome may depend on scheduling luck"; a
seeded scripted trial must give an identical envelope), and the MCP stdio shutdown sequence is:
close the server's input, wait for it to exit, and only then signal it.

The factories below sleep deliberately, so that today the server is ALWAYS still inside its
factory when the boundary kills it: the outcome is the wrong one every time, not by luck. Once the
boundary closes the server's input and waits for it to exit (within the trial's deadline), the
bridge finishes its factory, writes its starting snapshot, reads EOF and exits by itself, so the
trial is graded on the starting state every time.
"""

from __future__ import annotations

import sys
import time

from pydantic import JsonValue

from arci.runner import run_trial
from arci.schema import (
    Budgets,
    CommandSpec,
    DecisionSpec,
    Event,
    McpServerSpec,
    Outcome,
    TrialEnvelope,
    TrialSpec,
)
from tests.acceptance.decision_fixtures import PINNED_MODEL
from tests.acceptance.fixture_agents import World, make_world
from tests.acceptance.helpers import COND_CLEAN
from tests.acceptance.mcp_fixtures import mcp_contract, mcp_spec

ME = "tests.unit.mcp.test_tool_server_stop_at_trial_end"
DECISION_FIXTURE = "tests.acceptance.decision_fixtures:fixture"

# World.snapshot() before any tool call.
STARTING_STATE: dict[str, JsonValue] = {"stored": None, "log": []}

# Without decisions, the parent waits half of the time left before the deadline after the agent
# exits, then sends the boundary SIGTERM. With MAX_SECONDS_NO_DECISIONS = 16 and an agent that
# exits at once (t_a well under a second), that signal comes at about 8 + t_a / 2 seconds. The
# bridge cannot have written its first snapshot before 9 seconds (its factory alone sleeps
# SLOW_FACTORY_SECONDS) plus its own start-up, so today it is always killed first. Once the
# boundary waits, it gives the bridge half of the roughly 8 seconds then left, to about 12
# seconds, and the bridge is done at about 9.5: some 2.5 seconds of room on a slow machine.
# (The first version of this file used 5 and 8 seconds; a reviewer measured only about one
# second of room with those, so the orchestrator widened them. One trial of this kind is enough;
# the three-run test below uses the quicker decision lifetime.)
SLOW_FACTORY_SECONDS = 9.0
MAX_SECONDS_NO_DECISIONS = 16.0

# With decisions configured, the parent signals the boundary as soon as the agent has exited, so a
# one-second factory is already always too slow today; ten seconds leaves ample room afterwards.
BRIEF_FACTORY_SECONDS = 1.0
MAX_SECONDS_DECISIONS = 10.0

# An agent that exits successfully at once and never starts the MCP shim.
SILENT_AGENT = CommandSpec(argv=(sys.executable, "-c", "raise SystemExit(0)"))


def make_slow_world(task: dict[str, JsonValue], seed: int) -> World:
    """Trusted toolset factory, run inside the bridge: deliberately slow to construct."""
    time.sleep(SLOW_FACTORY_SECONDS)
    return make_world(task, seed)


def make_briefly_slow_world(task: dict[str, JsonValue], seed: int) -> World:
    """Trusted toolset factory, run inside the bridge: slow, but less than the decision run."""
    time.sleep(BRIEF_FACTORY_SECONDS)
    return make_world(task, seed)


def _bridge(factory: str) -> McpServerSpec:
    return McpServerSpec(
        argv=(
            sys.executable,
            "-P",
            "-m",
            "arci.mcp_toolset_server",
            "--toolset",
            f"{ME}:{factory}",
            "--tools",
            "fetch,store,log",
            "--workdir",
            "{workdir}",
            "--seed",
            "{seed}",
        ),
        snapshot="arci.mcp_toolset_server:snapshot",
    )


def _trial(
    *,
    factory: str,
    max_seconds: float,
    command: CommandSpec | None = None,
    variant: str = "good",
    decisions: DecisionSpec | None = None,
) -> TrialSpec:
    base = mcp_spec(variant, condition=COND_CLEAN, max_seconds=max_seconds)
    return TrialSpec(
        experiment_id=base.experiment_id,
        trial_id=base.trial_id,
        pair_id=base.pair_id,
        arm=base.arm,
        variant=base.variant,
        command=base.command if command is None else command,
        mcp_server=_bridge(factory),
        decisions=decisions,
        task_id=base.task_id,
        task=base.task,
        condition=base.condition,
        seed=base.seed,
        budgets=Budgets(max_tool_calls=20, max_seconds=max_seconds),
    )


def _run(spec: TrialSpec) -> TrialEnvelope:
    sink: list[Event] = []
    return run_trial(spec, sink.append, mcp_contract())


def _silent_trial() -> TrialSpec:
    return _trial(
        factory="make_slow_world",
        max_seconds=MAX_SECONDS_NO_DECISIONS,
        command=SILENT_AGENT,
        variant="silent",
    )


def test_an_unused_slow_server_is_graded_on_its_starting_state() -> None:
    # Fails today: the boundary kills the bridge while it is still inside its factory (see the
    # timing note at SLOW_FACTORY_SECONDS), so no state.json exists and final_state is {}.
    # Passes once the boundary closes the server's input and waits for it to exit: the bridge
    # finishes start-up, writes the starting snapshot and exits on EOF.
    envelope = _run(_silent_trial())
    assert envelope.outcome is not Outcome.ERROR, envelope.failure_detail
    assert envelope.agent_claimed_success is True
    assert envelope.final_state == STARTING_STATE


def _silent_trial_with_decisions() -> TrialSpec:
    return _trial(
        factory="make_briefly_slow_world",
        max_seconds=MAX_SECONDS_DECISIONS,
        command=SILENT_AGENT,
        variant="silent",
        decisions=DecisionSpec(upstream="fixture", fixture=DECISION_FIXTURE, model=PINNED_MODEL),
    )


def test_an_unused_slow_server_gives_the_same_record_every_time() -> None:
    # Today all three runs are graded on {} (always killed first), so the hashes agree with one
    # another but the state is wrong: the starting-state assertion fails. Once the boundary waits
    # for the server, all three runs are graded on the starting state and the envelopes, hence
    # record_sha256, are identical because nothing in them depends on timing.
    envelopes = [_run(_silent_trial_with_decisions()) for _ in range(3)]
    assert len({envelope.record_sha256 for envelope in envelopes}) == 1
    assert [envelope.final_state for envelope in envelopes] == [STARTING_STATE] * 3


def test_a_tool_call_before_exit_is_graded_on_the_state_after_the_call() -> None:
    # Passes today and must keep passing: the bridge writes state.json before it answers a
    # tools/call, and the agent waits for that answer before it exits, so the post-call state is
    # on disk before any stop begins. A boundary that waits for the server must not lose it.
    envelope = _run(_trial(factory="make_briefly_slow_world", max_seconds=MAX_SECONDS_DECISIONS))
    assert envelope.outcome is Outcome.PASS, envelope.failure_detail
    assert envelope.final_state == {"stored": 42, "log": ["start"]}


def test_an_unused_slow_server_with_decisions_is_graded_on_its_starting_state() -> None:
    # Fails today: with decisions configured the parent signals the boundary as soon as the agent
    # has exited, and the boundary kills the bridge at once, about a second before its factory
    # returns, so final_state is {}. Passes once the boundary closes the server's input and waits
    # for it to exit before the deadline. The decision fixture is never called (the agent makes no
    # request); configuring it only switches the boundary to its decision lifetime.
    envelope = _run(_silent_trial_with_decisions())
    assert envelope.outcome is not Outcome.ERROR, envelope.failure_detail
    assert envelope.agent_claimed_success is True
    assert envelope.final_state == STARTING_STATE
