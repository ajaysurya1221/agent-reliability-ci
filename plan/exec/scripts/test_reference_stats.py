"""Dry run of .github/workflows/ttfv-reference.yml and reference_stats.py, no network.

The workflow's own `run:` bodies are lifted from the YAML and executed: the timing step against a
fake `uv`/`uvx` on PATH (sample 3 fails, sample 6 hangs until the per-sample timeout kills it),
the parse step on the logs that produced, and the final check step. A second run gives the loop
no time budget, so every sample is recorded as timed out without starting. reference_stats.py is
then run on those JSONs and on hand-written ones with known stamps, valid and invalid.

    .venv/bin/pytest -p no:cacheprovider plan/exec/scripts/test_reference_stats.py
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
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
PACKAGE = "agent-reliability-ci==0.8.0"
# Short enough to keep the test quick, far above the fake's millisecond samples.
SAMPLE_TIMEOUT_S = "5"

FAKE_UV = """#!/usr/bin/env bash
echo "uv 0.12.5 (fake)"
"""
# Sample 3 fails; sample 6 prints every marker, then hangs. Every demo call records its number,
# the cache it saw and how many entries that cache had at start.
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
if [ "$n" = 6 ]; then sleep 300; fi
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


def workflow_env() -> dict[str, str]:
    doc = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    return {str(k): str(v) for k, v in doc["env"].items()}


def write_exe(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)


def run_step(
    name_prefix: str, tmp_path: Path, env: dict[str, str]
) -> subprocess.CompletedProcess[str]:
    body = step(name_prefix)
    assert body["shell"] == "python", name_prefix
    script = tmp_path / f"step-{len(list(tmp_path.glob('step-*.py')))}.py"
    script.write_text(body["run"], encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(script)], env=env, capture_output=True, text=True, check=False
    )


def fake_env(tmp_path: Path, **overrides: str) -> dict[str, str]:
    bin_dir, state, tmp = (tmp_path / d for d in ("bin", "state", "tmp"))
    for d in (bin_dir, state, tmp):
        d.mkdir()
    write_exe(bin_dir / "uv", FAKE_UV)
    write_exe(bin_dir / "uvx", FAKE_UVX)
    return (
        workflow_env()
        | {
            "PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}",
            "HOME": str(tmp_path),
            "TMPDIR": str(tmp),
            "FAKE_STATE": str(state),
            "OUT_DIR": str(tmp_path / "out"),
            "OUT_JSON": "reference-test.json",
            "REF_RUNNER_OS": "Linux",
            "REF_RUNNER_ARCH": "X64",
            "REF_RUNNER_LABEL": "ubuntu-latest",
            "REF_RUN_ID": "1",
            "REF_RUN_ATTEMPT": "1",
            "REF_SHA": "0" * 40,
        }
        | overrides
    )


def test_workflow_design_values() -> None:
    env = workflow_env()
    assert env["PACKAGE"] == PACKAGE
    assert (env["COLD_SAMPLES"], env["WARM_SAMPLES"]) == ("5", "2")
    assert env["SAMPLE_TIMEOUT_S"] == "600"
    doc = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    job_minutes = doc["jobs"]["reference"]["timeout-minutes"]
    # The sampling loop is bounded well inside the job, leaving time for the JSON and upload.
    assert int(env["TIMING_BUDGET_S"]) <= (job_minutes - 3) * 60
    assert step("Parse the logs")["if"] == "always()"
    assert step("Upload the JSON")["if"] == "always()"


def test_workflow_steps_dry_run(tmp_path: Path) -> None:
    env = fake_env(tmp_path, SAMPLE_TIMEOUT_S=SAMPLE_TIMEOUT_S)
    out_dir, state = Path(env["OUT_DIR"]), Path(env["FAKE_STATE"])

    done = run_step("Time the demo", tmp_path, env)
    assert done.returncode == 0, done.stderr
    assert "sample 3 (cold): exit 3" in done.stdout
    assert f"sample 6 (warm): timed out after {SAMPLE_TIMEOUT_S} s" in done.stdout

    calls = [line.split() for line in (state / "calls").read_text().splitlines()]
    assert [c[0] for c in calls] == ["1", "2", "3", "4", "5", "6", "7"]
    caches = [c[1] for c in calls]
    assert len(set(caches[:5])) == 5  # a new uv cache for every cold sample
    assert caches[5] == caches[6] == caches[4]  # warm samples reuse the last cold cache
    assert [c[2] for c in calls] == ["0", "0", "0", "0", "0", "1", "1"]

    log3 = (out_dir / "sample-3.log").read_text().splitlines()
    assert all(STAMP_RE.match(line.split(" ", 1)[0]) for line in log3)
    assert log3[-1].endswith(" Traceback: boom")
    # The unterminated last line survives the timestamping.
    assert (out_dir / "sample-1.log").read_text().splitlines()[-1].endswith(" Run stores: /tmp/x")
    log6 = (out_dir / "sample-6.log").read_text().splitlines()
    assert log6[-1].endswith(f"[ttfv-reference] killed after {SAMPLE_TIMEOUT_S} s")

    done = run_step("Parse the logs", tmp_path, env)
    assert done.returncode == 0, done.stderr
    out = out_dir / "reference-test.json"
    doc = json.loads(out.read_text())
    assert doc["package"] == PACKAGE
    assert doc["runner"]["os"] == "Linux" and doc["runner"]["arch"] == "X64"
    assert doc["python"] == "3.12.99"
    assert doc["uv"] == "uv 0.12.5 (fake)"
    assert doc["setup_python"]
    assert doc["design"]["cold_samples"] == 5 and doc["design"]["warm_samples"] == 2
    assert doc["design"]["sample_timeout_seconds"] == int(SAMPLE_TIMEOUT_S)
    samples = doc["samples"]
    assert [s["sample"] for s in samples] == [1, 2, 3, 4, 5, 6, 7]
    assert [s["uv_cache"] for s in samples] == ["cold"] * 5 + ["warm"] * 2
    assert [s["uv_cache_entries_at_start"] for s in samples] == [0, 0, 0, 0, 0, 1, 1]
    assert [s["exit_code"] for s in samples] == [0, 0, 3, 0, 0, None, 0]
    assert [s["timed_out"] for s in samples] == [False] * 5 + [True, False]
    assert all(s["started"] for s in samples)
    for s in samples:
        for key in ("command_start", "demo_banner", "demo_verdict"):
            assert STAMP_RE.match(s[key]), (s["sample"], key)
        assert s["log"] == f"sample-{s['sample']}.log"
    # Sample 6 printed the marker before hanging; a timed-out sample never counts as held.
    assert samples[2]["all_steps_held"] is None and samples[5]["all_steps_held"] is None
    assert all(STAMP_RE.match(s["all_steps_held"]) for s in samples if s["sample"] not in (3, 6))

    done = run_step("Fail if any sample", tmp_path, env | {"OUT_JSON": str(out)})
    assert done.returncode == 1
    assert "7 of 7 samples; not held: [3, 6]; timed out: [6]" in done.stdout

    assert stats.problems(doc) == []
    lines = stats.report(out)
    assert lines[0] == "reference-test.json: Linux X64 ubuntu-latest, agent-reliability-ci==0.8.0"
    assert lines[1].startswith("  cold totals (5): ") and "failed" in lines[1]
    assert lines[2].startswith("  cold: p50 ") and "p95 not reached over target" in lines[2]
    assert lines[3].startswith("  warm totals (2): timed out, ")
    assert lines[4].startswith("  warm: fewer than 5 samples")
    assert len(lines) == 5


def test_workflow_budget_used_up(tmp_path: Path) -> None:
    """No time left: nothing starts, every sample is recorded as timed out, the JSON still comes."""
    env = fake_env(tmp_path, TIMING_BUDGET_S="0")
    out_dir, state = Path(env["OUT_DIR"]), Path(env["FAKE_STATE"])
    done = run_step("Time the demo", tmp_path, env)
    assert done.returncode == 0, done.stderr
    assert not (state / "calls").exists()
    assert "not started" in (out_dir / "sample-7.log").read_text()
    assert run_step("Parse the logs", tmp_path, env).returncode == 0
    out = out_dir / "reference-test.json"
    samples = json.loads(out.read_text())["samples"]
    assert [(s["timed_out"], s["started"], s["exit_code"]) for s in samples] == [
        (True, False, None)
    ] * 7
    done = run_step("Fail if any sample", tmp_path, env | {"OUT_JSON": str(out)})
    assert done.returncode == 1
    assert "timed out: [1, 2, 3, 4, 5, 6, 7]" in done.stdout
    lines = stats.report(out)
    assert lines[1] == "  cold totals (5): " + ", ".join(["timed out"] * 5)
    assert lines[2].startswith("  cold: p50 not reached over target (<= 120 s)")


def test_parse_step_without_samples(tmp_path: Path) -> None:
    """The timing step died before writing anything: the JSON step still writes a file."""
    env = fake_env(tmp_path)
    done = run_step("Parse the logs", tmp_path, env)
    assert done.returncode == 0, done.stderr
    doc = json.loads((Path(env["OUT_DIR"]) / "reference-test.json").read_text())
    assert doc["samples"] == []


T0 = "2026-10-14T10:00:00Z"


def at(seconds: int) -> str:
    return f"2026-10-14T10:{seconds // 60:02d}:{seconds % 60:02d}Z"


def sample(
    n: int, cache: str, held: int | None, exit_code: int | None = 0, *, timed_out: bool = False
) -> dict[str, Any]:
    """A sample that started at T0 and held `held` seconds later (None: never held)."""
    return {
        "sample": n,
        "uv_cache": cache,
        "command_start": T0,
        "demo_banner": at(1),
        "demo_verdict": at(2),
        "all_steps_held": None if held is None else at(held),
        "exit_code": exit_code,
        "timed_out": timed_out,
    }


def write_doc(path: Path, samples: list[Any]) -> Path:
    doc = {
        "package": PACKAGE,
        "runner": {"os": "macOS", "arch": "ARM64", "label": "macos-latest"},
        "samples": samples,
    }
    path.write_text(json.dumps(doc), encoding="utf-8")
    return path


HEADER = "reference-macos-latest.json: macOS ARM64 macos-latest, agent-reliability-ci==0.8.0"


def test_cold_and_warm_blocks_are_separate(tmp_path: Path) -> None:
    cold = [sample(n, "cold", t) for n, t in zip(range(1, 6), (185, 40, 30, 50, 20), strict=True)]
    warm = [sample(6, "warm", 12), sample(7, "warm", 10)]
    path = write_doc(tmp_path / "reference-macos-latest.json", cold + warm)
    assert stats.report(path) == [
        HEADER,
        "  cold totals (5): 185 s, 40 s, 30 s, 50 s, 20 s",
        "  cold: p50 40 s within target (<= 120 s); p95 185 s over target (<= 180 s);"
        " p95 of 5 is the maximum",
        "  warm totals (2): 12 s, 10 s",
        "  warm: fewer than 5 samples, raw values only, no percentile claim;"
        " warm samples are never compared with the memo target",
    ]


def test_warm_samples_never_rescue_a_slow_cold_one(tmp_path: Path) -> None:
    """Review 18 finding 1: one cold 150 s and four warm 10 s used to read as within target."""
    samples = [sample(1, "cold", 150), *(sample(n, "warm", 10) for n in range(2, 6))]
    lines = stats.report(write_doc(tmp_path / "reference-macos-latest.json", samples))
    assert lines == [
        HEADER,
        "  cold totals (1): 150 s",
        "  cold: fewer than 5 samples, raw values only, no percentile claim",
        "  warm totals (4): 10 s, 10 s, 10 s, 10 s",
        "  warm: fewer than 5 samples, raw values only, no percentile claim;"
        " warm samples are never compared with the memo target",
    ]
    assert not any("within" in line for line in lines)


def test_five_warm_samples_get_percentiles_but_no_target(tmp_path: Path) -> None:
    samples = [sample(n, "cold", 100) for n in range(1, 6)]
    samples += [sample(n, "warm", 10) for n in range(6, 11)]
    lines = stats.report(write_doc(tmp_path / "r.json", samples))
    assert lines[2] == (
        "  cold: p50 100 s within target (<= 120 s); p95 100 s within target (<= 180 s);"
        " p95 of 5 is the maximum"
    )
    assert lines[4] == (
        "  warm: p50 10 s; p95 10 s; p95 of 5 is the maximum;"
        " warm samples are never compared with the memo target"
    )


def test_failed_and_timed_out_cold_samples(tmp_path: Path) -> None:
    samples = [
        sample(1, "cold", 60),
        sample(2, "cold", None, exit_code=1),
        sample(3, "cold", None, exit_code=None, timed_out=True),
        sample(4, "cold", 70),
        sample(5, "cold", 80),
    ]
    lines = stats.report(write_doc(tmp_path / "r.json", samples))
    assert lines[1] == "  cold totals (5): 60 s, failed, timed out, 70 s, 80 s"
    assert lines[2] == (
        "  cold: p50 80 s within target (<= 120 s); p95 not reached over target (<= 180 s);"
        " p95 of 5 is the maximum"
    )


INVALID_CASES: dict[str, tuple[object, str]] = {
    "top level not an object": ([1, 2], "the top level is not an object"),
    "no samples key": ({"package": PACKAGE}, "'samples' is missing or not a list"),
    "samples not a list": ({"samples": {"1": {}}}, "'samples' is missing or not a list"),
    "null sample": ({"samples": [None]}, "samples[0] is null, not an object"),
    "negative duration": (
        {"samples": [sample(1, "cold", None) | {"all_steps_held": "2026-10-14T09:59:00Z"}]},
        "samples[0]: all_steps_held is before demo_verdict",
    ),
    "out of order markers": (
        {"samples": [sample(1, "cold", 60) | {"demo_banner": at(5)}]},
        "samples[0]: demo_verdict is before demo_banner (-3 s, out of order)",
    ),
    "bad timestamp": (
        {"samples": [sample(1, "cold", 60) | {"command_start": "yesterday"}]},
        "samples[0]: 'command_start' is 'yesterday', not a UTC timestamp",
    ),
    "missing command_start": (
        {"samples": [sample(1, "cold", 60) | {"command_start": None}]},
        "samples[0]: 'command_start' is missing",
    ),
    "unknown cache": (
        {"samples": [sample(1, "lukewarm", 60)]},
        "samples[0]: 'uv_cache' is 'lukewarm', not cold or warm",
    ),
    "null exit code without timeout": (
        {"samples": [sample(1, "cold", None, exit_code=None)]},
        "samples[0]: 'exit_code' is None (null only for a timed-out sample)",
    ),
    "timed out but held": (
        {"samples": [sample(1, "cold", 60, exit_code=None, timed_out=True)]},
        "samples[0]: timed out but 'all_steps_held' is set",
    ),
    "duplicate sample": (
        {"samples": [sample(1, "cold", 60), sample(1, "warm", 10)]},
        "samples[1]: sample number 1 appears twice",
    ),
    "sample number not an integer": (
        {"samples": [sample(1, "cold", 60) | {"sample": "1"}]},
        "samples[0]: 'sample' is not an integer",
    ),
}


@pytest.mark.parametrize("case", sorted(INVALID_CASES))
def test_invalid_files_are_reported_without_figures(
    case: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    doc, expected = INVALID_CASES[case]
    path = tmp_path / "reference-bad.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    assert any(problem.startswith(expected) for problem in stats.problems(doc)), stats.problems(doc)
    assert stats.main([str(path)]) == 0
    out = capsys.readouterr().out
    assert out.startswith("reference-bad.json: INVALID, no figures reported\n")
    assert expected in out
    assert "p50" not in out and "within" not in out and "totals" not in out


def test_failed_samples_rank_last() -> None:
    assert stats.nearest_rank([10.0, None, 30.0, 20.0, 40.0], 50) == 30.0
    assert stats.nearest_rank([10.0, None, 30.0, 20.0, 40.0], 95) is None
    assert stats.nearest_rank([None, None, None, 5.0, 6.0], 50) is None
    assert stats.nearest_rank([], 50) is None


def test_total() -> None:
    assert stats.total(sample(1, "cold", 60)) == 60.0
    assert stats.total(sample(1, "cold", 60, exit_code=1)) is None
    assert stats.total(sample(1, "cold", None)) is None
    assert stats.total(sample(1, "cold", 60, exit_code=None, timed_out=True)) is None
    assert stats.total(sample(1, "cold", 60) | {"command_start": "garbage"}) is None


def test_main_always_exits_zero(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    bad = tmp_path / "reference-broken.json"
    bad.write_text("{not json", encoding="utf-8")
    empty = write_doc(tmp_path / "reference-empty.json", [])
    assert stats.main([str(bad), str(empty), str(tmp_path / "missing.json")]) == 0
    assert stats.main([]) == 0
    out = capsys.readouterr().out
    assert "reference-broken.json: unreadable" in out
    assert "missing.json: unreadable" in out
    assert "  cold totals (0): none" in out
