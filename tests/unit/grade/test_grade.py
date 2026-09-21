from __future__ import annotations

import json
import os
import subprocess
import sys

from arci.schema import ContractResult
from tests.acceptance.helpers import contract


def _grade(run_oracle: bool) -> ContractResult:
    request = {
        "contract": contract("raising_oracle").model_dump(mode="json"),
        "events": [],
        "task": {"goal": "store 42"},
        "final_state": {"stored": 42},
        "run_oracle": run_oracle,
    }
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(os.getcwd() if item == "" else item for item in sys.path)
    done = subprocess.run(
        [sys.executable, "-P", "-m", "arci.grade"],
        input=json.dumps(request) + "\n",
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert done.returncode == 0
    return ContractResult.model_validate_json(done.stdout)


def test_grader_can_skip_the_oracle_while_evaluating_invariants() -> None:
    assert _grade(run_oracle=False).grader_error is None


def test_grader_contains_oracle_exceptions() -> None:
    result = _grade(run_oracle=True)
    assert result.grader_error is not None
    assert "grader exploded" in result.grader_error
