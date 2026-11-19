"""Running the two stages over a synthetic pair of tables."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from bench.logsignals import analyze
from tests.unit.logsignals import tables

REGISTRATION_COMMIT = "0" * 39 + "1"
RECORD_COMMIT = "0" * 39 + "2"
# Only for the tests that call `printed_result` directly. Stage 2 takes no start time from its
# caller: `--first-run` stamps the clock and `--second-run-of FILE` takes that run's stamp.
START_TIME = "2026-11-19T14:35:07+00:00"


def provenance(start_time: str = START_TIME) -> dict[str, str]:
    """The provenance a result file carries, for the tests that call `printed_result` directly."""
    return {
        "registration_commit": "a" * 40,
        "record_commit": "b" * 40,
        "analyze_sha256": "c" * 64,
        "signal_sha256": "d" * 64,
        "outcome_sha256": "e" * 64,
        "start_time": start_time,
    }


def stage_one(signal: Path, outcome: Path, half: str, out_dir: Path) -> int:
    return analyze.main(
        [
            "--stage",
            "1",
            "--signal",
            str(signal),
            "--outcome",
            str(outcome),
            "--half",
            half,
            "--out-dir",
            str(out_dir),
        ]
    )


def stage_two(
    signal: Path,
    outcome: Path,
    half: str,
    out_dir: Path,
    checks: Path,
    *,
    registration_commit: str = REGISTRATION_COMMIT,
    record_commit: str = RECORD_COMMIT,
    first_run: bool = True,
    second_run_of: Path | None = None,
) -> int:
    """One execution of stage 2 through the real command line.

    Exactly one of the two flags is passed: by default `--first-run`, which stamps the clock, so
    no test injects a fixed time.
    """
    arguments = [
        "--stage",
        "2",
        "--signal",
        str(signal),
        "--outcome",
        str(outcome),
        "--half",
        half,
        "--out-dir",
        str(out_dir),
        "--checks",
        str(checks),
        "--registration-commit",
        registration_commit,
        "--record-commit",
        record_commit,
    ]
    if first_run:
        arguments.append("--first-run")
    if second_run_of is not None:
        arguments.extend(["--second-run-of", str(second_run_of)])
    return analyze.main(arguments)


def run_both_stages(
    directory: Path,
    half: str = "confirmation",
    sessions: Sequence[tables.Session] | None = None,
) -> tuple[Path, Path, Path]:
    """Returns (signal, outcome, out_dir) after stage 1 and stage 2 have both run."""
    rows = tables.both_halves() if sessions is None else list(sessions)
    signal, outcome = tables.write_tables(directory / "tables", rows)
    out_dir = directory / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    assert stage_one(signal, outcome, half, out_dir) == 0
    assert stage_two(signal, outcome, half, out_dir, out_dir / f"checks_{half}.json") == 0
    return signal, outcome, out_dir


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))
