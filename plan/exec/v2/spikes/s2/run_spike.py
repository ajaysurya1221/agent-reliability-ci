"""Run S2 evidence checks offline; preserve every invocation in out/run-NNNN/."""

from __future__ import annotations

import hashlib
import json
import os
import statistics
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from importlib.metadata import version
from pathlib import Path
from typing import Any, cast

from adapter_spike import ScriptedModel
from langchain.agents import create_agent
from langchain_core.tools import StructuredTool

from arci.runner import run_trial
from arci.schedule import build_schedule
from arci.schema import Condition, ReplayBundle, ToolMode, TrialEnvelope, TrialSpec
from arci.storage import load_run

OWNED = Path(__file__).resolve().parent
ROOT = OWNED.parents[4]
PYTHON = Path("/Users/ajay/Developer/.arci-worktrees/v2-spike-venv/bin/python")


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise AssertionError(reason)


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def native_parallel_probe() -> dict[str, object]:
    """Two rendezvousing tool bodies establish actual overlap, without timing guesses."""
    barrier = threading.Barrier(2, timeout=5)
    lock = threading.Lock()
    active = 0
    peak = 0
    calls = 0
    threads: list[str] = []

    def lookup(key: str) -> str:
        """Probe a native LangChain tool."""
        nonlocal active, peak, calls
        require(key == "answer", "unexpected probe key")
        with lock:
            active += 1
            calls += 1
            peak = max(peak, active)
            threads.append(threading.current_thread().name)
        try:
            barrier.wait()
        finally:
            with lock:
                active -= 1
        return json.dumps("forty-two")

    graph = create_agent(
        ScriptedModel(responses=[], parallel=True),
        tools=[StructuredTool.from_function(lookup)],
    )
    graph.invoke({"messages": [{"role": "user", "content": "Make two calls"}]})
    return {"body_calls": calls, "peak_active": peak, "threads": threads}


def main() -> int:
    require(Path(sys.executable).absolute() == PYTHON, f"use the supplied interpreter: {PYTHON}")
    sys.dont_write_bytecode = True
    output = OWNED / "out"
    output.mkdir(exist_ok=True)
    previous = sorted(output.glob("run-[0-9][0-9][0-9][0-9]"))
    run = output / f"run-{len(previous) + 1:04d}"
    run.mkdir()
    source_hashes = {
        name: hashlib.sha256((OWNED / name).read_bytes()).hexdigest()
        for name in ("adapter_spike.py", "run_spike.py", "arci.yaml")
    }
    write_json(run / "source-hashes.json", source_hashes)
    temporary = run / "tmp"
    temporary.mkdir()
    os.environ.update(
        PYTHONPATH=os.pathsep.join((str(ROOT / "src"), str(OWNED))),
        PYTHONDONTWRITEBYTECODE="1",
        LANGSMITH_TRACING="false",
        LANGCHAIN_TRACING_V2="false",
        LANGCHAIN_TRACING="false",
        TMPDIR=str(temporary),
    )
    checks: dict[str, bool] = {}
    notes: dict[str, str] = {}

    def check(name: str, action: Callable[[], str]) -> None:
        try:
            reason = action()
        except Exception as exc:
            checks[name] = False
            reason = f"{type(exc).__name__}: {exc}"
        else:
            checks[name] = True
        reason = " ".join(reason.splitlines())
        notes[name] = reason
        print(f"{'OK' if checks[name] else 'FAIL'} {name}: {reason}", flush=True)

    def cli(name: str, *args: str) -> subprocess.CompletedProcess[str]:
        command = [str(PYTHON), "-B", "-m", "arci", *args]
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=180)
        (run / f"{name}.stdout.txt").write_text(result.stdout)
        (run / f"{name}.stderr.txt").write_text(result.stderr)
        write_json(run / f"{name}.command.json", {"argv": command, "exit": result.returncode})
        return result

    def versions() -> str:
        expected = {"langchain": "1.4.9", "langgraph": "1.2.20", "langchain-core": "1.7.7"}
        observed = {package: version(package) for package in expected}
        write_json(run / "versions.json", observed)
        require(observed == expected, f"version drift: {observed}")
        return str(observed)

    check("versions", versions)
    store = run / "s2-langchain-spike"

    def experiment() -> str:
        result = cli(
            "experiment", "run", str(OWNED / "arci.yaml"), "--out", str(run), "--workers", "1"
        )
        require(result.returncode == 2, f"expected small-N exit 2; got {result.returncode}")
        _, trials = load_run(store)
        require(len(trials) == 12, f"expected 12 trials, got {len(trials)}")
        require(
            all(t.outcome == ("PASS" if t.arm == "baseline" else "FAIL") for t in trials),
            "expected six robust PASS and six fragile FAIL",
        )
        require(all(t.termination == "completed" for t in trials), "unexpected termination")
        return (
            "12 real-runner trials; baseline 6 PASS, candidate 6 FAIL; gate INCONCLUSIVE (exit 2)"
        )

    check("experiment", experiment)
    if not store.exists() or not (store / "trials.jsonl").exists():
        write_json(run / "checks.json", {"checks": checks, "notes": notes})
        return 1
    manifest, trials = load_run(store)
    specs = build_schedule(manifest)
    robust = next(t for t in trials if t.arm == "baseline" and t.condition_id == "tool_timeout")
    fragile = next(t for t in trials if t.pair_id == robust.pair_id and t.arm == "candidate")
    robust_spec = next(s for s in specs if s.trial_id == robust.trial_id)

    def trial(name: str, **updates: Any) -> TrialEnvelope:
        spec = TrialSpec.model_validate(robust_spec.model_dump() | updates)
        envelope = run_trial(spec, lambda _event: None, manifest.contract)
        (run / f"{name}.spec.json").write_text(spec.model_dump_json(indent=2) + "\n")
        (run / f"{name}.trial.json").write_text(envelope.model_dump_json(indent=2) + "\n")
        return envelope

    def exactly_once() -> str:
        for item in trials:
            require(item.final_state is not None, "missing snapshot")
            state = cast(dict[str, Any], item.final_state)
            boundary_calls = 2 if item.arm == "baseline" else 1
            expected = boundary_calls - (item.condition_id != "empty_result")
            require(item.usage.tool_calls == boundary_calls, "wrong boundary count")
            require(
                state["environment"]["body_calls"] == expected, f"wrong body count: {item.trial_id}"
            )
        clean = trial("clean", condition=Condition(condition_id="clean").model_dump())
        require(clean.outcome == "PASS", f"clean: {clean.failure_detail}")
        require(
            cast(dict[str, Any], clean.final_state)["environment"]["body_calls"] == 1,
            "clean body must run once",
        )
        return (
            "clean=1 body/call; pre-fault=0 bodies; empty_result=1 body/call; "
            "schema handler never ran"
        )

    check("exactly_once", exactly_once)

    def faults() -> str:
        counts: dict[str, int] = {}
        for name in ("tool_timeout", "tool_error_once", "empty_result"):
            matching = [t for t in trials if t.condition_id == name]
            counts[name] = sum(
                e.payload.get("injected_by") == name
                for t in matching
                for e in t.events
                if e.kind == "tool_finish"
            )
            require(counts[name] == 4, f"{name} did not fire in all four trials")
            for item in matching:
                observations = cast(dict[str, Any], item.final_state)["observations"]
                require(
                    observations[0]["status"] == ("success" if name == "empty_result" else "error"),
                    "fault was not visible with expected ToolMessage status",
                )
                if name == "empty_result":
                    require(observations[0]["content"] == "null", "empty result was hidden")
        write_json(run / "fault-accounting.json", counts)
        return f"recorded injections {counts}; error ToolMessages / JSON null reached the model"

    check("faults", faults)

    def real_error() -> str:
        for agent, expected in (("baseline", "PASS"), ("candidate", "FAIL")):
            item = trial(
                f"real-error-{agent}",
                agent=f"adapter_spike:{agent}",
                task={"answer": "forty-two", "real_error": True},
                condition=Condition(condition_id="real-error").model_dump(),
            )
            require(item.outcome == expected, f"real error: {item.failure_detail}")
            first = cast(dict[str, Any], item.final_state)["observations"][0]
            require(
                first["status"] == "error" and "fixture service unavailable" in first["content"],
                "real error not visible",
            )
        return (
            "real tool exception follows the same error ToolMessage path; retry PASS, no retry FAIL"
        )

    check("real_tool_failure", real_error)

    def budget() -> str:
        item = trial(
            "budget", budgets=manifest.budgets.model_copy(update={"max_tool_calls": 1}).model_dump()
        )
        require((item.outcome, item.termination) == ("FAIL", "budget"), str(item.failure_detail))
        require(item.usage.tool_calls == 1, "over-budget call emitted tool events")
        return "FAIL/budget; injected attempt counts; rejected retry has no tool_start"

    check("budget", budget)

    def snapshot() -> str:
        require(
            robust.agent_claimed_success is False and robust.outcome == "PASS",
            "claim affected PASS",
        )
        require(
            fragile.agent_claimed_success is True and fragile.outcome == "FAIL",
            "claim affected FAIL",
        )
        item = trial(
            "erased-capture",
            task={"answer": "forty-two", "erase_capture": True},
            condition=Condition(condition_id="clean").model_dump(),
        )
        require(item.outcome == "FAIL" and item.termination == "completed", "erased answer passed")
        state = cast(dict[str, Any], item.final_state)
        require(
            state["environment"]["answer"] == "forty-two" and state["final_output"] is None,
            "snapshot ablation was not isolated",
        )
        return (
            "false claim + correct snapshot PASS; true claim + wrong answer FAIL; "
            "erased capture FAIL"
        )

    check("snapshot_only", snapshot)
    bundle_path = run / "bundle.json"

    def replay_and_diff() -> str:
        result = cli(
            "bundle",
            "bundle",
            str(store),
            fragile.trial_id,
            "--out",
            str(bundle_path),
            "--root",
            str(OWNED),
            "--include",
            "adapter_spike.py",
        )
        require(result.returncode == 0, "bundle failed")
        result = cli("replay", "replay", str(bundle_path))
        require(result.returncode == 0 and result.stdout.startswith("REPRODUCED:"), result.stdout)
        result = cli("diff", "diff", str(store), robust.trial_id, fragile.trial_id)
        require(
            result.returncode == 0
            and "common_prefix: 5" in result.stdout
            and "after_injection: tool_timeout" in result.stdout
            and 'left: tool_start tool="lookup"' in result.stdout
            and "right: agent_result" in result.stdout,
            result.stdout,
        )
        return (
            "bundled failing candidate REPRODUCED; same-pair diff diverges after timeout, prefix 5"
        )

    check("replay_and_diff", replay_and_diff)

    def replay_miss() -> str:
        item = trial(
            "replay-miss",
            tool_mode=ToolMode.REPLAY,
            recording=[],
            replay_final_state=robust.final_state,
        )
        require(
            (item.outcome, item.termination) == ("ERROR", "replay_miss"), str(item.failure_detail)
        )
        bundle = ReplayBundle.model_validate_json(bundle_path.read_text())
        invalid = ReplayBundle.create(
            **(
                bundle.model_dump(exclude={"record_sha256"})
                | {"spec": bundle.spec.model_copy(update={"recording": ()})}
            )
        )
        path = run / "missing-recording.bundle.json"
        path.write_text(invalid.model_dump_json(indent=2) + "\n")
        result = cli("replay-miss", "replay", str(path))
        require(result.returncode == 3 and result.stdout.startswith("INVALID:"), result.stdout)
        return (
            "missing recording propagates ERROR/replay_miss; sealed bundle replays INVALID (exit 3)"
        )

    check("replay_miss", replay_miss)

    def parallel() -> str:
        observed = native_parallel_probe()
        write_json(run / "native-parallel.json", observed)
        require(observed["peak_active"] == 2 and observed["body_calls"] == 2, str(observed))
        item = trial("parallel", task={"answer": "forty-two", "shape": "parallel"})
        require((item.outcome, item.termination) == ("FAIL", "crash"), str(item.failure_detail))
        require(
            "parallel tool calls unsupported" in (item.failure_detail or ""), "unclear rejection"
        )
        require(item.usage.tool_calls == 0, "parallel response reached ToolBox")
        require(
            cast(dict[str, Any], item.final_state)["environment"]["body_calls"] == 0,
            "body executed",
        )
        return (
            "native create_agent overlaps 2 tool bodies; "
            "adapter rejects both before ToolBox (0 calls)"
        )

    check("parallel", parallel)

    def unsupported() -> str:
        for shape, expected, message in (
            ("command", ("ERROR", "harness_error"), "Command"),
            ("result", ("ERROR", "harness_error"), "set"),
            ("arguments", ("FAIL", "crash"), "non-JSON"),
            ("async", ("FAIL", "crash"), "async invocation unsupported"),
        ):
            item = trial(
                f"unsupported-{shape}",
                task={"answer": "forty-two", "shape": shape},
                condition=Condition(condition_id="clean").model_dump(),
            )
            require((item.outcome, item.termination) == expected, f"{shape}: {item.failure_detail}")
            diagnostic = item.failure_detail or ""
            if item.final_state:
                diagnostic += str(item.final_state.get("adapter_error", ""))
            require(message in diagnostic, f"unclear {shape} error: {diagnostic}")
            if shape in ("arguments", "async"):
                require(item.usage.tool_calls == 0, f"{shape} reached ToolBox")
        return (
            "Command/set results ERROR/harness_error; "
            "non-JSON arguments and async FAIL/crash; explicit errors"
        )

    check("unsupported", unsupported)

    def startup() -> str:
        samples: list[dict[str, float]] = []
        code = (
            "import time,json; t=time.perf_counter(); import arci.worker; "
            "import adapter_spike; from langchain.agents import create_agent; "
            "print(json.dumps({'imports_seconds':time.perf_counter()-t}),flush=True)"
        )
        for _ in range(10):
            started = time.perf_counter()
            child = subprocess.Popen(
                [str(PYTHON), "-B", "-P", "-c", code],
                cwd=ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            stdout, stderr = child.communicate(timeout=30)
            elapsed = time.perf_counter() - started
            require(child.returncode == 0, stderr)
            sample = cast(dict[str, float], json.loads(stdout))
            sample["spawn_import_exit_seconds"] = elapsed
            samples.append(sample)
        med = statistics.median(s["spawn_import_exit_seconds"] for s in samples)
        imports = statistics.median(s["imports_seconds"] for s in samples)
        write_json(
            run / "startup.json",
            {
                "samples": samples,
                "median_seconds": med,
                "median_imports_seconds": imports,
                "definition": (
                    "fresh interpreter + worker/adapter imports + exit; warm filesystem cache"
                ),
            },
        )
        return f"10 fresh children: median spawn/import/exit {med:.4f}s; imports {imports:.4f}s"

    check("startup", startup)

    def frozen() -> str:
        result = subprocess.run(
            ["shasum", "-a", "256", "-c", "FROZEN.sha256"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )
        (run / "frozen.txt").write_text(result.stdout + result.stderr)
        require(result.returncode == 0, "frozen hashes changed")
        return f"{result.stdout.count(': OK')} frozen hashes match"

    check("frozen", frozen)

    def scope() -> str:
        before = cast(dict[str, str], json.loads((OWNED / "scope_before.json").read_text()))
        files = (
            subprocess.check_output(
                ["git", "ls-files", "-co", "--exclude-standard", "-z"], cwd=ROOT
            )
            .decode()
            .split("\0")
        )
        current = {
            p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest()
            for p in files
            if p and not p.startswith("plan/exec/v2/spikes/s2/") and (ROOT / p).is_file()
        }
        differences = sorted(
            p for p in before.keys() | current.keys() if before.get(p) != current.get(p)
        )
        write_json(run / "scope-differences.json", differences)
        status = subprocess.check_output(
            ["git", "status", "--short", "--untracked-files=all"], cwd=ROOT
        ).decode()
        (run / "status.txt").write_text(status)
        require(not differences, f"outside-owned paths changed: {differences}")
        return (
            f"{len(before)} pre-existing outside-owned files unchanged; "
            "pre-existing untracked paths retained"
        )

    check("scope", scope)
    verdicts = {
        t.trial_id: {
            "outcome": t.outcome.value,
            "termination": t.termination.value,
            "record_sha256": t.record_sha256,
        }
        for t in trials
    }
    write_json(run / "verdicts.json", verdicts)

    def repeat() -> str:
        if not previous or not (previous[-1] / "source-hashes.json").exists():
            return (
                "first invocation saved; rerun to compare checks, verdicts and sealed trial hashes"
            )
        old = previous[-1]
        if json.loads((old / "source-hashes.json").read_text()) != source_hashes:
            return "source changed since previous invocation; rerun this version for repeatability"
        require(
            json.loads((old / "verdicts.json").read_text()) == verdicts,
            "trial verdicts or hashes differ",
        )
        old_checks = cast(dict[str, Any], json.loads((old / "checks.json").read_text()))["checks"]
        require(
            all(old_checks.get(name) == passed for name, passed in checks.items()),
            "check verdicts differ",
        )
        return "previous invocation has identical check verdicts and all 12 sealed trial hashes"

    check("repeatability", repeat)
    write_json(run / "checks.json", {"checks": checks, "notes": notes})
    (output / "latest.txt").write_text(str(run.relative_to(OWNED)) + "\n")
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
