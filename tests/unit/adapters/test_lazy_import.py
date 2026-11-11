"""Core import isolation must run even when the optional framework is absent."""

from __future__ import annotations

import os
import subprocess
import sys


def test_core_import_and_cli_help_do_not_load_optional_frameworks() -> None:
    """ADR 0012 item 9: fresh interpreter import and CLI help stay framework-free."""
    script = """
import sys
import arci
from arci.cli import main
try:
    main(["--help"])
except SystemExit as exc:
    assert exc.code == 0, exc.code
unexpected = sorted(
    name for name in sys.modules
    if name.split(".")[0] in {"langchain", "langchain_core", "langgraph", "langsmith"}
)
assert not unexpected, unexpected
print("core import and CLI help are framework-free")
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        timeout=30,
        env={**os.environ, "LANGSMITH_TRACING": "false"},
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "core import and CLI help are framework-free" in result.stdout


def test_absent_extra_has_one_actionable_import_error() -> None:
    """ADR 0012 item 4: absence is simulated without uninstalling any dependency."""
    script = """
import importlib.abc
import sys
class AbsentFramework(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] in {"langchain", "langchain_core", "langgraph", "langsmith"}:
            raise ModuleNotFoundError("optional framework unavailable", name=fullname)
sys.meta_path.insert(0, AbsentFramework())
import arci
import arci.adapters
try:
    import arci.adapters.langchain
except ImportError as exc:
    assert "pip install 'agent-reliability-ci[langchain]'" in str(exc), str(exc)
    assert len(str(exc).splitlines()) == 1, str(exc)
else:
    raise AssertionError("missing optional dependency was silently accepted")
print("missing-extra diagnostic verified")
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        timeout=30,
        env={**os.environ, "LANGSMITH_TRACING": "false"},
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "missing-extra diagnostic verified" in result.stdout


def test_grader_check_import_is_framework_free() -> None:
    """Findings 23, 35: grading a serialized snapshot must not import LangChain again."""
    import json

    request = {
        "contract": {"oracle": "tests.unit.adapters.checks:oracle"},
        "events": [],
        "task": {},
        "final_state": {"final_output": "done", "structured_response": None, "state": None},
        "run_oracle": True,
    }
    script = """
import sys
from arci.grade import main
assert main() == 0
frameworks = {'langchain', 'langchain_core', 'langgraph', 'langsmith'}
assert not any(name.split('.')[0] in frameworks for name in sys.modules)
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        input=json.dumps(request),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["success"] is True
