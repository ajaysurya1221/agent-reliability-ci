"""V7 adversarial regressions, exercising CLI delivery and real importers."""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

import pytest

from arci.cli import main
from arci.outcome_report import render_markdown, render_terminal
from arci.outcomes import OutcomeError, decide_outcomes, load_rule
from tests.unit.outcomes.test_cli import command, inputs
from tests.unit.outcomes.test_previous_validation import campaign, save
from tests.unit.outcomes.test_validation import good_csv, rule_file


@pytest.mark.parametrize("kind", ["hardlink", "casefold"])
@pytest.mark.parametrize("source", ["rule", "baseline", "candidate", "previous", "output", "tasks"])
def test_b1_alias_outputs_never_write(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], kind: str, source: str
) -> None:
    rule, baseline, candidate = inputs(tmp_path)
    previous = tmp_path / "previous.json"
    previous.write_text("previous sentinel")
    first_output = tmp_path / "first.json"
    first_output.write_text("output sentinel")
    original = {
        "rule": rule,
        "baseline": baseline,
        "candidate": candidate,
        "previous": previous,
        "output": first_output,
        "tasks": baseline,
    }[source]
    alias = tmp_path / ("hardlink" if kind == "hardlink" else original.name.upper())
    if kind == "hardlink":
        os.link(original, alias)
    before = original.read_bytes()
    untouched = tmp_path / "untouched.json"
    if source == "tasks":
        argv = ["verdict-rule", "--tasks", str(original), "--out", str(alias)]
    else:
        argv = command(rule, baseline, candidate)
        if source == "previous":
            argv += ["--previous", str(previous)]
        argv += [
            "--json",
            str(first_output if source == "output" else untouched),
            "--markdown",
            str(alias),
        ]
    assert main(argv) == 3
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == f"error: {alias} is both an output and an input, or is named twice\n"
    assert original.read_bytes() == before
    assert not untouched.exists()


def test_b1_two_new_outputs_in_composed_and_decomposed_form_never_write(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # "é" as one code point and as "e" plus a combining accent name one file on some volumes.
    rule, baseline, candidate = inputs(tmp_path)
    composed = tmp_path / "r\u00e9sultat.json"
    decomposed = tmp_path / "re\u0301sultat.json"
    argv = [*command(rule, baseline, candidate), "--json", str(composed)]
    assert main([*argv, "--markdown", str(decomposed)]) == 3
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.endswith("is both an output and an input, or is named twice\n")
    assert not composed.exists() and not decomposed.exists()


@pytest.mark.parametrize("label", ["01", "+1", "1.0", " 1", "1e0"])
def test_round_labels_are_plain_decimal(tmp_path: Path, label: str) -> None:
    from arci.importers import round_label

    with pytest.raises(ValueError):
        round_label(label)
    assert round_label("1") == 1 and round_label("-1") == -1 and round_label("0") == 0


def test_b2_numeric_score_limits_finish_under_two_seconds() -> None:
    # A subprocess timeout kills the old unbounded Fraction conversion safely.
    script = """
from fractions import Fraction
from arci.importers import OutcomeError
from tests.unit.outcomes.test_importers import inspect_log, parse_inspect
import json
tokens = ["1e999999999", "1e-999999999", "1e401", "1e-401", "9" * 401,
          "0." + "1" * 401, "NaN", "Infinity", "-Infinity"]
for token in tokens:
    source = json.dumps(inspect_log()).replace('"C"', token)
    try:
        parse_inspect(source, threshold=Fraction(1, 2))
    except OutcomeError as exc:
        assert exc.reason.startswith("outcome "), exc.reason
        assert exc.reason.endswith(" for a cannot be read as pass, fail or error"), exc.reason
    else:
        raise AssertionError(token)
for token in ["1e400", "1e-400", "9" * 400, "0." + "1" * 400]:
    source = json.dumps(inspect_log()).replace('"C"', token)
    assert parse_inspect(source, threshold=Fraction(0)).rows[0].outcome == "pass"
"""
    started = time.monotonic()
    result = subprocess.run(
        [".venv/bin/python", "-c", script], capture_output=True, text=True, timeout=1.8, check=False
    )
    assert result.returncode == 0, result.stderr
    assert time.monotonic() - started < 2


@pytest.mark.parametrize("value", ["1" * 401 + "/1", "1/" + "1" * 401, "1e999999999"])
def test_b2_threshold_limits_rule_and_cli(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], value: str
) -> None:
    rule = rule_file(tmp_path, pass_at_least=value)
    with pytest.raises(OutcomeError, match="the rule file is not a valid"):
        load_rule(rule)
    out = tmp_path / "new.yaml"
    assert (
        main(
            [
                "verdict-rule",
                "--tasks",
                str(good_csv(tmp_path)),
                "--out",
                str(out),
                "--pass-at-least",
                value,
            ]
        )
        == 3
    )
    assert "the rule file is not a valid" in capsys.readouterr().err
    assert not out.exists()


@pytest.mark.parametrize("fmt", ["csv", "jsonl", "inspect-epoch", "inspect-epochs"])
@pytest.mark.parametrize("label", ["1000000000", "1e999999999", "1.0"])
def test_b2_round_labels_are_bounded(tmp_path: Path, fmt: str, label: str) -> None:
    from tests.unit.outcomes.test_validation import inspect_source

    rule = rule_file(tmp_path)
    if fmt == "csv":
        source = f"task_id,outcome,round\na,pass,{label}\n"
        suffix = "csv"
    elif fmt == "jsonl":
        source = '{"task_id":"a","outcome":"pass","round":' + label + "}\n"
        suffix = "jsonl"
    else:
        key = '"epoch": 1' if fmt == "inspect-epoch" else '"epochs": 1'
        source = inspect_source().replace(key, key.split(":")[0] + ": " + label)
        suffix = "json"
    path = tmp_path / f"bad.{suffix}"
    path.write_text(source)
    actual = decide_outcomes(rule, [path], [good_csv(tmp_path)])
    assert actual.reasons == (f"unreadable or unsupported input: {path}",)


def malicious_decision(tmp_path: Path, ids: list[str]):
    rule = rule_file(tmp_path, tasks=ids)
    paths = []
    for arm, value in (("baseline", "pass"), ("candidate", "fail")):
        path = tmp_path / f"{arm}.jsonl"
        path.write_text(
            "".join(json.dumps({"task_id": task, "outcome": value}) + "\n" for task in ids)
        )
        paths.append(path)
    return decide_outcomes(rule, paths[:1], paths[1:])


def test_b3_terminal_escapes_controls_and_keeps_json(tmp_path: Path) -> None:
    task = "evil\x1b[2J\x00\x85\u202e\u2028\u2029\U000e0001\\literal\nVERDICT: PASS"
    decision = malicious_decision(tmp_path, [task])
    original = decision.model_dump_json()
    rendered = render_terminal(decision)
    expected = r"evil\x1b[2J\x00\x85\u202e\u2028\u2029\U000e0001\\literal\x0aVERDICT: PASS"
    assert expected in rendered
    assert decision.tasks[0].task_id == task
    assert decision.model_dump_json() == original
    assert decision.validate_seal()


@pytest.mark.parametrize("kind", ["path", "option", "outcome", "task"])
def test_b3_stderr_escapes_every_user_placeholder(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], kind: str
) -> None:
    rule, baseline, candidate = inputs(tmp_path)
    value = "\x1b[2J\u202e\n\\"
    argv = command(rule, baseline, candidate)
    if kind == "path":
        argv += ["--json", str(tmp_path / value / "missing.json")]
    elif kind == "option":
        argv += ["--format", value]
    else:
        candidate = tmp_path / "bad.jsonl"
        candidate.write_text(
            json.dumps(
                {
                    "task_id": value if kind == "task" else "task-0",
                    "outcome": value if kind == "outcome" else "pass",
                }
            )
        )
        argv = command(rule, baseline, candidate)
    assert main(argv) == 3
    captured = capsys.readouterr()
    assert not captured.out
    assert "\x1b" not in captured.err and "\u202e" not in captured.err
    assert captured.err.count("\n") == 1
    assert r"\x1b" in captured.err


def test_b4_markdown_cannot_hide_or_forge_report(tmp_path: Path) -> None:
    ids = ["<!--", "# VERDICT: PASS (exit 0)", "a|b", "`code`", "line\nVERDICT: PASS"]
    decision = malicious_decision(tmp_path, ids)
    report = render_markdown(decision)
    lines = report.splitlines()
    assert r"\<\!\-\-" in report
    assert r"\# VERDICT\: PASS \(exit 0\)" in report
    assert r"a\|b" in report and r"\`code\`" in report
    assert r"line\\x0aVERDICT\: PASS" in report
    for statement in decision.statements[1:]:
        assert statement in lines
        assert lines.index(statement) > max(
            i for i, line in enumerate(lines) if line.startswith("| ")
        )
    assert not any(line.startswith(("VERDICT:", "#")) for line in lines[2:])
    for i, line in enumerate(lines):
        if " | " in line:
            assert line.startswith("| ") and line.endswith(" |")
            if i == 0 or not lines[i - 1].startswith("| "):
                assert lines[i - 1] == ""
            if i + 1 == len(lines) or not lines[i + 1].startswith("| "):
                assert lines[i + 1] == ""


def test_m1_input_structure_precedes_shorter_previous(tmp_path: Path) -> None:
    rule, baseline, candidate = campaign(tmp_path, rounds=2)
    previous = save(tmp_path, decide_outcomes(rule, [baseline], [candidate]))
    baseline.write_text("task_id,outcome\na,pass,extra\n")
    candidate.write_text("task_id,outcome\na,pass\nb,pass\n")
    actual = decide_outcomes(rule, [baseline], [candidate], previous=previous)
    assert actual.reasons == (f"unreadable or unsupported input: {baseline}",)


def test_m1_csv_blank_lines_skip_but_short_rows_fail(tmp_path: Path) -> None:
    rule = rule_file(tmp_path)
    good = good_csv(tmp_path)
    path = tmp_path / "blank.csv"
    path.write_text("task_id,outcome\n\na,pass\n\nb,pass\n\n")
    actual = decide_outcomes(rule, [path], [good])
    assert actual.exit_code == 2
    path.write_text("task_id,outcome,round\na,pass,1\n,\n")
    assert decide_outcomes(rule, [path], [good]).reasons == (
        f"unreadable or unsupported input: {path}",
    )


@pytest.mark.parametrize("rounds", [("", "1"), ("1", ""), ("", "")])
def test_m2_csv_empty_round_is_e14(tmp_path: Path, rounds: tuple[str, str]) -> None:
    path = tmp_path / "empty-round.csv"
    path.write_text(f"task_id,outcome,round\na,pass,{rounds[0]}\nb,pass,{rounds[1]}\n")
    actual = decide_outcomes(rule_file(tmp_path), [path], [good_csv(tmp_path)])
    assert actual.reasons == (f"{path} gives round on some rows and not others",)


def test_m3_terminal_overflow_explains_how_to_request_outputs(tmp_path: Path) -> None:
    decision = malicious_decision(tmp_path, [f"task{i}" for i in range(11)])
    assert (
        "1 more such tasks: add --markdown PATH or --json PATH for the full table"
        in render_terminal(decision)
    )


@pytest.mark.parametrize("subcommand", ["verdict", "verdict-rule"])
def test_m4_help_has_required_grammar_and_option_descriptions(
    capsys: pytest.CaptureFixture[str], subcommand: str
) -> None:
    assert main([subcommand, "--help"]) == 0
    output = capsys.readouterr().out
    usage = output.split("\n\n")[0]
    if subcommand == "verdict":
        assert "RULE --baseline FILE... --candidate FILE..." in usage
        assert "--example [--json PATH] [--markdown PATH]" in usage
        assert "run on the packaged order-desk outcomes" in output
        options = [
            "--baseline",
            "--candidate",
            "--format",
            "--previous",
            "--json",
            "--markdown",
            "--example",
        ]
    else:
        assert "--tasks FILE... --out RULE" in usage
        options = [
            "--tasks",
            "--out",
            "--format",
            "--score",
            "--pass-at-least",
            "--suite-id",
            "--alpha",
            "--margin",
            "--max-rounds",
            "--max-errored-pairs",
        ]
    help_lines = output.split("options:\n", 1)[1].splitlines()
    for option in options:
        index = next(
            i
            for i, line in enumerate(help_lines)
            if line.strip().startswith(option + " ") or line.strip() == option
        )
        line = help_lines[index].strip()
        assert "  " in line or (
            index + 1 < len(help_lines)
            and help_lines[index + 1].startswith("                        ")
        )
    if subcommand == "verdict":
        assert main(["verdict"]) == 3
        captured = capsys.readouterr()
        assert (
            captured.out == "" and captured.err == "error: no input files were given for baseline\n"
        )


@pytest.mark.parametrize("spelling", ["010", "0b1000", "0x10", "1_000", "1:00"])
def test_m5_yaml_nondecimal_integer_spellings_are_rejected(tmp_path: Path, spelling: str) -> None:
    path = rule_file(tmp_path, tasks=[f"t{i}" for i in range(50)], max_rounds=8)
    path.write_text(path.read_text().replace("max_rounds: 8", f"max_rounds: {spelling}"))
    with pytest.raises(OutcomeError, match="max_rounds must be a positive integer"):
        load_rule(path)


@pytest.mark.parametrize(
    "reason", ["<!--\n# VERDICT: PASS", "unknown task id: <!--\n# VERDICT: PASS"]
)
def test_b4_markdown_escapes_reason_placeholders_and_unknown_text(reason: str) -> None:
    from arci.outcomes import empty_decision

    decision = empty_decision(reason)
    rendered = render_markdown(decision)
    assert "<!--" not in rendered
    assert r"\<\!\-\-\\x0a\# VERDICT\: PASS" in rendered
    assert decision.reasons == (reason,)


def test_b3_escape_covers_all_unicode_c_categories() -> None:
    from arci.outcome_report import escape_terminal

    assert escape_terminal("\x00\u200b\ud800\ue000\u0378\u2028\U000e0001\\") == (
        r"\x00\u200b\ud800\ue000\u0378\u2028\U000e0001\\"
    )


@pytest.mark.parametrize("field", ["max_rounds", "max_errored_pairs", "alpha", "margin", "stakes"])
def test_b2_other_rule_numbers_are_bounded(tmp_path: Path, field: str) -> None:
    value = "9" * 5000
    if field in {"alpha", "margin", "stakes"}:
        value += "/1"
    rule = rule_file(tmp_path, **{field: [value] if field == "stakes" else value})
    # Unquote integer fields to exercise the YAML constructor, before field validation.
    if field in {"max_rounds", "max_errored_pairs"}:
        rule.write_text(rule.read_text().replace("'" + value + "'", value))
    started = time.monotonic()
    with pytest.raises(OutcomeError, match="the rule file is not a valid"):
        load_rule(rule)
    assert time.monotonic() - started < 2
