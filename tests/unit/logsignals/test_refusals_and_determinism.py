"""Stage 2 refuses what the registration forbids, and gives the same bytes twice."""

from __future__ import annotations

import json
import random
import stat
from pathlib import Path

import pytest

from bench.logsignals import analyze
from tests.unit.logsignals import pipeline, tables


def _tables(tmp_path: Path) -> tuple[Path, Path]:
    return tables.write_tables(tmp_path / "tables", tables.both_halves())


def _checks(signal: Path, outcome: Path, out_dir: Path, half: str = "confirmation") -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    assert pipeline.stage_one(signal, outcome, half, out_dir) == 0
    return out_dir / f"checks_{half}.json"


def test_the_result_holds_the_printed_forms_and_the_provenance(tmp_path: Path) -> None:
    signal, outcome, out_dir = pipeline.run_both_stages(tmp_path)
    result = pipeline.read_json(out_dir / "result_confirmation.json")
    assert result["half"] == "confirmation"
    assert result["sessions"] == 423
    assert result["repositories"] == 33
    assert result["provenance"]["registration_commit"] == pipeline.REGISTRATION_COMMIT
    assert result["provenance"]["record_commit"] == pipeline.RECORD_COMMIT
    assert result["provenance"]["analyze_sha256"] == analyze.digest_of(Path(analyze.__file__))
    assert result["provenance"]["signal_sha256"] == analyze.digest_of(signal)
    assert result["provenance"]["outcome_sha256"] == analyze.digest_of(outcome)
    assert stat.S_IMODE((out_dir / "result_confirmation.json").stat().st_mode) == 0o600

    # The result file itself records the start time, as the registration says (decision 6), and
    # there is no companion file.
    assert analyze.START_TIME_RE.match(str(result["provenance"]["start_time"])) is not None
    assert not (out_dir / "result_confirmation.run.json").exists()


def test_the_first_run_stamps_the_clock_itself(tmp_path: Path) -> None:
    # Decision A: `--first-run` takes the time; no caller passes one in.
    signal, outcome = _tables(tmp_path)
    out_dir = tmp_path / "out"
    checks = _checks(signal, outcome, out_dir)
    before = analyze.started_now()
    assert pipeline.stage_two(signal, outcome, "confirmation", out_dir, checks) == 0
    after = analyze.started_now()
    written = str(
        pipeline.read_json(out_dir / "result_confirmation.json")["provenance"]["start_time"]
    )
    assert analyze.START_TIME_RE.match(written) is not None
    assert before <= written <= after


def test_stage_two_needs_exactly_one_of_the_two_run_flags(tmp_path: Path) -> None:
    # Decision A: neither flag and both flags are refused, so no run can start without saying
    # which of the two it is.
    signal, outcome = _tables(tmp_path)
    out_dir = tmp_path / "out"
    checks = _checks(signal, outcome, out_dir)
    first = tmp_path / "first"
    first.mkdir()
    assert pipeline.stage_two(signal, outcome, "confirmation", first, checks) == 0
    result = first / "result_confirmation.json"

    assert (
        pipeline.stage_two(signal, outcome, "confirmation", out_dir, checks, first_run=False) == 2
    )
    assert (
        pipeline.stage_two(
            signal, outcome, "confirmation", out_dir, checks, first_run=True, second_run_of=result
        )
        == 2
    )
    assert not (out_dir / "result_confirmation.json").exists()


def test_the_second_run_refuses_a_file_without_a_registered_start_time(tmp_path: Path) -> None:
    # Decision A: only `provenance.start_time` is read from the first run's file, and only in the
    # registered form.
    signal, outcome = _tables(tmp_path)
    out_dir = tmp_path / "out"
    checks = _checks(signal, outcome, out_dir)
    first = tmp_path / "first"
    first.mkdir()
    assert pipeline.stage_two(signal, outcome, "confirmation", first, checks) == 0
    honest = pipeline.read_json(first / "result_confirmation.json")

    for index, value in enumerate(
        ("2026-11-19T14:35:07.123456+00:00", "2026-11-19T14:35:07Z", "yesterday", 7, None)
    ):
        doctored = json.loads(json.dumps(honest))
        doctored["provenance"]["start_time"] = value
        path = tmp_path / f"doctored-{index}.json"
        _ = path.write_text(json.dumps(doctored), encoding="utf-8")
        assert (
            pipeline.stage_two(
                signal,
                outcome,
                "confirmation",
                out_dir,
                checks,
                first_run=False,
                second_run_of=path,
            )
            == 2
        )
    assert (
        pipeline.stage_two(
            signal,
            outcome,
            "confirmation",
            out_dir,
            checks,
            first_run=False,
            second_run_of=tmp_path / "absent.json",
        )
        == 2
    )
    assert not (out_dir / "result_confirmation.json").exists()


def test_the_second_run_refuses_the_first_runs_own_folder(tmp_path: Path) -> None:
    # Decision A: the output folder must differ from the first run's folder, so the second run
    # cannot be the same file read back.
    signal, outcome = _tables(tmp_path)
    out_dir = tmp_path / "out"
    checks = _checks(signal, outcome, out_dir)
    assert pipeline.stage_two(signal, outcome, "confirmation", out_dir, checks) == 0
    result = out_dir / "result_confirmation.json"
    before = result.read_bytes()
    assert (
        pipeline.stage_two(
            signal,
            outcome,
            "confirmation",
            out_dir,
            checks,
            first_run=False,
            second_run_of=result,
        )
        == 2
    )
    assert result.read_bytes() == before


def test_the_result_holds_nothing_per_session_or_per_repository(tmp_path: Path) -> None:
    _signal, _outcome, out_dir = pipeline.run_both_stages(tmp_path)
    result = pipeline.read_json(out_dir / "result_confirmation.json")
    text = json.dumps(result)
    assert "transcripts0" not in text
    assert tables.CANARY not in text
    for measure in analyze.MEASURES:
        for definition in analyze.DEFINITIONS:
            block = result["measures"][measure][definition]
            assert set(block) == {"rho_bar", "m", "W", "sessions"}


def test_stage_two_refuses_without_a_passing_checks_file(tmp_path: Path) -> None:
    signal, outcome = _tables(tmp_path)
    out_dir = tmp_path / "out"
    checks = _checks(signal, outcome, out_dir)

    broken = json.loads(checks.read_text(encoding="utf-8"))
    broken["all_same"] = False
    failing = tmp_path / "failing.json"
    _ = failing.write_text(json.dumps(broken), encoding="utf-8")
    assert pipeline.stage_two(signal, outcome, "confirmation", out_dir, failing) == 3
    assert not (out_dir / "result_confirmation.json").exists()

    assert pipeline.stage_two(signal, outcome, "confirmation", out_dir, tmp_path / "absent") == 3
    nonsense = tmp_path / "nonsense.json"
    _ = nonsense.write_text("[]", encoding="utf-8")
    assert pipeline.stage_two(signal, outcome, "confirmation", out_dir, nonsense) == 3
    assert not (out_dir / "result_confirmation.json").exists()


def test_stage_two_does_not_trust_the_all_same_flag(tmp_path: Path) -> None:
    # Decision 2 (finding 2): every entry of the file's own list is read, so flipping the flag
    # over a failing run no longer lets stage 2 run.
    sessions = tables.both_halves()
    short = [session for session in sessions if session.half == "discovery"] + [
        session for session in sessions if session.half == "confirmation"
    ][:-1]
    signal, outcome = tables.write_tables(tmp_path / "tables", short)
    out_dir = tmp_path / "out"
    out_dir.mkdir(parents=True)
    assert pipeline.stage_one(signal, outcome, "confirmation", out_dir) == 3

    checks = out_dir / "checks_confirmation.json"
    recorded = json.loads(checks.read_text(encoding="utf-8"))
    assert recorded["all_same"] is False
    recorded["all_same"] = True
    flipped = tmp_path / "flipped.json"
    _ = flipped.write_text(json.dumps(recorded), encoding="utf-8")
    assert pipeline.stage_two(signal, outcome, "confirmation", out_dir, flipped) == 3
    assert not (out_dir / "result_confirmation.json").exists()


def test_stage_two_refuses_a_checks_file_whose_own_entries_were_doctored(tmp_path: Path) -> None:
    # Decision 2: the recorded `found` and `registered` figures of every entry must agree with
    # each other and with the figures this registration fixes.
    signal, outcome = _tables(tmp_path)
    out_dir = tmp_path / "out"
    checks = _checks(signal, outcome, out_dir)
    honest = json.loads(checks.read_text(encoding="utf-8"))

    for index, change in enumerate(
        (
            {"found": 999},
            {"registered": 999},
            {"verdict": "different"},
            {"name": "sessions_renamed"},
        )
    ):
        doctored = json.loads(json.dumps(honest))
        doctored["checks"][0].update(change)
        path = tmp_path / f"doctored-{index}.json"
        _ = path.write_text(json.dumps(doctored), encoding="utf-8")
        assert pipeline.stage_two(signal, outcome, "confirmation", out_dir, path) == 3

    # A check the file leaves out is a refusal too.
    dropped = json.loads(json.dumps(honest))
    del dropped["checks"][0]
    path = tmp_path / "dropped.json"
    _ = path.write_text(json.dumps(dropped), encoding="utf-8")
    assert pipeline.stage_two(signal, outcome, "confirmation", out_dir, path) == 3
    assert not (out_dir / "result_confirmation.json").exists()


def test_stage_two_refuses_a_checks_file_whose_also_printed_was_doctored(tmp_path: Path) -> None:
    # Decision C (MAJOR 3): the two counts the registration names beside the checks are compared
    # with the recount's own, so neither can be invented.
    signal, outcome = _tables(tmp_path)
    out_dir = tmp_path / "out"
    checks = _checks(signal, outcome, out_dir)
    honest = json.loads(checks.read_text(encoding="utf-8"))
    assert honest["also_printed"] == {"month_unknown": 0, "model_unknown": 0}

    for index, change in enumerate(
        ({"month_unknown": 999}, {"model_unknown": 7777}, {"invented": 1})
    ):
        doctored = json.loads(json.dumps(honest))
        doctored["also_printed"].update(change)
        path = tmp_path / f"also-{index}.json"
        _ = path.write_text(json.dumps(doctored), encoding="utf-8")
        assert pipeline.stage_two(signal, outcome, "confirmation", out_dir, path) == 3
    dropped = json.loads(json.dumps(honest))
    del dropped["also_printed"]
    path = tmp_path / "also-dropped.json"
    _ = path.write_text(json.dumps(dropped), encoding="utf-8")
    assert pipeline.stage_two(signal, outcome, "confirmation", out_dir, path) == 3
    assert not (out_dir / "result_confirmation.json").exists()


def test_stage_two_recomputes_the_check_counts_itself(tmp_path: Path) -> None:
    # Decision 2: stage 2 recounts stage 1's figures from the two tables and refuses unless
    # they equal the registered ones, so an honest checks file over other tables is not enough.
    signal, outcome = _tables(tmp_path)
    out_dir = tmp_path / "out"
    checks = _checks(signal, outcome, out_dir)

    # The same tables with one month moved: the digests still match, the counts no longer do.
    sessions = tables.both_halves()
    moved = [tables.with_month(sessions[0], "2026-09"), *sessions[1:]]
    other = tmp_path / "moved"
    signal_b, outcome_b = tables.write_tables(other / "tables", moved)
    recorded = json.loads(checks.read_text(encoding="utf-8"))
    recorded["signal_sha256"] = analyze.digest_of(signal_b)
    recorded["outcome_sha256"] = analyze.digest_of(outcome_b)
    path = tmp_path / "matching-digests.json"
    _ = path.write_text(json.dumps(recorded), encoding="utf-8")
    (other / "out").mkdir(parents=True)
    assert pipeline.stage_two(signal_b, outcome_b, "confirmation", other / "out", path) == 3
    assert not (other / "out" / "result_confirmation.json").exists()


def test_stage_two_refuses_a_checks_file_of_the_other_half(tmp_path: Path) -> None:
    signal, outcome = _tables(tmp_path)
    out_dir = tmp_path / "out"
    checks = _checks(signal, outcome, out_dir, "discovery")
    assert pipeline.stage_two(signal, outcome, "confirmation", out_dir, checks) == 3
    assert not (out_dir / "result_confirmation.json").exists()


def test_stage_two_refuses_a_changed_input_table(tmp_path: Path) -> None:
    signal, outcome = _tables(tmp_path)
    out_dir = tmp_path / "out"
    checks = _checks(signal, outcome, out_dir)

    rows = signal.read_text(encoding="utf-8")
    _ = signal.write_text(rows.replace("\t20\t", "\t21\t", 1), encoding="utf-8")
    assert pipeline.stage_two(signal, outcome, "confirmation", out_dir, checks) == 3
    _ = signal.write_text(rows, encoding="utf-8")

    values = outcome.read_text(encoding="utf-8")
    _ = outcome.write_text(values.replace("\t0.0\n", "\t1.0\n", 1), encoding="utf-8")
    assert pipeline.stage_two(signal, outcome, "confirmation", out_dir, checks) == 3
    assert not (out_dir / "result_confirmation.json").exists()


def test_stage_two_refuses_an_existing_result(tmp_path: Path) -> None:
    signal, outcome, out_dir = pipeline.run_both_stages(tmp_path)
    before = (out_dir / "result_confirmation.json").read_bytes()
    assert (
        pipeline.stage_two(
            signal, outcome, "confirmation", out_dir, out_dir / "checks_confirmation.json"
        )
        == 2
    )
    assert (out_dir / "result_confirmation.json").read_bytes() == before


@pytest.mark.parametrize(
    ("registration", "record"),
    [("short", pipeline.RECORD_COMMIT), (pipeline.REGISTRATION_COMMIT, "NOTHEX")],
)
def test_stage_two_refuses_a_commit_that_is_not_a_digest(
    tmp_path: Path, registration: str, record: str
) -> None:
    signal, outcome = _tables(tmp_path)
    out_dir = tmp_path / "out"
    checks = _checks(signal, outcome, out_dir)
    assert (
        pipeline.stage_two(
            signal,
            outcome,
            "confirmation",
            out_dir,
            checks,
            registration_commit=registration,
            record_commit=record,
        )
        == 2
    )
    assert not (out_dir / "result_confirmation.json").exists()


def test_stage_two_without_its_arguments_refuses(tmp_path: Path) -> None:
    signal, outcome = _tables(tmp_path)
    assert (
        analyze.main(
            [
                "--stage",
                "2",
                "--signal",
                str(signal),
                "--outcome",
                str(outcome),
                "--half",
                "confirmation",
                "--out-dir",
                str(tmp_path),
            ]
        )
        == 2
    )
    assert not (tmp_path / "result_confirmation.json").exists()


def test_the_two_runs_of_step_five_give_the_same_bytes_with_no_time_injected(
    tmp_path: Path,
) -> None:
    # Decision A: the paired sequence of two executions through the real command line, the
    # second taking the first's stamp, gives byte-identical files with nothing passed in by hand.
    signal, outcome = _tables(tmp_path)
    first = tmp_path / "first"
    second = tmp_path / "second"
    checks = _checks(signal, outcome, first)
    assert pipeline.stage_two(signal, outcome, "confirmation", first, checks) == 0
    second.mkdir()
    assert (
        pipeline.stage_two(
            signal,
            outcome,
            "confirmation",
            second,
            checks,
            first_run=False,
            second_run_of=first / "result_confirmation.json",
        )
        == 0
    )
    assert (first / "result_confirmation.json").read_bytes() == (
        second / "result_confirmation.json"
    ).read_bytes()


def test_the_row_order_of_the_input_tables_changes_no_output(tmp_path: Path) -> None:
    sessions = tables.both_halves()
    shuffled = list(sessions)
    random.Random(20261119).shuffle(shuffled)
    assert [session.path for session in shuffled] != [session.path for session in sessions]

    plain = tmp_path / "plain"
    mixed = tmp_path / "mixed"
    signal_a, outcome_a = tables.write_tables(plain / "tables", sessions)
    # The outcome table is written in yet another order, and holds rows the half never reads.
    other_order = list(reversed(shuffled))
    signal_b = mixed / "tables" / "signal.tsv"
    outcome_b = mixed / "tables" / "outcome.tsv"
    (mixed / "tables").mkdir(parents=True)
    _ = signal_b.write_text(tables.signal_text(shuffled), encoding="utf-8")
    _ = outcome_b.write_text(tables.outcome_text(other_order), encoding="utf-8")

    checks_a = _checks(signal_a, outcome_a, plain / "out")
    checks_b = _checks(signal_b, outcome_b, mixed / "out")
    first = pipeline.read_json(checks_a)
    second = pipeline.read_json(checks_b)
    for found in (first, second):
        del found["signal_sha256"]
        del found["outcome_sha256"]
    assert first == second

    assert pipeline.stage_two(signal_a, outcome_a, "confirmation", plain / "out", checks_a) == 0
    assert pipeline.stage_two(signal_b, outcome_b, "confirmation", mixed / "out", checks_b) == 0
    result_a = pipeline.read_json(plain / "out" / "result_confirmation.json")
    result_b = pipeline.read_json(mixed / "out" / "result_confirmation.json")
    del result_a["provenance"]
    del result_b["provenance"]
    assert result_a == result_b
