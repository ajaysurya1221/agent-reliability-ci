"""Dry run of .github/workflows/ttfv-reference.yml and reference_stats.py, no network.

The workflow's own `run:` bodies are lifted from the YAML and executed: the timing step against a
fake `uv`/`uvx` on PATH (sample 3 fails), the parse step on the logs that produced, and the final
check step. reference_stats.py is then run on the JSON and on a hand-written one with known stamps.

    .venv/bin/pytest -p no:cacheprovider plan/exec/scripts/test_reference_stats.py
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
import yaml

HERE = Path(__file__).resolve().parent
WORKFLOW = HERE.parents[2] / ".github" / "workflows" / "ttfv-reference.yml"
STAMP_RE = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")

FAKE_UV = """#!/usr/bin/env bash
echo "uv 0.12.5 (fake)"
"""
# Sample 3 fails; every call records which cache it saw and how full it was at start.
FAKE_UVX = """#!/usr/bin/env bash
set -u
if [ "$1" != --from ] || [ "$2" != "agent-reliability-ci==0.8.0" ]; then
  echo "bad args: $*" >&2
  exit 90
fi
if [ "$3" = python ]; then echo 3.12.99; exit 0; fi
[ "$3 $4" = "arci demo" ] || { echo "bad args: $*" >&2; exit 91; }
n=$(( $(cat "$FAKE_STATE/count" 2>/dev/null || echo 0) + 1 ))
echo "$n" >"$FAKE_STATE/count"
printf '%s %s %s\\n' "$n" "$UV_CACHE_DIR" "$(ls -A "$UV_CACHE_DIR" | wc -l | tr -d ' ')" \\
  >>"$FAKE_STATE/calls"
touch "$UV_CACHE_DIR/filled"
echo "Installed 3 packages in 5ms" >&2
echo "arci demo: the retry story, 8 workers, run stores in /tmp/x"
echo "  VERDICT: BLOCK (exit 1)   [A vs agent_b]"
echo "  VERDICT: PASS (exit 0)   [A vs agent_a]"
if [ "$n" = 3 ]; then echo "Traceback: boom" >&2; exit 3; fi
echo "All six steps held."
printf 'Run stores: /tmp/x'
"""


def load_stats() -> ModuleType:
    spec = importlib.util.spec_from_file_location("reference_stats", HERE / "reference_stats.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


stats = load_stats()


def step(name_prefix: str) -> dict[str, Any]:
    doc = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    steps: list[dict[str, Any]] = doc["jobs"]["reference"]["steps"]
    matches = [s for s in steps if str(s.get("name", "")).startswith(name_prefix)]
    assert len(matches) == 1, name_prefix
    return matches[0]


def write_exe(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)


@pytest.mark.skipif(shutil.which("bash") is None, reason="needs bash")
def test_workflow_steps_dry_run(tmp_path: Path) -> None:
    bin_dir, state, out_dir, tmp = (tmp_path / d for d in ("bin", "state", "out", "tmp"))
    for d in (bin_dir, state, tmp):
        d.mkdir()
    write_exe(bin_dir / "uv", FAKE_UV)
    write_exe(bin_dir / "uvx", FAKE_UVX)
    (bin_dir / "python").symlink_to(sys.executable)
    env = {
        "PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}",
        "HOME": str(tmp_path),
        "TMPDIR": str(tmp),
        "FAKE_STATE": str(state),
        "OUT_DIR": str(out_dir),
        "PACKAGE": "agent-reliability-ci==0.8.0",
    }

    timing = step("Time five demo runs")
    script = tmp_path / "time.sh"
    script.write_text(timing["run"], encoding="utf-8")
    # The interpreter GitHub uses for `shell: bash`.
    done = subprocess.run(
        ["bash", "--noprofile", "--norc", "-eo", "pipefail", str(script)],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0, done.stderr
    assert "sample 3 (warm): exit 3" in done.stdout

    calls = [line.split() for line in (state / "calls").read_text().splitlines()]
    assert [c[0] for c in calls] == ["1", "2", "3", "4", "5"]
    assert len({c[1] for c in calls}) == 1  # one uv cache for all five samples
    assert [c[2] for c in calls] == ["0", "1", "1", "1", "1"]  # empty only for sample 1

    log3 = (out_dir / "sample-3.log").read_text().splitlines()
    assert all(STAMP_RE.match(line.split(" ", 1)[0]) for line in log3)
    assert log3[-1].endswith(" Traceback: boom")
    # The unterminated last line survives the timestamping filter.
    assert (out_dir / "sample-1.log").read_text().splitlines()[-1].endswith(" Run stores: /tmp/x")

    parse = step("Parse the logs")
    assert parse["shell"] == "python"
    parser = tmp_path / "parse.py"
    parser.write_text(parse["run"], encoding="utf-8")
    parse_env = env | {
        "OUT_JSON": "reference-test.json",
        "REF_RUNNER_OS": "Linux",
        "REF_RUNNER_ARCH": "X64",
        "REF_RUNNER_LABEL": "ubuntu-latest",
        "REF_RUN_ID": "1",
        "REF_RUN_ATTEMPT": "1",
        "REF_SHA": "0" * 40,
    }
    done = subprocess.run(
        [sys.executable, str(parser)], env=parse_env, capture_output=True, text=True, check=False
    )
    assert done.returncode == 0, done.stderr
    out = out_dir / "reference-test.json"
    doc = json.loads(out.read_text())
    assert doc["package"] == "agent-reliability-ci==0.8.0"
    assert doc["runner"]["os"] == "Linux" and doc["runner"]["arch"] == "X64"
    assert doc["python"] == "3.12.99"
    assert doc["uv"] == "uv 0.12.5 (fake)"
    assert doc["setup_python"]
    samples = doc["samples"]
    assert [s["sample"] for s in samples] == [1, 2, 3, 4, 5]
    assert [s["uv_cache"] for s in samples] == ["cold", "warm", "warm", "warm", "warm"]
    assert [s["exit_code"] for s in samples] == [0, 0, 3, 0, 0]
    for s in samples:
        for key in ("command_start", "demo_banner", "demo_verdict"):
            assert STAMP_RE.match(s[key]), (s["sample"], key)
        assert s["log"] == f"sample-{s['sample']}.log"
    assert samples[2]["all_steps_held"] is None
    assert all(STAMP_RE.match(s["all_steps_held"]) for i, s in enumerate(samples) if i != 2)

    check = step("Fail if any sample did not hold")
    checker = tmp_path / "check.py"
    checker.write_text(check["run"], encoding="utf-8")
    done = subprocess.run(
        [sys.executable, str(checker)],
        env=env | {"OUT_JSON": str(out)},
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 1
    assert "not held: [3]" in done.stdout

    lines = stats.report(out)
    assert lines[0] == "reference-test.json: Linux X64 ubuntu-latest, agent-reliability-ci==0.8.0"
    assert "failed" in lines[1]
    assert len(lines) == 4  # header, totals, p50, p95


def sample(n: int, start: str, held: str | None, exit_code: int = 0) -> dict[str, Any]:
    return {
        "sample": n,
        "uv_cache": "cold" if n == 1 else "warm",
        "command_start": start,
        "demo_banner": start,
        "demo_verdict": start,
        "all_steps_held": held,
        "exit_code": exit_code,
    }


def write_doc(path: Path, samples: list[dict[str, Any]]) -> Path:
    doc = {
        "package": "agent-reliability-ci==0.8.0",
        "runner": {"os": "macOS", "arch": "ARM64", "label": "macos-latest"},
        "samples": samples,
    }
    path.write_text(json.dumps(doc), encoding="utf-8")
    return path


def test_totals_and_nearest_rank_percentiles(tmp_path: Path) -> None:
    t0 = "2026-10-14T10:00:00Z"
    path = write_doc(
        tmp_path / "reference-macos-latest.json",
        [
            sample(1, t0, "2026-10-14T10:03:05Z"),  # 185 s, cold
            sample(2, t0, "2026-10-14T10:00:40Z"),  # 40
            sample(3, t0, "2026-10-14T10:00:30Z"),  # 30
            sample(4, t0, "2026-10-14T10:00:50Z"),  # 50
            sample(5, t0, "2026-10-14T10:00:20Z"),  # 20
        ],
    )
    assert stats.report(path) == [
        "reference-macos-latest.json: macOS ARM64 macos-latest, agent-reliability-ci==0.8.0",
        "  totals (5): 185 s (cold), 40 s, 30 s, 50 s, 20 s",
        "  p50 = 40 s  (within target <= 120 s)",
        "  p95 = 185 s  (NOT within target <= 180 s)",
    ]


def test_failed_samples_rank_last() -> None:
    assert stats.nearest_rank([10.0, None, 30.0, 20.0, 40.0], 50) == 30.0
    assert stats.nearest_rank([10.0, None, 30.0, 20.0, 40.0], 95) is None
    assert stats.nearest_rank([None, None, None, 5.0, 6.0], 50) is None
    assert stats.nearest_rank([], 50) is None


def test_failed_exit_code_has_no_total() -> None:
    t0 = "2026-10-14T10:00:00Z"
    assert stats.total(sample(1, t0, "2026-10-14T10:01:00Z")) == 60.0
    assert stats.total(sample(1, t0, "2026-10-14T10:01:00Z", exit_code=1)) is None
    assert stats.total(sample(1, t0, None)) is None
    assert stats.total(sample(1, "garbage", "2026-10-14T10:01:00Z")) is None


def test_main_always_exits_zero(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    bad = tmp_path / "reference-broken.json"
    bad.write_text("{not json", encoding="utf-8")
    empty = write_doc(tmp_path / "reference-empty.json", [])
    assert stats.main([str(bad), str(empty), str(tmp_path / "missing.json")]) == 0
    assert stats.main([]) == 0
    out = capsys.readouterr().out
    assert "reference-broken.json: unreadable" in out
    assert "missing.json: unreadable" in out
    assert "reference-empty.json" in out and "no samples" in out
