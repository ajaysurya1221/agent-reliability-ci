"""Dry run of .github/workflows/ttfv-reference.yml and reference_stats.py, no network.

The workflow's own `run:` bodies are lifted from the YAML and executed: the job-start step, the
timing step against a fake `uv`/`uvx` on PATH (sample 3 fails, sample 6 hangs until the
per-sample timeout kills it), the parse step on the logs that produced, and the final check step.
Further runs put the job start far enough back that the deadline arithmetic shrinks the loop
budget, cuts a hanging sample off at the loop deadline (timeout_reason "budget", not a hang) or
leaves no budget at all (nothing starts, the probe is skipped), cut the journal's last line off,
and feed the parse step journals it must survive. reference_stats.py is then run on those JSONs
and on hand-written ones with known stamps, valid, contradictory and otherwise invalid.

    .venv/bin/pytest -p no:cacheprovider plan/exec/scripts/test_reference_stats.py
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
import time
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
# Sample 3 fails; sample FAKE_HANG_AT (default 6) prints every marker, then hangs. Every demo
# call records its number, the cache it saw and how many entries that cache had at start.
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
if [ "$n" = "${FAKE_HANG_AT:-6}" ]; then sleep 300; fi
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


def workflow() -> dict[str, Any]:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def workflow_env() -> dict[str, str]:
    return {str(k): str(v) for k, v in workflow()["env"].items()}


def job_start_ago(seconds: int) -> str:
    return str(int(time.time()) - seconds)


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
            "JOB_START": job_start_ago(0),
        }
        | overrides
    )


def test_workflow_design_values() -> None:
    env = workflow_env()
    assert env["PACKAGE"] == PACKAGE
    assert (env["COLD_SAMPLES"], env["WARM_SAMPLES"]) == ("5", "2")
    assert env["SAMPLE_TIMEOUT_S"] == "600"
    assert env["TIMING_BUDGET_S"] == "2400"
    assert (env["RESERVE_S"], env["PROBE_TIMEOUT_S"], env["PROBE_MIN_LEFT_S"]) == (
        "420",
        "120",
        "420",
    )
    job = workflow()["jobs"]["reference"]
    assert job["timeout-minutes"] == 40
    assert int(env["JOB_TIMEOUT_S"]) == job["timeout-minutes"] * 60
    steps: list[dict[str, Any]] = job["steps"]
    assert steps[0]["id"] == "start" and "date +%s" in steps[0]["run"]
    assert step("Set up Python")["timeout-minutes"] == 5
    assert step("Install uv")["timeout-minutes"] == 5
    assert all("timeout-minutes" in s for s in steps)  # every step is bounded
    job_s, reserve = int(env["JOB_TIMEOUT_S"]), int(env["RESERVE_S"])
    sample_s, probe = int(env["SAMPLE_TIMEOUT_S"]), int(env["PROBE_TIMEOUT_S"])
    # The loop budget is min(TIMING_BUDGET_S, job - elapsed - reserve): the reserve is always
    # left, and in a 40-minute job the 2400 s ceiling never binds (the loop gets at most 1980 s).
    assert job_s - reserve < int(env["TIMING_BUDGET_S"])
    # What the bounds do NOT guarantee: seven samples at their full 600 s limit (4200 s > 1980 s).
    # A sample the loop cannot give its full limit is cut off (timeout_reason "budget").
    assert job_s - reserve - 600 < 7 * sample_s
    # What they do guarantee: seven samples of the measured ~225 s (run 38451606669: 213-227 s on
    # both runners), the probe and the reserve fit when setup takes under 4 minutes.
    assert 4 * 60 + 7 * 225 + probe + reserve <= job_s
    # The reserve covers everything after sampling COMBINED: the probe (which only runs with
    # PROBE_MIN_LEFT_S left, itself at least the reserve), the parse, upload and final-check
    # steps at their full timeouts, and 60 s of headroom for cleanup and the reader join.
    after = ("Parse the logs", "Upload the JSON", "Fail if any sample")
    after_s = sum(60 * step(name)["timeout-minutes"] for name in after)
    assert probe + after_s + 60 <= reserve
    assert probe < int(env["PROBE_MIN_LEFT_S"]) <= reserve
    assert int(env["PROBE_MIN_LEFT_S"]) >= probe + after_s + 60
    # The timing step's own timeout is only a backstop: the step ends by job time
    # job - reserve + probe (+ the kill/join of a last sample), well inside it, and the job
    # timeout still comes first.
    timing_s = step("Time the demo")["timeout-minutes"] * 60
    assert job_s - reserve + probe + 60 <= timing_s < job_s
    ref = "${{ steps.start.outputs.job_start }}"
    assert step("Time the demo")["env"]["JOB_START"] == ref
    assert step("Parse the logs")["env"]["JOB_START"] == ref
    assert step("Parse the logs")["if"] == "always()"
    assert step("Upload the JSON")["if"] == "always()"


def test_job_start_step(tmp_path: Path) -> None:
    out = tmp_path / "github_output"
    before = int(time.time())
    done = subprocess.run(
        ["bash", "-c", step("Record the job start")["run"]],
        env={"PATH": os.environ.get("PATH", ""), "GITHUB_OUTPUT": str(out)},
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0, done.stderr
    key, _, value = out.read_text().strip().partition("=")
    assert key == "job_start"
    assert before <= int(value) <= int(time.time())


def test_workflow_steps_dry_run(tmp_path: Path) -> None:
    env = fake_env(tmp_path, SAMPLE_TIMEOUT_S=SAMPLE_TIMEOUT_S)
    out_dir, state = Path(env["OUT_DIR"]), Path(env["FAKE_STATE"])

    done = run_step("Time the demo", tmp_path, env)
    assert done.returncode == 0, done.stderr
    assert "sample 3 (cold): exit 3" in done.stdout
    assert (
        f"sample 6 (warm): timed out after {SAMPLE_TIMEOUT_S} s (per-sample limit)" in done.stdout
    )

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
    design = doc["design"]
    assert design["job_start"] == int(env["JOB_START"])
    assert design["job_timeout_seconds"] == 2400 and design["reserve_seconds"] == 420
    # The job just started: the loop gets the 40 minutes less the 300 s reserve.
    assert 1980 - 5 <= design["budget_seconds_used"] <= 1980
    assert design["timing_budget_seconds"] == 2400
    assert design["python_probe"] == "ran"
    assert isinstance(design["sampling_seconds"], int)
    assert design["seconds_left_after_sampling"] >= 2400 - 60
    assert doc["journal_incomplete"] is False
    samples = doc["samples"]
    assert not any(s["missing"] for s in samples)
    assert [s["sample"] for s in samples] == [1, 2, 3, 4, 5, 6, 7]
    assert [s["uv_cache"] for s in samples] == ["cold"] * 5 + ["warm"] * 2
    assert [s["uv_cache_entries_at_start"] for s in samples] == [0, 0, 0, 0, 0, 1, 1]
    assert [s["exit_code"] for s in samples] == [0, 0, 3, 0, 0, None, 0]
    assert [s["timed_out"] for s in samples] == [False] * 5 + [True, False]
    assert [s["timeout_reason"] for s in samples] == [None] * 5 + ["sample", None]
    assert [s["timeout_seconds"] for s in samples] == [int(SAMPLE_TIMEOUT_S)] * 7
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
    assert "7 of 7 samples; not held: [3, 6]; timed out (hang): [6]\n" in done.stdout

    assert stats.problems(doc) == []
    lines = stats.report(out)
    assert lines[0] == "reference-test.json: Linux X64 ubuntu-latest, agent-reliability-ci==0.8.0"
    assert lines[1].startswith("  cold totals (5): ") and "failed" in lines[1]
    assert lines[2].startswith("  cold: p50 ") and "p95 not reached over target" in lines[2]
    assert lines[3].startswith("  warm totals (2): timed out (hang), ")
    assert lines[4].startswith("  warm: fewer than 5 samples")
    assert len(lines) == 5


def test_workflow_budget_used_up(tmp_path: Path) -> None:
    """2300 s into the 2400 s job: below the reserve, so no sample starts and the probe (only
    100 s left, under 420) is skipped; every sample is recorded as not started (timed out by the
    budget), the JSON still comes.
    """
    env = fake_env(tmp_path, JOB_START=job_start_ago(2300))
    out_dir, state = Path(env["OUT_DIR"]), Path(env["FAKE_STATE"])
    done = run_step("Time the demo", tmp_path, env)
    assert done.returncode == 0, done.stderr
    assert "python probe skipped" in done.stdout
    assert not (state / "calls").exists()  # neither a sample nor the probe ran
    assert "not started" in (out_dir / "sample-7.log").read_text()
    assert run_step("Parse the logs", tmp_path, env).returncode == 0
    out = out_dir / "reference-test.json"
    doc = json.loads(out.read_text())
    assert doc["design"]["budget_seconds_used"] == 0
    assert doc["design"]["python_probe"] == "skipped"
    assert doc["python"] is None
    samples = doc["samples"]
    assert [
        (s["timed_out"], s["timeout_reason"], s["started"], s["exit_code"], s["timeout_seconds"])
        for s in samples
    ] == [(True, "budget", False, None, 0)] * 7
    done = run_step("Fail if any sample", tmp_path, env | {"OUT_JSON": str(out)})
    assert done.returncode == 1
    assert "; not started: [1, 2, 3, 4, 5, 6, 7]\n" in done.stdout
    assert "hang" not in done.stdout and "cut off" not in done.stdout
    assert stats.problems(doc) == []
    lines = stats.report(out)
    assert lines[1] == "  cold totals (5): " + ", ".join(["not started"] * 5)
    assert lines[2].startswith("  cold: p50 not reached over target (<= 120 s)")


def test_workflow_budget_shrunk_by_setup(tmp_path: Path) -> None:
    """1500 s into the job (a slow setup), the loop gets 2400 - 1500 - 420 = 480 s, not 1980."""
    env = fake_env(tmp_path, JOB_START=job_start_ago(1500), FAKE_HANG_AT="0")
    done = run_step("Time the demo", tmp_path, env)
    assert done.returncode == 0, done.stderr
    assert run_step("Parse the logs", tmp_path, env).returncode == 0
    doc = json.loads((Path(env["OUT_DIR"]) / "reference-test.json").read_text())
    assert 470 <= doc["design"]["budget_seconds_used"] <= 480
    assert doc["design"]["seconds_before_sampling"] >= 1500
    assert doc["design"]["python_probe"] == "ran"
    samples = doc["samples"]
    assert [s["timeout_seconds"] <= 600 for s in samples] == [True] * 7
    assert [s["exit_code"] for s in samples] == [0, 0, 3, 0, 0, 0, 0]


def test_workflow_budget_cut_off(tmp_path: Path) -> None:
    """1976 s into the job the loop gets about 4 s (2400 - 1976 - 420). Samples 1-6 take
    milliseconds; sample 7 hangs and is killed at the loop deadline, well before its 5 s
    per-sample limit: recorded as cut off by the budget, not as a hang."""
    env = fake_env(
        tmp_path, JOB_START=job_start_ago(1976), SAMPLE_TIMEOUT_S=SAMPLE_TIMEOUT_S, FAKE_HANG_AT="7"
    )
    out_dir = Path(env["OUT_DIR"])
    done = run_step("Time the demo", tmp_path, env)
    assert done.returncode == 0, done.stderr
    assert re.search(r"sample 7 \(warm\): timed out after [1-4] s \(loop budget\)", done.stdout)
    assert run_step("Parse the logs", tmp_path, env).returncode == 0
    out = out_dir / "reference-test.json"
    doc = json.loads(out.read_text())
    assert doc["design"]["budget_seconds_used"] <= 4
    seventh = doc["samples"][6]
    assert seventh["started"] is True and seventh["timed_out"] is True
    assert seventh["timeout_reason"] == "budget"
    assert seventh["timeout_seconds"] < int(SAMPLE_TIMEOUT_S)
    assert seventh["exit_code"] is None and seventh["all_steps_held"] is None
    assert [s["timeout_reason"] for s in doc["samples"][:6]] == [None] * 6

    done = run_step("Fail if any sample", tmp_path, env | {"OUT_JSON": str(out)})
    assert done.returncode == 1
    assert "7 of 7 samples; not held: [3, 7]; cut off by budget: [7]\n" in done.stdout

    assert stats.problems(doc) == []
    lines = stats.report(out)
    assert lines[3].startswith("  warm totals (2): ") and lines[3].endswith(", cut off by budget")


def test_workflow_truncated_journal(tmp_path: Path) -> None:
    """The journal's last row is cut off mid-line (a killed or cancelled step): the complete rows
    are kept, the partial line is one incomplete entry, and its sample is counted as missing."""
    env = fake_env(tmp_path, FAKE_HANG_AT="0")
    out_dir = Path(env["OUT_DIR"])
    assert run_step("Time the demo", tmp_path, env).returncode == 0
    journal = out_dir / "samples.jsonl"
    rows = journal.read_text().splitlines()
    assert len(rows) == 7
    partial = rows[-1][: len(rows[-1]) // 2]
    journal.write_text("\n".join(rows[:-1]) + "\n" + partial)

    done = run_step("Parse the logs", tmp_path, env)
    assert done.returncode == 0, done.stderr
    out = out_dir / "reference-test.json"
    doc = json.loads(out.read_text())
    assert doc["journal_incomplete"] is True
    samples = doc["samples"]
    assert [s["sample"] for s in samples] == [1, 2, 3, 4, 5, 6, 7, None]
    assert samples[-1] == {"sample": None, "incomplete": True, "raw_prefix": partial[:80]}
    seventh = samples[6]
    assert seventh["missing"] is True and seventh["started"] is False
    assert seventh["timed_out"] is False and seventh["timeout_reason"] is None
    assert seventh["uv_cache"] == "warm"
    assert seventh["exit_code"] is None and seventh["all_steps_held"] is None
    assert seventh["log"] == "sample-7.log"  # its log is kept and named
    assert not any(s["missing"] for s in samples[:6])

    done = run_step("Fail if any sample", tmp_path, env | {"OUT_JSON": str(out)})
    assert done.returncode == 1
    assert "7 of 7 samples; not held: [3, 7]; missing: [7]; journal incomplete\n" in done.stdout

    assert stats.problems(doc) == []
    lines = stats.report(out)
    assert lines[3].startswith("  warm totals (2): ") and lines[3].endswith(", missing")
    assert lines[-1] == (
        "  journal: 1 incomplete line(s), not counted;"
        " a sample with no complete journal row is counted as missing"
    )


JOURNALS: dict[str, bytes] = {
    "partial row": b'{"sample": 1, "uv_cache": "cold", "comm',
    "not a record": b"42\n[]\nnull\n",
    "sample number not an integer": b'{"sample": "1"}\n{"sample": true}\n',
    "row without fields": b'{"sample": 1}\n',
    "invalid utf-8": b"\xff\xfe\x00garbage\n",
    "deep nesting": b"[" * 200_000 + b"\n",
    "blank lines only": b"\n\n  \n",
}


@pytest.mark.parametrize("case", sorted(JOURNALS))
def test_parse_step_survives_any_journal(case: str, tmp_path: Path) -> None:
    env = fake_env(tmp_path)
    out_dir = Path(env["OUT_DIR"])
    out_dir.mkdir()
    (out_dir / "samples.jsonl").write_bytes(JOURNALS[case])
    (out_dir / "timing.json").write_text("{not json")
    done = run_step("Parse the logs", tmp_path, env)
    assert done.returncode == 0, done.stderr
    doc = json.loads((out_dir / "reference-test.json").read_text())
    numbered = [s for s in doc["samples"] if s["sample"] is not None]
    assert [s["sample"] for s in numbered] == [1, 2, 3, 4, 5, 6, 7]
    incomplete = [s for s in doc["samples"] if s.get("incomplete")]
    assert doc["journal_incomplete"] is bool(incomplete)
    assert all(len(s["raw_prefix"]) <= 80 for s in incomplete)
    assert doc["design"]["job_start"] == int(env["JOB_START"])  # from env, timing.json unreadable
    assert doc["design"]["budget_seconds_used"] is None
    stats.problems(doc)  # never raises either
    done = run_step(
        "Fail if any sample", tmp_path, env | {"OUT_JSON": str(out_dir / "reference-test.json")}
    )
    assert done.returncode == 1


def test_parse_step_without_samples(tmp_path: Path) -> None:
    """The timing step died before writing anything: the JSON step still writes a file, with
    every designed sample recorded as missing."""
    env = fake_env(tmp_path)
    done = run_step("Parse the logs", tmp_path, env)
    assert done.returncode == 0, done.stderr
    out = Path(env["OUT_DIR"]) / "reference-test.json"
    doc = json.loads(out.read_text())
    assert doc["journal_incomplete"] is False
    assert [(s["sample"], s["missing"], s["started"]) for s in doc["samples"]] == [
        (n, True, False) for n in range(1, 8)
    ]
    assert [s["log"] for s in doc["samples"]] == [None] * 7
    assert stats.problems(doc) == []
    assert stats.report(out)[1] == "  cold totals (5): " + ", ".join(["missing"] * 5)


T0 = "2026-10-14T10:00:00Z"


def at(seconds: int) -> str:
    return f"2026-10-14T10:{seconds // 60:02d}:{seconds % 60:02d}Z"


def sample(
    n: int,
    cache: str,
    held: int | None,
    exit_code: int | None = 0,
    *,
    timed_out: bool = False,
    reason: str | None = None,
) -> dict[str, Any]:
    """A sample that started at T0 and held `held` seconds later (None: never held).

    A timed-out sample is a hang (timeout_reason "sample") unless `reason` says otherwise.
    """
    return {
        "sample": n,
        "uv_cache": cache,
        "command_start": T0,
        "demo_banner": at(1),
        "demo_verdict": at(2),
        "all_steps_held": None if held is None else at(held),
        "exit_code": exit_code,
        "timed_out": timed_out,
        "timeout_reason": (reason or "sample") if timed_out else reason,
        "started": True,
    }


def write_doc(path: Path, samples: list[Any]) -> Path:
    doc = {
        "package": PACKAGE,
        "runner": {"os": "macOS", "arch": "ARM64", "label": "macos-latest"},
        "samples": samples,
    }
    path.write_text(json.dumps(doc), encoding="utf-8")
    return path


# A designed sample with no complete journal row, as the parse step writes it.
MISSING: dict[str, Any] = {
    "sample": 1,
    "uv_cache": "cold",
    "command_start": None,
    "demo_banner": None,
    "demo_verdict": None,
    "all_steps_held": None,
    "exit_code": None,
    "log": None,
    "timed_out": False,
    "timeout_reason": None,
    "started": False,
    "missing": True,
}
# A sample the loop had no time left for, as the timing step writes it.
NOT_STARTED: dict[str, Any] = {
    "started": False,
    "timed_out": True,
    "timeout_reason": "budget",
    "timeout_seconds": 0,
    "demo_banner": None,
    "demo_verdict": None,
}
NO_REASON: dict[str, Any] = {"timeout_reason": None}
INCOMPLETE: dict[str, Any] = {"sample": None, "incomplete": True, "raw_prefix": '{"sample": 7, "u'}

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
    assert lines[1] == "  cold totals (5): 60 s, failed, timed out (hang), 70 s, 80 s"
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
        "samples[0]: 'exit_code' is None"
        " (null only for a timed-out, not-started or missing sample)",
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
    # Contradictions (review 18 round 2, finding 3): fields of one sample that cannot all hold.
    "exit 0 without banner": (
        {"samples": [sample(1, "cold", 60) | {"demo_banner": None}]},
        "samples[0]: exit 0 but 'demo_banner' is missing",
    ),
    "exit 0 without verdict": (
        {"samples": [sample(1, "cold", 60) | {"demo_verdict": None}]},
        "samples[0]: exit 0 but 'demo_verdict' is missing",
    ),
    "exit 0 without all steps held": (
        {"samples": [sample(1, "cold", None)]},
        "samples[0]: exit 0 but 'all_steps_held' is missing",
    ),
    "not started but exit 0": (
        {"samples": [sample(1, "cold", 60) | {"started": False}]},
        "samples[0]: not started but 'exit_code' is 0",
    ),
    "not started but stamped": (
        {"samples": [sample(1, "cold", None, exit_code=None) | {"started": False}]},
        "samples[0]: not started but 'demo_banner' is set",
    ),
    "started missing": (
        {"samples": [{k: v for k, v in sample(1, "cold", 60).items() if k != "started"}]},
        "samples[0]: 'started' is None, not true or false",
    ),
    "started not a bool": (
        {"samples": [sample(1, "cold", 60) | {"started": "yes"}]},
        "samples[0]: 'started' is 'yes', not true or false",
    ),
    "timed_out missing": (
        {"samples": [{k: v for k, v in sample(1, "cold", 60).items() if k != "timed_out"}]},
        "samples[0]: 'timed_out' is None, not true or false",
    ),
    "timed out with exit code": (
        {"samples": [sample(1, "cold", None, exit_code=0, timed_out=True)]},
        "samples[0]: timed out but 'exit_code' is 0",
    ),
    "exit code not an integer": (
        {"samples": [sample(1, "cold", 60) | {"exit_code": "0"}]},
        "samples[0]: 'exit_code' is '0', not an integer or null",
    ),
    "missing but started": (
        {"samples": [MISSING | {"started": True}]},
        "samples[0]: missing from the journal but 'started' is true",
    ),
    "missing but timed out": (
        {"samples": [MISSING | {"timed_out": True}]},
        "samples[0]: missing from the journal but 'timed_out' is true",
    ),
    "missing but stamped": (
        {"samples": [MISSING | {"command_start": T0}]},
        "samples[0]: missing from the journal but 'command_start' is set",
    ),
    "missing not a bool": (
        {"samples": [sample(1, "cold", 60) | {"missing": "no"}]},
        "samples[0]: 'missing' is 'no', not true or false",
    ),
    "uv_cache missing": (
        {"samples": [{k: v for k, v in sample(1, "cold", 60).items() if k != "uv_cache"}]},
        "samples[0]: 'uv_cache' is None, not cold or warm",
    ),
    "cold cache not empty": (
        {"samples": [sample(1, "cold", 60) | {"uv_cache_entries_at_start": 3}]},
        "samples[0]: cold sample but its uv cache had 3 entries at start",
    ),
    # Review 18r2: a sample left unstarted is recorded as timed out by the budget; only a sample
    # missing from the journal is neither started nor timed out.
    "not started and not timed out": (
        {"samples": [sample(1, "cold", None, exit_code=None) | NOT_STARTED | {"timed_out": False}]},
        "samples[0]: not started but 'timed_out' is false (and not missing)",
    ),
    "timed out without a reason": (
        {"samples": [sample(1, "cold", None, exit_code=None, timed_out=True) | NO_REASON]},
        "samples[0]: timed out but 'timeout_reason' is null",
    ),
    "reason without a timeout": (
        {"samples": [sample(1, "cold", 60, reason="budget")]},
        "samples[0]: not timed out but 'timeout_reason' is 'budget'",
    ),
    "unknown reason": (
        {"samples": [sample(1, "cold", None, exit_code=None, timed_out=True, reason="slow")]},
        "samples[0]: 'timeout_reason' is 'slow', not 'sample', 'budget' or null",
    ),
    "not started by a hang": (
        {
            "samples": [
                sample(1, "cold", None, exit_code=None) | NOT_STARTED | {"timeout_reason": "sample"}
            ]
        },
        "samples[0]: not started but 'timeout_reason' is 'sample'",
    ),
    "hang below the per-sample limit": (
        {
            "design": {"sample_timeout_seconds": 600},
            "samples": [
                sample(1, "cold", None, exit_code=None, timed_out=True) | {"timeout_seconds": 77}
            ],
        },
        "samples[0]: 'timeout_reason' is 'sample' but its limit 77 s < 600 s",
    ),
    "budget cut-off at the full limit": (
        {
            "design": {"sample_timeout_seconds": 600},
            "samples": [
                sample(1, "cold", None, exit_code=None, timed_out=True, reason="budget")
                | {"timeout_seconds": 600}
            ],
        },
        "samples[0]: 'timeout_reason' is 'budget' but its limit 600 s >= 600 s",
    ),
    "timeout seconds not a count": (
        {"samples": [sample(1, "cold", 60) | {"timeout_seconds": 1.5}]},
        "samples[0]: 'timeout_seconds' is 1.5, not a whole number of seconds",
    ),
    "cache entries not a count": (
        {"samples": [sample(1, "warm", 60) | {"uv_cache_entries_at_start": -1}]},
        "samples[0]: 'uv_cache_entries_at_start' is -1, not a count",
    ),
    "incomplete line without the journal flag": (
        {"samples": [INCOMPLETE]},
        "1 incomplete journal line(s) but 'journal_incomplete' is not true",
    ),
    "journal flag without an incomplete line": (
        {"journal_incomplete": True, "samples": [sample(1, "cold", 60)]},
        "'journal_incomplete' is true but no entry is an incomplete journal line",
    ),
    "journal flag not a bool": (
        {"journal_incomplete": "yes", "samples": [sample(1, "cold", 60)]},
        "'journal_incomplete' is 'yes', not true or false",
    ),
    "incomplete line with a sample number": (
        {"journal_incomplete": True, "samples": [INCOMPLETE | {"sample": 3}]},
        "samples[0]: incomplete journal line but 'sample' is 3",
    ),
    "incomplete line without raw prefix": (
        {"journal_incomplete": True, "samples": [{"sample": None, "incomplete": True}]},
        "samples[0]: incomplete journal line without a 'raw_prefix'",
    ),
    "incomplete not a bool": (
        {"samples": [sample(1, "cold", 60) | {"incomplete": 1}]},
        "samples[0]: 'incomplete' is 1, not true or false",
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


def test_astra_repro_unstamped_successes_are_invalid(tmp_path: Path) -> None:
    """Review 18 round 2, finding 3: five 10 s "successes" with no banner or verdict stamp (and
    the same with started: false) used to report both targets "within"."""
    unstamped = [
        sample(n, "cold", 10) | {"demo_banner": None, "demo_verdict": None} for n in range(1, 6)
    ]
    not_started = [sample(n, "cold", 10) | {"started": False} for n in range(1, 6)]
    for name, samples in (("unstamped", unstamped), ("not-started", not_started)):
        lines = stats.report(write_doc(tmp_path / f"reference-{name}.json", samples))
        assert lines[0] == f"reference-{name}.json: INVALID, no figures reported"
        assert not any("within" in line or "p50" in line for line in lines)
        for s in samples:
            assert stats.total(s) is None


def test_missing_and_not_started_samples_are_failures(tmp_path: Path) -> None:
    samples = [
        sample(1, "cold", 60),
        MISSING | {"sample": 2},
        sample(3, "cold", None, exit_code=None) | NOT_STARTED,
        sample(4, "cold", 70),
        sample(5, "cold", 80),
    ]
    path = write_doc(tmp_path / "r.json", samples)
    assert stats.problems(json.loads(path.read_text())) == []
    lines = stats.report(path)
    assert lines[1] == "  cold totals (5): 60 s, missing, not started, 70 s, 80 s"
    assert lines[2] == (
        "  cold: p50 80 s within target (<= 120 s); p95 not reached over target (<= 180 s);"
        " p95 of 5 is the maximum"
    )


def test_hang_budget_cut_off_and_not_started_are_told_apart(tmp_path: Path) -> None:
    """Review 18r2: a budget cut-off used to read exactly like a hang. All three are failures
    that rank above every success."""
    samples = [
        sample(1, "cold", 50),
        sample(2, "cold", 60),
        sample(3, "cold", None, exit_code=None, timed_out=True) | {"timeout_seconds": 600},
        sample(4, "cold", None, exit_code=None, timed_out=True, reason="budget")
        | {"timeout_seconds": 77},
        sample(5, "cold", None, exit_code=None) | NOT_STARTED,
    ]
    doc = {"design": {"sample_timeout_seconds": 600}, "samples": samples}
    assert stats.problems(doc) == []
    path = tmp_path / "r.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    lines = stats.report(path)
    assert lines[1] == (
        "  cold totals (5): 50 s, 60 s, timed out (hang), cut off by budget, not started"
    )
    assert lines[2] == (
        "  cold: p50 not reached over target (<= 120 s); p95 not reached over target (<= 180 s);"
        " p95 of 5 is the maximum"
    )
    assert all(stats.total(s) is None for s in samples[2:])


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
    assert (
        stats.total(sample(1, "cold", 60, exit_code=None, timed_out=True, reason="budget")) is None
    )
    assert stats.total(sample(1, "cold", 60) | {"command_start": "garbage"}) is None
    assert stats.total(sample(1, "cold", 60) | {"demo_banner": None}) is None
    assert stats.total(sample(1, "cold", 60) | {"demo_verdict": at(70)}) is None  # out of order
    assert stats.total(sample(1, "cold", 60) | {"started": False}) is None
    assert stats.total(sample(1, "cold", 60) | {"started": None}) is None
    assert stats.total(sample(1, "cold", 60) | {"missing": True}) is None
    assert stats.total(sample(1, "cold", 60) | {"exit_code": False}) is None
    assert stats.total({k: v for k, v in sample(1, "cold", 60).items() if k != "timed_out"}) is None


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
