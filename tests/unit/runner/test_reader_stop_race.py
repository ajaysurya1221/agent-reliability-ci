"""A reader must not end on a "not ready" verdict computed before it was asked to stop.

On a loaded machine a reader thread can poll (nothing there yet), be descheduled across the
child's write and exit, and wake up after the parent has already set the stop flag. Acting on
that stale verdict drops the whole response. The grader reader and the MCP boundary reader
both did this (about 1 trial in 400 with 8 workers on 4 cores); the worker reader did not.
"""

from __future__ import annotations

import os
import queue
import select as real_select
import threading
import time
import types
from typing import Any

import arci.runner as runner
from arci.schedule import build_schedule
from tests.acceptance.helpers import contract, manifest


class _StaleFirstPoll:
    """Stand-in for the ``select`` module.

    The first poll on ``fd`` that happens while the pipe is still empty is held until
    ``release`` is set and then reports "not ready", exactly as a poll that timed out before
    the data landed and whose thread was descheduled. Every later poll is real.
    """

    def __init__(self, fd: int, release: threading.Event, entered: threading.Event) -> None:
        self.fd = fd
        self.release = release
        self.entered = entered
        self.served = False

    def select(
        self, rlist: list[int], wlist: list[int], xlist: list[int], timeout: float | None = None
    ) -> tuple[list[int], list[int], list[int]]:
        if not self.served and self.fd in rlist:
            self.served = True
            ready, _, _ = real_select.select(rlist, [], [], 0.0)
            self.entered.set()
            if not ready:
                self.release.wait(10)
                return [], [], []
        return real_select.select(rlist, wlist, xlist, timeout)

    def __getattr__(self, name: str) -> Any:
        return getattr(real_select, name)


def test_boundary_reader_keeps_frames_that_land_before_a_stale_poll_returns(
    monkeypatch: Any,
) -> None:
    read_fd, write_fd = os.pipe()
    process = types.SimpleNamespace(stdout=os.fdopen(read_fd, "rb", buffering=0))
    release, entered = threading.Event(), threading.Event()
    stop, abandon = threading.Event(), threading.Event()
    messages: queue.Queue[tuple[str, object]] = queue.Queue()
    monkeypatch.setattr(runner, "select", _StaleFirstPoll(read_fd, release, entered))
    reader = threading.Thread(
        target=runner._protocol_reader,  # pyright: ignore[reportPrivateUsage]  the unit under test
        args=(process, messages, stop, abandon),
        daemon=True,
    )
    try:
        reader.start()
        assert entered.wait(5), "reader never polled"
        os.write(write_fd, b'{"kind": "result"}\n')  # the boundary's final frame ...
        os.close(write_fd)  # ... and its exit
        stop.set()  # the parent saw the exit and asks for a drain
        release.set()  # only now does the stale verdict reach the reader
        reader.join(5)
        assert not reader.is_alive()
        received: list[tuple[str, object]] = []
        while not messages.empty():
            received.append(messages.get_nowait())
        assert ("line", b'{"kind": "result"}') in received, received
        assert ("reader_done", None) in received
    finally:
        process.stdout.close()


def test_grader_response_survives_a_stale_poll(monkeypatch: Any) -> None:
    spec = build_schedule(manifest())[0]
    release, entered = threading.Event(), threading.Event()

    class _StaleGraderPoll(_StaleFirstPoll):
        def select(
            self,
            rlist: list[int],
            wlist: list[int],
            xlist: list[int],
            timeout: float | None = None,
        ) -> tuple[list[int], list[int], list[int]]:
            if not self.served:
                self.served = True
                ready, _, _ = real_select.select(rlist, [], [], 0.0)
                if not ready:
                    # Hold until the grader has written and exited, then a little longer so the
                    # parent's wait() returns and it sets the stop flag; then lie: "not ready".
                    real_select.select(rlist, [], [], 15.0)
                    time.sleep(0.3)
                    return [], [], []
            return real_select.select(rlist, wlist, xlist, timeout)

    monkeypatch.setattr(runner, "select", _StaleGraderPoll(-1, release, entered))
    result, _ = runner._grade(  # pyright: ignore[reportPrivateUsage]  the unit under test
        spec, contract("raising_oracle"), (), {"stored": 42}, run_oracle=False, extra_pythonpath=()
    )
    assert result.grader_error is None, result.grader_error
