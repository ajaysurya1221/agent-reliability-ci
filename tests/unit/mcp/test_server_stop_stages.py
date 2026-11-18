"""The staged stop of the MCP tool server at the end of a trial (`arci.mcp_boundary.stop_server`).

Most tests drive `stop_server` (and the boundary's `_cleanup`, including its idle rule,
`_server_is_idle`) with a fake clock and a fake server process, so every stage is exact and
nothing sleeps. The rest use real processes: one shows that the server's output is drained while
the boundary waits; the others run whole command trials, among them a server that ignores EOF
and exits on SIGTERM, with an agent that used it (killed at once: idle) and one that never
connected (staged stop).
"""

from __future__ import annotations

import io
import math
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, cast

import pytest

import arci.mcp_boundary as boundary_module
from arci import mcp_toolset_server, runner
from arci.mcp_boundary import stop_server, trial_deadline
from arci.runner import run_trial
from arci.schema import (
    Budgets,
    CommandSpec,
    DecisionSpec,
    Event,
    McpServerSpec,
    Outcome,
    Termination,
    TrialEnvelope,
    TrialSpec,
)
from tests.acceptance.decision_fixtures import PINNED_MODEL
from tests.acceptance.helpers import COND_CLEAN
from tests.acceptance.mcp_fixtures import mcp_contract, mcp_spec

ME = "tests.unit.mcp.test_server_stop_stages"
Boundary = vars(boundary_module)["_Boundary"]
TICK = 0.05
START = 100.0


class FakeClock:
    def __init__(self, now: float = START) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


class FakeStdin:
    def __init__(self, server: FakeServer) -> None:
        self.server = server

    def close(self) -> None:
        self.server.close_input()


class FakeServer:
    """A server process on a fake clock.

    `exit_after_eof`: seconds after its input closes at which it writes its first snapshot and
    exits (None: it ignores EOF). The snapshot and the exit happen only while the stopper
    yields (in `idle` / `wait`), never during `close_input` itself, as with a real process that
    is still finishing its start-up when its input closes.
    """

    def __init__(
        self,
        clock: FakeClock,
        *,
        exit_after_eof: float | None = None,
        exits_on_sigterm: bool = False,
    ) -> None:
        self.clock = clock
        self.exit_after_eof = exit_after_eof
        self.exits_on_sigterm = exits_on_sigterm
        self.returncode: int | None = None
        self.input_closed_at: float | None = None
        self.snapshot_written = False
        self.log: list[tuple[str, float]] = []
        self.stdin = FakeStdin(self)
        self.stdout = None

    def close_input(self) -> None:
        self.log.append(("close_input", self.clock.now))
        self.input_closed_at = self.clock.now

    def advance(self, seconds: float) -> None:
        self.clock.now += seconds
        if (
            self.returncode is None
            and self.input_closed_at is not None
            and self.exit_after_eof is not None
            and self.clock.now >= self.input_closed_at + self.exit_after_eof
        ):
            self.snapshot_written = True
            self.returncode = 0

    def poll(self) -> int | None:
        return self.returncode

    def terminate(self) -> None:
        self.log.append(("terminate", self.clock.now))
        if self.returncode is None and self.exits_on_sigterm:
            self.returncode = -15

    def kill(self) -> None:
        self.log.append(("kill", self.clock.now))
        if self.returncode is None:
            self.returncode = -9

    def wait(self, timeout: float | None = None) -> int:
        if self.returncode is not None:
            return self.returncode
        if timeout is None:
            raise AssertionError("waited forever on a fake server that is still running")
        self.log.append(("idle", timeout))
        self.advance(timeout)
        if self.returncode is None:
            raise subprocess.TimeoutExpired("fake-server", timeout)
        return self.returncode

    def signals(self) -> list[tuple[str, float]]:
        return [entry for entry in self.log if entry[0] in {"terminate", "kill"}]

    def idles(self) -> list[float]:
        return [value for kind, value in self.log if kind == "idle"]


def _stop(server: FakeServer, remaining: float) -> None:
    def idle(seconds: float) -> None:
        server.log.append(("idle", seconds))
        server.advance(seconds)

    stop_server(
        server,
        close_input=server.close_input,
        idle=idle,
        remaining=remaining,
        clock=server.clock,
        tick=TICK,
    )


def test_a_server_that_exits_after_eof_is_never_signalled_and_keeps_its_snapshot() -> None:
    clock = FakeClock()
    server = FakeServer(clock, exit_after_eof=0.3)
    _stop(server, remaining=10.0)
    assert server.signals() == []
    assert server.returncode == 0
    assert server.snapshot_written
    assert server.log[0] == ("close_input", START)


def test_the_first_snapshot_needs_the_exit_wait_and_killing_first_prevents_it() -> None:
    # The consultant's regression: the server's first snapshot becomes available only once the
    # stopper yields to its exit wait after EOF.
    clock = FakeClock()
    waited = FakeServer(clock, exit_after_eof=0.0)
    _stop(waited, remaining=10.0)
    assert waited.snapshot_written
    assert waited.signals() == []
    assert waited.idles() == [TICK]

    # Documentation of the old behaviour only (it drives the fake, not the boundary): the old
    # cleanup closed the input, then killed at once if still running, and never yielded.
    killed = FakeServer(FakeClock(), exit_after_eof=0.0)
    killed.close_input()
    if killed.poll() is None:
        killed.kill()
    assert not killed.snapshot_written
    assert killed.returncode == -9


def test_a_server_that_ignores_eof_and_sigterm_gets_sigterm_then_sigkill_on_time() -> None:
    clock = FakeClock()
    server = FakeServer(clock)
    remaining = 8.0
    _stop(server, remaining=remaining)
    assert server.signals() == [
        ("terminate", START + remaining / 2),
        ("kill", START + remaining * 3 / 4),
    ]
    # Never earlier: no idle crosses a stage, and each one is at most a tick.
    assert all(0 < value <= TICK for value in server.idles())
    assert math.isclose(sum(server.idles()), remaining * 3 / 4)
    assert server.returncode == -9


def test_a_server_that_exits_on_sigterm_is_not_killed() -> None:
    clock = FakeClock()
    server = FakeServer(clock, exits_on_sigterm=True)
    _stop(server, remaining=6.0)
    assert server.signals() == [("terminate", START + 3.0)]
    assert server.returncode == -15
    assert clock.now == START + 3.0


@pytest.mark.parametrize("remaining", [0.0, -1.0, math.nan])
def test_no_time_left_kills_at_once(remaining: float) -> None:
    clock = FakeClock()
    server = FakeServer(clock, exit_after_eof=0.0, exits_on_sigterm=True)
    _stop(server, remaining=remaining)
    assert server.log == [("close_input", START), ("kill", START)]
    assert server.idles() == []
    assert not server.snapshot_written


def test_the_stop_returns_as_soon_as_the_server_exits() -> None:
    clock = FakeClock()
    # Exits during the third idle (2.5 ticks after EOF): no fourth idle, no signal.
    server = FakeServer(clock, exit_after_eof=2.5 * TICK)
    _stop(server, remaining=20.0)
    assert len(server.idles()) == 3
    assert math.isclose(clock.now, START + 3 * TICK)
    assert server.signals() == []


def test_a_server_already_gone_is_neither_waited_for_nor_signalled() -> None:
    clock = FakeClock()
    server = FakeServer(clock)
    server.returncode = 1
    _stop(server, remaining=20.0)
    assert server.log == [("close_input", START)]


def test_the_time_left_is_measured_when_cleanup_starts_not_when_the_boundary_was_built(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(boundary_module, "_PROTOCOL", io.BytesIO())
    clock = FakeClock()
    server = FakeServer(clock)
    instance = Boundary(
        "nonce",
        mcp_spec("good", condition=COND_CLEAN),
        "unused",
        str(tmp_path),
        deadline=START + 8.0,
        clock=clock,
    )
    instance.server = cast(Any, server)
    clock.now += 4.0  # the trial ran for 4 s before cleanup; 4 s are left
    entry = clock.now
    instance._cleanup()
    assert server.signals() == [("terminate", entry + 2.0), ("kill", entry + 3.0)]


def test_the_boundary_deadline_is_never_later_than_the_parent_deadline() -> None:
    # Shared clock (macOS and Linux): the parent's reading is the exact deadline, earlier than
    # the one anchored after this process's start-up.
    assert trial_deadline(10.1, 3.9, 13.9) == 13.9
    # A parent reading that was somehow too late is capped by the anchored one.
    assert trial_deadline(10.1, 3.9, 99.0) == 14.0
    # One that was too early only shortens the stop.
    assert trial_deadline(10.1, 3.9, 1.0) == 1.0


def test_the_runner_passes_the_time_left_and_its_own_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[dict[str, object]] = []
    original = runner.canonical_json

    def recording(value: Any) -> bytes:
        if isinstance(value, dict) and "socket_path" in value and "nonce" in value:
            seen.append(cast(dict[str, object], value))
        return original(value)

    monkeypatch.setattr(runner, "canonical_json", recording)
    max_seconds = 20.0
    before = time.monotonic()
    run_trial(
        mcp_spec("silent", condition=COND_CLEAN, max_seconds=max_seconds),
        lambda _: None,
        mcp_contract(),
    )
    after = time.monotonic()
    assert len(seen) == 1
    left = cast(float, seen[0]["seconds_remaining"])
    deadline = cast(float, seen[0]["deadline_monotonic"])
    assert before + max_seconds <= deadline <= after + max_seconds
    # The time LEFT at launch, not the budget: some of the budget is already spent.
    assert 0.0 < left < max_seconds
    # Measured at launch: the parent's clock then lies between `before` and `after`.
    assert before <= deadline - left <= after


def _cleanup_frames(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, server: FakeServer
) -> tuple[bytes, bytes, int]:
    protocol = io.BytesIO()
    monkeypatch.setattr(boundary_module, "_PROTOCOL", protocol)
    instance = Boundary(
        "nonce",
        mcp_spec("good", condition=COND_CLEAN),
        "unused",
        str(tmp_path),
        deadline=server.clock.now + 8.0,
        clock=server.clock,
    )
    instance.server = cast(Any, server)
    seq = instance.emitter.seq
    instance._cleanup()
    during = protocol.getvalue()
    instance.write_result()
    return during, protocol.getvalue()[len(during) :], instance.emitter.seq - seq


def test_nothing_about_the_stop_reaches_an_event_a_latch_or_the_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    quick = FakeServer(FakeClock(), exit_after_eof=0.1)
    stubborn = FakeServer(FakeClock())
    quick_during, quick_result, quick_events = _cleanup_frames(tmp_path, monkeypatch, quick)
    stub_during, stub_result, stub_events = _cleanup_frames(tmp_path, monkeypatch, stubborn)

    # The boundary's own cleanup used the trial deadline, through the injected clock.
    assert quick.signals() == []
    assert stubborn.signals() == [("terminate", START + 4.0), ("kill", START + 6.0)]
    # No frame (event, latch, recording) during the stop, and an identical result frame.
    assert quick_during == stub_during == b""
    assert quick_events == stub_events == 0
    assert quick_result == stub_result
    assert b'"termination":"completed"' in quick_result


Pending = vars(boundary_module)["_Pending"]
id_key = vars(boundary_module)["_id_key"]
REMAINING = 8.0
STAGED = [("terminate", START + REMAINING / 2), ("kill", START + REMAINING * 3 / 4)]


class FakeConnection:
    """The agent's MCP socket, enough for the boundary to answer one forwarded request."""

    def __init__(self) -> None:
        self.sent = bytearray()

    def sendall(self, data: bytes) -> None:
        self.sent.extend(data)

    def close(self) -> None:
        pass


def _add_pending(instance: Any, upstream_id: int, client_id: int) -> None:
    # What `_forward` records for a request it sends to the server (without writing it).
    instance.pending[id_key(upstream_id)] = Pending(
        method="ping",
        rpc_id=client_id,
        client_key=id_key(client_id),
        occurrence=0,
        arguments={},
    )
    instance.client_pending.add(id_key(client_id))


def _boundary(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, server: FakeServer) -> Any:
    monkeypatch.setattr(boundary_module, "_PROTOCOL", io.BytesIO())
    instance = Boundary(
        "nonce",
        mcp_spec("good", condition=COND_CLEAN),
        "unused",
        str(tmp_path),
        deadline=server.clock.now + REMAINING,
        clock=server.clock,
    )
    instance.server = cast(Any, server)
    instance.connection = FakeConnection()
    return instance


def _answered(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, server: FakeServer) -> Any:
    """A boundary whose server has answered the one request it forwarded: idle."""
    instance = _boundary(tmp_path, monkeypatch, server)
    _add_pending(instance, 0, 7)
    instance._server_message(b'{"id":0,"jsonrpc":"2.0","result":{}}')
    assert instance.server_answered
    assert instance._server_is_idle()
    return instance


def test_an_idle_server_that_ignores_eof_is_killed_at_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    server = FakeServer(FakeClock())
    instance = _answered(tmp_path, monkeypatch, server)
    instance._cleanup()
    # Exactly the stop from before the staged one: close, kill, no wait, reaped.
    assert server.log == [("close_input", START), ("kill", START)]
    assert server.idles() == []
    assert server.clock.now == START
    assert server.returncode == -9


def test_an_idle_server_that_already_exited_is_only_reaped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    server = FakeServer(FakeClock())
    instance = _answered(tmp_path, monkeypatch, server)
    server.returncode = 0
    instance._cleanup()
    assert server.log == [("close_input", START)]


def test_condition_1_a_server_that_never_answered_gets_the_staged_stop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    server = FakeServer(FakeClock())
    instance = _boundary(tmp_path, monkeypatch, server)
    assert not instance._server_is_idle()
    instance._cleanup()
    assert server.signals() == STAGED


@pytest.mark.parametrize("field", ["pending", "client_pending", "tools_inflight"])
def test_condition_2_a_request_without_its_response_gets_the_staged_stop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, field: str
) -> None:
    server = FakeServer(FakeClock())
    instance = _answered(tmp_path, monkeypatch, server)
    # Each of the three records of an open request on its own.
    if field == "pending":
        instance.pending[id_key(1)] = Pending(
            method="ping", rpc_id=8, client_key=id_key(8), occurrence=1, arguments={}
        )
    elif field == "client_pending":
        instance.client_pending.add(id_key(8))
    else:
        instance.tools_inflight = True
    assert not instance._server_is_idle()
    instance._cleanup()
    assert server.signals() == STAGED


def test_condition_3_bytes_still_queued_for_the_server_get_the_staged_stop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    server = FakeServer(FakeClock())
    instance = _answered(tmp_path, monkeypatch, server)
    instance.output["server"].extend(b'{"jsonrpc":"2.0","method":"notifications/initialized"}\n')
    assert not instance._server_is_idle()
    instance._cleanup()
    assert server.signals() == STAGED


def test_condition_4_a_latched_harness_fault_gets_the_staged_stop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    server = FakeServer(FakeClock())
    instance = _answered(tmp_path, monkeypatch, server)
    instance.latches.set_harness("some fault")
    assert not instance._server_is_idle()
    instance._cleanup()
    assert server.signals() == STAGED


def test_a_server_notification_does_not_count_as_an_answer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    instance = _boundary(tmp_path, monkeypatch, FakeServer(FakeClock()))
    instance._server_message(b'{"jsonrpc":"2.0","method":"notifications/message"}')
    assert not instance.server_answered


def test_server_bytes_that_are_not_a_matched_response_do_not_count_as_an_answer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Through the read path: a notification and a partial, unterminated response line reach
    # `_consume_chunk`, and neither sets the flag; only the completed, matched line does.
    instance = _boundary(tmp_path, monkeypatch, FakeServer(FakeClock()))
    _add_pending(instance, 0, 7)
    instance._consume_chunk("server", b'{"jsonrpc":"2.0","method":"notifications/message"}\n')
    assert not instance.server_answered
    instance._consume_chunk("server", b'{"id":0,"jsonrpc":"2.0","res')
    assert not instance.server_answered
    assert not instance._server_is_idle()
    instance._consume_chunk("server", b'ult":{}}\n')
    assert instance.server_answered


def test_an_unmatched_response_does_not_count_as_an_answer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    instance = _boundary(tmp_path, monkeypatch, FakeServer(FakeClock()))
    _add_pending(instance, 0, 7)
    with pytest.raises(ValueError, match="unexpected MCP server response"):
        instance._server_message(b'{"id":5,"jsonrpc":"2.0","result":{}}')
    assert not instance.server_answered


@pytest.mark.parametrize(
    "raw",
    [
        b'{"id":0,"jsonrpc":"2.0"}',
        b'{"id":0,"jsonrpc":"2.0","result":{},"error":{"code":-32601,"message":"x"}}',
        b'{"id":0,"jsonrpc":"1.0","result":{}}',
        b'{"id":0,"jsonrpc":"2.0","error":"not an object"}',
    ],
)
def test_an_invalid_response_does_not_count_as_an_answer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, raw: bytes
) -> None:
    instance = _boundary(tmp_path, monkeypatch, FakeServer(FakeClock()))
    _add_pending(instance, 0, 7)
    with pytest.raises(ValueError):
        instance._server_message(raw)
    assert not instance.server_answered
    assert instance.pending


def test_stated_limit_an_idle_server_that_answers_before_saving_loses_the_unsaved_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Not desired behaviour: the documented limit of the idle rule (see `_server_is_idle`). This
    # fake server answered its request but publishes its snapshot only once the stopper yields
    # after EOF. Idle, it is killed at once, before it yields, so that state is lost, exactly
    # as before the staged stop. The project's own bridge and fixture server write first.
    server = FakeServer(FakeClock(), exit_after_eof=0.0)
    instance = _answered(tmp_path, monkeypatch, server)
    instance._cleanup()
    assert not server.snapshot_written
    assert server.returncode == -9
    # The same server, before it has answered, gets the wait and keeps its snapshot.
    waited = FakeServer(FakeClock(), exit_after_eof=0.0)
    _boundary(tmp_path, monkeypatch, waited)._cleanup()
    assert waited.snapshot_written
    assert waited.signals() == []


DRAIN_BYTES = 4 * 1024 * 1024
NOISY_SERVER = (
    "import sys\n"
    "sys.stdin.buffer.read()\n"
    f"sys.stdout.buffer.write(b'x' * {DRAIN_BYTES})\n"
    "sys.stdout.buffer.flush()\n"
)


def test_output_written_after_eof_is_drained_so_the_server_exits_by_itself(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # 4 MB is far more than a pipe holds: without draining, the server would block in write
    # until SIGTERM at R/2 (here 10 s).
    monkeypatch.setattr(boundary_module, "_PROTOCOL", io.BytesIO())
    base = mcp_spec("good", condition=COND_CLEAN)
    spec = base.model_copy(
        update={
            "mcp_server": McpServerSpec(
                argv=(sys.executable, "-c", NOISY_SERVER),
                snapshot="tests.acceptance.mcp_fixtures:snapshot",
            )
        }
    )
    remaining = 20.0
    instance = Boundary(
        "nonce", spec, "unused", str(tmp_path), deadline=time.monotonic() + remaining
    )
    instance.async_io = True
    instance._start_server()
    server = instance.server
    assert server is not None
    started = time.monotonic()
    instance._cleanup()
    elapsed = time.monotonic() - started
    assert server.returncode == 0
    assert elapsed < remaining / 4


def serve_ignoring_eof() -> None:
    """A real tool server for the end-to-end test: the bridge, which then ignores EOF.

    It serves like `arci.mcp_toolset_server` until its input closes, then stays alive until a
    signal ends it (SIGTERM's default action), like a server that does not follow the MCP
    stdio shutdown.
    """
    mcp_toolset_server.main(sys.argv[1:])
    while True:
        time.sleep(3600)


def _ignoring_eof_trial(max_seconds: float) -> TrialSpec:
    base = mcp_spec("good", condition=COND_CLEAN, max_seconds=max_seconds)
    return base.model_copy(
        update={
            "mcp_server": McpServerSpec(
                argv=(
                    sys.executable,
                    "-P",
                    "-c",
                    f"from {ME} import serve_ignoring_eof; serve_ignoring_eof()",
                    "--toolset",
                    "tests.acceptance.fixture_agents:make_world",
                    "--tools",
                    "fetch,store,log",
                    "--workdir",
                    "{workdir}",
                    "--seed",
                    "{seed}",
                ),
                snapshot="arci.mcp_toolset_server:snapshot",
            ),
            "budgets": Budgets(max_tool_calls=20, max_seconds=max_seconds),
        }
    )


def test_a_real_server_that_ignores_eof_does_not_delay_a_trial_whose_agent_used_it() -> None:
    # The agent ("good") makes its calls, each written to state.json before it is answered, and
    # exits with nothing open; the server is then idle and is killed at once, as before the
    # staged stop. Same outcome, termination and final state as on the code before the staged
    # stop: PASS, completed, the post-call state. A staged stop would add about half of the
    # time left (some 10 s here); the agent itself needs about a second.
    max_seconds = 20.0
    sink: list[Event] = []
    started = time.monotonic()
    envelope: TrialEnvelope = run_trial(
        _ignoring_eof_trial(max_seconds), sink.append, mcp_contract()
    )
    elapsed = time.monotonic() - started
    assert envelope.outcome is Outcome.PASS, envelope.failure_detail
    assert envelope.termination is Termination.COMPLETED
    assert envelope.final_state == {"stored": 42, "log": ["start"]}
    assert elapsed < max_seconds / 4, elapsed


def test_a_real_server_that_ignores_eof_is_stopped_at_half_the_time_left_if_never_used() -> None:
    # The agent never connects, so the server never answered a request: it may still be
    # starting, so the boundary gives it the staged stop. The bridge wrote its starting state
    # long before. Decisions are configured so that the parent signals the boundary as soon as
    # the agent has exited: the trial then lasts the agent's fraction of a second plus the
    # staged stop's wait of half the time left before SIGTERM, which ends this server, so about
    # 0.5 * max_seconds in all. An immediate kill at cleanup would end the trial in well under a
    # second, which the lower bound rejects; the upper bound is far from both the wait and the
    # deadline, so a slow machine does not decide the result. (Without decisions the parent's
    # own half-deadline wait comes first and the two cases differ by much less.)
    max_seconds = 8.0
    spec = _ignoring_eof_trial(max_seconds).model_copy(
        update={
            "command": CommandSpec(argv=(sys.executable, "-c", "raise SystemExit(0)")),
            "decisions": DecisionSpec(
                upstream="fixture",
                fixture="tests.acceptance.decision_fixtures:fixture",
                model=PINNED_MODEL,
            ),
        }
    )
    started = time.monotonic()
    envelope = run_trial(spec, lambda _: None, mcp_contract())
    elapsed = time.monotonic() - started
    assert envelope.termination is Termination.COMPLETED, envelope.failure_detail
    assert envelope.final_state == {"stored": None, "log": []}
    assert max_seconds * 0.3 <= elapsed <= max_seconds * 0.8, elapsed


def serve_ignoring_eof_and_sigterm() -> None:
    """A tool server that writes its state, then ignores EOF and SIGTERM until SIGKILL."""
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    workdir = sys.argv[sys.argv.index("--workdir") + 1]
    Path(workdir, "state.json").write_text('{"stored": null, "log": []}')
    sys.stdin.buffer.read()
    while True:
        time.sleep(3600)


@pytest.mark.parametrize(("decisions", "agent_seconds"), [(True, 6.0), (False, 4.0)])
def test_an_agent_leaving_shortly_before_the_deadline_is_still_completed(
    decisions: bool, agent_seconds: float
) -> None:
    # The boundary's deadline must not be later than the parent's. When the boundary anchored
    # its deadline after its own start-up, a server needing SIGKILL could keep it alive past
    # the parent's deadline, and a completed trial became FAIL / timeout (reproduced, with a
    # 4 s budget, at an agent sleep of 3.45 s with decisions and 3.5 s without). This test is a
    # broad guard on the outcome, not a sharp one: the stop leaves the boundary a quarter of
    # the time left at cleanup, and the times here are chosen so that quarter is nearly half a
    # second (with decisions the stop begins when the agent exits at about 6.1 s of 8; without,
    # the parent first waits half of what is left after about 4.1 s), so that a slow machine
    # does not decide the result. The mechanism itself is pinned exactly by the
    # `trial_deadline` and runner-configuration tests above.
    max_seconds = 8.0
    base = mcp_spec("silent", condition=COND_CLEAN, max_seconds=max_seconds)
    spec = base.model_copy(
        update={
            "command": CommandSpec(
                argv=(sys.executable, "-c", f"import time; time.sleep({agent_seconds})")
            ),
            "mcp_server": McpServerSpec(
                argv=(
                    sys.executable,
                    "-P",
                    "-c",
                    f"from {ME} import serve_ignoring_eof_and_sigterm as s; s()",
                    "--workdir",
                    "{workdir}",
                ),
                snapshot="arci.mcp_toolset_server:snapshot",
            ),
            "decisions": DecisionSpec(
                upstream="fixture",
                fixture="tests.acceptance.decision_fixtures:fixture",
                model=PINNED_MODEL,
            )
            if decisions
            else None,
        }
    )
    envelope = run_trial(spec, lambda _: None, mcp_contract())
    assert envelope.termination is Termination.COMPLETED, envelope.failure_detail
    assert envelope.final_state == {"stored": None, "log": []}
