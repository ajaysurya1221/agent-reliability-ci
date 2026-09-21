"""Fresh-process contract grader used by :mod:`arci.runner`."""

from __future__ import annotations

import contextlib
import json
import sys
from typing import Any, cast

from pydantic import JsonValue

from arci.contracts import evaluate_contract, resolve
from arci.hashing import canonical_json
from arci.schema import ContractResult, ContractSpec, Event


def _snapshot(request: dict[str, Any], task: dict[str, JsonValue]) -> dict[str, JsonValue] | None:
    reference = request.get("snapshot")
    workdir = request.get("workdir")
    if reference is None:
        value = request.get("final_state") if request.get("run_oracle") is True else None
        if value is not None and not isinstance(value, dict):
            raise TypeError("grader final_state is not an object")
        return cast(dict[str, JsonValue] | None, value)
    if not isinstance(reference, str) or not isinstance(workdir, str):
        raise TypeError("grader snapshot request is invalid")
    try:
        value = resolve(reference)(task, workdir)
    except BaseException:
        raise RuntimeError("snapshot failed") from None
    if not isinstance(value, dict):
        raise TypeError("snapshot returned non-object")
    try:
        canonical_json(value)
    except BaseException:
        raise RuntimeError("snapshot returned invalid JSON") from None
    return cast(dict[str, JsonValue], value)


def main() -> int:
    try:
        request = json.loads(sys.stdin.buffer.readline())
        if not isinstance(request, dict):
            raise TypeError("grader request is not an object")
        contract = ContractSpec.model_validate(request.get("contract"))
        events = tuple(Event.model_validate(item) for item in request.get("events", ()))
        raw_task = request.get("task")
        if not isinstance(raw_task, dict):
            raise TypeError("grader task is not an object")
        task = cast(dict[str, JsonValue], raw_task)
        with contextlib.redirect_stdout(sys.stderr):
            try:
                final_state = _snapshot(request, task)
            except (RuntimeError, TypeError) as exc:
                result = ContractResult(success=False, grader_error=str(exc))
                final_state = None
            else:
                graded_state = final_state if request.get("run_oracle") is True else None
                result = evaluate_contract(contract, events, task, graded_state)
        if request.get("snapshot") is None:
            output: object = result.model_dump(mode="json")
        else:
            output = {
                "contract": result.model_dump(mode="json"),
                "final_state": final_state,
            }
        sys.stdout.write(json.dumps(output, sort_keys=True, separators=(",", ":")) + "\n")
        sys.stdout.flush()
        return 0
    except BaseException:
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
