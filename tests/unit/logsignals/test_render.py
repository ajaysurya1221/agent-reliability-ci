"""The result page: the registration's own words, and no figure of its own.

The fixed texts below are typed from `PREREGISTRATION-2.md` and never imported from the module
under test, so an edit to either copy fails this file.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

from bench.logsignals import analyze, render
from tests.unit.logsignals import pipeline, tables

TYPED_HEADLINE = (
    "In [N] Codex sessions from [R] repositories, inside the same repository, the weighted rank "
    "agreement between the share of responses whose recorded reasoning-token count is 0 and the "
    "share of changed lines attributed to the agent was **[X]** ([m] repositories carried "
    'weight, [W] units of weight). Inside repository-and-month blocks it was [Y, or the "not '
    'formed" form]. Inside repository, model-name and session-length blocks it was [Z, or the '
    '"not formed" form]. [a] of the [m] repositories had a number above 0, [b] below 0 and [c] '
    "exactly 0; those above 0 carry [S]% of the weight. Leaving out one repository at a time "
    "moves the first number between [lo] and [hi] (or: the leave-one-out range was not formed). "
    "No inferential test is applied to the paired data, because neither candidate test passed "
    "every required calibration case. This describes two records attached to the same session. "
    "It is not a cause, not a prediction, not a measure of quality, and it says nothing about "
    "order in time."
)
TYPED_CAPTION = (
    "**Yardstick table (simulated, not counted; fixed now; not recomputed, extended or trimmed "
    "after the result).**"
)
TYPED_WARNING = (
    "**Do not read significance from this table. Comparing the published number with these means "
    "or spreads is not a test and supports no statement that the number is, or is not, larger "
    "than chance.** The table shows only that the number moves by itself when no link is built "
    "in between a session's two numbers, and by how much in ten simulated cases. From the round "
    "3 reviewer's implementation unless marked."
)
TYPED_TABLE = (
    "| Simulated case | Mean of `rho_bar` | SD of `rho_bar` | Data sets |\n"
    "|---|---|---|---|\n"
    "| Sessions independent (round 2, three implementations) | +0.00 | 0.05 | 3,000 |\n"
    "| Moderate dependence in time (AR(1) 0.6) | +0.00 | 0.07 | 2,000 |\n"
    "| Strong dependence in time (AR(1) 0.9), round 2 | -0.00 | 0.11 | 1,000 |\n"
    "| Long constant runs, mean 15 sessions | -0.00 | 0.11 | 2,000 |\n"
    "| Calendar drift shared by all repositories, 0.3 of the variance | +0.00 | 0.07 | 2,000 |\n"
    "| The same at 0.6 of the variance | -0.01 | 0.17 | 2,000 |\n"
    "| One shared level per calendar month | -0.00 | 0.09 | 2,000 |\n"
    "| Every repository spread over the whole window, drift 0.3 | -0.01 | 0.19 | 1,000 |\n"
    "| One shared break date in each number, as coded | +0.02 | 0.06 | 2,000 |\n"
    "| One dated event that moves both numbers at once | +0.09 | 0.08 | 1,000 |"
)
TYPED_NOTE = (
    '"AR(1) 0.6" means each session\'s value leans on the one before it with weight 0.6. The '
    "rule applies to nine null cases of round 3. The first row is the round 2 run of one of them "
    "(independent sessions). The third row is a round 2 case that is not among the nine. The "
    "eighth and the tenth rows are round 3 cases outside the nine. The tenth is a shared cause, "
    "not a session-level link: one dated change that affects both records puts the number near "
    "+0.09. The ninth row is one of the nine, but it has a coding fault found in review (the "
    "break had a fixed direction in both numbers); it is kept because it was measured."
)
TYPED_LIMITS: tuple[str, ...] = (
    "The first number is a weighted average, and a few large repositories hold most of the "
    "possible weight (see the facts of each half). Realized contributing weights may differ from "
    "the possible weights.",
    "Most sessions sit at an outcome endpoint (see the facts of each half), so many sessions "
    "share the same outcome value.",
    "Many sessions carry no user id (see the facts of each half). Blocking by repository does "
    "not separate differences between people from the number.",
    "The halves are not independent: 7 user ids appear in both.",
    "All sessions fall between April and September 2026. A shared change over those months in "
    "both numbers moves the first number with no session-level link.",
    "The first measure's denominator is the session length. A pattern carried by length cannot "
    "be separated from it here.",
    "The population is conditional on the reader finding 20 countable responses: 855 of 1,444 "
    "Codex pool sessions.",
    "The size gate of the brief (at least 1,000 eligible sessions in at least 30 repositories, "
    "both tools together) passed with 1,171 sessions in 104 repositories. 316 of them are Claude "
    "Code sessions that are not analysed. The analysed Codex population is 855 sessions in 65 "
    "repositories. The gate is a floor for feasibility, not a statement of power.",
    "Each half's separate counts were inspected before the first registration was written, and "
    "more signal-side counts were made before this one (next section). The block definitions, "
    "the floors and the sentence were chosen knowing the first set. After the second set, two "
    "readings inside the third block definition were written down; nothing else in them was "
    "changed.",
    "The yardstick table is all that is known about how large this number gets with no "
    "session-level link, and it is simulated.",
)
TYPED_FACTS: dict[str, tuple[str, ...]] = {
    "confirmation": (
        "The four largest repositories hold a little over three fifths of the possible weight.",
        "307 of the 423 sessions sit at an outcome endpoint (79 at 0%, 228 at 100%).",
        "168 of the 423 sessions carry no user id. 11 repositories mix sessions with and without "
        "one and hold about seven tenths of the possible weight (whether the four largest "
        "repositories are among these 11 was not counted); 4 repositories have no identified "
        "user.",
        "No repository shows two or more identified user ids: 29 show one and 4 show none.",
        "The 7 shared user ids hold 62 of the 423 sessions, in 11 repositories (whether these "
        "are the 11 of the line above was not counted).",
    ),
    "discovery": (
        "The four largest repositories hold a little over three fifths of the possible weight.",
        "291 of the 432 sessions sit at an outcome endpoint (107 at 0%, 184 at 100%).",
        "101 of the 432 sessions carry no user id.",
        "Some of the 32 repositories show two or more identified user ids.",
        "The 7 shared user ids hold 80 of the 432 sessions, in 8 repositories.",
    ),
}


TYPED_README_SENTENCE = (
    "One study describes how a reasoning measure and an attribution share line up in public "
    "Codex sessions (`docs/results/log-signals-study/`). It is a description. It does not "
    "validate these measures against any outcome."
)
TYPED_CONDITIONS: tuple[str, ...] = (
    "The registration commit is an ancestor of the implementation-record commit; that commit is "
    "an ancestor of the commit that holds the result file; the result file's recorded code digest "
    "matches the implementation record; and the recorded start time is later than the "
    "implementation record's commit date. Commit dates are what the committer wrote; the "
    "ancestry is not. The chain is checked on the records branch `v2/phase0`, where this text, "
    "the implementation record, the check counts and the result files are committed. The "
    "published folder on the code branch holds copies with the same bytes.",
    "Stage 1 finds 423 sessions in 33 repositories in the first half and reproduces the separate "
    "counts: 79, 228 and 116 for the outcome; 25 sessions at 0 for the first measure; the six "
    "month counts.",
    "The repository blocks of the first measure meet the floor: at least 10 repositories carry "
    "weight and `W` is at least 150.",
    "The two runs are equal byte for byte, and the hostile-input and canary tests pass (no "
    "transcript text, path, session id, repository name or user name in any output).",
)
TYPED_NOTICE = "A privacy check failed before publication. No number is published."
# "Order of work" step 7: "For the second half, condition 2 uses these second-half targets (432
# sessions in 32 repositories; 107, 184 and 141; 18 sessions at 0; the six month counts)".
TYPED_CONDITION_2_OF_THE_SECOND_HALF = (
    "Failed condition: condition 2 of the registration, with the second-half targets of step 7 "
    "(432 sessions in 32 repositories; 107, 184 and 141; 18 sessions at 0; the six month counts)."
)
# "Order of work": the sentence of the note published when a step misses its date.
TYPED_STOPPED_SENTENCE = (
    "The study stopped at this step because its date passed; nothing was run after it."
)


def test_the_readme_sentence_and_the_conditions_are_the_registrations_own_words() -> None:
    # Decision 14 (finding 14): the registered README sentence is held as a constant with a
    # typed copy here, compared character for character.
    assert render.README_SENTENCE == TYPED_README_SENTENCE
    assert render.CONDITIONS == TYPED_CONDITIONS
    assert render.NOTICE == TYPED_NOTICE
    # Decisions B and G: the second half's condition 2 and the date-miss sentence.
    assert render.CONDITION_2_OF_THE_SECOND_HALF == TYPED_CONDITION_2_OF_THE_SECOND_HALF
    assert render.STOPPED_SENTENCE == TYPED_STOPPED_SENTENCE


def test_the_failed_condition_line_of_each_half() -> None:
    # Decision B (MAJOR 2): condition 2 of the second half carries step 7's own targets; every
    # other line is the condition's own sentence.
    for number, sentence in enumerate(TYPED_CONDITIONS, start=1):
        expected = f"Failed condition: condition {number} of the registration: {sentence}"
        assert render.failed_condition_line(number, "confirmation") == expected
        if number != 2:
            assert render.failed_condition_line(number, "discovery") == expected
    assert render.failed_condition_line(2, "discovery") == TYPED_CONDITION_2_OF_THE_SECOND_HALF
    # The first half's condition 2 is the one the registration writes with the first half's
    # figures, and it never reaches the second half's section.
    assert "423 sessions in 33 repositories" in render.failed_condition_line(2, "confirmation")
    assert "423" not in render.failed_condition_line(2, "discovery")
    for number in (0, 5):
        with pytest.raises(render.ResultInvalid):
            _ = render.failed_condition_line(number, "confirmation")


def test_the_fixed_texts_are_the_registrations_own_words() -> None:
    assert render.HEADLINE == TYPED_HEADLINE
    assert render.YARDSTICK_CAPTION == TYPED_CAPTION
    assert render.YARDSTICK_WARNING == TYPED_WARNING
    assert render.YARDSTICK_TABLE == TYPED_TABLE
    assert render.YARDSTICK_NOTE == TYPED_NOTE
    assert render.GENERAL_LIMITS == TYPED_LIMITS
    assert render.FACTS == TYPED_FACTS
    assert render.LOO_CLAUSE in TYPED_HEADLINE
    clause = TYPED_HEADLINE[TYPED_HEADLINE.index("Leaving out") : TYPED_HEADLINE.index(" (or:")]
    assert clause + "." == render.LOO_FORMED
    assert render.LOO_NOT_FORMED == "The leave-one-out range was not formed."


def _fill(result: Any) -> str:
    """The typed headline filled from the result file, by this file's own code."""
    first = result["measures"]["no_reasoning_share"]
    extra = result["first_measure_repository"]
    if "loo_range" in extra:
        clause = "The leave-one-out range was not formed."
    else:
        clause = (
            "Leaving out one repository at a time moves the first number between "
            f"{extra['loo_min']} and {extra['loo_max']}."
        )
    text = TYPED_HEADLINE.replace(render.LOO_CLAUSE, clause)
    for placeholder, value in (
        ("[N]", str(result["sessions"])),
        ("[R]", str(result["repositories"])),
        ("[X]", str(first["repository"]["rho_bar"])),
        ("[m]", str(first["repository"]["m"])),
        ("[W]", str(first["repository"]["W"])),
        ('[Y, or the "not formed" form]', str(first["repository_month"]["rho_bar"])),
        ('[Z, or the "not formed" form]', str(first["repository_model_length"]["rho_bar"])),
        ("[a]", str(extra["above"])),
        ("[b]", str(extra["below"])),
        ("[c]", str(extra["zero"])),
        ("[S]%", str(extra["positive_weight_share"])),
    ):
        text = text.replace(placeholder, value)
    return text


def _result(tmp_path: Path, half: str = "confirmation") -> Any:
    _signal, _outcome, out_dir = pipeline.run_both_stages(tmp_path, half)
    return pipeline.read_json(out_dir / f"result_{half}.json")


def _page(tmp_path: Path) -> tuple[Any, str]:
    """The first half's result file and its page. A result file of the second half is rendered in
    the second half's section only: decision C ties every file to the section it stands in."""
    result = _result(tmp_path)
    return result, render.page(result)


def test_the_headline_is_the_registered_sentence_with_the_brackets_filled(tmp_path: Path) -> None:
    result, text = _page(tmp_path)
    filled = _fill(result)
    assert filled in text
    assert "[" not in filled
    assert "not formed" not in filled


def _allowed_tokens(result: Any) -> set[str]:
    tokens: set[str] = {str(result["sessions"]), str(result["repositories"])}
    for measure in result["measures"].values():
        for block in measure.values():
            for value in block.values():
                tokens.add(str(value))
    for value in result["first_measure_repository"].values():
        tokens.add(str(value))
    return tokens


def _figures(text: str) -> set[str]:
    return set(re.findall(r"[+-]?[0-9]+(?:,[0-9]{3})*(?:\.[0-9]+)?%?", text))


def _check_figures(checks: Any) -> set[str]:
    """Every digit sequence a checks file carries, its check names included."""
    return _figures(json.dumps(checks))


def test_every_figure_on_the_page_is_in_the_result_file(tmp_path: Path) -> None:
    result, text = _page(tmp_path)
    stripped = text.replace(_fill(result), "")
    for fixed in (
        render.YARDSTICK_CAPTION,
        render.YARDSTICK_WARNING,
        render.YARDSTICK_TABLE,
        render.YARDSTICK_NOTE,
        *render.GENERAL_LIMITS,
        *render.FACTS["confirmation"],
    ):
        stripped = stripped.replace(fixed, "")
    # The numbered limits, and the registration's own words "above 0", "below 0",
    # "exactly 0" in the sign count.
    allowed = _allowed_tokens(result) | {str(index) for index in range(1, 11)} | {"0"}
    assert _figures(stripped) <= allowed


def test_every_printed_number_of_the_result_reaches_the_page(tmp_path: Path) -> None:
    result, text = _page(tmp_path)
    for measure in result["measures"].values():
        for block in measure.values():
            for value in block.values():
                assert str(value) in text
    for value in result["first_measure_repository"].values():
        assert str(value) in text


def test_the_page_holds_no_path_and_no_key(tmp_path: Path) -> None:
    _result, text = _page(tmp_path)
    assert tables.CANARY not in text
    assert "transcripts0" not in text


def test_the_second_half_stands_beside_the_first(tmp_path: Path) -> None:
    first = _result(tmp_path / "first")
    second = _result(tmp_path / "second", "discovery")
    text = render.page(first, second)
    assert render.SECOND_HALF_LABEL in text
    assert _fill(first) in text
    assert _fill(second) in text
    for fact in render.FACTS["discovery"]:
        assert fact in text
    # Nothing is said about the two halves agreeing or disagreeing: outside the two
    # registered headlines the page adds no sentence of its own.
    outside = text.replace(_fill(first), "").replace(_fill(second), "").lower()
    for word in ("replicat", "agreement with", "disagree", "confirms", "consistent", "better"):
        assert word not in outside


def test_an_unformed_first_measure_gives_the_not_an_answer_form(tmp_path: Path) -> None:
    provenance = pipeline.provenance()
    signal, outcome = tables.write_tables(
        tmp_path / "small", tables.make_sessions(repositories=9, per_repository=20)
    )
    result = analyze.printed_result(analyze.describe(signal, outcome, "confirmation"), provenance)
    text = render.page(result)
    assert "**not an answer**" in text
    assert render.failed_condition_line(3, "confirmation") in text
    assert "not formed (9 repositories, 171 units)" in text
    assert "weighted rank agreement" not in text


def test_a_failed_condition_given_from_outside_is_printed(tmp_path: Path) -> None:
    # The failed condition is given per half, as a number from 1 to 4 (decision 3, finding 13).
    result, _text = _page(tmp_path)
    text = render.page(result, failed_condition_confirmation=4)
    assert "**not an answer**" in text
    assert f"Failed condition: condition 4 of the registration: {TYPED_CONDITIONS[3]}" in text


def test_a_failed_condition_of_one_half_leaves_the_other_an_answer(tmp_path: Path) -> None:
    first = _result(tmp_path / "first")
    second = _result(tmp_path / "second", "discovery")
    text = render.page(first, second, failed_condition_discovery=1)
    before, after = text.split(f"## {render.SECOND_HALF_LABEL}")
    assert render.NOT_AN_ANSWER not in before
    assert f"Failed condition: condition 1 of the registration: {TYPED_CONDITIONS[0]}" in after


# --- the check counts on the page ---------------------------------------------


def _short_half(tmp_path: Path, half: str = "confirmation") -> tuple[Path, Path, Path]:
    """One half one session short: its stage 1 exits 3 and stage 2 never runs."""
    signal, outcome = tables.write_tables(tmp_path / "tables", tables.both_halves_short(half))
    out_dir = tmp_path / "out"
    out_dir.mkdir(parents=True)
    assert pipeline.stage_one(signal, outcome, half, out_dir) == 3
    return signal, outcome, out_dir / f"checks_{half}.json"


def test_the_page_prints_the_check_counts_of_every_half_given(tmp_path: Path) -> None:
    # Decision 3 (finding 3): the registration prints the check counts, and they live only in
    # the checks file.
    _signal, _outcome, out_dir = pipeline.run_both_stages(tmp_path)
    result = pipeline.read_json(out_dir / "result_confirmation.json")
    checks = pipeline.read_json(out_dir / "checks_confirmation.json")
    text = render.page(result, checks_confirmation=checks)
    assert "### Printed as checks" in text
    entries = render.check_entries(checks, "confirmation")
    for name, found, registered, verdict in entries:
        assert f"| `{name}` | {found} | {registered} | {verdict} |" in text
    # Exactly the registered names, in the registered order (decision C).
    assert [name for name, _found, _registered, _verdict in entries] == list(
        analyze.REGISTERED_CHECKS["confirmation"]
    )
    assert len(entries) == 12
    month_unknown = checks["also_printed"]["month_unknown"]
    model_unknown = checks["also_printed"]["model_unknown"]
    assert f"- Sessions that took the month label `unknown`: {month_unknown}." in text
    assert f"- Sessions that took the model name `unknown`: {model_unknown}." in text


def test_a_checks_file_that_failed_gives_the_step_four_page(tmp_path: Path) -> None:
    # Decision 3: with a checks file whose `all_same` is false and no result file, the page is
    # the one step 4 describes: "not an answer", the failed condition, the check counts, and no
    # other number.
    _signal, _outcome, checks_path = _short_half(tmp_path)
    page_path = tmp_path / "page.md"
    assert (
        render.main(
            ["--checks-confirmation", str(checks_path), "--out", str(page_path)],
        )
        == 0
    )
    text = page_path.read_text(encoding="utf-8")
    assert f"**{render.NOT_AN_ANSWER}**" in text
    assert f"Failed condition: condition 2 of the registration: {TYPED_CONDITIONS[1]}" in text
    assert "| `sessions` | 422 | 423 | different |" in text
    assert "### Printed numbers" not in text
    # The yardstick table and the limits carry the registration's own figures, so they are
    # printed only beside a half that has its numbers.
    assert render.YARDSTICK_TABLE not in text
    assert render.GENERAL_LIMITS[0] not in text
    stripped = text
    for fixed in (
        f"Failed condition: condition 2 of the registration: {TYPED_CONDITIONS[1]}",
        render.TITLE,
        f"**{render.NOT_AN_ANSWER}**",
    ):
        stripped = stripped.replace(fixed, "")
    allowed = _check_figures(pipeline.read_json(checks_path))
    assert _figures(stripped) <= allowed


def test_the_step_four_page_of_the_second_half_carries_step_sevens_targets(
    tmp_path: Path,
) -> None:
    # Decision B (MAJOR 2): the second half's section never quotes the first half's figures.
    # The second half misses one of its outcome counts, which the other-half guard of point 3
    # does not read: that is step 7's own path, "a mismatch stops the study before second-half
    # pairing and is reported under step 4".
    moved = False
    rows: list[tables.Session] = []
    for session in tables.both_halves():
        if not moved and session.half == "discovery" and session.outcome == repr(0.0):
            rows.append(tables.with_outcome(session, repr(50.5)))
            moved = True
        else:
            rows.append(session)
    assert moved
    signal, outcome = tables.write_tables(tmp_path / "tables", rows)
    out_dir = tmp_path / "out"
    out_dir.mkdir(parents=True)
    assert pipeline.stage_one(signal, outcome, "confirmation", out_dir) == 0
    checks_first = out_dir / "checks_confirmation.json"
    assert pipeline.stage_two(signal, outcome, "confirmation", out_dir, checks_first) == 0
    assert pipeline.stage_one(signal, outcome, "discovery", out_dir) == 3

    text = render.page(
        pipeline.read_json(out_dir / "result_confirmation.json"),
        checks_confirmation=pipeline.read_json(checks_first),
        checks_discovery=pipeline.read_json(out_dir / "checks_discovery.json"),
    )
    before, after = text.split(f"## {render.SECOND_HALF_LABEL}")
    assert TYPED_CONDITION_2_OF_THE_SECOND_HALF in after
    assert TYPED_CONDITIONS[1] not in after
    assert "| `outcome_at_0` | 106 | 107 | different |" in after
    assert render.NOT_AN_ANSWER not in before


def _seventh_month(tmp_path: Path) -> tuple[Path, Any]:
    """The first half with one session in a month outside the six, through the real stage 1.

    Stage 1 gives that month its own entry, so its checks file holds 13 entries and exits 3:
    exactly the case of step 4.
    """
    rows = tables.both_halves()
    moved = [tables.with_month(rows[0], "2026-03"), *rows[1:]]
    assert moved[0].half == "confirmation"
    signal, outcome = tables.write_tables(tmp_path / "tables", moved)
    out_dir = tmp_path / "out"
    out_dir.mkdir(parents=True)
    assert pipeline.stage_one(signal, outcome, "confirmation", out_dir) == 3
    checks_path = out_dir / "checks_confirmation.json"
    return checks_path, pipeline.read_json(checks_path)


def test_a_month_outside_the_six_is_printed_as_a_row_of_its_own(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # MAJOR 2 of review 3: a checks file stage 1 itself writes must be renderable, or step 4 has
    # no page. The seventh month comes with a registered figure of 0, its verdict is recomputed
    # like the others and it enters `all_same`.
    checks_path, checks = _seventh_month(tmp_path)
    _ = capsys.readouterr()
    assert len(checks["checks"]) == 13
    assert checks["all_same"] is False

    entries = render.check_entries(checks, "confirmation")
    assert [name for name, _found, _registered, _verdict in entries] == [
        *analyze.REGISTERED_CHECKS["confirmation"],
        "month_2026-03",
    ]
    assert entries[-1] == ("month_2026-03", 1, 0, "different")

    page_path = tmp_path / "page.md"
    assert render.main(["--checks-confirmation", str(checks_path), "--out", str(page_path)]) == 0
    text = page_path.read_text(encoding="utf-8")
    assert f"**{render.NOT_AN_ANSWER}**" in text
    assert f"Failed condition: condition 2 of the registration: {TYPED_CONDITIONS[1]}" in text
    assert "| `month_2026-03` | 1 | 0 | different |" in text
    # In name order, after the registered rows.
    assert text.index("| `month_2026-03` |") > text.index("| `month_2026-09` |")
    assert "### Printed numbers" not in text
    stripped = text
    for fixed in (
        f"Failed condition: condition 2 of the registration: {TYPED_CONDITIONS[1]}",
        render.TITLE,
        f"**{render.NOT_AN_ANSWER}**",
    ):
        stripped = stripped.replace(fixed, "")
    assert _figures(stripped) <= _check_figures(checks)


def test_a_month_outside_the_six_with_a_registered_figure_of_its_own_is_refused(
    tmp_path: Path,
) -> None:
    # Only the figure stage 1 writes for such a month is accepted, and only a real month number.
    _checks_path, checks = _seventh_month(tmp_path)
    doctored = json.loads(json.dumps(checks))
    doctored["checks"][0]["registered"] = 1
    doctored["checks"][0]["found"] = 1
    with pytest.raises(render.ResultInvalid):
        _ = render.check_entries(doctored, "confirmation")
    for name in ("month_2026-13", "month_2026-3", "month_unknown", "month_1999-05", "invented"):
        renamed = json.loads(json.dumps(checks))
        renamed["checks"][0]["name"] = name
        with pytest.raises(render.ResultInvalid):
            _ = render.check_entries(renamed, "confirmation")


def test_the_two_also_printed_counts_are_bounded_by_the_check_counts(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # MAJOR 3 of review 3: the step 4 page is the one page written from a checks file with no
    # result file, so nothing else stands in front of these two published numbers. They are
    # integers from 0 to the found `sessions`, and the found month rows plus `month_unknown` are
    # the found `sessions`.
    _signal, _outcome, checks_path = _short_half(tmp_path)
    _ = capsys.readouterr()
    checks = pipeline.read_json(checks_path)
    sessions = next(entry["found"] for entry in checks["checks"] if entry["name"] == "sessions")
    assert checks["also_printed"] == {"month_unknown": 0, "model_unknown": 0}

    def _boolean(doctored: Any) -> None:
        doctored["also_printed"]["month_unknown"] = True

    def _above_the_sessions(doctored: Any) -> None:
        doctored["also_printed"]["model_unknown"] = sessions + 1

    def _negative(doctored: Any) -> None:
        doctored["also_printed"]["model_unknown"] = -1

    def _months_do_not_sum(doctored: Any) -> None:
        doctored["also_printed"]["month_unknown"] = 1

    for index, change in enumerate((_boolean, _above_the_sessions, _negative, _months_do_not_sum)):
        path = _doctored_checks(tmp_path, checks, change, f"also-{index}.json")
        page_path = tmp_path / f"also-page-{index}.md"
        assert render.main(["--checks-confirmation", str(path), "--out", str(page_path)]) == 2
        assert capsys.readouterr().err == "result-invalid\n"
        assert not page_path.exists()

    # The honest file still renders, and a month label `unknown` is allowed when the months and
    # that count add up to the sessions.
    def _one_month_unknown(doctored: Any) -> None:
        doctored["also_printed"]["month_unknown"] = 1
        for entry in doctored["checks"]:
            if entry["name"] == "month_2026-04":
                entry["found"] -= 1
                entry["verdict"] = "different"

    path = _doctored_checks(tmp_path, checks, _one_month_unknown, "also-ok.json")
    page_path = tmp_path / "also-page-ok.md"
    assert render.main(["--checks-confirmation", str(path), "--out", str(page_path)]) == 0
    text = page_path.read_text(encoding="utf-8")
    assert "- Sessions that took the month label `unknown`: 1." in text


def test_a_condition_number_on_the_command_line_is_an_integer(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # MINOR 10 of review 3: the parser converts the flag, and `_condition_number` takes an integer
    # and nothing else.
    _signal, _outcome, out_dir = pipeline.run_both_stages(tmp_path)
    _ = capsys.readouterr()
    arguments = [
        "--confirmation",
        str(out_dir / "result_confirmation.json"),
        "--checks-confirmation",
        str(out_dir / "checks_confirmation.json"),
        "--out",
    ]
    page_path = tmp_path / "page.md"
    assert render.main([*arguments, str(page_path), "--failed-condition-confirmation", "4"]) == 0
    assert f"Failed condition: condition 4 of the registration: {TYPED_CONDITIONS[3]}" in (
        page_path.read_text(encoding="utf-8")
    )
    for value in ("x", "0", "5", "2.0", "true"):
        refused = tmp_path / f"page-{value}.md"
        assert (
            render.main([*arguments, str(refused), "--failed-condition-confirmation", value]) == 2
        )
        assert capsys.readouterr().err == "arguments-invalid\n"
        assert not refused.exists()


# --- a checks file is read, not copied (decision C) ---------------------------


def _doctored_checks(tmp_path: Path, checks: Any, change: Any, name: str) -> Path:
    path = tmp_path / name
    doctored = json.loads(json.dumps(checks))
    change(doctored)
    _ = path.write_text(json.dumps(doctored), encoding="utf-8")
    return path


def test_a_doctored_checks_file_is_refused_by_the_page(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Decision C (MAJOR 3): the half, the names, the registered figures, every verdict and
    # `all_same` are checked against the constant, so no doctored file reaches the page.
    _signal, _outcome, out_dir = pipeline.run_both_stages(tmp_path)
    _ = capsys.readouterr()
    checks = pipeline.read_json(out_dir / "checks_confirmation.json")

    def _edited_found(doctored: Any) -> None:
        doctored["checks"][0]["found"] = 424

    def _removed(doctored: Any) -> None:
        del doctored["checks"][0]

    def _invented(doctored: Any) -> None:
        doctored["checks"].append(
            {"name": "invented", "found": 7, "registered": 1, "verdict": "same"}
        )

    def _duplicated(doctored: Any) -> None:
        doctored["checks"].append(dict(doctored["checks"][0]))

    def _figure(doctored: Any) -> None:
        doctored["checks"][0]["registered"] = 424
        doctored["checks"][0]["found"] = 424

    def _flipped(doctored: Any) -> None:
        doctored["all_same"] = False

    def _half(doctored: Any) -> None:
        doctored["half"] = "discovery"

    def _also(doctored: Any) -> None:
        doctored["also_printed"]["invented"] = 7

    for index, change in enumerate(
        (_edited_found, _removed, _invented, _duplicated, _figure, _flipped, _half, _also)
    ):
        path = _doctored_checks(tmp_path, checks, change, f"doctored-{index}.json")
        page_path = tmp_path / f"page-{index}.md"
        assert (
            render.main(
                [
                    "--confirmation",
                    str(out_dir / "result_confirmation.json"),
                    "--checks-confirmation",
                    str(path),
                    "--out",
                    str(page_path),
                ]
            )
            == 2
        )
        assert capsys.readouterr().err == "result-invalid\n"
        assert not page_path.exists()


def test_a_checks_file_of_the_other_half_cannot_stand_in_the_first_halfs_section(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Decision C: without a result file nothing else tied the file to the section.
    _signal, _outcome, out_dir = pipeline.run_both_stages(tmp_path, "discovery")
    _ = capsys.readouterr()
    page_path = tmp_path / "page.md"
    assert (
        render.main(
            [
                "--checks-confirmation",
                str(out_dir / "checks_discovery.json"),
                "--out",
                str(page_path),
            ]
        )
        == 2
    )
    assert capsys.readouterr().err == "result-invalid\n"
    assert not page_path.exists()


def test_the_page_ties_the_result_file_to_the_committed_check_counts(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Decision E (MINOR 3): `check_result.check` is given the half's checks object, so the
    # result file's two top counts must equal the counts the checks file carries.
    _signal, _outcome, out_dir = pipeline.run_both_stages(tmp_path)
    _ = capsys.readouterr()
    doctored = pipeline.read_json(out_dir / "result_confirmation.json")
    doctored["sessions"] = 422
    path = tmp_path / "result.json"
    _ = path.write_text(json.dumps(doctored), encoding="utf-8")
    page_path = tmp_path / "page.md"
    assert (
        render.main(
            [
                "--confirmation",
                str(path),
                "--checks-confirmation",
                str(out_dir / "checks_confirmation.json"),
                "--out",
                str(page_path),
            ]
        )
        == 2
    )
    assert capsys.readouterr().err == "result-invalid\n"
    assert not page_path.exists()


# --- the date-miss note and the two runs of step 5 ----------------------------


def test_the_date_miss_note_holds_the_step_the_sections_and_the_sentence(tmp_path: Path) -> None:
    # Decision G (MINOR 6): the line "Last step completed: N."; the check counts already
    # committed, as the page prints them; for a result file already committed, what the page
    # carries for that half (the headline sentence, the printed numbers, the yardstick table, the
    # limits and that half's facts); and the sentence.
    _signal, _outcome, out_dir = pipeline.run_both_stages(tmp_path)
    result = pipeline.read_json(out_dir / "result_confirmation.json")
    checks = pipeline.read_json(out_dir / "checks_confirmation.json")
    text = render.page(result, checks_confirmation=checks, stopped_after_step=5)
    assert "Last step completed: 5." in text
    assert text.rstrip("\n").endswith(TYPED_STOPPED_SENTENCE)
    assert "### Printed as checks" in text
    assert "### Printed numbers" in text
    # MINOR 1 of review 3: between the last-step line and the sentence the note prints exactly
    # what the ordinary page prints for these files, so a result file comes with the limits, the
    # yardstick table and the half's facts, as the registration prints them "with the result".
    assert render.YARDSTICK_TABLE in text
    for limit in TYPED_LIMITS:
        assert limit in text
    for fact in TYPED_FACTS["confirmation"]:
        assert fact in text
    ordinary = render.page(result, checks_confirmation=checks)
    assert text == (
        f"{render.TITLE}\n\nLast step completed: 5.\n"
        + ordinary[len(f"{render.TITLE}\n") :].rstrip("\n")
        + f"\n\n{TYPED_STOPPED_SENTENCE}\n"
    )

    # A half with a passing checks file and no result file prints its check section only.
    only_checks = render.page(checks_confirmation=checks, stopped_after_step=4)
    assert "Last step completed: 4." in only_checks
    assert "### Printed as checks" in only_checks
    assert "### Printed numbers" not in only_checks
    assert render.YARDSTICK_TABLE not in only_checks
    assert TYPED_LIMITS[0] not in only_checks
    assert only_checks.rstrip("\n").endswith(TYPED_STOPPED_SENTENCE)

    # A step that missed its date before anything was committed: the step and the sentence.
    assert render.page(stopped_after_step=1) == (
        f"{render.TITLE}\n\nLast step completed: 1.\n\n{TYPED_STOPPED_SENTENCE}\n"
    )
    for number in (0, 8):
        with pytest.raises(render.ResultInvalid):
            _ = render.page(stopped_after_step=number)


def test_the_two_runs_of_step_five_are_listed_key_by_key(tmp_path: Path) -> None:
    # Decision H: the difference is listed with both values, and the half is "not an answer"
    # under condition 4.
    result = _result(tmp_path)
    second = json.loads(json.dumps(result))
    second["measures"]["no_reasoning_share"]["repository"]["rho_bar"] = "+0.999"
    del second["first_measure_repository"]["above"]
    differences = render.differing_keys(result, second)
    names = {key for key, _mine, _theirs in differences}
    assert names == {
        "measures.no_reasoning_share.repository.rho_bar",
        "first_measure_repository.above",
    }
    assert (
        "first_measure_repository.above",
        str(result["first_measure_repository"]["above"]),
        render.ABSENT,
    ) in differences

    text = render.page(
        result, failed_condition_confirmation=4, differences_confirmation=differences
    )
    assert f"**{render.NOT_AN_ANSWER}**" in text
    assert f"Failed condition: condition 4 of the registration: {TYPED_CONDITIONS[3]}" in text
    assert "- `measures.no_reasoning_share.repository.rho_bar`: first run " in text
    assert "+0.999" in text
    # The first run's numbers are printed as usual.
    assert _fill(result) in text


def test_the_notice_only_page_carries_no_digit(tmp_path: Path) -> None:
    # Decision 3: "only a notice without any number is published".
    page_path = tmp_path / "page.md"
    assert render.main(["--notice-only", "--out", str(page_path)]) == 0
    text = page_path.read_text(encoding="utf-8")
    assert text == f"{render.TITLE}\n\n{render.NOTICE}\n"
    assert not any(character.isdigit() for character in text)


def test_the_page_is_not_written_when_a_result_file_fails_the_disclosure_check(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Decision 16 (finding 18): `check_result.check` runs on every result file first.
    _signal, _outcome, out_dir = pipeline.run_both_stages(tmp_path)
    _ = capsys.readouterr()
    doctored = pipeline.read_json(out_dir / "result_confirmation.json")
    doctored["first_measure_repository"]["without_shared_m"] = 31
    path = tmp_path / "doctored.json"
    _ = path.write_text(json.dumps(doctored), encoding="utf-8")
    page_path = tmp_path / "page.md"
    assert (
        render.main(
            [
                "--confirmation",
                str(path),
                "--checks-confirmation",
                str(out_dir / "checks_confirmation.json"),
                "--out",
                str(page_path),
            ]
        )
        == 2
    )
    assert capsys.readouterr().err == "result-invalid\n"
    assert not page_path.exists()


def test_the_page_is_written_once_and_not_overwritten(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _signal, _outcome, out_dir = pipeline.run_both_stages(tmp_path)
    page = tmp_path / "page.md"
    arguments = [
        "--confirmation",
        str(out_dir / "result_confirmation.json"),
        "--checks-confirmation",
        str(out_dir / "checks_confirmation.json"),
        "--out",
        str(page),
    ]
    assert render.main(arguments) == 0
    written = page.read_bytes()
    assert render.main(arguments) == 2
    assert page.read_bytes() == written
    _ = capsys.readouterr()


def test_a_result_file_that_is_not_a_result_is_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _signal, _outcome, out_dir = pipeline.run_both_stages(tmp_path)
    broken = tmp_path / "broken.json"
    _ = broken.write_text("[]", encoding="utf-8")
    assert (
        render.main(
            [
                "--confirmation",
                str(broken),
                "--checks-confirmation",
                str(out_dir / "checks_confirmation.json"),
                "--out",
                str(tmp_path / "page.md"),
            ]
        )
        == 2
    )
    assert capsys.readouterr().err.splitlines()[-1] == "result-invalid"


def test_the_page_needs_a_checks_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _signal, _outcome, out_dir = pipeline.run_both_stages(tmp_path)
    _ = capsys.readouterr()
    assert (
        render.main(
            [
                "--confirmation",
                str(out_dir / "result_confirmation.json"),
                "--out",
                str(tmp_path / "page.md"),
            ]
        )
        == 2
    )
    assert capsys.readouterr().err == "arguments-invalid\n"
    assert not (tmp_path / "page.md").exists()
