"""Offline S2b evidence runner. Every invocation and failing assertion is retained."""

from __future__ import annotations

import hashlib
import json
import os
import statistics
import subprocess
import sys
import tempfile
from collections.abc import Callable
from importlib.metadata import version
from pathlib import Path
from typing import Any, cast

from langchain_core.messages import ToolMessage
from pydantic import JsonValue

from arci.replay import make_bundle, replay
from arci.runner import run_trial
from arci.schedule import build_schedule
from arci.schema import ReplayBundle, ToolMode, TrialEnvelope, TrialSpec
from arci.storage import load_run

OWNED = Path(__file__).resolve().parent
ROOT = OWNED.parents[4]
PYTHON = Path("/Users/ajay/Developer/.arci-worktrees/v2-spike-venv/bin/python")


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise AssertionError(reason)


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def inventory() -> dict[str, str]:
    files = (
        subprocess.check_output(["git", "ls-files", "-co", "--exclude-standard", "-z"], cwd=ROOT)
        .decode()
        .split("\0")
    )
    return {
        p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest()
        for p in files
        if p and not p.startswith("plan/exec/v2/") and (ROOT / p).is_file()
    }


def body_calls(envelope: TrialEnvelope) -> int:
    state = cast(dict[str, Any], envelope.final_state)
    return int(state["tool_metadata"]["lookup"]["user_state"]["body_calls"])


def final_output(envelope: TrialEnvelope) -> Any:
    return (envelope.final_state or {}).get("final_output")


def native(task: dict[str, JsonValue]) -> dict[str, Any]:
    from probe_app import build_agent, make_tools

    tools = make_tools(task, 42000)
    graph = build_agent(tools, [])
    answer = None
    exception = None
    observations: list[dict[str, Any]] = []
    try:
        result = graph.invoke({"messages": [{"role": "user", "content": json.dumps(task)}]})
        answer = result["messages"][-1].text
        observations = [
            {"content": m.content, "status": m.status}
            for m in result["messages"]
            if isinstance(m, ToolMessage)
        ]
    except Exception as exc:
        exception = type(exc).__name__
    return {
        "answer": answer,
        "exception": exception,
        "observations": observations,
        "body_calls": (tools[0].metadata or {})["user_state"]["body_calls"],
    }


def main() -> int:
    require(Path(sys.executable).absolute() == PYTHON, f"use {PYTHON}")
    sys.dont_write_bytecode = True
    output = OWNED / "out"
    output.mkdir(exist_ok=True)
    previous = sorted(output.glob("run-[0-9][0-9][0-9][0-9]"))
    run = output / f"run-{len(previous) + 1:04d}"
    run.mkdir()
    (run / "tmp").mkdir()
    os.environ.update(
        PYTHONPATH=os.pathsep.join((str(ROOT / "src"), str(OWNED))),
        PYTHONDONTWRITEBYTECODE="1",
        LANGSMITH_TRACING="false",
        LANGCHAIN_TRACING_V2="false",
        LANGCHAIN_TRACING="false",
        TMPDIR=str(run / "tmp"),
    )
    tempfile.tempdir = str(run / "tmp")
    sources = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in [*sorted(OWNED.glob("*.py")), OWNED / "arci.yaml"]
    }
    write_json(run / "source-hashes.json", sources)
    checks: dict[str, bool] = {}
    notes: dict[str, str] = {}
    envelopes: dict[str, TrialEnvelope] = {}

    def check(name: str, action: Callable[[], str]) -> None:
        try:
            reason = action()
        except Exception as exc:
            checks[name] = False
            reason = f"{type(exc).__name__}: {exc}"
        else:
            checks[name] = True
        notes[name] = " ".join(reason.splitlines())
        print(f"{'OK' if checks[name] else 'FAIL'} {name}: {notes[name]}", flush=True)
        write_json(run / "checks.json", {"checks": checks, "notes": notes})

    def command(name: str, args: list[str], timeout: int = 180) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, timeout=timeout)
        (run / f"{name}.stdout.txt").write_text(result.stdout)
        (run / f"{name}.stderr.txt").write_text(result.stderr)
        write_json(run / f"{name}.command.json", {"argv": args, "exit": result.returncode})
        return result

    def versions() -> str:
        expected = {"langchain": "1.4.9", "langgraph": "1.2.20", "langchain-core": "1.7.7"}
        actual = {name: version(name) for name in expected}
        write_json(run / "versions.json", actual)
        require(actual == expected, str(actual))
        return str(actual)

    check("versions", versions)
    result = command(
        "experiment",
        [
            str(PYTHON),
            "-B",
            "-m",
            "arci",
            "run",
            str(OWNED / "arci.yaml"),
            "--out",
            str(run),
            "--workers",
            "1",
        ],
    )
    store = run / "s2b-langchain-spike"
    if not (store / "trials.jsonl").exists():
        check("experiment", lambda: require(False, f"no store; CLI exit {result.returncode}") or "")
        return 1
    manifest, trials = load_run(store)
    specs = build_schedule(manifest)
    base = specs[0]
    for item in trials:
        envelopes[f"scheduled-{item.trial_id}"] = item

    def experiment() -> str:
        require(result.returncode == 2, f"CLI exit {result.returncode}; expected INCONCLUSIVE=2")
        require(len(trials) == 12, f"{len(trials)} scheduled trials")
        require(all(t.validate_seal() for t in trials), "invalid envelope seal")
        for t in trials:
            expected = (
                "PASS" if t.arm == "baseline" and t.condition_id != "empty_result" else "FAIL"
            )
            require(t.outcome == expected, f"{t.trial_id}: {t.outcome}, {t.failure_detail}")
        return "12 graded envelopes; baseline 4 PASS / 2 FAIL; candidate 6 FAIL; INCONCLUSIVE"

    check("experiment", experiment)

    def trial(
        name: str,
        task: dict[str, JsonValue] | None = None,
        fault: str | None = None,
        **updates: Any,
    ) -> tuple[TrialSpec, TrialEnvelope]:
        condition = {"condition_id": "clean", "faults": []}
        if fault:
            condition = {
                "condition_id": fault,
                "faults": [
                    {"name": fault, "bucket": "falsify", "tool": "lookup", "at_occurrence": 0}
                ],
            }
        values = dict(
            agent="probe_app:baseline",
            toolset="probe_app:toolset",
            task=task or {},
            condition=condition,
        )
        values.update(updates)
        spec = TrialSpec.model_validate(base.model_dump() | values)
        envelope = run_trial(spec, lambda _event: None, manifest.contract)
        (run / f"{name}.spec.json").write_text(spec.model_dump_json(indent=2) + "\n")
        (run / f"{name}.trial.json").write_text(envelope.model_dump_json(indent=2) + "\n")
        require(envelope.validate_seal(), f"{name}: invalid seal")
        envelopes[name] = envelope
        return spec, envelope

    parity: dict[str, dict[str, Any]] = {}
    for policy in ("none", "retry", "error"):
        native_result = native({"policy": policy, "real_error": True})
        _, adapted = trial(f"parity-{policy}", {"policy": policy}, "tool_error_once")
        adapted_result = {
            "answer": final_output(adapted),
            "body_calls": body_calls(adapted),
            "exception": (
                str(adapted.failure_detail).split(":", 1)[0]
                if adapted.termination == "crash"
                else None
            ),
            "outcome": adapted.outcome.value,
            "termination": adapted.termination.value,
            "recorded_calls": len(adapted.recording),
        }
        parity[policy] = {"native": native_result, "adapter": adapted_result}
    write_json(run / "parity.json", parity)

    def parity_check() -> str:
        mismatches: list[str] = []
        for policy, pair in parity.items():
            for key in ("answer", "exception", "body_calls"):
                if pair["native"][key] != pair["adapter"][key]:
                    mismatches.append(
                        f"{policy}.{key}: native={pair['native'][key]!r} "
                        f"adapter={pair['adapter'][key]!r}"
                    )
        require(not mismatches, "; ".join(mismatches))
        return "native and injected-fault parity in all three configurations"

    check("native_parity", parity_check)

    def exception_positions() -> str:
        require(
            parity["none"]["adapter"]["outcome"] == "FAIL"
            and parity["none"]["adapter"]["termination"] == "crash",
            "no middleware must crash",
        )
        require(
            parity["retry"]["adapter"]["outcome"] == "PASS"
            and parity["retry"]["adapter"]["recorded_calls"] == 2,
            "retry must PASS with two calls",
        )
        require(
            parity["error"]["adapter"]["answer"] == parity["error"]["native"]["answer"],
            "error middleware answer mismatch",
        )
        require(parity["error"]["adapter"]["termination"] == "completed", "error must complete")
        return (
            "none FAIL/crash; retry PASS/two calls; "
            "error native=adapter unavailable, FAIL/completed"
        )

    check("exception_positions", exception_positions)

    def exactly_once() -> str:
        _, clean = trial("clean")
        require(clean.outcome == "PASS" and body_calls(clean) == 1, "clean execution count")
        for item in trials:
            expected_count = len(item.recording) - (item.condition_id != "empty_result")
            require(body_calls(item) == expected_count, f"duplicate body: {item.trial_id}")
        _, real = trial("real-error-retry", {"policy": "retry", "real_error": True})
        require(
            real.outcome == "PASS" and body_calls(real) == 2 and len(real.recording) == 2,
            "real exception retry must execute twice",
        )
        return "own-body counters: clean 1, injected retry 1/2 calls, real-error retry 2/2 calls"

    check("exactly_once", exactly_once)

    def arguments() -> str:
        rows: dict[str, Any] = {}
        for policy in ("none", "retry", "error"):
            task: dict[str, JsonValue] = {"bad_argument": True, "policy": policy}
            n = native(task)
            _, adapted = trial(f"bad-argument-{policy}", task)
            observations = (adapted.final_state or {}).get("observations")
            rows[policy] = {"native": n, "adapter_observations": observations}
            write_json(run / "argument-parity.json", rows)
            require(n["body_calls"] == body_calls(adapted) == 0, "invalid input reached body")
            require(final_output(adapted) == n["answer"], f"{policy}: validation answer differs")
            require(observations == n["observations"], f"{policy}: validation feedback differs")
            require(adapted.termination == "completed", f"validation: {adapted.failure_detail}")
        return "all three policies: invalid key rejected; zero bodies; identical native feedback"

    check("argument_validation", arguments)

    def faults() -> str:
        fired = {
            name: sum(
                e.kind == "tool_finish" and e.payload.get("injected_by") == name
                for t in trials
                for e in t.events
            )
            for name in ("tool_timeout", "tool_error_once", "empty_result")
        }
        write_json(run / "faults.json", fired)
        require(all(n == 4 for n in fired.values()), str(fired))
        return str(fired)

    check("built_in_faults", faults)

    def budget() -> str:
        budgets = base.budgets.model_dump() | {"max_tool_calls": 1}
        _, item = trial("budget", {"policy": "retry"}, "tool_timeout", budgets=budgets)
        require(item.outcome == "FAIL" and item.termination == "budget", str(item.failure_detail))
        _, multi = trial("multi-budget", {"multi": True, "policy": "retry"}, budgets=budgets)
        require(
            multi.outcome == "FAIL" and multi.termination == "budget", str(multi.failure_detail)
        )
        # First call hits zero budget while another thread waits: finally must release it.
        _, zero = trial(
            "multi-zero-budget",
            {"multi": True},
            budgets=base.budgets.model_dump() | {"max_tool_calls": 0},
        )
        require(zero.outcome == "FAIL" and zero.termination == "budget", str(zero.failure_detail))
        require(
            all(t.final_state is not None for t in (item, multi, zero)),
            "budget latch may hide timeout: require completed worker snapshot",
        )
        return "single retry, second multi-call and first multi-call exhaustion all FAIL/budget"

    check("budget", budget)

    def multicall() -> str:
        signatures: list[object] = []
        hashes: list[str] = []
        first: tuple[TrialSpec, TrialEnvelope] | None = None
        for index in range(20):
            spec, item = trial(
                f"multi-{index:02d}",
                {"multi": True, "policy": "retry", "expected": "deliberately wrong"},
                "tool_timeout",
            )
            if first is None:
                first = spec, item
            require(
                item.termination == "completed" and item.outcome == "FAIL",
                f"repetition {index}: {item.failure_detail}",
            )
            keys = [
                cast(dict[str, JsonValue], e.payload["arguments"])["key"]
                for e in item.events
                if e.kind == "tool_start"
            ]
            require(keys == ["key-0", "key-0", "key-1"], f"call order: {keys}")
            require(body_calls(item) == 2, "multi bodies must run exactly twice")
            signatures.append([(e.kind, e.payload) for e in item.events])
            hashes.append(item.record_sha256)
        require(all(s == signatures[0] for s in signatures), "event sequences differ")
        require(len(set(hashes)) == 1, "multi-call sealed hashes differ")
        assert first is not None
        bundle = make_bundle(manifest, first[1], first[0])
        (run / "multi.bundle.json").write_text(bundle.model_dump_json(indent=2) + "\n")
        result = replay(bundle)
        write_json(run / "multi-replay.json", result.model_dump(mode="json"))
        require(result.status == "REPRODUCED", str(result))
        return "20 repetitions: key-0 retry then key-1; identical events/seals; replay REPRODUCED"

    check("multi_call", multicall)

    def unsupported() -> str:
        rows: dict[str, Any] = {}
        for shape in ("async", "artifact", "return_direct", "command"):
            _, item = trial(f"unsupported-{shape}", {"shape": shape})
            rows[shape] = {
                "outcome": item.outcome.value,
                "termination": item.termination.value,
                "detail": item.failure_detail,
            }
        write_json(run / "unsupported.json", rows)
        reasons = {
            "async": "async invocation",
            "artifact": "tool artifacts",
            "return_direct": "return_direct",
            "command": "Command result",
        }
        require(
            all(
                row
                == {
                    "outcome": "ERROR",
                    "termination": "harness_error",
                    "detail": "UnsupportedAdapterError: LangChain adapter unsupported: "
                    + reasons[shape],
                }
                for shape, row in rows.items()
            ),
            str(rows),
        )
        _, swallowed = trial("unsupported-command-caught", {"shape": "command", "policy": "error"})
        require(
            swallowed.outcome == "ERROR"
            and swallowed.termination == "harness_error"
            and "Command result" in str(swallowed.failure_detail),
            "caught rejection must remain harness ERROR",
        )
        return "; ".join(
            f"{shape}={row['outcome']}/{row['termination']}" for shape, row in rows.items()
        )

    check("unsupported_shapes", unsupported)

    def unsupported_replay() -> str:
        _, item = trial(
            "unsupported-async-replay",
            {"shape": "async"},
            tool_mode=ToolMode.REPLAY,
            recording=[],
            replay_final_state={},
        )
        require(
            item.outcome == "FAIL"
            and item.termination == "crash"
            and "async invocation" in str(item.failure_detail),
            f"unexpected unsupported replay classification: {item.failure_detail}",
        )
        return "LIMIT: replay skips snapshot; async rejection is FAIL/crash, needs worker support"

    check("unsupported_replay_limit", unsupported_replay)

    def messages() -> str:
        rows: dict[str, Any] = {}
        for shape, value in [
            ("string", "first line\nsecond line"),
            ("dict", {"z": "café", "a": [1, True]}),
        ]:
            task: dict[str, JsonValue] = {"value": cast(JsonValue, value), "list_final": True}
            if shape == "dict":
                task = {"shape": "message-dict", "list_final": True}
            n = native(task)
            _, item = trial(f"message-{shape}", task)
            observed = cast(list[dict[str, Any]], (item.final_state or {})["observations"])
            require(
                [m["content"] for m in observed] == [m["content"] for m in n["observations"]],
                f"{shape}: native text differs: {n} vs {observed}",
            )
            require(final_output(item) == n["answer"], f"{shape}: list final not captured")
            rows[shape] = {"native": n, "adapter": observed, "captured": final_output(item)}
        write_json(run / "message-parity.json", rows)
        return "multiline string and dict observations identical; list-block final .text captured"

    check("message_shapes", messages)

    def replay_check() -> str:
        spec, item = trial("replay-source", {"expected": "different answer"})
        require(item.outcome == "FAIL" and item.termination == "completed", "need oracle failure")
        bundle = make_bundle(
            manifest,
            item,
            spec,
            root=OWNED,
            include=tuple(sorted(p.name for p in OWNED.glob("*.py"))),
        )
        (run / "failure.bundle.json").write_text(bundle.model_dump_json(indent=2) + "\n")
        normal = replay(bundle)
        require(normal.status == "REPRODUCED", str(normal))
        altered_spec = bundle.spec.model_copy(
            update={"task": dict(spec.task) | {"final_answer": "ALTERED"}}
        )
        altered = ReplayBundle.create(
            **(bundle.model_dump(exclude={"record_sha256"}) | {"spec": altered_spec})
        )
        (run / "altered-answer.bundle.json").write_text(altered.model_dump_json(indent=2) + "\n")
        negative = replay(altered)
        # Direct replay envelope proves the executed answer changed; source snapshot stays old.
        _, changed = trial(
            "altered-answer", **altered_spec.model_dump(exclude={"task"}), task=altered_spec.task
        )
        answers = [
            e.payload.get("answer")
            for e in changed.events
            if e.kind == "model_step" and e.payload.get("summary") == "final answer"
        ]
        require("ALTERED" in answers, f"negative test did not alter executed answer: {answers}")
        require(changed.final_state == item.final_state, "replay should use sealed source snapshot")
        require(negative.status == "REPRODUCED", "known replay limit changed; investigate")
        write_json(
            run / "replay-limit.json",
            {
                "normal": normal.model_dump(mode="json"),
                "altered": negative.model_dump(mode="json"),
                "executed_answers": answers,
                "graded_snapshot": changed.final_state,
            },
        )
        return (
            "LIMIT DEMONSTRATED: altered final answer still REPRODUCED; source snapshot is graded"
        )

    check("replay_answer_limit", replay_check)

    def cost() -> str:
        samples = [t.usage.wall_seconds for t in trials]
        require(
            len(samples) >= 12 and all(t.contract is not None for t in trials),
            "need at least 12 real graded trials",
        )
        probe = command(
            "check-imports",
            [
                str(PYTHON),
                "-B",
                "-c",
                "import sys,user_check; "
                "print(any(n.startswith(('langchain','langgraph')) for n in sys.modules))",
            ],
        )
        require(
            probe.returncode == 0 and probe.stdout.strip() == "False", "check imports LangChain"
        )
        median = statistics.median(samples)
        write_json(
            run / "cost.json",
            {
                "wall_seconds": samples,
                "median_seconds": median,
                "s2_import_only_seconds": 0.7476,
                "s2_review_graded_approx_seconds": 1.5,
                "definition": "Usage.wall_seconds includes grading; warm local cache",
            },
        )
        return (
            f"12 graded trials median={median:.4f}s; "
            "S2 review ~1.5s graded (0.7476s was import-only)"
        )

    check("cost", cost)

    def burden() -> str:
        counts = {
            name: len((OWNED / name).read_text().splitlines())
            for name in ("user_app.py", "user_check.py")
        }
        names = [
            "make_tools (including own lookup tool)",
            "build_baseline",
            "build_candidate",
            "toolset, baseline, candidate = make_adapter(...)",
            "check",
            "arci.yaml (task embedded; no separate task file)",
        ]
        write_json(
            run / "user-burden.json",
            {
                "line_counts": counts,
                "user_written_names": names,
                "fixture": "ScriptedModel substitutes for existing model; not adapter code",
            },
        )
        return f"{counts}; user writes: " + "; ".join(names)

    check("user_burden", burden)

    def frozen() -> str:
        result = command("frozen", ["shasum", "-a", "256", "-c", "FROZEN.sha256"])
        require(result.returncode == 0, "frozen hash failure")
        return f"{result.stdout.count(': OK')} hashes match"

    check("frozen", frozen)

    def scope() -> str:
        before = cast(dict[str, str], json.loads((OWNED / "scope_before.json").read_text()))
        after = inventory()
        changed = sorted(p for p in before.keys() | after.keys() if before.get(p) != after.get(p))
        write_json(run / "scope-differences.json", changed)
        require(not changed, f"outside plan/exec/v2 changed: {changed}")
        return f"{len(before)} outside-plan files unchanged; parallel plan/exec/v2 jobs excluded"

    check("scope", scope)
    verdicts = {
        name: {
            "outcome": t.outcome.value,
            "termination": t.termination.value,
            "record_sha256": t.record_sha256,
        }
        for name, t in envelopes.items()
    }
    write_json(run / "verdicts.json", verdicts)

    def repeatability() -> str:
        require(bool(previous), "first invocation retained; second invocation required")
        old = previous[-1]
        require(
            json.loads((old / "source-hashes.json").read_text()) == sources,
            "source changed; rerun this source version",
        )
        require(
            json.loads((old / "verdicts.json").read_text()) == verdicts,
            "trial verdicts or seals changed",
        )
        old_checks = json.loads((old / "checks.json").read_text())["checks"]
        require(
            all(old_checks.get(name) == passed for name, passed in checks.items()),
            "check verdicts changed",
        )
        return f"identical check verdicts and {len(verdicts)} sealed trial hashes versus {old.name}"

    check("repeatability", repeatability)
    (output / "latest.txt").write_text(str(run.relative_to(OWNED)) + "\n")
    failed = [name for name, passed in checks.items() if not passed]
    print(
        f"RESULT: {len(checks) - len(failed)} OK, {len(failed)} FAIL; exit {int(bool(failed))}",
        flush=True,
    )
    return int(bool(failed))


if __name__ == "__main__":
    raise SystemExit(main())
