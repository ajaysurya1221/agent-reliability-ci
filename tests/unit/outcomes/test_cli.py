"""Imported-outcome commands: ordered refusal, artifact delivery and isolation."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, cast

import pytest

from arci.cli import main


def inputs(tmp_path: Path, *, fixed: bool = False, n: int = 50) -> tuple[Path, Path, Path]:
    rule = tmp_path / "rule.yaml"
    rule.write_text(
        json.dumps(
            {
                "schema_version": "arci-outcomes/1",
                "suite_id": "cli-test",
                "fixed_before_runs": fixed,
                "tasks": [f"task-{i}" for i in range(n)],
            }
        ),
        encoding="utf-8",
    )
    baseline, candidate = tmp_path / "baseline.csv", tmp_path / "candidate.csv"
    rows = "task_id,outcome\n" + "".join(f"task-{i},pass\n" for i in range(n))
    baseline.write_text(rows, encoding="utf-8")
    candidate.write_text(rows, encoding="utf-8")
    return rule, baseline, candidate


def command(rule: Path, baseline: Path, candidate: Path) -> list[str]:
    return ["verdict", str(rule), "--baseline", str(baseline), "--candidate", str(candidate)]


def refusal(argv: list[str], reason: str, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(argv) == 3
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == f"error: {reason}\n"


@pytest.mark.parametrize("arm", ["baseline", "candidate"])
def test_e16_missing_or_empty_arm(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], arm: str
) -> None:
    rule, baseline, candidate = inputs(tmp_path)
    argv = command(rule, baseline, candidate)
    index = argv.index(f"--{arm}")
    del argv[index + 1]
    refusal(argv, f"no input files were given for {arm}", capsys)
    del argv[index]
    refusal(argv, f"no input files were given for {arm}", capsys)


@pytest.mark.parametrize("source", ["baseline", "rule", "previous", "output"])
def test_e17_resolved_output_collision(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], source: str
) -> None:
    rule, baseline, candidate = inputs(tmp_path)
    argv = command(rule, baseline, candidate)
    paths = {"baseline": baseline, "rule": rule, "previous": tmp_path / "previous.json"}
    if source == "output":
        path = tmp_path / "decision.json"
        argv += ["--json", str(path), "--markdown", str(tmp_path / "." / path.name)]
    else:
        original = paths[source]
        path = tmp_path / "alias"
        path.symlink_to(original)
        if source == "previous":
            argv += ["--previous", str(original)]
        argv += ["--json", str(path)]
    refusal(argv, f"{path} is both an output and an input, or is named twice", capsys)


def test_e18_missing_output_parent(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    rule, baseline, candidate = inputs(tmp_path)
    path = tmp_path / "absent" / "decision.json"
    refusal(
        [*command(rule, baseline, candidate), "--json", str(path)],
        f"the directory for {path} does not exist",
        capsys,
    )
    assert not path.parent.exists()


@pytest.mark.parametrize("failed", ["json", "markdown"])
def test_e19_artifacts_are_written_json_first(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], failed: str
) -> None:
    rule, baseline, candidate = inputs(tmp_path)
    output_json, markdown = tmp_path / "decision.json", tmp_path / "decision.md"
    target = output_json if failed == "json" else markdown
    target.mkdir()
    # Deliberately pass Markdown first: delivery still has its registered order.
    refusal(
        [
            *command(rule, baseline, candidate),
            "--markdown",
            str(markdown),
            "--json",
            str(output_json),
        ],
        f"cannot write {target}",
        capsys,
    )
    if failed == "json":
        assert not markdown.exists()
    else:
        saved = cast(dict[str, Any], json.loads(output_json.read_text(encoding="utf-8")))
        assert saved["verdict"] == "INCONCLUSIVE"


@pytest.mark.parametrize(
    "suffix,option",
    [
        (["--baseline=x"], "--baseline"),
        (["--format", "csv", "--format=jsonl"], "--format"),
        (["--json=a", "--json=b"], "--json"),
        (["--example", "--example"], "--example"),
    ],
)
def test_e20_repeated_options(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], suffix: list[str], option: str
) -> None:
    rule, baseline, candidate = inputs(tmp_path)
    refusal(
        command(rule, baseline, candidate) + suffix, f"{option} was given more than once", capsys
    )


@pytest.mark.parametrize(
    "suffix",
    [
        ["rule.yaml"],
        ["--baseline"],
        ["--candidate", "c.csv"],
        ["--previous=p.json"],
        ["--format=auto"],
    ],
)
def test_e21_example_excludes_inputs(suffix: list[str], capsys: pytest.CaptureFixture[str]) -> None:
    refusal(["verdict", "--example", *suffix], "--example takes no other input", capsys)


def test_e22_rule_output_exists(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    rule, baseline, _ = inputs(tmp_path)
    before = rule.read_bytes()
    refusal(
        ["verdict-rule", "--tasks", str(baseline), "--out", str(rule)],
        f"--out already exists: {rule}",
        capsys,
    )
    assert rule.read_bytes() == before


@pytest.mark.parametrize("case", range(6))
def test_step_one_precedence_with_simultaneous_faults(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], case: int
) -> None:
    rule, baseline, candidate = inputs(tmp_path)
    bad_parent = tmp_path / "absent" / "decision.json"
    argv = command(rule, baseline, candidate)
    if case == 0:  # E20 before E21.
        argv += ["--example", "--example"]
        reason = "--example was given more than once"
    elif case == 1:  # E21 before empty candidate E16.
        argv = ["verdict", "--example", "--candidate"]
        reason = "--example takes no other input"
    elif case == 2:  # E16 before E17.
        argv = ["verdict", str(rule), "--candidate", str(candidate), "--json", str(candidate)]
        reason = "no input files were given for baseline"
    elif case == 3:  # All collisions precede all missing parents.
        argv += ["--json", str(bad_parent), "--markdown", str(rule)]
        reason = f"{rule} is both an output and an input, or is named twice"
    elif case == 4:  # E18 before malformed rule E15.
        rule.write_text("not: [valid", encoding="utf-8")
        argv += ["--json", str(bad_parent)]
        reason = f"the directory for {bad_parent} does not exist"
    else:  # E22 before malformed discovery input E6.
        baseline.write_text("", encoding="utf-8")
        argv = ["verdict-rule", "--tasks", str(baseline), "--out", str(rule)]
        reason = f"--out already exists: {rule}"
    refusal(argv, reason, capsys)
    assert not bad_parent.exists()


def test_validation_error_still_writes_sealed_artifacts(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rule, baseline, candidate = inputs(tmp_path)
    candidate.write_text("task_id,outcome\nunknown,pass\n", encoding="utf-8")
    output_json, markdown = tmp_path / "decision.json", tmp_path / "decision.md"
    refusal(
        [
            *command(rule, baseline, candidate),
            "--json",
            str(output_json),
            "--markdown",
            str(markdown),
        ],
        "unknown task id: unknown",
        capsys,
    )
    from arci.outcome_schema import OutcomeDecision

    saved = OutcomeDecision.model_validate_json(output_json.read_text(encoding="utf-8"))
    assert saved.validate_seal()
    assert saved.last_round_evaluated == 0
    assert "unknown task id: unknown" in markdown.read_text(encoding="utf-8")


def test_opaque_id_line_breaks_are_escaped_only_on_stderr(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rule, baseline, _ = inputs(tmp_path)
    candidate = tmp_path / "candidate.jsonl"
    task_id = "unknown\nforged line\rreturn"
    candidate.write_text(
        json.dumps({"task_id": task_id, "outcome": "pass"}) + "\n", encoding="utf-8"
    )
    output_json = tmp_path / "decision.json"
    refusal(
        [*command(rule, baseline, candidate), "--json", str(output_json)],
        "unknown task id: unknown\\nforged line\\rreturn",
        capsys,
    )
    from arci.outcome_schema import OutcomeDecision

    saved = OutcomeDecision.model_validate_json(output_json.read_text(encoding="utf-8"))
    assert saved.reasons == (f"unknown task id: {task_id}",)
    assert saved.validate_seal()


def test_path_line_breaks_are_escaped_on_direct_error_path(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rule, baseline, candidate = inputs(tmp_path)
    output = tmp_path / "unknown\nparent" / "decision.json"
    escaped = str(output).replace("\n", "\\n")
    refusal(
        [*command(rule, baseline, candidate), "--json", str(output)],
        f"the directory for {escaped} does not exist",
        capsys,
    )


def test_non_utf8_path_returns_sealed_error_instead_of_raising(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rule, _, candidate = inputs(tmp_path)
    baseline = tmp_path / "undecodable\udcff.jsonl"
    output_json = tmp_path / "decision.json"
    escaped = str(baseline).encode("utf-8", errors="backslashreplace").decode("utf-8")
    refusal(
        [*command(rule, baseline, candidate), "--json", str(output_json)],
        f"unreadable or unsupported input: {escaped}",
        capsys,
    )
    from arci.outcome_schema import OutcomeDecision
    from arci.outcomes import decide_outcomes

    saved = OutcomeDecision.model_validate_json(output_json.read_text(encoding="utf-8"))
    direct = decide_outcomes(rule, [baseline], [candidate])
    assert saved.validate_seal() and direct.validate_seal()
    assert saved == direct
    assert saved.exit_code == 3


@pytest.mark.parametrize("fixed", [True, False])
def test_inference_report_and_artifacts(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], fixed: bool
) -> None:
    rule, baseline, candidate = inputs(tmp_path, fixed=fixed)
    output_json, markdown = tmp_path / "decision.json", tmp_path / "decision.md"
    assert (
        main(
            [
                *command(rule, baseline, candidate),
                "--json",
                str(output_json),
                "--markdown",
                str(markdown),
            ]
        )
        == 2
    )
    captured = capsys.readouterr()
    assert not captured.err
    descriptive = (
        "Descriptive verdict: the rule file declares it was written after outcomes existed. "
        "The error bound is not claimed."
    )
    lines = captured.out.splitlines()
    assert lines[0 if fixed else 1] == "VERDICT: INCONCLUSIVE (exit 2)"
    if not fixed:
        assert lines[0] == descriptive
        assert markdown.read_text(encoding="utf-8").splitlines()[0] == descriptive
        assert "probability at most" not in captured.out
    else:
        assert "probability at most 1/40" in captured.out
    from arci.outcome_schema import OutcomeDecision

    saved = OutcomeDecision.model_validate_json(output_json.read_text(encoding="utf-8"))
    assert saved.validate_seal()
    for message in (*saved.statements, *saved.notices):
        assert message in captured.out
        assert message in markdown.read_text(encoding="utf-8")


def test_inference_error_prints_stdout_only(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rule, baseline, candidate = inputs(tmp_path)
    candidate.write_text(
        "task_id,outcome\n" + "".join(f"task-{i},error\n" for i in range(50)), encoding="utf-8"
    )
    assert main(command(rule, baseline, candidate)) == 3
    captured = capsys.readouterr()
    assert not captured.err
    assert "VERDICT: ERROR (exit 3)" in captured.out
    assert "errored pairs exceed max_errored_pairs" in captured.out


def test_verdict_rule_writes_complete_false_registration(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _, baseline, _ = inputs(tmp_path)
    output = tmp_path / "extracted.yaml"
    assert main(["verdict-rule", "--tasks", str(baseline), "--out", str(output)]) == 0
    captured = capsys.readouterr()
    assert not captured.err
    assert captured.out == (
        "task ids were extracted from the given files. This does not establish that the rule "
        "preceded the data. Fix the rule before either evaluated arm is run.\n"
    )
    import yaml

    data = cast(dict[str, Any], yaml.safe_load(output.read_text(encoding="utf-8")))
    assert data["fixed_before_runs"] is False
    assert data["suite_id"] == "imported-outcomes"
    assert data["alpha"] == "1/20"
    assert data["margin"] == "1/10"
    assert data["stakes"] == ["1/4", "1/2"]
    assert data["max_rounds"] == 8
    assert data["max_errored_pairs"] == 4
    assert data["tasks"] == sorted(f"task-{i}" for i in range(50))
    assert "score" not in data and "pass_at_least" not in data


@pytest.mark.parametrize("help_requested", [False, True])
def test_startup_does_not_import_outcome_readers(help_requested: bool) -> None:
    snippet = (
        "import sys\nimport arci.cli\n"
        + (
            "try:\n    arci.cli.main(['--help'])\n"
            "except SystemExit as exc:\n    assert exc.code == 0\n"
            if help_requested
            else ""
        )
        + "assert not any(name == 'xml' or name.startswith(('xml.', 'arci.outcomes', "
        "'arci.importers')) for name in sys.modules), sorted(sys.modules)\n"
    )
    result = subprocess.run(
        [".venv/bin/python", "-c", snippet], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("argv", [["verdict", "--unknown"], ["verdict-rule", "--tasks"]])
def test_invalid_new_command_syntax_does_not_raise(
    argv: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(argv) == 3
    captured = capsys.readouterr()
    assert not captured.out
    assert captured.err.startswith("error: ")
    assert captured.err.count("\n") == 1
    assert "Traceback" not in captured.err
