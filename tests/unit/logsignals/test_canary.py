"""No token of a transcript, a path or a key may leave the private tables.

Every synthetic transcript, path, repository key, user key and model name carries a token. The
two private tables hold paths and keys by design and are excluded; everything else the study
writes or prints is searched for every token.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from bench.logsignals import check_result, extract_signal, render
from tests.unit.logsignals import pipeline, tables, transcripts


def _tokens(sessions: list[tables.Session]) -> set[str]:
    found: set[str] = {tables.CANARY}
    for session in sessions:
        found.add(session.path)
        found.add(session.repo_key)
        found.add(session.model)
        if session.user_key:
            found.add(session.user_key)
    return found


def test_no_token_reaches_any_output_of_the_two_stages(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    sessions = tables.both_halves()
    tokens = _tokens(sessions)
    assert len(tokens) > 100

    signal, outcome = tables.write_tables(tmp_path / "tables", sessions)
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    page = tmp_path / "page.md"

    assert pipeline.stage_one(signal, outcome, "confirmation", out_dir) == 0
    assert pipeline.stage_one(signal, outcome, "discovery", out_dir) == 0
    for half in ("confirmation", "discovery"):
        assert (
            pipeline.stage_two(signal, outcome, half, out_dir, out_dir / f"checks_{half}.json") == 0
        )
        assert check_result.main(["--result", str(out_dir / f"result_{half}.json")]) == 0
    assert (
        render.main(
            [
                "--confirmation",
                str(out_dir / "result_confirmation.json"),
                "--discovery",
                str(out_dir / "result_discovery.json"),
                "--checks-confirmation",
                str(out_dir / "checks_confirmation.json"),
                "--checks-discovery",
                str(out_dir / "checks_discovery.json"),
                "--out",
                str(page),
            ]
        )
        == 0
    )

    captured = capsys.readouterr()
    # The companion run file is gone: the result file itself records the start time (decision 6).
    written = [
        out_dir / "checks_confirmation.json",
        out_dir / "checks_discovery.json",
        out_dir / "result_confirmation.json",
        out_dir / "result_discovery.json",
        page,
    ]
    searched = [captured.out, captured.err] + [path.read_text(encoding="utf-8") for path in written]
    assert all(text for text in searched[2:])
    for text in searched:
        for token in tokens:
            assert token not in text
        assert "transcripts0" not in text

    # The two private tables do hold the paths and the keys; that is their purpose.
    assert tables.CANARY in signal.read_text(encoding="utf-8")
    assert tables.CANARY in outcome.read_text(encoding="utf-8")


def test_no_token_reaches_the_step_four_page_or_the_notice(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The page forms of decision 3: the check section, the step 4 page and the notice."""
    sessions = tables.both_halves()
    tokens = _tokens(sessions)
    short = [session for session in sessions if session.half == "discovery"] + [
        session for session in sessions if session.half == "confirmation"
    ][:-1]
    signal, outcome = tables.write_tables(tmp_path / "tables", short)
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    # The stage 1 exit 3 path: its counts and its file carry no token either.
    assert pipeline.stage_one(signal, outcome, "confirmation", out_dir) == 3
    checks = out_dir / "checks_confirmation.json"
    step_four = tmp_path / "step-four.md"
    assert render.main(["--checks-confirmation", str(checks), "--out", str(step_four)]) == 0
    notice = tmp_path / "notice.md"
    assert render.main(["--notice-only", "--out", str(notice)]) == 0

    captured = capsys.readouterr()
    searched = [
        captured.out,
        captured.err,
        checks.read_text(encoding="utf-8"),
        step_four.read_text(encoding="utf-8"),
        notice.read_text(encoding="utf-8"),
    ]
    assert all(text for text in searched[2:])
    assert "not an answer" in searched[3]
    for text in searched:
        for token in tokens:
            assert token not in text
        assert "transcripts0" not in text


def test_no_token_reaches_the_error_paths(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The `table-invalid` and `checks-refused` paths print a fixed word and nothing else."""
    sessions = tables.both_halves()
    tokens = _tokens(sessions)
    signal, outcome = tables.write_tables(tmp_path / "tables", sessions)
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    # A table whose rows carry the tokens and break the format.
    broken = tmp_path / "broken.tsv"
    _ = broken.write_text(
        signal.read_text(encoding="utf-8").replace("\t20\t", "\ttwenty\t", 1), encoding="utf-8"
    )
    assert pipeline.stage_one(broken, outcome, "confirmation", out_dir) == 2
    assert pipeline.stage_two(broken, outcome, "confirmation", out_dir, tmp_path / "absent") == 3

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.splitlines() == ["table-invalid", "checks-refused"]
    for token in tokens:
        assert token not in captured.err
    assert not list(out_dir.iterdir())


def test_no_token_of_a_transcript_reaches_the_extractors_streams(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    data_dir = tmp_path / "data"
    (data_dir / "transcripts0").mkdir(parents=True)
    lines: list[str] = []
    tokens: set[str] = {transcripts.CANARY}
    for index in range(6):
        name = f"{transcripts.CANARY}-s{index}"
        path = f"transcripts0/{name}.jsonl"
        transcripts.write_transcript(
            data_dir / path,
            transcripts.codex_rows(
                tag=name,
                reasoning=[0, 1, None] * 10,
                models=[transcripts.canary(f"model-{index}")] * 30,
            ),
        )
        repo_key = tables.canary_key(index)
        user_key = tables.canary_key(100 + index)
        lines.append("\t".join([path, "codex", repo_key, "confirmation", "2026-04", user_key]))
        tokens.update({path, repo_key, user_key, transcripts.canary(f"model-{index}")})

    manifest = tmp_path / "manifest.tsv"
    _ = manifest.write_text("".join(line + "\n" for line in lines), encoding="utf-8")
    out = tmp_path / "signal.tsv"
    assert (
        extract_signal.main(
            ["--manifest", str(manifest), "--data-dir", str(data_dir), "--out", str(out)]
        )
        == 0
    )
    captured = capsys.readouterr()
    for text in (captured.out, captured.err):
        for token in tokens:
            assert token not in text
    counts = json.loads(captured.out)
    assert counts["rows_written"] == 6
    assert all(isinstance(value, int) for value in counts.values())
