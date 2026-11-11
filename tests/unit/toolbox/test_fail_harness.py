"""Immediate harness rejection is independent of execution mode and agent catches."""

from __future__ import annotations

from contextlib import suppress

import pytest

from arci.schema import Budgets, ToolMode
from arci.toolbox import HarnessError, ToolBox


@pytest.mark.parametrize("mode", list(ToolMode))
def test_fail_harness_latches_before_raising_outside_exception_handlers(mode: ToolMode) -> None:
    """Requirement 6: live and replay rejections bypass ordinary retry handlers."""
    observed: list[str] = []
    box = ToolBox({}, Budgets(), lambda _kind, _payload: None, mode=mode)

    def latch(detail: str) -> None:
        assert box.harness_fault
        observed.append(detail)

    box = ToolBox({}, Budgets(), lambda _kind, _payload: None, mode=mode, latch_harness=latch)
    with pytest.raises(HarnessError, match="unsupported operation"):
        try:
            box.fail_harness("unsupported operation")
        except Exception:
            pytest.fail("ordinary agent exception handler caught the carrier")
    assert observed == ["unsupported operation"]
    assert box.harness_fault
    assert box.recording == ()
    assert box.tool_calls == box.model_steps == 0
    assert not box.budget_exceeded
    assert not box.replay_miss


@pytest.mark.parametrize("mode", list(ToolMode))
def test_catching_baseexception_cannot_clear_harness_latch(mode: ToolMode) -> None:
    """Requirement 6: even a BaseException handler cannot undo the harness outcome."""
    latched: list[str] = []
    box = ToolBox(
        {}, Budgets(), lambda _kind, _payload: None, mode=mode, latch_harness=latched.append
    )
    with suppress(BaseException):
        box.fail_harness("adapter rejected the call")
    assert box.harness_fault
    assert latched == ["adapter rejected the call"]


def test_in_body_rejection_is_never_recorded_as_a_real_tool_error() -> None:
    """Requirement 6: the carrier bypasses ToolBox's real tool Exception recording."""

    def tool() -> None:
        box.fail_harness("unsupported result")

    box = ToolBox({"tool": tool}, Budgets(), lambda _kind, _payload: None)
    with pytest.raises(HarnessError, match="unsupported result"):
        box.call("tool")
    assert box.harness_fault
    assert box.recording == ()
