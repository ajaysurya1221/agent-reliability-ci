"""Fresh-process contract grader used by :mod:`arci.runner`."""

from __future__ import annotations

import contextlib
import json
import sys

from arci.contracts import evaluate_contract
from arci.schema import ContractSpec, Event


def main() -> int:
    try:
        request = json.loads(sys.stdin.buffer.readline())
        if not isinstance(request, dict):
            raise TypeError("grader request is not an object")
        contract = ContractSpec.model_validate(request.get("contract"))
        events = tuple(Event.model_validate(item) for item in request.get("events", ()))
        task = request.get("task")
        final_state = request.get("final_state") if request.get("run_oracle") is True else None
        if not isinstance(task, dict):
            raise TypeError("grader task is not an object")
        if final_state is not None and not isinstance(final_state, dict):
            raise TypeError("grader final_state is not an object")
        with contextlib.redirect_stdout(sys.stderr):
            result = evaluate_contract(contract, events, task, final_state)
        sys.stdout.write(result.model_dump_json() + "\n")
        sys.stdout.flush()
        return 0
    except BaseException:
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
