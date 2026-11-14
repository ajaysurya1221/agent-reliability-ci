"""The packaged example uses the ordinary verdict path and its qualifications."""

from importlib import resources
from pathlib import Path

import pytest

from arci.cli import main
from arci.outcome_report import text
from arci.outcome_schema import OutcomeDecision
from arci.schema import Verdict


@pytest.mark.parametrize("empty_cwd", [False, True], ids=["repo", "empty-directory"])
def test_packaged_example(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    empty_cwd: bool,
) -> None:
    if empty_cwd:
        monkeypatch.chdir(tmp_path)
        assert not tuple(tmp_path.iterdir())
    json_path, markdown_path = tmp_path / "decision.json", tmp_path / "report.md"
    assert (
        main(["verdict", "--example", "--json", str(json_path), "--markdown", str(markdown_path)])
        == 1
    )
    output = capsys.readouterr()
    assert output.err == ""
    assert output.out.splitlines()[:2] == [text("F1"), "VERDICT: BLOCK (exit 1)"]
    assert text("F16") in output.out.splitlines()
    assert text("F14") in output.out.splitlines()
    assert "rounds after the stopping round" not in output.out
    markdown = markdown_path.read_text(encoding="utf-8")
    assert [line for line in markdown.splitlines() if line][:2] == [
        text("F1"),
        "VERDICT: BLOCK (exit 1)",
    ]
    assert text("F14") in markdown.splitlines()
    decision = OutcomeDecision.model_validate_json(json_path.read_text(encoding="utf-8"))
    assert decision.validate_seal()
    assert decision.verdict is Verdict.BLOCK
    assert decision.exit_code == 1
    assert decision.reasons == (text("F16"),)
    assert decision.notices[-1] == text("F14")
    assert decision.rule is not None and not decision.rule.fixed_before_runs
    assert len(decision.rule.tasks) == 96
    assert decision.rounds_registered == 5
    assert (
        decision.rounds_supplied == decision.last_round_evaluated == decision.stopped_at_round == 1
    )
    (look,) = decision.history
    assert look.counts.model_dump() == {"minus": 26, "zero": 70, "plus": 0, "errored": 0}
    assert look.pass_wealth == "1.92124e-03"
    assert look.block_wealth == "1.56229e+02"
    assert not look.pass_crossed and look.block_crossed


@pytest.mark.parametrize("name", ["rule.yaml", "baseline.csv", "candidate.csv"])
@pytest.mark.parametrize("option", ["--json", "--markdown"])
def test_example_refuses_output_over_its_inputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    name: str,
    option: str,
) -> None:
    packaged = resources.files("arci.demo.outcomes").joinpath("order-desk-run-1")
    example = tmp_path / "order-desk-run-1"
    example.mkdir()
    originals = {
        filename: packaged.joinpath(filename).read_bytes()
        for filename in ("rule.yaml", "baseline.csv", "candidate.csv")
    }
    for filename, body in originals.items():
        (example / filename).write_bytes(body)

    def temporary_package(anchor: str) -> Path:
        assert anchor == "arci.demo.outcomes"
        return tmp_path

    monkeypatch.setattr(resources, "files", temporary_package)
    output = tmp_path / "output-alias"
    output.symlink_to(example / name)
    assert main(["verdict", "--example", option, str(output)]) == 3
    captured = capsys.readouterr()
    assert not captured.out
    assert captured.err == f"error: {text('E17', path=output)}\n"
    for filename, body in originals.items():
        assert (example / filename).read_bytes() == body
