"""Step 6: every figure on the published page is re-derived from the files beside it.

The published folder is `docs/results/log-signals-study/`. It holds `README.md` (the page),
`status.json`, `checks_confirmation.json`, and when they exist `result_confirmation.json`,
`result_confirmation.second.json`, `checks_discovery.json`, `result_discovery.json` and
`result_discovery.second.json`. While it does not exist this file is skipped; the same checks run
on a folder this file builds from synthetic tables, so they are exercised now.

The page is re-derived from the folder and must equal `README.md` byte for byte, every result
file must pass `check_result.check`, a second run's file must equal the first's bytes unless the
page lists the difference, and every digit sequence on the page outside the fixed texts must come
from a result file or from a checks file.

The fixed texts are stripped as exact strings first: decision D leaves no blanket allowance of
small numbers. They are the registration's own texts (its title, notice, headline segments,
yardstick, limits, facts, failed-condition lines, the sign count's own words, the step label of
the date-miss note and its sentence) and the numbering this module generates for the limits.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

from bench.logsignals import check_result, render
from tests.unit.logsignals import pipeline, tables

PUBLISHED = Path(render.__file__).parents[2] / "docs" / "results" / "log-signals-study"
NOT_PUBLISHED_YET = "the result is not published yet"

_FIGURE_RE = re.compile(r"[+-]?[0-9]+(?:,[0-9]{3})*(?:\.[0-9]+)?%?")
_PLACEHOLDER_RE = re.compile(r"\[[^\]]*\]%?")
# The registration's own words in the sign count, which carry three zeros.
SIGN_COUNT_WORDS: tuple[str, ...] = (
    " repositories above 0, ",
    " below 0, ",
    " exactly 0; those above 0 carry ",
)


def _figures(text: str) -> set[str]:
    return set(_FIGURE_RE.findall(text))


def _segments(sentence: str) -> list[str]:
    """The fixed segments of a sentence with filled brackets, the brackets left out."""
    return [part for part in _PLACEHOLDER_RE.split(sentence) if part]


def _fixed_texts() -> list[str]:
    """Every text the page copies from the registration, and the numbering it generates.

    Longest first, so no text hides another.
    """
    texts = [
        render.TITLE,
        render.NOTICE,
        render.YARDSTICK_CAPTION,
        render.YARDSTICK_WARNING,
        render.YARDSTICK_TABLE,
        render.YARDSTICK_NOTE,
        render.STOPPED_SENTENCE,
        *render.GENERAL_LIMITS,
        *render.FACTS["confirmation"],
        *render.FACTS["discovery"],
        *_segments(render.HEADLINE),
        *_segments(render.LOO_FORMED),
        render.LOO_NOT_FORMED,
        *SIGN_COUNT_WORDS,
        *(
            render.failed_condition_line(number, half)
            for half in render.HALF_LABELS
            for number in range(1, len(render.CONDITIONS) + 1)
        ),
        *(render.LAST_STEP_LINE.format(number=number) for number in render.STEPS),
        # The numbering of the general limits is this module's own structure. It is stripped with
        # the newline that carries it, so that a figure followed by ". " inside a sentence is
        # never taken for a list number.
        *(f"\n{index}. " for index in range(1, len(render.GENERAL_LIMITS) + 1)),
    ]
    # Only a text that carries a digit can hide a figure, and a text that carries none must stay
    # where it is: a lone "." is one of the headline's own segments.
    digit_bearing = [text for text in texts if any(letter.isdigit() for letter in text)]
    return sorted(digit_bearing, key=len, reverse=True)


def _figures_outside_the_fixed_texts(page: str) -> set[str]:
    """Every digit sequence the page carries outside the fixed texts.

    Each fixed text leaves a space behind, so two figures that stood on either side of one are
    not read as a single longer figure.
    """
    stripped = page
    for fixed in _fixed_texts():
        stripped = stripped.replace(fixed, " ")
    return _figures(stripped)


def _allowed_figures(folder: Path) -> set[str]:
    """Every digit sequence the result files and the checks files of a folder carry."""
    allowed: set[str] = set()
    for name in (
        *render.RESULT_NAMES.values(),
        *render.SECOND_RESULT_NAMES.values(),
        *render.CHECKS_NAMES.values(),
    ):
        path = folder / name
        if path.is_file():
            allowed |= _figures(path.read_text(encoding="utf-8"))
    return allowed


def _rederive(folder: Path, out: Path) -> str:
    assert render.main(["--dir", str(folder), "--out", str(out)]) == 0
    return out.read_text(encoding="utf-8")


def _check_the_folder(folder: Path, tmp_path: Path) -> str:
    """The checks of step 6 on one published folder. Returns the page."""
    page = (folder / render.PAGE_NAME).read_bytes()
    rewritten = tmp_path / "rederived.md"
    text = _rederive(folder, rewritten)
    assert rewritten.read_bytes() == page

    for half, name in render.RESULT_NAMES.items():
        path = folder / name
        if not path.is_file():
            continue
        checks_path = folder / render.CHECKS_NAMES[half]
        checks: Any | None = (
            json.loads(checks_path.read_text(encoding="utf-8")) if checks_path.is_file() else None
        )
        for candidate in (path, folder / render.SECOND_RESULT_NAMES[half]):
            if not candidate.is_file():
                continue
            result: Any = json.loads(candidate.read_text(encoding="utf-8"))
            check_result.check(result, checks)
        second = folder / render.SECOND_RESULT_NAMES[half]
        if second.is_file() and second.read_bytes() != path.read_bytes():
            # Step 5: the two runs differ, so the page carries the difference.
            assert "### The two runs" in text
        elif second.is_file():
            assert second.read_bytes() == path.read_bytes()

    assert _figures_outside_the_fixed_texts(text) <= _allowed_figures(folder)
    return text


# --- the folder this file builds itself ---------------------------------------


def _status_text(
    *,
    notice_only: bool = False,
    failed_condition: dict[str, Any] | None = None,
    stopped_after_step: int | None = None,
) -> str:
    conditions = {"confirmation": None, "discovery": None}
    if failed_condition is not None:
        conditions.update(failed_condition)
    return (
        json.dumps(
            {
                "notice_only": notice_only,
                "failed_condition": conditions,
                "stopped_after_step": stopped_after_step,
            },
            indent=2,
        )
        + "\n"
    )


def _status(folder: Path, text: str) -> None:
    path = folder / render.STATUS_NAME
    path.unlink(missing_ok=True)
    _ = path.write_text(text, encoding="utf-8")


def _build_folder(
    tmp_path: Path, *, halves: tuple[str, ...] = ("confirmation", "discovery")
) -> Path:
    """A published folder from synthetic tables: both stages, then the page."""
    rows = tables.both_halves()
    signal, outcome = tables.write_tables(tmp_path / "tables", rows)
    out_dir = tmp_path / "out"
    out_dir.mkdir(parents=True)
    folder = tmp_path / "published"
    folder.mkdir()
    for half in halves:
        assert pipeline.stage_one(signal, outcome, half, out_dir) == 0
        checks = out_dir / f"checks_{half}.json"
        assert pipeline.stage_two(signal, outcome, half, out_dir, checks) == 0
        _ = (folder / render.CHECKS_NAMES[half]).write_text(
            checks.read_text(encoding="utf-8"), encoding="utf-8"
        )
        _ = (folder / render.RESULT_NAMES[half]).write_text(
            (out_dir / f"result_{half}.json").read_text(encoding="utf-8"), encoding="utf-8"
        )
    _status(folder, _status_text())
    _ = _rederive(folder, folder / render.PAGE_NAME)
    return folder


def test_the_checks_hold_on_a_folder_built_from_synthetic_tables(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    folder = _build_folder(tmp_path)
    _ = capsys.readouterr()
    text = _check_the_folder(folder, tmp_path)
    assert render.SECOND_HALF_LABEL in text
    assert tables.CANARY not in text


def test_the_checks_hold_on_a_folder_of_the_first_half_alone(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    folder = _build_folder(tmp_path, halves=("confirmation",))
    _ = capsys.readouterr()
    text = _check_the_folder(folder, tmp_path)
    assert render.SECOND_HALF_LABEL not in text


def test_a_figure_the_files_do_not_carry_fails_the_check(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # The check is not vacuous: one number added to the page is caught.
    folder = _build_folder(tmp_path, halves=("confirmation",))
    _ = capsys.readouterr()
    page = folder / render.PAGE_NAME
    _ = page.write_text(
        page.read_text(encoding="utf-8") + "\nThe weight of the largest repository was 71.\n",
        encoding="utf-8",
    )
    text = page.read_text(encoding="utf-8")
    assert not _figures_outside_the_fixed_texts(text) <= _allowed_figures(folder)


def test_a_small_stray_number_fails_the_check(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Decision D (MINOR 2): the blanket allowance of 0 to 10 is gone, so a stray small number is
    # caught too.
    folder = _build_folder(tmp_path, halves=("confirmation",))
    _ = capsys.readouterr()
    page = folder / render.PAGE_NAME
    allowed = _allowed_figures(folder)
    stray = next(str(number) for number in range(11) if str(number) not in allowed)
    _ = page.write_text(
        page.read_text(encoding="utf-8") + f"\nRepositories left out: {stray}.\n",
        encoding="utf-8",
    )
    text = page.read_text(encoding="utf-8")
    assert not _figures_outside_the_fixed_texts(text) <= allowed


def test_a_folder_of_a_half_that_failed_its_checks_gives_the_step_four_page(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    signal, outcome = tables.write_tables(
        tmp_path / "tables", tables.both_halves_short("confirmation")
    )
    out_dir = tmp_path / "out"
    out_dir.mkdir(parents=True)
    assert pipeline.stage_one(signal, outcome, "confirmation", out_dir) == 3
    folder = tmp_path / "published"
    folder.mkdir()
    _ = (folder / render.CHECKS_NAMES["confirmation"]).write_text(
        (out_dir / "checks_confirmation.json").read_text(encoding="utf-8"), encoding="utf-8"
    )
    _status(folder, _status_text())
    _ = _rederive(folder, folder / render.PAGE_NAME)
    _ = capsys.readouterr()

    text = _check_the_folder(folder, tmp_path)
    assert render.failed_condition_line(2, "confirmation") in text
    assert render.YARDSTICK_TABLE not in text


def test_a_folder_whose_checks_hold_a_month_outside_the_six_is_re_derived(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # MAJOR 2 of review 3: stage 1 writes such a checks file itself, so step 6 must accept the
    # step 4 page written from it.
    rows = tables.both_halves()
    moved = [tables.with_month(rows[0], "2026-03"), *rows[1:]]
    signal, outcome = tables.write_tables(tmp_path / "tables", moved)
    out_dir = tmp_path / "out"
    out_dir.mkdir(parents=True)
    assert pipeline.stage_one(signal, outcome, "confirmation", out_dir) == 3
    folder = tmp_path / "published"
    folder.mkdir()
    _ = (folder / render.CHECKS_NAMES["confirmation"]).write_text(
        (out_dir / "checks_confirmation.json").read_text(encoding="utf-8"), encoding="utf-8"
    )
    _status(folder, _status_text())
    _ = _rederive(folder, folder / render.PAGE_NAME)
    _ = capsys.readouterr()

    text = _check_the_folder(folder, tmp_path)
    assert render.failed_condition_line(2, "confirmation") in text
    assert "| `month_2026-03` | 1 | 0 | different |" in text
    assert render.YARDSTICK_TABLE not in text
    assert tables.CANARY not in text


def test_a_folder_whose_status_says_notice_only_gives_the_notice(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    folder = _build_folder(tmp_path, halves=("confirmation",))
    # Point 4 of this round: a privacy failure publishes no numeric file, so the folder holds
    # the page and the status file only.
    for name in (*render.CHECKS_NAMES.values(), *render.RESULT_NAMES.values()):
        (folder / name).unlink(missing_ok=True)
    _status(folder, _status_text(notice_only=True))
    (folder / render.PAGE_NAME).unlink()
    _ = _rederive(folder, folder / render.PAGE_NAME)
    _ = capsys.readouterr()

    text = _check_the_folder(folder, tmp_path)
    assert text == f"{render.TITLE}\n\n{render.NOTICE}\n"
    assert not any(character.isdigit() for character in text)


def test_a_notice_only_folder_that_holds_a_numeric_file_is_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Point 4 of this round: `render.py --dir` refuses such a folder and writes nothing, and the
    # re-derivation of step 6 fails on it.
    names = (render.CHECKS_NAMES["confirmation"], render.RESULT_NAMES["confirmation"])
    for index, name in enumerate(names):
        folder = _build_folder(tmp_path / f"case-{index}", halves=("confirmation",))
        for other in names:
            if other != name:
                (folder / other).unlink(missing_ok=True)
        _status(folder, _status_text(notice_only=True))
        _ = capsys.readouterr()

        out = tmp_path / f"page-{index}.md"
        assert render.main(["--dir", str(folder), "--out", str(out)]) == 4
        assert capsys.readouterr().err == "notice-only-folder\n"
        assert not out.exists()
        # Step 6 cannot re-derive such a folder either.
        with pytest.raises(AssertionError):
            _ = _check_the_folder(folder, tmp_path / f"out-{index}")
        _ = capsys.readouterr()


def test_a_status_file_that_is_not_one_refuses(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    folder = _build_folder(tmp_path, halves=("confirmation",))
    _ = capsys.readouterr()
    for index, status in enumerate(
        (
            {"notice_only": False},
            {"notice_only": False, "failed_condition": {"confirmation": None, "discovery": None}},
            {
                "notice_only": "no",
                "failed_condition": {"confirmation": None, "discovery": None},
                "stopped_after_step": None,
            },
            {
                "notice_only": False,
                "failed_condition": {"confirmation": 5, "discovery": None},
                "stopped_after_step": None,
            },
            {
                "notice_only": False,
                "failed_condition": {"confirmation": None},
                "stopped_after_step": None,
            },
            {
                "notice_only": False,
                "failed_condition": {"confirmation": None, "discovery": None},
                "stopped_after_step": 8,
            },
            {
                "notice_only": False,
                "failed_condition": {"confirmation": None, "discovery": None},
                "stopped_after_step": "3",
            },
            # MINOR 10 of review 3: a condition number is an integer, not a digit string and not
            # a boolean.
            {
                "notice_only": False,
                "failed_condition": {"confirmation": "2", "discovery": None},
                "stopped_after_step": None,
            },
            {
                "notice_only": False,
                "failed_condition": {"confirmation": True, "discovery": None},
                "stopped_after_step": None,
            },
            {
                "notice_only": False,
                "failed_condition": {"confirmation": None, "discovery": None},
                "stopped_after_step": True,
            },
        )
    ):
        _status(folder, json.dumps(status, indent=2) + "\n")
        out = tmp_path / f"page-{index}.md"
        assert render.main(["--dir", str(folder), "--out", str(out)]) == 2
        assert capsys.readouterr().err == "arguments-invalid\n"
        assert not out.exists()


# --- the date-miss note and the two runs of step 5 ----------------------------


def test_a_folder_of_a_passing_checks_file_without_a_result_is_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Decision G: without `stopped_after_step` this folder is still refused, because step 4 is
    # reached only by a difference.
    folder = _build_folder(tmp_path, halves=("confirmation",))
    _ = capsys.readouterr()
    (folder / render.RESULT_NAMES["confirmation"]).unlink()
    out = tmp_path / "page.md"
    assert render.main(["--dir", str(folder), "--out", str(out)]) == 2
    assert capsys.readouterr().err == "result-invalid\n"
    assert not out.exists()


def test_a_folder_that_stopped_at_its_date_gives_the_note(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Decision G (MINOR 6): the note of "Order of work", on exactly the folder the registration
    # describes: a committed checks file whose checks matched, and no result file.
    folder = _build_folder(tmp_path, halves=("confirmation",))
    _ = capsys.readouterr()
    (folder / render.RESULT_NAMES["confirmation"]).unlink()
    (folder / render.PAGE_NAME).unlink()
    _status(folder, _status_text(stopped_after_step=4))
    _ = _rederive(folder, folder / render.PAGE_NAME)
    _ = capsys.readouterr()

    text = _check_the_folder(folder, tmp_path)
    assert "Last step completed: 4." in text
    assert text.rstrip("\n").endswith(render.STOPPED_SENTENCE)
    assert "### Printed as checks" in text
    assert "### Printed numbers" not in text
    assert tables.CANARY not in text


def test_a_folder_that_stopped_after_a_result_prints_it_with_the_limits(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # MINOR 1 of review 3: "the check counts already committed, as the page prints them; for a
    # result file already committed, what the page carries for that half" is read as exactly
    # what the ordinary page prints for those files, so the result comes with the limits, the
    # yardstick table and the half's facts, as the registration prints them "with the result".
    folder = _build_folder(tmp_path, halves=("confirmation",))
    _ = capsys.readouterr()
    ordinary = (folder / render.PAGE_NAME).read_text(encoding="utf-8")
    (folder / render.PAGE_NAME).unlink()
    _status(folder, _status_text(stopped_after_step=5))
    _ = _rederive(folder, folder / render.PAGE_NAME)
    _ = capsys.readouterr()

    text = _check_the_folder(folder, tmp_path)
    assert "Last step completed: 5." in text
    assert text.rstrip("\n").endswith(render.STOPPED_SENTENCE)
    assert render.YARDSTICK_TABLE in text
    for limit in render.GENERAL_LIMITS:
        assert limit in text
    for fact in render.FACTS["confirmation"]:
        assert fact in text
    assert ordinary[len(render.TITLE) :].rstrip("\n") in text
    assert tables.CANARY not in text


def test_a_second_run_whose_bytes_are_equal_changes_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Decision H: the two runs of step 5 agreed, so the page is the one the first run gives.
    folder = _build_folder(tmp_path, halves=("confirmation",))
    _ = capsys.readouterr()
    first = folder / render.RESULT_NAMES["confirmation"]
    _ = (folder / render.SECOND_RESULT_NAMES["confirmation"]).write_text(
        first.read_text(encoding="utf-8"), encoding="utf-8"
    )
    before = (folder / render.PAGE_NAME).read_bytes()
    text = _check_the_folder(folder, tmp_path)
    assert (folder / render.PAGE_NAME).read_bytes() == before
    assert "### The two runs" not in text


def test_a_second_run_that_differs_is_listed_under_condition_four(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Decision H: the difference is printed with both values, the half is "not an answer" under
    # condition 4, and the first run's numbers are the ones printed.
    folder = _build_folder(tmp_path, halves=("confirmation",))
    _ = capsys.readouterr()
    first = folder / render.RESULT_NAMES["confirmation"]
    second = json.loads(first.read_text(encoding="utf-8"))
    second["measures"]["reasoning_tokens"]["repository_month"]["rho_bar"] = "+0.123"
    _ = (folder / render.SECOND_RESULT_NAMES["confirmation"]).write_text(
        json.dumps(second, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    # The status file must carry condition 4 for that half.
    out = tmp_path / "page.md"
    assert render.main(["--dir", str(folder), "--out", str(out)]) == 2
    assert capsys.readouterr().err == "result-invalid\n"
    assert not out.exists()

    _status(folder, _status_text(failed_condition={"confirmation": 4}))
    (folder / render.PAGE_NAME).unlink()
    _ = _rederive(folder, folder / render.PAGE_NAME)
    _ = capsys.readouterr()

    text = _check_the_folder(folder, tmp_path)
    assert f"**{render.NOT_AN_ANSWER}**" in text
    assert render.failed_condition_line(4, "confirmation") in text
    assert "- `measures.reasoning_tokens.repository_month.rho_bar`: first run " in text
    assert "+0.123" in text
    first_value = json.loads(first.read_text(encoding="utf-8"))
    printed = first_value["measures"]["no_reasoning_share"]["repository"]["rho_bar"]
    assert f"`rho_bar` {printed};" in text


def test_the_published_page_is_re_derived_from_the_files_beside_it(tmp_path: Path) -> None:
    if not PUBLISHED.is_dir():
        pytest.skip(NOT_PUBLISHED_YET)
    _ = _check_the_folder(PUBLISHED, tmp_path)
