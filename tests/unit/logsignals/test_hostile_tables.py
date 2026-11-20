"""Hostile private tables: every violation stops the run and writes nothing."""

from __future__ import annotations

from datetime import UTC, datetime
from fractions import Fraction
from pathlib import Path

import pytest

from bench.logsignals import analyze
from tests.unit.logsignals import pipeline, tables

GOOD = (
    "transcripts0/a.jsonl\t00000000000000a1\tconfirmation\t2026-04\t00000000000000b2\t"
    "gpt-6-astra\t20\t2026-05-03T14:07:09+00:00\t3\t11\t1"
)
OUTCOME_GOOD = "transcripts0/a.jsonl\t40.0"


def _write(tmp_path: Path, signal_body: str, outcome_body: str = OUTCOME_GOOD) -> tuple[Path, Path]:
    signal = tmp_path / "signal.tsv"
    outcome = tmp_path / "outcome.tsv"
    _ = signal.write_text(tables.SIGNAL_HEADER + "\n" + signal_body, encoding="utf-8")
    _ = outcome.write_text(tables.OUTCOME_HEADER + "\n" + outcome_body, encoding="utf-8")
    return signal, outcome


@pytest.mark.parametrize(
    "body",
    [
        "",  # no header at all is covered separately; an empty body is valid
    ],
)
def test_a_table_with_no_rows_is_read(tmp_path: Path, body: str) -> None:
    signal, _outcome = _write(tmp_path, body)
    assert analyze.read_signal(signal) == []


@pytest.mark.parametrize(
    "row",
    [
        # one field short, one field too many
        "\t".join(GOOD.split("\t")[:-1]),
        GOOD + "\textra",
        # a path that is not a transcript path, or holds a tab
        GOOD.replace("transcripts0/a.jsonl", "elsewhere/a.jsonl"),
        GOOD.replace("transcripts0/a.jsonl", "transcripts0/a\tb.jsonl"),
        # an enormous field
        GOOD.replace("\tgpt-6-astra\t", "\t" + "m" * 2000 + "\t"),
        # a key, a half, a month that is not of the fixed form
        GOOD.replace("00000000000000a1", "NOTHEX0000000001"),
        GOOD.replace("\tconfirmation\t", "\tneither\t"),
        GOOD.replace("\t2026-04\t", "\t2026-13\t"),
        GOOD.replace("00000000000000b2", "NOTHEX0000000002"),
        # a session length below the minimum, and zero above the length
        GOOD.replace("\t20\t2026-05", "\t19\t2026-05"),
        GOOD.replace("+00:00\t3\t", "+00:00\t21\t"),
        # a token denominator that is not 1 or 2, a negative numerator
        GOOD[:-1] + "3",
        GOOD.replace("\t11\t1", "\t-11\t1"),
        # the token pair, one field or both empty: point 1 of this round requires both fields,
        # because the registration gives every eligible session a second measure
        GOOD.replace("\t11\t1", "\t\t1"),
        GOOD.replace("\t11\t1", "\t11\t"),
        GOOD.replace("\t11\t1", "\t\t"),
        # a first response time without a zone, and one that is not a time
        GOOD.replace("2026-05-03T14:07:09+00:00", "2026-05-03T14:07:09"),
        GOOD.replace("2026-05-03T14:07:09+00:00", "not-a-time"),
        # a length and a count that are not integers
        GOOD.replace("\t20\t2026-05", "\ttwenty\t2026-05"),
        GOOD.replace("+00:00\t3\t", "+00:00\t3.5\t"),
    ],
)
def test_a_signal_row_that_breaks_the_format_stops_the_run(tmp_path: Path, row: str) -> None:
    signal, _outcome = _write(tmp_path, row + "\n")
    with pytest.raises(analyze.TableInvalid):
        _ = analyze.read_signal(signal)


def test_an_enormous_transcript_path_is_read_as_the_reference_reads_it(tmp_path: Path) -> None:
    # Decision 13 (finding 12): the reference bounds no path length, so neither does this
    # program. An enormous line is no longer a format violation by its length alone.
    name = "transcripts0/" + "x" * 2000 + ".jsonl"
    signal, _outcome = _write(tmp_path, GOOD.replace("transcripts0/a.jsonl", name) + "\n")
    assert [row.path for row in analyze.read_signal(signal)] == [name]


def test_an_empty_first_response_time_is_read(tmp_path: Path) -> None:
    signal, _outcome = _write(tmp_path, GOOD.replace("2026-05-03T14:07:09+00:00", "") + "\n")
    assert analyze.read_signal(signal)[0].first_time is None


def test_a_time_with_another_offset_is_read_as_an_instant(tmp_path: Path) -> None:
    signal, _outcome = _write(
        tmp_path, GOOD.replace("2026-05-03T14:07:09+00:00", "2026-05-03T16:07:09+02:00") + "\n"
    )
    row = analyze.read_signal(signal)[0]
    assert row.first_time is not None
    assert row.first_time == datetime(2026, 5, 3, 14, 7, 9, tzinfo=UTC)


def test_a_repeated_path_stops_the_run(tmp_path: Path) -> None:
    signal, _outcome = _write(tmp_path, GOOD + "\n" + GOOD + "\n")
    with pytest.raises(analyze.TableInvalid):
        _ = analyze.read_signal(signal)


def test_a_wrong_header_stops_the_run(tmp_path: Path) -> None:
    signal = tmp_path / "signal.tsv"
    _ = signal.write_text("path\trepo_key\n" + GOOD + "\n", encoding="utf-8")
    with pytest.raises(analyze.TableInvalid):
        _ = analyze.read_signal(signal)


def test_a_table_that_is_not_utf_eight_stops_the_run(tmp_path: Path) -> None:
    signal = tmp_path / "signal.tsv"
    _ = signal.write_bytes(tables.SIGNAL_HEADER.encode("utf-8") + b"\n\xff\xfe\n")
    with pytest.raises(analyze.TableInvalid):
        _ = analyze.read_signal(signal)


def test_an_absent_table_stops_the_run(tmp_path: Path) -> None:
    with pytest.raises(analyze.TableInvalid):
        _ = analyze.read_signal(tmp_path / "absent.tsv")


def test_a_directory_in_place_of_a_table_stops_the_run(tmp_path: Path) -> None:
    (tmp_path / "folder.tsv").mkdir()
    with pytest.raises(analyze.TableInvalid):
        _ = analyze.read_signal(tmp_path / "folder.tsv")


@pytest.mark.parametrize(
    "written",
    [
        "not-a-number",
        "nan",
        "inf",
        "-inf",
        "-0.5",
        "100.5",
        "1e400",
        # Decision 8 (finding 8): only the exact `repr(float)` spelling is a value.
        "1_0",
        " 50 ",
        "5e1",
        "+50",
        "50",
        "0.30",
    ],
)
def test_an_outcome_value_a_session_needs_must_be_a_share(tmp_path: Path, written: str) -> None:
    signal, outcome = _write(tmp_path, GOOD + "\n", f"transcripts0/a.jsonl\t{written}\n")
    with pytest.raises(analyze.TableInvalid):
        _ = analyze.read_outcome(outcome, {"transcripts0/a.jsonl"})
    assert len(analyze.read_signal(signal)) == 1


def test_an_outcome_row_that_is_absent_stops_the_run(tmp_path: Path) -> None:
    _signal, outcome = _write(tmp_path, GOOD + "\n", "transcripts0/b.jsonl\t40.0\n")
    with pytest.raises(analyze.TableInvalid):
        _ = analyze.read_outcome(outcome, {"transcripts0/a.jsonl"})


def test_a_repeated_outcome_path_stops_the_run_even_when_it_is_not_needed(tmp_path: Path) -> None:
    body = "transcripts0/b.jsonl\t40.0\ntranscripts0/b.jsonl\t41.0\n"
    _signal, outcome = _write(tmp_path, GOOD + "\n", body)
    with pytest.raises(analyze.TableInvalid):
        _ = analyze.read_outcome(outcome, set())


def test_an_empty_outcome_value_is_a_missing_value(tmp_path: Path) -> None:
    _signal, outcome = _write(tmp_path, GOOD + "\n", "transcripts0/a.jsonl\t\n")
    assert analyze.read_outcome(outcome, {"transcripts0/a.jsonl"}) == {"transcripts0/a.jsonl": None}


def test_a_missing_outcome_leaves_a_session_out_of_every_block(tmp_path: Path) -> None:
    sessions = tables.make_sessions(repositories=10, per_repository=16)
    sessions = [tables.with_outcome(session, "") for session in sessions[:1]] + list(sessions[1:])
    signal, outcome = tables.write_tables(tmp_path, sessions)
    description = analyze.describe(signal, outcome, "confirmation")
    checks = description["checks"]
    assert isinstance(checks, dict)
    assert checks["outcome_missing"] == 1
    assert description["sessions"] == 160
    measures = description["measures"]
    assert isinstance(measures, dict)
    first = measures["no_reasoning_share"]
    assert isinstance(first, dict)
    block = first["repository"]
    assert isinstance(block, dict)
    assert block["sessions"] == 159
    assert block["W"] == 149


def test_both_measures_are_read_from_every_row(tmp_path: Path) -> None:
    # Point 1 of this round: there is no row without a second measure, so no path leaves a
    # session out of the `reasoning_tokens` blocks.
    signal, _outcome = _write(tmp_path, GOOD + "\n")
    row = analyze.read_signal(signal)[0]
    assert row.tokens == Fraction(11)
    assert row.value("reasoning_tokens") == Fraction(11)
    assert row.value("no_reasoning_share") == Fraction(3, 20)


def test_describe_refuses_a_table_without_the_other_half(tmp_path: Path) -> None:
    # Decision 5 (finding 5): with the other half absent the number without shared users would
    # exclude nothing and silently equal `rho_bar`.
    sessions = tables.make_sessions(repositories=12, per_repository=16)
    one_half = tables.write_tables(tmp_path / "one", sessions, fill_other_half=False)
    with pytest.raises(analyze.TableInvalid):
        _ = analyze.describe(one_half[0], one_half[1], "confirmation")

    both = tables.write_tables(tmp_path / "both", sessions)
    description = analyze.describe(both[0], both[1], "confirmation")
    assert description["sessions"] == 192
    # Stage 1 does not need the other half: it reads no user id.
    counts = analyze.stage_one(one_half[0], one_half[1], "confirmation")
    assert counts["half"] == "confirmation"


def test_a_second_half_that_differs_stops_the_second_half_alone(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # MAJOR 1 of review 3: the registration wins over point 3 of `SPEC_H.md`. "Order of work"
    # step 7: "A mismatch stops the study before second-half pairing and is reported under step
    # 4", and step 4 commits the first half's check counts either way. So neither stage refuses a
    # table because of the *other* half's counts: with the second half one session short, the
    # first half runs through and only the second half is stopped.
    signal, outcome = tables.write_tables(
        tmp_path / "tables", tables.both_halves_short("discovery")
    )
    out_dir = tmp_path / "out"
    out_dir.mkdir(parents=True)

    assert pipeline.stage_one(signal, outcome, "confirmation", out_dir) == 0
    first_checks = out_dir / "checks_confirmation.json"
    assert first_checks.is_file()
    assert pipeline.stage_two(signal, outcome, "confirmation", out_dir, first_checks) == 0
    assert (out_dir / "result_confirmation.json").is_file()

    assert pipeline.stage_one(signal, outcome, "discovery", out_dir) == 3
    second_checks = out_dir / "checks_discovery.json"
    assert second_checks.is_file()
    assert pipeline.read_json(second_checks)["all_same"] is False
    _ = capsys.readouterr()

    assert pipeline.stage_two(signal, outcome, "discovery", out_dir, second_checks) == 3
    assert capsys.readouterr().err == "checks-refused\n"
    assert not (out_dir / "result_discovery.json").exists()


@pytest.mark.parametrize("stage", ["1", "2"])
def test_a_broken_table_exits_two(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], stage: str
) -> None:
    signal, outcome = _write(tmp_path, GOOD + "\textra\n")
    checks = tmp_path / "checks_confirmation.json"
    _ = checks.write_text("{}", encoding="utf-8")
    code = analyze.main(
        [
            "--stage",
            stage,
            "--signal",
            str(signal),
            "--outcome",
            str(outcome),
            "--half",
            "confirmation",
            "--out-dir",
            str(tmp_path),
            "--checks",
            str(checks),
            "--registration-commit",
            "a" * 40,
            "--record-commit",
            "b" * 40,
            "--first-run",
        ]
    )
    # Stage 2 refuses on the checks file before it reads a table; stage 1 names the table.
    assert code in {2, 3}
    captured = capsys.readouterr()
    assert captured.err.strip() in {"table-invalid", "checks-refused"}
    assert captured.out == ""
    assert not (tmp_path / "result_confirmation.json").exists()
