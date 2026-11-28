"""Exercise ADR 0020 through the normal convert and verdict CLI entry points."""

from __future__ import annotations

import hashlib
import io
import json
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

from arci.cli import main
from tests.unit.integrations.test_promptfoo_reader import (
    REAL,
    REFUSALS,
    Refusal,
    canonical,
    raw_rows,
)

SENTENCE = (
    "These are existing results: use arci verdict-rule and arci verdict for a descriptive verdict; "
    "the error bound needs fresh runs (arci check-change)."
)


def run_convert(source: Path, out: Path, *selectors: str) -> int:
    return main(["convert", "--from", "promptfoo", str(source), "--out", str(out), *selectors])


@pytest.mark.parametrize("file", ["cache-cold", "cache-env-off"])
def test_a03_cache_setting_notice(
    file: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "out.jsonl"
    assert run_convert(REAL / f"{file}.json", out) == 0
    assert out.is_file()
    assert (
        "the cache was on, so answers may come from earlier runs that the file cannot show"
        in capsys.readouterr().out
    )


@pytest.mark.parametrize("file", ["words-single", "words-candidate"])
def test_a04_exact_bytes_and_summary(
    file: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = REAL / f"{file}.json"
    raw = source.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    doc = json.loads(raw)
    expected = raw_rows(doc)
    lines: list[bytes] = []
    for round_no, task, outcome in expected:
        record: dict[str, object] = dict(
            reader="promptfoo/1", task_id=task, outcome=outcome, source_sha256=digest
        )
        if round_no is not None:
            record["round"] = round_no
        lines.append(canonical(record) + b"\n")
    stats = doc["results"]["stats"]
    for n in ("first", "second"):
        directory = tmp_path / n
        directory.mkdir()
        out = directory / "out.jsonl"
        assert run_convert(source, out) == 0
        assert list(directory.iterdir()) == [out]
        assert out.read_bytes() == b"".join(lines)
        report = capsys.readouterr()
        assert report.err == ""
        label = doc["results"]["results"][0]["provider"]["label"]
        assert report.out.splitlines() == [
            "reader: promptfoo/1",
            "tool version: 0.126.0",
            f"source_sha256: {digest}",
            f'selected cell: prompt=0 provider="{label}"',
            f"rows: {len(expected)}, rounds: {len({r for r, _, _ in expected})}",
            f"pass: {stats['successes']}, fail: {stats['failures']}, error: {stats['errors']}",
            SENTENCE,
        ]


def test_a04_untested_version_notice(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    doc = json.loads((REAL / "words-single.json").read_bytes())
    doc["metadata"]["promptfooVersion"] = "other\nextra"
    source = tmp_path / "other.json"
    source.write_bytes(canonical(doc))
    assert run_convert(source, tmp_path / "out.jsonl") == 0
    lines = capsys.readouterr().out.splitlines()
    assert r"tool version: other\x0aextra" in lines
    notices = [s for s in lines if "not tested" in s]
    assert notices == [r"Notice: promptfoo/1 was not tested with promptfoo version other\x0aextra."]


@pytest.mark.parametrize("case", REFUSALS, ids=lambda c: c.name)
def test_a04_reader_refusals_write_nothing(
    case: Refusal, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = tmp_path / "source.json"
    source.write_bytes(case.source())
    selectors = [] if case.prompt is None else ["--prompt", str(case.prompt)]
    assert run_convert(source, tmp_path / "out.jsonl", *selectors) == 3
    assert list(tmp_path.iterdir()) == [source]
    assert case.reason in capsys.readouterr().err


@pytest.mark.parametrize(
    "case",
    [
        "suffix",
        "existing",
        "same",
        "missing folder",
        "missing source",
        "directory",
        "dangling symlink",
    ],
)
def test_a04_path_refusals_preserve_files(case: str, tmp_path: Path) -> None:
    source = tmp_path / "source.jsonl"
    raw = (REAL / "words-single.json").read_bytes()
    source.write_bytes(raw)
    out = tmp_path / "out.jsonl"
    if case == "suffix":
        out = tmp_path / "result.json"
    elif case == "existing":
        out.write_bytes(b"keep these bytes")
    elif case == "same":
        out = source
    elif case == "missing folder":
        out = tmp_path / "new" / "out.jsonl"
    elif case == "missing source":
        source = tmp_path / "missing"
    elif case == "directory":
        source = tmp_path
    elif case == "dangling symlink":
        out.symlink_to(tmp_path / "missing")
    before = set(tmp_path.iterdir())
    assert run_convert(source, out) == 3
    assert set(tmp_path.iterdir()) == before
    assert (tmp_path / "source.jsonl").read_bytes() == raw
    if case == "existing":
        assert out.read_bytes() == b"keep these bytes"
    if case == "dangling symlink":
        assert out.is_symlink()


def test_a05_verdict_pair_counts_from_raw_inputs(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    arms: list[dict[tuple[int | None, str], str]] = []
    for arm in ("baseline", "candidate"):
        source = REAL / f"words-{arm}.json"
        arms.append(
            {(n, key): value for n, key, value in raw_rows(json.loads(source.read_bytes()))}
        )
        assert run_convert(source, tmp_path / f"{arm}.jsonl") == 0
    baseline, candidate = arms
    assert baseline.keys() == candidate.keys()
    rule = str(tmp_path / "rule.yaml")
    base, cand = str(tmp_path / "baseline.jsonl"), str(tmp_path / "candidate.jsonl")
    assert main(["verdict-rule", "--tasks", base, "--out", rule]) == 0
    capsys.readouterr()
    decision = tmp_path / "decision.json"
    assert (
        main(["verdict", rule, "--baseline", base, "--candidate", cand, "--json", str(decision)])
        == 2
    )
    assert capsys.readouterr().out.splitlines()[0] == (
        "Descriptive verdict: the rule file declares it was written after outcomes existed. "
        "The error bound is not claimed."
    )
    history = json.loads(decision.read_bytes())["history"]
    assert [look["round"] for look in history] == [1, 2, 3]
    counts: Counter[str] = Counter(dict(minus=0, zero=0, plus=0, errored=0))
    for look in history:
        for pair, a in baseline.items():
            if pair[0] != look["round"]:
                continue
            b = candidate[pair]
            if "error" in (a, b):
                counts["errored"] += 1
            elif a == b:
                counts["zero"] += 1
            else:
                counts["minus" if a == "pass" else "plus"] += 1
        assert look["counts"] == dict(counts)


@pytest.mark.parametrize(
    ("file", "selector", "values"),
    [
        ("two-prompts", "--prompt", ("0", "1")),
        ("two-providers", "--provider", ("old", "new")),
    ],
)
def test_a06_convert_each_cell(
    file: str, selector: str, values: tuple[str, str], tmp_path: Path
) -> None:
    source = REAL / f"{file}.json"
    doc = json.loads(source.read_bytes())
    ids: list[set[str]] = []
    for value in values:
        out = tmp_path / f"{value}.jsonl"
        assert run_convert(source, out, selector, value) == 0
        rows = [json.loads(line) for line in out.read_bytes().splitlines()]
        triples = [(r["round"], r["task_id"], r["outcome"]) for r in rows]
        expected = (
            raw_rows(doc, int(value)) if selector == "--prompt" else raw_rows(doc, provider=value)
        )
        assert triples == expected
        assert {n for n, _, _ in triples} == {1, 2, 3}
        ids.append({key for _, key, _ in triples})
    assert ids[0] == ids[1]


@pytest.mark.parametrize(
    ("file", "options"),
    [
        ("two-prompts", []),
        ("two-providers", []),
        ("two-prompts", ["--prompt", "5"]),
        ("two-prompts", ["--provider", "scripted"]),
        ("two-providers", ["--prompt", "0", "--provider", "new"]),
    ],
)
def test_a06_selector_refusal_lists_cells(
    file: str, options: list[str], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = REAL / f"{file}.json"
    assert run_convert(source, tmp_path / "out.jsonl", *options) == 3
    assert list(tmp_path.iterdir()) == []
    message = capsys.readouterr().err
    for r in json.loads(source.read_bytes())["results"]["results"]:
        assert f'prompt={r["promptIdx"]} provider="{r["provider"]["label"]}"' in message


@pytest.mark.parametrize("failure", [OSError, KeyboardInterrupt])
def test_midwrite_never_publishes_partial_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: type[BaseException]
) -> None:
    out = tmp_path / "out.jsonl"
    open_file = io.open
    visible: list[bool] = []

    def interrupted_open(file: Any, mode: str = "r", *args: Any, **kwargs: Any) -> Any:
        stream = open_file(file, mode, *args, **kwargs)
        if "b" in mode and stream.writable():
            write = stream.write

            def interrupt(data: bytes) -> int:
                write(data[:4])
                stream.flush()
                visible.append(out.exists())
                raise failure()

            monkeypatch.setattr(stream, "write", interrupt)
        return stream

    with monkeypatch.context() as patch:
        patch.setattr(io, "open", interrupted_open)
        if failure is KeyboardInterrupt:
            with pytest.raises(KeyboardInterrupt):
                run_convert(REAL / "words-single.json", out)
        else:
            assert run_convert(REAL / "words-single.json", out) == 3
    assert visible == [False]
    assert list(tmp_path.iterdir()) == []


def test_ascii_streams_escape_imported_cell_names(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    doc = json.loads((REAL / "words-single.json").read_bytes())
    for row in doc["results"]["results"]:
        row["provider"]["label"] = "café\u2028end"
    source = tmp_path / "source.json"
    source.write_bytes(canonical(doc))
    out = tmp_path / "out.jsonl"
    with (
        io.TextIOWrapper(io.BytesIO(), encoding="ascii") as stdout,
        io.TextIOWrapper(io.BytesIO(), encoding="ascii") as stderr,
        monkeypatch.context() as patch,
    ):
        patch.setattr(sys, "stdout", stdout)
        patch.setattr(sys, "stderr", stderr)
        assert run_convert(source, out) == 0
        assert run_convert(source, tmp_path / "missing.jsonl", "--provider", "absent") == 3
        for stream in (stdout, stderr):
            stream.seek(0)
            assert r'provider="caf\xe9\u2028end"' in stream.read()
    assert out.is_file()


@pytest.mark.parametrize("unbuffered", [False, True])
def test_closed_pipe_preserves_published_exit_status(tmp_path: Path, unbuffered: bool) -> None:
    out = tmp_path / "out.jsonl"
    reader, writer = os.pipe()
    os.close(reader)
    with os.fdopen(writer, "wb") as pipe:
        result = subprocess.run(
            [
                sys.executable,
                *(["-u"] if unbuffered else []),
                "-m",
                "arci",
                "convert",
                "--from",
                "promptfoo",
                str(REAL / "words-single.json"),
                "--out",
                str(out),
            ],
            stdout=pipe,
            stderr=subprocess.PIPE,
            check=False,
        )
    assert out.read_bytes().endswith(b"\n")
    assert result.returncode == 0, result.stderr
