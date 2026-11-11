"""Regressions from the independent P2a review."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from arci import descriptor
from arci.cli import main
from arci.suite_schema import SuiteManifest
from arci.suite_storage import SuiteStore
from tests.unit.suite_cli.test_descriptor import TEXT, compile_text


def file_descriptor(name: str) -> str:
    return f"suite_id: file-suite\ntasks: {name}\n" + TEXT[TEXT.index("baseline:") :]


def test_json_and_jsonl_preserve_json_values(tmp_path: Path) -> None:
    tasks = [{"id": str(i), "number": 1e-5, "text": "a\u0085b\u2028c\u2029😀"} for i in range(5)]
    results: list[SuiteManifest] = []
    for extension in ("json", "jsonl"):
        name = f"tasks.{extension}"
        content = (
            json.dumps(tasks, indent="\t")
            if extension == "json"
            else "\r\n\n".join(json.dumps(task, ensure_ascii=False) for task in tasks)
        )
        (tmp_path / name).write_text("\ufeff" + content, encoding="utf-8")
        results.append(compile_text(file_descriptor(name), str(tmp_path / "arci.yaml")))
    assert results[0] == results[1]
    assert results[0].tasks[0].task == {"number": 1e-5, "text": tasks[0]["text"]}


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity", '{"x":1,"x":2}'])
def test_json_rejects_non_json_or_duplicate_values(tmp_path: Path, value: str) -> None:
    (tmp_path / "tasks.json").write_text('[{"id":"a", "value":' + value + "}]")
    with pytest.raises(descriptor.DescriptorError, match=r"tasks.*(non-finite|duplicate)"):
        compile_text(file_descriptor("tasks.json"), str(tmp_path / "arci.yaml"))


def test_jsonl_error_names_file_line(tmp_path: Path) -> None:
    (tmp_path / "tasks.jsonl").write_text('\n{"id":"a"}\n{"id":}\n')
    with pytest.raises(descriptor.DescriptorError, match=r"tasks.jsonl.*line 3"):
        compile_text(file_descriptor("tasks.jsonl"), str(tmp_path / "arci.yaml"))


@pytest.mark.parametrize("key", ["tasks", "suite_id"])
def test_v1_stray_suite_keys_name_the_stray_key(tmp_path: Path, key: str) -> None:
    path = tmp_path / "v1.yaml"
    path.write_text("experiment_id: v1\n" + TEXT[TEXT.index("baseline:") :] + f"{key}: []\n")
    with pytest.raises(descriptor.DescriptorError) as error:
        descriptor.compile_run_descriptor(path)
    assert error.value.path == (key,)
    assert f'unknown key "{key}"' in str(error.value)
    assert "remove" in str(error.value)


@pytest.mark.parametrize(
    "change,key,fix",
    [
        ({"candidate": {"label": "cmd", "command": {"argv": ["agent"]}}}, "candidate", "same kind"),
        (
            {
                "baseline": {"label": "cmd", "command": {"argv": ["agent"]}},
                "candidate": {"label": "cmd", "command": {"argv": ["agent"]}},
                "mcp_server": {"argv": ["server"], "snapshot": "app:snapshot"},
            },
            "toolset",
            "remove toolset",
        ),
        ({"conditions": [{"id": "has space"}]}, "conditions[0].id", "1 to 64"),
        ({"tasks": [{"id": 17}]}, "tasks[0].id", "quote"),
        ({"tasks": [{"id": "a"}, {"id": "a"}]}, "tasks[1].id", "duplicate task id 'a'"),
        ({"conditions": [{"id": "a"}, {"id": "a"}]}, "conditions[1].id", "unique"),
        (
            {"tasks": [{"id": str(i)} for i in range(100)]},
            "rule.acknowledge_single_round",
            "default budget gives one round",
        ),
    ],
)
def test_descriptor_errors_identify_action(change: dict[str, Any], key: str, fix: str) -> None:
    data = descriptor.parse_yaml(TEXT)
    assert isinstance(data, dict)
    data.update(change)
    with pytest.raises(descriptor.DescriptorError) as error:
        compile_text(json.dumps(data))
    assert key in str(error.value) and fix in str(error.value)
    if "acknowledge" in key:
        assert "increase rule.max_rounds" in str(error.value)


def test_oversized_grid_names_tasks_not_rounds() -> None:
    # Build the validated descriptor directly to avoid YAML's separate expansion limit.
    data = descriptor.parse_yaml(TEXT)
    assert isinstance(data, dict)
    data["tasks"] = [{"id": str(i)} for i in range(25001)]
    spec = descriptor.SuiteDescriptor.model_validate_json(json.dumps(data))
    with pytest.raises(descriptor.DescriptorError, match=r"tasks.*reduce tasks or conditions"):
        spec.to_manifest()


@pytest.mark.parametrize(
    "corruption", ["json", "utf8", "missing", "version", "seal", "incomplete", "unreadable"]
)
def test_bad_neighbours_warn_and_skip(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    corruption: str,
) -> None:
    source = tmp_path / "arci.yaml"
    source.write_text(TEXT)
    out = tmp_path / "runs"
    first = compile_text(TEXT)
    good = SuiteStore(out, first)
    bad = out / "bad"
    bad.mkdir()
    path = bad / "manifest.json"
    data = first.model_dump()
    if corruption == "missing":
        (bad / "trials.jsonl").touch()
    elif corruption == "json":
        path.write_text("{bad")
    elif corruption == "utf8":
        path.write_bytes(b"\xff")
    else:
        if corruption == "version":
            data["schema_version"] = "arci-suite/0"
        if corruption == "seal":
            data["record_sha256"] = "bad"
        if corruption == "incomplete":
            data = {"schema_version": "arci-suite/1"}
        path.write_text(json.dumps(data))
    if corruption == "unreadable":
        original = Path.read_text

        def read(self: Path, *args: Any, **kwargs: Any) -> str:
            if self == path:
                raise PermissionError("denied")
            return original(self, *args, **kwargs)

        monkeypatch.setattr(Path, "read_text", read)
    result = descriptor.compile_run_descriptor(source, out_dir=out)
    assert result.prior_runs == (first.experiment_id,)
    warning = capsys.readouterr().err
    assert str(path) in warning and "warning: skipping" in warning
    assert len(warning.splitlines()) == 1
    assert good.run_dir.exists()


def test_prior_history_transitive_label_independent_and_v1_skipped(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = tmp_path / "arci.yaml"
    source.write_text(TEXT)
    first = compile_text(TEXT + "prior_runs: [pruned]\n")
    SuiteStore(tmp_path / "runs", first)
    source.write_text(
        TEXT.replace(
            "candidate: arci.demo.suite:control",
            "candidate: {label: renamed, agent: 'arci.demo.suite:control'}",
        )
    )
    v1 = tmp_path / "runs" / "v1"
    v1.mkdir()
    # Kind is checked before suite validation; unrelated v1 contents are irrelevant.
    (v1 / "manifest.json").write_text('{"schema_version":"arci/0.5"}')
    (tmp_path / "runs" / "unrelated").mkdir()
    result = descriptor.compile_run_descriptor(source, out_dir=tmp_path / "runs")
    assert result.prior_runs == ("pruned", first.experiment_id)
    assert capsys.readouterr().err == ""


@pytest.mark.parametrize(
    "command,args",
    [
        ("bundle", ["--o", "unused", "--inc", "fixture"]),
        ("minimize", ["--o", "unused"]),
        ("trace-check", ["--for", "json"]),
    ],
)
def test_deferred_abbreviated_options(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], command: str, args: list[str]
) -> None:
    path = tmp_path / "suite.yaml"
    path.write_text(TEXT)
    assert main([command, *args, str(path)]) == 3
    output = capsys.readouterr()
    assert output.out + output.err == f"suite support for {command} is not built yet\n"


def test_gate_junit_is_one_line_refusal(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    store = SuiteStore(tmp_path, compile_text(TEXT))
    assert main(["gate", str(store.run_dir), "--junit", str(tmp_path / "report.xml")]) == 3
    output = capsys.readouterr()
    assert len((output.out + output.err).splitlines()) == 1
    assert "JUnit export for suites is not built yet" in output.err
    assert not (tmp_path / "report.xml").exists()


def assert_summary(output: str, decision: Any, trials: int) -> None:
    last = decision.history[-1]
    counts = last.counts
    expected = [
        f"VERDICT: {decision.verdict.value} (exit {decision.exit_code})",
        f"reason: {'; '.join(decision.reasons)}",
        f"stopping round: {decision.stopped_at_round}",
        f"pairs: {trials // 2} ({trials} trials)",
        f"counts: minus={counts.minus}, zero={counts.zero}, "
        f"plus={counts.plus}, errored={counts.errored}",
        f"PASS wealth: {last.pass_wealth}; threshold: {decision.threshold}; "
        f"crossed: {last.pass_crossed}",
        f"BLOCK wealth: {last.block_wealth}; threshold: {decision.threshold}; "
        f"crossed: {last.block_crossed}",
        f"errored pairs: {counts.errored}; tolerance: {decision.max_errored_pairs}",
        f"candidate hard violations: {last.candidate_hard_violations}",
        "The bound covers statistical BLOCK only; hard-invariant BLOCK is a separate rule.",
    ]
    for line in expected:
        assert line in output.splitlines()
    document = Path("docs/STATISTICS_SUITE.md").read_text()
    document = " ".join(document.replace("**", "").split())
    condition = (
        "Its error guarantee requires that in every round the suite mean over that "
        "round's scenario instances obey the relevant null, with the independence "
        "conditions above (or their conditional form)."
    )
    assert condition in document
    if decision.scenario_seeds == "per_round":
        assert (
            "scenario_seeds: per_round. Assuming joint independence across cells within rounds "
            "and across rounds (or the conditional form), each directional statistical error "
            f"is at most alpha/2 (alpha={decision.alpha}); " + condition
        ) in output.splitlines()
        assert (
            "ARCI does not check or enforce this premise; "
            "there is no guarantee averaged over seeds."
        ) in output.splitlines()
        assert "scenario_seeds: fixed" not in output
    else:
        assert (
            "scenario_seeds: fixed. For the registered scenarios, each directional statistical "
            f"error is at most alpha/2 (alpha={decision.alpha}), under joint independence across "
            "cells and rounds and stationary per-cell laws, including no execution-order effect."
        ) in output.splitlines()
        assert "The claim is for the registered scenarios over outcome randomness." in document
        assert "each cell has the same law across rounds" in document
        assert "Joint independence across cells within each round and across rounds." in document
        assert "alpha/2" in document and "Assume no order effect" in document
        assert "scenario_seeds: per_round" not in output
    if decision.prior_runs:
        assert "prior runs: " + ", ".join(decision.prior_runs) in output.splitlines()


@pytest.mark.parametrize("mode", ["fixed", "per_round"])
@pytest.mark.parametrize("route", ["descriptor", "sealed"])
def test_run_gate_summary_workers_and_sealed_route(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    mode: str,
    route: str,
) -> None:
    from arci import cli as api
    from arci.schema import Outcome
    from arci.suite_gate import decide_suite
    from arci.suite_schedule import build_suite_schedule
    from tests.unit.suite_runner.test_runner import envelope

    path = tmp_path / "arci.yaml"
    path.write_text(
        TEXT + f"rule: {{scenario_seeds: {mode}, max_rounds: 4, max_errored_pairs: 1}}\n"
        "prior_runs: [old]\n"
    )
    m = descriptor.compile_run_descriptor(path)
    assert isinstance(m, SuiteManifest)
    if route == "sealed":
        path = tmp_path / "manifest.json"
        path.write_text(m.model_dump_json())
    scheduled = build_suite_schedule(m)
    trials = tuple(
        envelope(spec, Outcome.ERROR if i == 0 else Outcome.PASS)
        for i, spec in enumerate(scheduled)
    )
    decision = decide_suite(m, trials)
    workers: list[int] = []

    def run(loaded: SuiteManifest, out_dir: str, *, workers: int) -> Any:
        assert loaded == m
        seen_workers.append(workers)
        store = SuiteStore(out_dir, loaded)
        for trial in trials:
            store.append_trial(trial)
        store.write_decision(decision)
        return trials

    seen_workers = workers
    monkeypatch.setattr(api, "run_suite", run)
    out = tmp_path / "runs"
    assert main(["run", str(path), "--workers", "2", "--out", str(out)]) == decision.exit_code
    assert workers == [2]
    assert_summary(capsys.readouterr().out, decision, len(trials))
    assert main(["gate", str(out / m.experiment_id)]) == decision.exit_code
    assert_summary(capsys.readouterr().out, decision, len(trials))


@pytest.mark.parametrize("saved", ["garbage", "unsealed", "absent"])
def test_stored_decision_edges(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], saved: str
) -> None:
    from arci.suite_gate import decide_suite
    from arci.suite_schedule import build_suite_schedule
    from tests.unit.suite_runner.test_runner import envelope, manifest

    m = manifest()
    store = SuiteStore(tmp_path, m)
    trials = tuple(envelope(s) for s in build_suite_schedule(m))
    for trial in trials:
        store.append_trial(trial)
    decision = decide_suite(m, trials)
    path = store.run_dir / "decision.json"
    before = b""
    if saved != "absent":
        path.write_text(
            "not json"
            if saved == "garbage"
            else decision.model_copy(update={"record_sha256": ""}).model_dump_json()
        )
        before = path.read_bytes()
    assert main(["gate", str(store.run_dir)]) == (0 if saved == "absent" else 3)
    output = capsys.readouterr().out
    if saved == "absent":
        assert "stored decision: absent" in output and not path.exists()
    else:
        assert output.startswith("VERDICT: ERROR (exit 3)")
        assert "stored decision: MISMATCH" in output
        assert path.read_bytes() == before


@pytest.mark.parametrize("transport", ["pipe", "file"])
def test_v1_manifest_and_bundle_stdin(tmp_path: Path, transport: str) -> None:
    import os
    import subprocess
    import sys

    from arci.replay import make_bundle
    from arci.schedule import build_schedule
    from arci.storage import load_run
    from tests.acceptance.helpers import manifest

    m = manifest(n_per_arm=1)

    def invoke(command: str, content: str, *args: str) -> subprocess.CompletedProcess[str]:
        env = {**os.environ, "PYTHONPATH": os.pathsep.join(sys.path)}
        argv = [sys.executable, "-m", "arci.cli", command, "/dev/stdin", *args]
        if transport == "pipe":
            return subprocess.run(
                argv, input=content, text=True, capture_output=True, env=env, timeout=30
            )
        path = tmp_path / "stdin.json"
        path.write_text(content)
        with path.open() as stream:
            return subprocess.run(
                argv, stdin=stream, text=True, capture_output=True, env=env, timeout=30
            )

    result = invoke("run", m.model_dump_json(), "--out", str(tmp_path / "runs"), "--workers", "1")
    assert result.returncode == 2, result.stdout + result.stderr
    _, trials = load_run(tmp_path / "runs" / m.experiment_id)
    spec = build_schedule(m)[1]
    trial = next(t for t in trials if t.trial_id == spec.trial_id)
    bundle = make_bundle(m, trial, spec)
    result = invoke("replay", bundle.model_dump_json())
    assert result.returncode == 0, result.stdout + result.stderr
    assert "REPRODUCED" in result.stdout


def test_cli_discovers_prior_runs(tmp_path: Path) -> None:
    from arci.suite_storage import load_suite_run
    from tests.unit.suite_cli.test_cli import cli

    source = tmp_path / "arci.yaml"
    text = TEXT.replace(
        "candidate: arci.demo.suite:control",
        "candidate: {label: regression, agent: 'arci.demo.suite:regression', "
        "candidate_id: revision}",
    )
    source.write_text(text + "rule: {scenario_seeds: per_round, max_rounds: 4}\n")
    out = tmp_path / "runs"
    first_id = ""
    for attempt in range(2):
        result = cli("run", str(source), "--out", str(out), "--workers", "2")
        assert result.returncode == 1, result.stdout + result.stderr
        if attempt == 0:
            (first_path,) = out.iterdir()
            first, _ = load_suite_run(first_path)
            first_id = first.experiment_id
            junk = out / "junk"
            junk.mkdir()
            (junk / "manifest.json").write_text("bad json")
        else:
            manifests = [load_suite_run(p)[0] for p in out.iterdir() if p.name != "junk"]
            second = next(m for m in manifests if m.prior_runs)
            assert second.prior_runs == (first_id,)
            assert f"prior runs: {first_id}" in result.stdout
            assert str(out / "junk" / "manifest.json") in result.stderr
    source.write_text(source.read_text().replace("candidate_id: revision", "candidate_id: changed"))
    result = cli("run", str(source), "--out", str(out), "--workers", "2")
    assert result.returncode == 1, result.stdout + result.stderr
    assert "prior runs:" not in result.stdout
