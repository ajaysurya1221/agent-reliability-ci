"""The signal extractor: eligibility, the measures, hostile input and its silence."""

from __future__ import annotations

import json
import os
import stat
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from bench.logsignals import extract_signal
from tests.unit.logsignals import transcripts

REPO = "00000000000000a1"
USER = "00000000000000b2"
TDIR = "transcripts0"


@dataclass(frozen=True, slots=True)
class _StubResponse:
    """One response as the unchanged reader returns it, for the fields `session_fields` reads."""

    when: datetime
    main_thread: bool
    reasoning: int | None
    model: int = 0


@dataclass(frozen=True, slots=True)
class _StubResult:
    responses: tuple[_StubResponse, ...]
    models: tuple[str | None, ...] = field(default=("gpt-6-astra",))


class _Fixture:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.data_dir = root / "data"
        (self.data_dir / TDIR).mkdir(parents=True, exist_ok=True)
        self.lines: list[str] = []

    def manifest_line(
        self,
        path: str,
        *,
        group: str = "codex",
        repo_key: str = REPO,
        half: str = "confirmation",
        month: str = "2026-04",
        user_key: str = USER,
    ) -> None:
        self.lines.append("\t".join([path, group, repo_key, half, month, user_key]))

    def add_session(
        self,
        name: str,
        *,
        reasoning: Sequence[int | None],
        models: Sequence[str] | None = None,
        subagent: bool = False,
        group: str = "codex",
        offsets: Sequence[int] | None = None,
    ) -> str:
        path = f"{TDIR}/{name}.jsonl"
        transcripts.write_transcript(
            self.data_dir / path,
            transcripts.codex_rows(
                tag=name,
                reasoning=reasoning,
                models=models,
                subagent=subagent,
                offsets=offsets,
            ),
        )
        self.manifest_line(path, group=group)
        return path

    def write(self) -> Path:
        manifest = self.root / "manifest.tsv"
        _ = manifest.write_text("".join(line + "\n" for line in self.lines), encoding="utf-8")
        return manifest

    def run(self, out_name: str = "signal.tsv") -> tuple[int, Path]:
        out = self.root / out_name
        code = extract_signal.main(
            [
                "--manifest",
                str(self.write()),
                "--data-dir",
                str(self.data_dir),
                "--out",
                str(out),
            ]
        )
        return code, out


def _rows(out: Path) -> list[list[str]]:
    lines = out.read_text(encoding="utf-8").split("\n")
    assert lines[0] == "\t".join(extract_signal.HEADER)
    assert lines[-1] == ""
    return [line.split("\t") for line in lines[1:-1]]


def test_a_session_of_twenty_counts_is_eligible_and_one_of_nineteen_is_not(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    fixture = _Fixture(tmp_path)
    eligible = fixture.add_session("twenty", reasoning=[0] * 5 + list(range(1, 16)))
    _short = fixture.add_session("nineteen", reasoning=[1] * 19)
    code, out = fixture.run()
    assert code == 0
    rows = _rows(out)
    assert [row[0] for row in rows] == [eligible]
    row = rows[0]
    assert row[1:6] == [REPO, "confirmation", "2026-04", USER, "gpt-6-astra"]
    assert row[6] == "20"
    assert row[7] == transcripts.response_time(0)
    assert row[8] == "5"
    # The counts above 0 are 1..15; their median is 8.
    assert row[9:11] == ["8", "1"]

    counts = json.loads(capsys.readouterr().out)
    assert counts["codex_rows"] == 2
    assert counts["rows_written"] == 1
    assert counts["not_eligible"] == 1


def test_an_even_number_of_counts_above_zero_gives_a_half(tmp_path: Path) -> None:
    fixture = _Fixture(tmp_path)
    _ = fixture.add_session("even", reasoning=[0] * 10 + [1, 1, 1, 1, 1, 2, 2, 2, 2, 2])
    code, out = fixture.run()
    assert code == 0
    # The counts above 0 are five 1s and five 2s; their median is 3/2.
    assert _rows(out)[0][9:11] == ["3", "2"]


def test_responses_without_a_recorded_count_are_not_counted_but_carry_the_time(
    tmp_path: Path,
) -> None:
    fixture = _Fixture(tmp_path)
    _ = fixture.add_session("mixed", reasoning=[None, None] + [3] * 20)
    code, out = fixture.run()
    assert code == 0
    row = _rows(out)[0]
    assert row[6] == "20"
    assert row[7] == transcripts.response_time(0)


def test_a_subagent_transcript_is_not_eligible(tmp_path: Path) -> None:
    fixture = _Fixture(tmp_path)
    _ = fixture.add_session("sub", reasoning=[1] * 30, subagent=True)
    code, out = fixture.run()
    assert code == 0
    assert _rows(out) == []


def test_the_model_name_is_the_most_frequent_and_a_tie_sorts_first(tmp_path: Path) -> None:
    fixture = _Fixture(tmp_path)
    _ = fixture.add_session(
        "frequent", reasoning=[1] * 30, models=["gpt-6-astra"] * 10 + ["gpt-6-mini"] * 20
    )
    _ = fixture.add_session(
        "tied", reasoning=[1] * 20, models=["gpt-6-mini"] * 10 + ["gpt-6-astra"] * 10
    )
    code, out = fixture.run()
    assert code == 0
    by_path = {row[0]: row[5] for row in _rows(out)}
    assert by_path[f"{TDIR}/frequent.jsonl"] == "gpt-6-mini"
    assert by_path[f"{TDIR}/tied.jsonl"] == "gpt-6-astra"


def test_a_model_name_the_reader_does_not_render_becomes_unknown(tmp_path: Path) -> None:
    fixture = _Fixture(tmp_path)
    _ = fixture.add_session("odd", reasoning=[1] * 20, models=[transcripts.canary("model")] * 20)
    code, out = fixture.run()
    assert code == 0
    assert _rows(out)[0][5] == "unknown"


def test_the_vote_is_over_the_names_the_counted_responses_carry(tmp_path: Path) -> None:
    # Decision 4 (finding 4): a response with no rendered name gives no vote, so a session
    # whose plurality of responses carries no name still takes the one name it has.
    fixture = _Fixture(tmp_path)
    _ = fixture.add_session(
        "mostly-nameless",
        reasoning=[1] * 20,
        models=["gpt-6-astra"] * 8 + [transcripts.canary("model")] * 12,
    )
    code, out = fixture.run()
    assert code == 0
    assert _rows(out)[0][5] == "gpt-6-astra"


# --- the second measure's own condition ----------------------------------------


def test_exactly_ten_counts_above_zero_give_the_median(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    fixture = _Fixture(tmp_path)
    ten = fixture.add_session("ten", reasoning=[0] * 15 + list(range(1, 11)))
    code, out = fixture.run()
    assert code == 0
    # The counts above 0 are 1..10; their median is 11/2.
    assert {row[0]: row[9:11] for row in _rows(out)} == {ten: ["11", "2"]}
    counts = json.loads(capsys.readouterr().out)
    assert counts["rows_written"] == 1
    # The empty pair and its count are gone with point 1 of this round.
    assert "second_measure_undefined" not in counts


@pytest.mark.parametrize(
    "reasoning",
    [
        [0] * 16 + list(range(1, 10)),  # nine counts above 0
        [0] * 25,  # none at all
    ],
)
def test_fewer_than_ten_counts_above_zero_stop_the_extraction(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], reasoning: list[int]
) -> None:
    # Point 1 of this round, replacing decision 1 of SPEC_G: the registration says "every
    # eligible Codex session has it", so such a session ends the study before pairing instead of
    # being written with an empty pair and counted.
    fixture = _Fixture(tmp_path)
    _ = fixture.add_session("good", reasoning=[1] * 20)
    _ = fixture.add_session("short", reasoning=reasoning)
    code, out = fixture.run()
    assert code == 5
    assert not out.exists()
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "second-measure-undefined\n"


# --- the first main-thread response time ---------------------------------------


def test_the_first_time_is_the_earliest_and_not_the_first_in_file_order(tmp_path: Path) -> None:
    # The convention stated in `session_fields`: the earliest timestamp among the main-thread
    # responses the reader returns, not the first response the file holds.
    fixture = _Fixture(tmp_path)
    offsets = list(range(120, 100, -1))
    _ = fixture.add_session("out-of-order", reasoning=[1] * 20, offsets=offsets)
    code, out = fixture.run()
    assert code == 0
    assert _rows(out)[0][7] == transcripts.response_time(min(offsets))


def test_the_first_time_leaves_out_a_sub_thread_response_and_keeps_an_uncounted_one() -> None:
    # Responses of another thread are left out before the minimum is taken, and a main-thread
    # response without a known reasoning count still carries the time.
    earliest_main = datetime(2026, 5, 3, 10, 0, 0, tzinfo=UTC)
    result = _StubResult(
        responses=(
            _StubResponse(datetime(2026, 5, 3, 12, 0, 0, tzinfo=UTC), True, 5),
            _StubResponse(datetime(2026, 5, 3, 8, 0, 0, tzinfo=UTC), False, 5),
            _StubResponse(earliest_main, True, None),
            *(
                _StubResponse(datetime(2026, 5, 3, 13, 0, index, tzinfo=UTC), True, 7)
                for index in range(20)
            ),
        )
    )
    fields = extract_signal.session_fields(result)
    assert fields is not None
    assert fields["first_time"] == earliest_main.isoformat()
    assert fields["d"] == "21"


def test_rows_of_the_other_tool_are_not_read(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    fixture = _Fixture(tmp_path)
    _ = fixture.add_session("other", reasoning=[1] * 30, group="claude_code")
    code, out = fixture.run()
    assert code == 0
    assert _rows(out) == []
    counts = json.loads(capsys.readouterr().out)
    assert counts["codex_rows"] == 0
    assert counts["manifest_lines"] == 1


# --- the files that are not read ----------------------------------------------


def test_an_absent_a_directory_and_a_symbolic_link_are_counted_and_skipped(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    fixture = _Fixture(tmp_path)
    fixture.manifest_line(f"{TDIR}/absent.jsonl")
    (fixture.data_dir / TDIR / "folder.jsonl").mkdir()
    fixture.manifest_line(f"{TDIR}/folder.jsonl", repo_key="00000000000000a2")
    outside = tmp_path / "outside"
    outside.mkdir()
    target = outside / "target.jsonl"
    transcripts.write_transcript(target, transcripts.codex_rows(tag="link", reasoning=[1] * 30))
    os.symlink(target, fixture.data_dir / TDIR / "link.jsonl")
    fixture.manifest_line(f"{TDIR}/link.jsonl", repo_key="00000000000000a3")

    code, out = fixture.run()
    assert code == 0
    assert _rows(out) == []
    counts = json.loads(capsys.readouterr().out)
    assert counts["files_absent"] == 1
    assert counts["files_not_regular"] == 2
    assert counts["files_present"] == 0


def test_a_transcript_whose_reader_raises_is_counted_and_leaks_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    class _Raising:
        def read(self, *_args: object, **_kwargs: object) -> object:
            raise RuntimeError(f"boom {transcripts.CANARY} transcripts0/leaked.jsonl")

    fixture = _Fixture(tmp_path)
    _ = fixture.add_session("raises", reasoning=[1] * 30)
    monkeypatch.setattr(extract_signal, "codex", _Raising())
    code, out = fixture.run()
    assert code == 0
    assert _rows(out) == []
    captured = capsys.readouterr()
    assert captured.err == ""
    assert transcripts.CANARY not in captured.out
    counts = json.loads(captured.out)
    assert counts["reader_exception"] == 1


def test_a_raise_while_reading_the_readers_result_stops_the_extraction(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    # Point 2 of this round, replacing decision 11 of SPEC_G: a raise inside `session_fields` is
    # not counted and not skipped. A raise of the reader itself stays counted and skipped, as
    # the test above shows.
    fixture = _Fixture(tmp_path)
    _ = fixture.add_session("first", reasoning=[1] * 20)
    _ = fixture.add_session("second", reasoning=[1] * 20)
    calls: list[int] = []

    def _raising(result: object) -> dict[str, str] | None:
        calls.append(1)
        raise RuntimeError(f"boom {transcripts.CANARY}")

    monkeypatch.setattr(extract_signal, "session_fields", _raising)
    code, out = fixture.run()
    assert code == 1
    assert not out.exists()
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "fields-unreadable\n"
    assert transcripts.CANARY not in captured.err
    assert len(calls) == 1


def test_an_eligible_session_with_an_unsafe_model_name_stops_the_extraction(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    # Decision 10 (finding 9): "All eligible sessions enter. No trimming, no transformation, no
    # deletion", so such a session is not dropped: nothing is written and the run ends.
    fixture = _Fixture(tmp_path)
    _ = fixture.add_session("unsafe", reasoning=[1] * 20)

    def _unsafe(result: object) -> dict[str, str] | None:
        return {
            "model": f"{transcripts.CANARY}\tmodel",
            "d": "20",
            "first_time": "",
            "zero": "0",
            "tokens_num": "1",
            "tokens_den": "1",
        }

    monkeypatch.setattr(extract_signal, "session_fields", _unsafe)
    code, out = fixture.run()
    assert code == 1
    assert not out.exists()
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "field-unsafe\n"


def test_a_reader_that_exits_ends_the_run_without_a_table(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    # Decision 12 (finding 11): `SystemExit` is caught as the reference catches it.
    class _Exiting:
        def read(self, *_args: object, **_kwargs: object) -> object:
            raise SystemExit(2)

    fixture = _Fixture(tmp_path)
    _ = fixture.add_session("exits", reasoning=[1] * 20)
    monkeypatch.setattr(extract_signal, "codex", _Exiting())
    code, out = fixture.run()
    assert code == 1
    assert not out.exists()
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_the_reader_wrapper_keeps_nothing_of_an_exception() -> None:
    class _Raising:
        def read(self, *_args: object, **_kwargs: object) -> object:
            raise RuntimeError(transcripts.CANARY)

    ok, result = extract_signal.safe_read(_Raising(), Path("transcripts0/x.jsonl"))
    assert ok is False
    assert result is None


# --- hostile manifests ---------------------------------------------------------


@pytest.mark.parametrize(
    "line",
    [
        "transcripts0/a.jsonl\tcodex\t00000000000000a1\tconfirmation\t2026-04",
        "transcripts0/a.jsonl\tcodex\t00000000000000a1\tconfirmation\t2026-04\t\textra",
        "transcripts0/a.jsonl\tother\t00000000000000a1\tconfirmation\t2026-04\t",
        "transcripts0/a.jsonl\tcodex\tNOTHEX\tconfirmation\t2026-04\t",
        "transcripts0/a.jsonl\tcodex\t00000000000000a1\tneither\t2026-04\t",
        "transcripts0/a.jsonl\tcodex\t00000000000000a1\tconfirmation\t2026-13\t",
        "transcripts0/a.jsonl\tcodex\t00000000000000a1\tconfirmation\t2026-04\tNOTHEX",
        "elsewhere/a.jsonl\tcodex\t00000000000000a1\tconfirmation\t2026-04\t",
        "transcripts0/a.txt\tcodex\t00000000000000a1\tconfirmation\t2026-04\t",
        "transcripts0/\x00.jsonl\tcodex\t00000000000000a1\tconfirmation\t2026-04\t",
    ],
)
def test_a_manifest_that_breaks_the_format_writes_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], line: str
) -> None:
    manifest = tmp_path / "manifest.tsv"
    _ = manifest.write_text(line + "\n", encoding="utf-8")
    out = tmp_path / "signal.tsv"
    code = extract_signal.main(
        ["--manifest", str(manifest), "--data-dir", str(tmp_path), "--out", str(out)]
    )
    assert code == 2
    assert not out.exists()
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "manifest-invalid\n"


def test_a_long_transcript_path_is_read_as_the_reference_reads_it() -> None:
    # Decision 13 (finding 12): the reference bounds no path length, so neither does this
    # program. An over-long path no longer makes the whole manifest invalid.
    name = "transcripts0/" + "x" * 600 + ".jsonl"
    line = f"{name}\tcodex\t00000000000000a1\tconfirmation\t2026-04\t"
    rows = extract_signal.validate_and_parse_manifest(line + "\n")
    assert [row["transcript_path"] for row in rows] == [name]


def test_a_repeated_path_writes_nothing(tmp_path: Path) -> None:
    line = "transcripts0/a.jsonl\tcodex\t00000000000000a1\tconfirmation\t2026-04\t"
    manifest = tmp_path / "manifest.tsv"
    _ = manifest.write_text(line + "\n" + line + "\n", encoding="utf-8")
    out = tmp_path / "signal.tsv"
    assert (
        extract_signal.main(
            ["--manifest", str(manifest), "--data-dir", str(tmp_path), "--out", str(out)]
        )
        == 2
    )
    assert not out.exists()


def test_a_manifest_that_is_not_utf_eight_writes_nothing(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.tsv"
    _ = manifest.write_bytes(
        b"transcripts0/\xff.jsonl\tcodex\t00000000000000a1\tconfirmation\t2026-04\t\n"
    )
    out = tmp_path / "signal.tsv"
    assert (
        extract_signal.main(
            ["--manifest", str(manifest), "--data-dir", str(tmp_path), "--out", str(out)]
        )
        == 2
    )
    assert not out.exists()


def test_a_path_holding_a_tab_or_a_newline_breaks_the_format(tmp_path: Path) -> None:
    for raw in (
        "transcripts0/a\tb.jsonl\tcodex\t00000000000000a1\tconfirmation\t2026-04\t",
        "transcripts0/a\nb.jsonl\tcodex\t00000000000000a1\tconfirmation\t2026-04\t",
    ):
        manifest = tmp_path / "manifest.tsv"
        _ = manifest.write_text(raw + "\n", encoding="utf-8")
        out = tmp_path / f"signal-{len(raw)}.tsv"
        assert (
            extract_signal.main(
                ["--manifest", str(manifest), "--data-dir", str(tmp_path), "--out", str(out)]
            )
            == 2
        )
        assert not out.exists()


def test_a_missing_manifest_writes_nothing(tmp_path: Path) -> None:
    out = tmp_path / "signal.tsv"
    assert (
        extract_signal.main(
            [
                "--manifest",
                str(tmp_path / "absent.tsv"),
                "--data-dir",
                str(tmp_path),
                "--out",
                str(out),
            ]
        )
        == 2
    )
    assert not out.exists()


# --- the output ----------------------------------------------------------------


def test_the_table_is_private_and_is_not_overwritten(tmp_path: Path) -> None:
    fixture = _Fixture(tmp_path)
    _ = fixture.add_session("one", reasoning=[1] * 20)
    code, out = fixture.run()
    assert code == 0
    assert stat.S_IMODE(out.stat().st_mode) == 0o600
    first = out.read_bytes()

    manifest = fixture.root / "manifest.tsv"
    assert (
        extract_signal.main(
            [
                "--manifest",
                str(manifest),
                "--data-dir",
                str(fixture.data_dir),
                "--out",
                str(out),
            ]
        )
        == 2
    )
    assert out.read_bytes() == first


def test_two_runs_write_the_same_table(tmp_path: Path) -> None:
    fixture = _Fixture(tmp_path)
    for index in range(4):
        _ = fixture.add_session(f"s{index}", reasoning=[0, 1] * 12)
    code, first = fixture.run("first.tsv")
    assert code == 0
    code, second = fixture.run("second.tsv")
    assert code == 0
    assert first.read_bytes() == second.read_bytes()


def test_nothing_of_a_transcript_reaches_the_output_streams(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    fixture = _Fixture(tmp_path)
    _ = fixture.add_session("leak", reasoning=[None] * 3 + [1] * 20)
    code, _out = fixture.run()
    assert code == 0
    captured = capsys.readouterr()
    assert transcripts.CANARY not in captured.out
    assert transcripts.CANARY not in captured.err
    assert "transcripts0" not in captured.out
    values: Any = json.loads(captured.out)
    assert all(isinstance(value, int) for value in values.values())


def test_bad_arguments_print_one_word(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert extract_signal.main(["--manifest", str(tmp_path / "m.tsv")]) == 2
    assert capsys.readouterr().err == "arguments-invalid\n"
