#!/usr/bin/env python3
"""Writes the result page from the result files and the check counts.

Every fixed text below is copied character for character from `PREREGISTRATION.md`: the headline
sentence, the yardstick table with its warning, the general limits, the facts of each half, the
four conditions, the README sentence and the date-miss note. Nothing is added to them: no
adjective and no sentence of this module's own. Every result file passes `check_result.check`
before anything is written.

"No other number" on the step 4 page means no number computed from the data other than the check
counts. The registration's own figures and its condition and step labels are fixed text: the
sentence of a condition carries the figures that text fixes, and a label such as "condition 2" or
"Last step completed: 3" is structure, not a count. Every number that comes from the data is read
from a result file or from a checks file.

A checks file is never copied as it stands. For each one this module requires the file's half to
be the section's, exactly the registered check names once each, every `registered` figure to
equal the constant it imports from `analyze`, and it recomputes each verdict from
`found == registered`, refusing a file whose verdict or `all_same` disagrees. Beside the six
registered months it accepts a month outside them, which stage 1 writes as its own entry
`month_YYYY-MM` with a registered figure of 0, so that the step 4 page of exactly that case can
be written; every other unknown name is refused.

The two counts the registration names beside the checks ("Also printed: how many sessions took
the month label `unknown` and how many the model name `unknown`") have no second source on the
page side: nothing here can recompute them, and `model_unknown` in particular is compared by hand
with the signal-side count of the implementation record. They are bounded instead: each must be a
whole number from 0 to the found `sessions`, and the found month rows plus `month_unknown` must
be the found `sessions`, since every session either carries one of the months counted above or
none.

The date-miss note of "Order of work" is read as follows: "the last step completed; any check
counts and result file already committed; and the sentence" means the last-step line, then exactly
what the ordinary page would print for the files the folder holds — a result file therefore comes
with the limits, the yardstick table and the half's facts, which the registration prints "with
the result", and a half with only a passing checks file gives its check section alone — then the
registration's own sentence.

The standard library, the study's own `check_result` (which step 6 requires to run before
publication) and the one name `REGISTERED_CHECKS` of `analyze`. Run it as
`.venv/bin/python -m bench.logsignals.render` from the repository root. Importing this module has
no side effects.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NoReturn, cast

from bench.logsignals import check_result
from bench.logsignals.analyze import REGISTERED_CHECKS

TITLE = "# Log-signals study: result"

HALF_LABELS: dict[str, str] = {
    "confirmation": "first reported half",
    "discovery": "second reported half",
}
SECOND_HALF_LABEL = "second reported half, run after the first result was committed"

# --- the fixed texts of the registration -------------------------------------

HEADLINE = (
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
LOO_CLAUSE = (
    "Leaving out one repository at a time moves the first number between [lo] and [hi] (or: the "
    "leave-one-out range was not formed)."
)
LOO_FORMED = "Leaving out one repository at a time moves the first number between [lo] and [hi]."
LOO_NOT_FORMED = "The leave-one-out range was not formed."

YARDSTICK_CAPTION = (
    "**Yardstick table (simulated, not counted; fixed now; not recomputed, extended or trimmed "
    "after the result).**"
)
YARDSTICK_WARNING = (
    "**Do not read significance from this table. Comparing the published number with these means "
    "or spreads is not a test and supports no statement that the number is, or is not, larger "
    "than chance.** The table shows only that the number moves by itself when no link is built "
    "in between a session's two numbers, and by how much in ten simulated cases. From the round "
    "3 reviewer's implementation unless marked."
)
YARDSTICK_TABLE = (
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
YARDSTICK_NOTE = (
    '"AR(1) 0.6" means each session\'s value leans on the one before it with weight 0.6. The '
    "last three rows are not applicable null cases of the rule. The last one is a shared cause, "
    "not a session-level link: one dated change that affects both records puts the number near "
    "+0.09. The row above it has a coding fault found in review (the break had a fixed direction "
    "in both numbers); it is kept because it was measured."
)

GENERAL_LIMITS: tuple[str, ...] = (
    "The first number is a weighted average, and a few large repositories hold most of the "
    "possible weight (see the facts of each half). Realized contributing weights may differ from "
    "the possible weights.",
    "Most sessions sit at an outcome endpoint. Inside many repositories the outcome takes few "
    "distinct values, and ties carry much of the weight.",
    "Many sessions carry no user id, and no repository shows two identified users. Repository "
    "and person cannot be told apart.",
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
    "Each half's separate counts were inspected before this text was written (next section). "
    "The block definitions, the floors and the sentence were chosen knowing them.",
    "The yardstick table is all that is known about how large this number gets with no "
    "session-level link, and it is simulated.",
)

FACTS: dict[str, tuple[str, ...]] = {
    "confirmation": (
        "The four largest repositories hold a little over three fifths of the possible weight.",
        "307 of the 423 sessions sit at an outcome endpoint (79 at 0%, 228 at 100%).",
        "168 of the 423 sessions carry no user id. 11 repositories mix sessions with and without "
        "one and hold about seven tenths of the possible weight; 4 repositories have no "
        "identified user.",
        "The 7 shared user ids hold 62 of the 423 sessions, in 11 repositories (whether these "
        "are the 11 of the line above was not counted).",
    ),
    "discovery": (
        "The four largest repositories hold a little over three fifths of the possible weight.",
        "291 of the 432 sessions sit at an outcome endpoint (107 at 0%, 184 at 100%).",
        "101 of the 432 sessions carry no user id.",
        "The 7 shared user ids hold 80 of the 432 sessions, in 8 repositories.",
    ),
}

NOT_AN_ANSWER = "not an answer"

# The README's own fixed sentence. It belongs to the README, not to this page; it is held here so
# that one typed copy in the tests guards it character for character.
README_SENTENCE = (
    "One study describes how a reasoning measure and an attribution share line up in public "
    "Codex sessions (`docs/results/log-signals-study/`). It is a description. It does not "
    "validate these measures against any outcome."
)

# "Conditions for reading the numbers as an answer", in the registration's own words.
CONDITIONS: tuple[str, ...] = (
    "The registration commit is an ancestor of the implementation-record commit; that commit is "
    "an ancestor of the commit that holds the result file; the result file's recorded code digest "
    "matches the implementation record; and the recorded start time is later than the "
    "implementation record's commit date. Commit dates are what the committer wrote; the "
    "ancestry is not.",
    "Stage 1 finds 423 sessions in 33 repositories in the first half and reproduces the separate "
    "counts: 79, 228 and 116 for the outcome; 25 sessions at 0 for the first measure; the six "
    "month counts.",
    "The repository blocks of the first measure meet the floor: at least 10 repositories carry "
    "weight and `W` is at least 150.",
    "The two runs are equal byte for byte, and the hostile-input and canary tests pass (no "
    "transcript text, path, session id, repository name or user name in any output).",
)
CONDITION_FAILED_BY_THE_CHECK_COUNTS = 2
CONDITION_FAILED_BY_THE_FLOOR = 3
CONDITION_FAILED_BY_THE_TWO_RUNS = 4

# "Order of work" step 7: "For the second half, condition 2 uses these second-half targets (432
# sessions in 32 repositories; 107, 184 and 141; 18 sessions at 0; the six month counts)." The
# words inside the brackets are step 7's own, so the second half's section never quotes the
# first half's figures.
CONDITION_2_OF_THE_SECOND_HALF = (
    "Failed condition: condition 2 of the registration, with the second-half targets of step 7 "
    "(432 sessions in 32 repositories; 107, 184 and 141; 18 sessions at 0; the six month counts)."
)

# "Order of work": the note published when a step misses its date.
STOPPED_SENTENCE = (
    "The study stopped at this step because its date passed; nothing was run after it."
)
LAST_STEP_LINE = "Last step completed: {number}."
STEPS = range(1, 8)

# The notice of the privacy case: "only a notice without any number is published".
NOTICE = "A privacy check failed before publication. No number is published."

# A key one of the two runs of step 5 carries and the other does not.
ABSENT = "absent"

DEFINITION_LABELS: tuple[tuple[str, str], ...] = (
    ("repository", "Repository blocks"),
    ("repository_month", "Repository-and-month blocks"),
    ("repository_model_length", "Repository, model-name and session-length blocks"),
)
MEASURE_LABELS: tuple[tuple[str, str], ...] = (
    ("no_reasoning_share", "first measure"),
    ("reasoning_tokens", "second measure"),
)


class ResultInvalid(Exception):
    """Raised when a result file does not carry what the page needs."""


class OutputRefused(Exception):
    """Raised when the output file exists already."""


class _ArgumentParser(argparse.ArgumentParser):
    """Prints the single word ``arguments-invalid`` (no usage text) and exits 2."""

    def error(self, message: str) -> NoReturn:  # argparse override: it never returns
        print("arguments-invalid", file=sys.stderr)
        raise SystemExit(2)


# --- reading a result file ----------------------------------------------------


def _block(result: Any, measure: str, definition: str) -> Any:
    try:
        return result["measures"][measure][definition]
    except (KeyError, TypeError):
        raise ResultInvalid from None


def _formed(block: Any) -> bool:
    return "not_formed" not in block


def _printed(block: Any) -> str:
    """The `rho_bar` of a block, or its exact "not formed" form."""
    if not _formed(block):
        return str(block["not_formed"])
    return str(block["rho_bar"])


def headline(result: Any) -> str:
    """The registered sentence with the brackets filled from the result file."""
    first = _block(result, "no_reasoning_share", "repository")
    if not _formed(first):
        raise ResultInvalid
    extra: Any = result["first_measure_repository"]
    if "not_formed" in extra:
        raise ResultInvalid

    if "loo_range" in extra:
        clause = LOO_NOT_FORMED
    else:
        clause = LOO_FORMED.replace("[lo]", str(extra["loo_min"])).replace(
            "[hi]", str(extra["loo_max"])
        )
    text = HEADLINE.replace(LOO_CLAUSE, clause)
    pairs: tuple[tuple[str, str], ...] = (
        ("[N]", str(result["sessions"])),
        ("[R]", str(result["repositories"])),
        ("[X]", str(first["rho_bar"])),
        ("[m]", str(first["m"])),
        ("[W]", str(first["W"])),
        (
            '[Y, or the "not formed" form]',
            _printed(_block(result, "no_reasoning_share", "repository_month")),
        ),
        (
            '[Z, or the "not formed" form]',
            _printed(_block(result, "no_reasoning_share", "repository_model_length")),
        ),
        ("[a]", str(extra["above"])),
        ("[b]", str(extra["below"])),
        ("[c]", str(extra["zero"])),
        ("[S]%", str(extra["positive_weight_share"])),
    )
    for placeholder, value in pairs:
        text = text.replace(placeholder, value)
    return text


def numbers(result: Any) -> list[str]:
    """The list of printed numbers, for the first measure and for the second."""
    lines: list[str] = []
    for measure, measure_label in MEASURE_LABELS:
        lines.append(f"**{measure_label} (`{measure}`)**")
        lines.append("")
        for definition, definition_label in DEFINITION_LABELS:
            block = _block(result, measure, definition)
            if not _formed(block):
                lines.append(f"- {definition_label}: {block['not_formed']}.")
                continue
            lines.append(
                f"- {definition_label}: `rho_bar` {block['rho_bar']}; {block['m']} "
                f"weight-carrying repositories; {block['W']} units of weight; "
                f"{block['sessions']} sessions inside weight-carrying blocks."
            )
        lines.append("")
        if measure != "no_reasoning_share":
            continue
        extra: Any = result["first_measure_repository"]
        if "not_formed" in extra:
            lines.append(f"- Sign count: {extra['not_formed']}.")
            lines.append(f"- Leave-one-out range: {extra['not_formed']}.")
            lines.append(
                "- Without the repositories that share an identified user with the other half: "
                f"{extra['not_formed']}."
            )
            lines.append("")
            continue
        lines.append(
            f"- Sign count: {extra['above']} repositories above 0, {extra['below']} below 0, "
            f"{extra['zero']} exactly 0; those above 0 carry "
            f"{extra['positive_weight_share']} of the weight."
        )
        if "loo_range" in extra:
            lines.append(f"- Leave-one-out range: {extra['loo_range']}.")
        else:
            lines.append(f"- Leave-one-out range: {extra['loo_min']} to {extra['loo_max']}.")
        lines.append(
            "- Without the repositories that share an identified user with the other half: "
            f"{extra['without_shared']}."
        )
        lines.append("")
    return lines


# --- the check counts ---------------------------------------------------------

# A month entry of a checks file: the six carry the registered names, and a name of this form
# that is not one of them is stage 1's own key for a month outside the six (a real month number).
_MONTH_ENTRY_RE = re.compile(r"\Amonth_20[0-9]{2}-(0[1-9]|1[0-2])\Z")


def _integer(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ResultInvalid
    return value


def check_entries(checks: Any, half: str) -> list[tuple[str, int, int, str]]:
    """Every check of one half as (name, found, registered, verdict).

    The file is read, not copied. Its half must be the section's; its list must hold exactly the
    registered names, once each; every `registered` figure must equal the one this module imports
    from `analyze`; every verdict is recomputed from `found == registered`, and a file whose
    verdict or `all_same` disagrees with the recount is refused. The registered rows come out in
    the registered order, whatever order the file wrote them in.

    A month outside the six is the one further name accepted, under its own entry
    `month_YYYY-MM` with a registered figure of 0 — the form and the figure stage 1 writes for it,
    so that the step 4 page of that case can be written. Its verdict is recomputed like the
    others, it enters `all_same`, and it is printed after the registered rows in name order. Every
    other unknown name is refused.
    """
    if half not in REGISTERED_CHECKS or str(checks["half"]) != half:
        raise ResultInvalid
    registered = REGISTERED_CHECKS[half]
    raw: object = checks["checks"]
    if not isinstance(raw, list):
        raise ResultInvalid
    recorded: dict[str, tuple[int, object]] = {}
    outside: dict[str, tuple[int, object]] = {}
    for entry in cast(list[object], raw):
        if not isinstance(entry, dict):
            raise ResultInvalid
        item = {str(key): value for key, value in cast(dict[object, object], entry).items()}
        name = item["name"]
        if not isinstance(name, str) or name in recorded or name in outside:
            raise ResultInvalid
        if name in registered:
            if _integer(item["registered"]) != registered[name]:
                raise ResultInvalid
            recorded[name] = (_integer(item["found"]), item["verdict"])
        elif _MONTH_ENTRY_RE.match(name):
            if _integer(item["registered"]) != 0:
                raise ResultInvalid
            outside[name] = (_integer(item["found"]), item["verdict"])
        else:
            raise ResultInvalid
    if set(recorded) != set(registered):
        raise ResultInvalid

    rows: list[tuple[str, int, int, str]] = []
    all_same = True
    for name, figure in (
        *registered.items(),
        *((name, 0) for name in sorted(outside)),
    ):
        found, claimed = recorded[name] if name in recorded else outside[name]
        verdict = "same" if found == figure else "different"
        if claimed != verdict:
            raise ResultInvalid
        all_same = all_same and verdict == "same"
        rows.append((name, found, figure, verdict))
    if checks["all_same"] is not all_same:
        raise ResultInvalid
    return rows


def _also_printed(checks: Any, rows: list[tuple[str, int, int, str]]) -> tuple[int, int]:
    """The two counts the registration names beside the checks, bounded by the rows themselves.

    Neither has a second source on the page side: nothing here can recompute them, and
    `model_unknown` is compared by hand with the signal-side count in the implementation record.
    Each must be a whole number from 0 to the found `sessions`, and the found month rows (the six
    and any month outside them) plus `month_unknown` must be the found `sessions`, because every
    session either carries one of the months counted above or none.
    """
    also: Any = checks["also_printed"]
    if not isinstance(also, dict) or set(cast(dict[str, object], also)) != {
        "month_unknown",
        "model_unknown",
    }:
        raise ResultInvalid
    month_unknown = _integer(also["month_unknown"])
    model_unknown = _integer(also["model_unknown"])
    found = {name: number for name, number, _registered, _verdict in rows}
    sessions = found["sessions"]
    for number in (month_unknown, model_unknown):
        if not 0 <= number <= sessions:
            raise ResultInvalid
    months = sum(number for name, number in found.items() if _MONTH_ENTRY_RE.match(name))
    if months + month_unknown != sessions:
        raise ResultInvalid
    return month_unknown, model_unknown


def _check_lines(checks: Any, half: str) -> list[str]:
    """The check section: every check beside the figure the registration fixes."""
    rows = check_entries(checks, half)
    month_unknown, model_unknown = _also_printed(checks, rows)
    lines = [
        "### Printed as checks",
        "",
        "| Check | Found | Registered | Verdict |",
        "|---|---|---|---|",
    ]
    for name, found, registered, verdict in rows:
        lines.append(f"| `{name}` | {found} | {registered} | {verdict} |")
    lines.append("")
    lines.append(f"- Sessions that took the month label `unknown`: {month_unknown}.")
    lines.append(f"- Sessions that took the model name `unknown`: {model_unknown}.")
    lines.append("")
    return lines


# --- the page -----------------------------------------------------------------


def _limits_lines(half: str) -> list[str]:
    lines = ["General limits, printed for both halves:", ""]
    for index, limit in enumerate(GENERAL_LIMITS, start=1):
        lines.append(f"{index}. {limit}")
    lines.append("")
    lines.append(f"Facts of the {HALF_LABELS[half]} (counted before any pairing):")
    lines.append("")
    for fact in FACTS[half]:
        lines.append(f"- {fact}")
    lines.append("")
    return lines


def failed_condition_line(condition: int, half: str) -> str:
    """The failed-condition line of one half.

    Condition 2 of the second half is the one case the registration gives its own words: step 7
    replaces the first half's figures with the second half's targets. Every other line is the
    condition's own sentence.
    """
    if condition not in range(1, len(CONDITIONS) + 1) or half not in HALF_LABELS:
        raise ResultInvalid
    if condition == CONDITION_FAILED_BY_THE_CHECK_COUNTS and half == "discovery":
        return CONDITION_2_OF_THE_SECOND_HALF
    sentence = CONDITIONS[condition - 1]
    return f"Failed condition: condition {condition} of the registration: {sentence}"


def _flat(value: object, prefix: str = "") -> dict[str, str]:
    """Every leaf of a result file as "key.path" -> the value as printed."""
    if isinstance(value, dict):
        flat: dict[str, str] = {}
        for key, item in sorted(cast(dict[str, object], value).items()):
            flat.update(_flat(item, f"{prefix}.{key}" if prefix else str(key)))
        return flat
    return {prefix: str(value)}


def differing_keys(first: Any, second: Any) -> list[tuple[str, str, str]]:
    """Every key whose printed value the two runs of step 5 do not share, with both values."""
    left, right = _flat(first), _flat(second)
    rows: list[tuple[str, str, str]] = []
    for key in sorted(set(left) | set(right)):
        mine, theirs = left.get(key, ABSENT), right.get(key, ABSENT)
        if mine != theirs:
            rows.append((key, mine, theirs))
    return rows


def _half_section(
    result: Any | None,
    checks: Any | None,
    *,
    half: str,
    label: str,
    failed_condition: int | None,
    differences: list[tuple[str, str, str]] | None = None,
) -> list[str]:
    """One half: the failed condition when there is one, the numbers when a result file was
    given, the difference between the two runs when there is one, and the check counts when a
    checks file was given."""
    if result is not None and str(result["half"]) != half:
        raise ResultInvalid
    if checks is not None and str(checks["half"]) != half:
        raise ResultInvalid
    lines = [f"## {label}", ""]

    first = None if result is None else _block(result, "no_reasoning_share", "repository")
    condition = failed_condition
    if condition is None and checks is not None and checks["all_same"] is not True:
        condition = CONDITION_FAILED_BY_THE_CHECK_COUNTS
    if condition is None and first is not None and not _formed(first):
        condition = CONDITION_FAILED_BY_THE_FLOOR
    if condition is not None:
        lines.append(f"**{NOT_AN_ANSWER}**")
        lines.append("")
        lines.append(failed_condition_line(condition, half))
        lines.append("")

    if first is not None and _formed(first):
        lines.append(headline(result))
        lines.append("")
    if result is not None:
        lines.append("### Printed numbers")
        lines.append("")
        lines.extend(numbers(result))
    if differences:
        lines.append("### The two runs")
        lines.append("")
        for key, mine, theirs in differences:
            lines.append(f"- `{key}`: first run {mine}; second run {theirs}.")
        lines.append("")
    if checks is not None:
        lines.extend(_check_lines(checks, half))
    return lines


def _yardstick_lines() -> list[str]:
    return [
        "### Yardstick table",
        "",
        YARDSTICK_CAPTION,
        "",
        YARDSTICK_WARNING,
        "",
        YARDSTICK_TABLE,
        "",
        YARDSTICK_NOTE,
        "",
    ]


def page(
    confirmation: Any | None = None,
    discovery: Any | None = None,
    *,
    checks_confirmation: Any | None = None,
    checks_discovery: Any | None = None,
    failed_condition_confirmation: int | None = None,
    failed_condition_discovery: int | None = None,
    differences_confirmation: list[tuple[str, str, str]] | None = None,
    differences_discovery: list[tuple[str, str, str]] | None = None,
    notice_only: bool = False,
    stopped_after_step: int | None = None,
) -> str:
    """The result page as Markdown.

    With `notice_only` the page carries the notice and no number at all. A half with a checks
    file and no result file gets the step 4 page: "not an answer", the failed condition and the
    check counts, and no other number — so the yardstick table and the limits, which carry the
    registration's own figures, are printed only beside a half that has its numbers.

    With `stopped_after_step` the page is the note of "Order of work": the last step completed,
    then exactly what this function would print for the files it was given (so a result file comes
    with the limits, the yardstick table and the half's facts), then the registration's own
    sentence.
    """
    lines = [TITLE, ""]
    if notice_only:
        lines.append(NOTICE)
        return "\n".join(lines).rstrip("\n") + "\n"
    if stopped_after_step is not None:
        return _stopped_note(
            confirmation,
            discovery,
            checks_confirmation=checks_confirmation,
            checks_discovery=checks_discovery,
            failed_condition_confirmation=failed_condition_confirmation,
            failed_condition_discovery=failed_condition_discovery,
            differences_confirmation=differences_confirmation,
            differences_discovery=differences_discovery,
            stopped_after_step=stopped_after_step,
        )
    if confirmation is None and checks_confirmation is None:
        raise ResultInvalid

    lines.extend(
        _body(
            confirmation,
            discovery,
            checks_confirmation=checks_confirmation,
            checks_discovery=checks_discovery,
            failed_condition_confirmation=failed_condition_confirmation,
            failed_condition_discovery=failed_condition_discovery,
            differences_confirmation=differences_confirmation,
            differences_discovery=differences_discovery,
        )
    )
    return "\n".join(lines).rstrip("\n") + "\n"


def _body(
    confirmation: Any | None,
    discovery: Any | None,
    *,
    checks_confirmation: Any | None,
    checks_discovery: Any | None,
    failed_condition_confirmation: int | None,
    failed_condition_discovery: int | None,
    differences_confirmation: list[tuple[str, str, str]] | None,
    differences_discovery: list[tuple[str, str, str]] | None,
) -> list[str]:
    """What the page prints for the files it was given, under the title.

    A half with its numbers is followed by the limits the registration prints "with the result",
    and the first such half by the yardstick table; a half with a checks file alone prints its
    check section and no figure of the registration's own.
    """
    lines: list[str] = []
    if confirmation is not None or checks_confirmation is not None:
        lines.extend(
            _half_section(
                confirmation,
                checks_confirmation,
                half="confirmation",
                label=HALF_LABELS["confirmation"].capitalize(),
                failed_condition=failed_condition_confirmation,
                differences=differences_confirmation,
            )
        )
        if confirmation is not None:
            lines.extend(_yardstick_lines())
            lines.append("### Limits that are printed with the result")
            lines.append("")
            lines.extend(_limits_lines("confirmation"))
    if discovery is not None or checks_discovery is not None:
        lines.extend(
            _half_section(
                discovery,
                checks_discovery,
                half="discovery",
                label=SECOND_HALF_LABEL,
                failed_condition=failed_condition_discovery,
                differences=differences_discovery,
            )
        )
        if discovery is not None:
            lines.append("### Limits that are printed with the result")
            lines.append("")
            lines.extend(_limits_lines("discovery"))
    return lines


def _stopped_note(
    confirmation: Any | None,
    discovery: Any | None,
    *,
    checks_confirmation: Any | None,
    checks_discovery: Any | None,
    failed_condition_confirmation: int | None,
    failed_condition_discovery: int | None,
    differences_confirmation: list[tuple[str, str, str]] | None = None,
    differences_discovery: list[tuple[str, str, str]] | None = None,
    stopped_after_step: int,
) -> str:
    """The note of "Order of work": "the last step completed; any check counts and result file
    already committed; and the sentence".

    "Any check counts and result file already committed" is read as exactly what the ordinary page
    prints for the files the folder holds: a result file therefore comes with the limits, the
    yardstick table and that half's facts, which the registration prints "with the result", and a
    half with only a passing checks file gives its check section alone.
    """
    if stopped_after_step not in STEPS:
        raise ResultInvalid
    lines = [TITLE, "", LAST_STEP_LINE.format(number=stopped_after_step), ""]
    lines.extend(
        _body(
            confirmation,
            discovery,
            checks_confirmation=checks_confirmation,
            checks_discovery=checks_discovery,
            failed_condition_confirmation=failed_condition_confirmation,
            failed_condition_discovery=failed_condition_discovery,
            differences_confirmation=differences_confirmation,
            differences_discovery=differences_discovery,
        )
    )
    lines.append(STOPPED_SENTENCE)
    return "\n".join(lines).rstrip("\n") + "\n"


def read_result(path: Path) -> Any:
    try:
        raw: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError):
        raise ResultInvalid from None
    if not isinstance(raw, dict):
        raise ResultInvalid
    return raw


# --- the published folder ------------------------------------------------------

PAGE_NAME = "README.md"
STATUS_NAME = "status.json"
RESULT_NAMES: dict[str, str] = {
    "confirmation": "result_confirmation.json",
    "discovery": "result_discovery.json",
}
CHECKS_NAMES: dict[str, str] = {
    "confirmation": "checks_confirmation.json",
    "discovery": "checks_discovery.json",
}
# Step 5's second run, when the published folder carries it.
SECOND_RESULT_NAMES: dict[str, str] = {
    "confirmation": "result_confirmation.second.json",
    "discovery": "result_discovery.second.json",
}


class ArgumentsInvalid(Exception):
    """Raised when the arguments, or a status file, do not name a page this module can write."""


class FolderRefused(Exception):
    """Raised when the published folder may not hold what it holds."""


@dataclass(frozen=True, slots=True)
class Inputs:
    """The files and the two condition numbers one page is written from."""

    result: dict[str, Path | None]
    checks: dict[str, Path | None]
    failed_condition: dict[str, int | None]
    notice_only: bool
    second: dict[str, Path | None] | None = None
    stopped_after_step: int | None = None

    def second_of(self, half: str) -> Path | None:
        return None if self.second is None else self.second[half]


def _condition_number(value: object) -> int | None:
    """One condition number: an integer from 1 to 4, or None.

    A boolean and a digit string are not numbers here: the status file carries JSON numbers, and
    the command line is converted by the parser itself, so nothing else has to be guessed.
    """
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ArgumentsInvalid
    if value not in range(1, len(CONDITIONS) + 1):
        raise ArgumentsInvalid
    return value


def _step_number(value: object) -> int | None:
    """The last step completed: an integer from 1 to 7, or None. A boolean and a digit string are
    not numbers here, as in `_condition_number`."""
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value not in STEPS:
        raise ArgumentsInvalid
    return value


def read_status(path: Path) -> tuple[bool, dict[str, int | None], int | None]:
    """`status.json`: whether only the notice is published, the failed condition per half, and
    the last step completed when the study stopped at its date."""
    try:
        raw: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError):
        raise ArgumentsInvalid from None
    if not isinstance(raw, dict):
        raise ArgumentsInvalid
    status = {str(key): value for key, value in cast(dict[object, object], raw).items()}
    if set(status) != {"notice_only", "failed_condition", "stopped_after_step"}:
        raise ArgumentsInvalid
    notice_only = status["notice_only"]
    if not isinstance(notice_only, bool):
        raise ArgumentsInvalid
    conditions = status["failed_condition"]
    if not isinstance(conditions, dict):
        raise ArgumentsInvalid
    named = {str(key): value for key, value in cast(dict[object, object], conditions).items()}
    if set(named) != set(HALF_LABELS):
        raise ArgumentsInvalid
    return (
        notice_only,
        {half: _condition_number(named[half]) for half in HALF_LABELS},
        _step_number(status["stopped_after_step"]),
    )


def _numeric_files(folder: Path) -> list[str]:
    """The checks files and result files the folder holds."""
    names = (*CHECKS_NAMES.values(), *RESULT_NAMES.values(), *SECOND_RESULT_NAMES.values())
    return [name for name in names if os.path.lexists(str(folder / name))]


def inputs_of_folder(folder: Path) -> Inputs:
    """The published folder: the page's inputs as `docs/results/log-signals-study/` holds them.

    With `notice_only` the folder may hold `README.md` and `status.json` only: a privacy failure
    publishes no numeric file, so a checks file or a result file beside the notice is refused and
    nothing is written.
    """
    notice_only, conditions, stopped_after_step = read_status(folder / STATUS_NAME)
    if notice_only:
        if _numeric_files(folder):
            raise FolderRefused
        return Inputs(
            result=dict.fromkeys(HALF_LABELS),
            checks=dict.fromkeys(HALF_LABELS),
            failed_condition=conditions,
            notice_only=True,
            second=dict.fromkeys(HALF_LABELS),
            stopped_after_step=stopped_after_step,
        )
    checks = folder / CHECKS_NAMES["confirmation"]
    if not checks.is_file() and stopped_after_step is None:
        raise ArgumentsInvalid

    def _present(names: dict[str, str]) -> dict[str, Path | None]:
        return {
            half: (folder / name) if (folder / name).is_file() else None
            for half, name in names.items()
        }

    return Inputs(
        result=_present(RESULT_NAMES),
        checks=_present(CHECKS_NAMES),
        failed_condition=conditions,
        notice_only=False,
        second=_present(SECOND_RESULT_NAMES),
        stopped_after_step=stopped_after_step,
    )


def _inputs(args: argparse.Namespace) -> Inputs:
    """The page's inputs, either from one folder or from the explicit flags."""
    explicit = (
        args.confirmation,
        args.discovery,
        args.checks_confirmation,
        args.checks_discovery,
    )
    if args.dir is not None:
        if any(value is not None for value in explicit):
            raise ArgumentsInvalid
        if args.notice_only or args.failed_condition_confirmation is not None:
            raise ArgumentsInvalid
        if args.failed_condition_discovery is not None:
            raise ArgumentsInvalid
        return inputs_of_folder(Path(str(args.dir)))

    notice_only = bool(args.notice_only)
    if args.checks_confirmation is None and not notice_only:
        raise ArgumentsInvalid

    def _path(value: object) -> Path | None:
        return None if value is None else Path(str(value))

    return Inputs(
        result={"confirmation": _path(args.confirmation), "discovery": _path(args.discovery)},
        checks={
            "confirmation": _path(args.checks_confirmation),
            "discovery": _path(args.checks_discovery),
        },
        failed_condition={
            "confirmation": _condition_number(args.failed_condition_confirmation),
            "discovery": _condition_number(args.failed_condition_discovery),
        },
        notice_only=notice_only,
    )


def _differences_of(
    inputs: Inputs, half: str, result: Any | None, checks: Any | None
) -> list[tuple[str, str, str]]:
    """The difference between the two runs of step 5, when the folder holds the second run.

    Equal bytes change nothing. A difference makes that half "not an answer" under condition 4,
    so the status file must carry that condition; both files pass `check_result` first.
    """
    second_path, result_path = inputs.second_of(half), inputs.result[half]
    if second_path is None:
        return []
    if result_path is None:
        raise ResultInvalid
    second = read_result(second_path)
    try:
        same = second_path.read_bytes() == result_path.read_bytes()
    except OSError:
        raise ResultInvalid from None
    if same:
        return []
    check_result.check(second, checks)
    if inputs.failed_condition[half] != CONDITION_FAILED_BY_THE_TWO_RUNS:
        raise ResultInvalid
    return differing_keys(result, second)


def page_of(inputs: Inputs) -> str:
    """The page of these inputs. Every result file passes `check_result.check` first."""
    if inputs.notice_only:
        return page(notice_only=True)
    results: dict[str, Any | None] = {}
    checks: dict[str, Any | None] = {}
    differences: dict[str, list[tuple[str, str, str]]] = {}
    for half in HALF_LABELS:
        result_path, checks_path = inputs.result[half], inputs.checks[half]
        result = None if result_path is None else read_result(result_path)
        recorded = None if checks_path is None else read_result(checks_path)
        if (
            result is None
            and recorded is not None
            and recorded["all_same"] is True
            and inputs.stopped_after_step is None
        ):
            # No result file, yet every check matched: outside the date-miss note, the page this
            # module writes for a half without numbers is the step 4 page, and step 4 is reached
            # only by a difference.
            raise ResultInvalid
        results[half], checks[half] = result, recorded
        differences[half] = _differences_of(inputs, half, result, recorded)
    for half in HALF_LABELS:
        result = results[half]
        if result is not None:
            # Decision 15: the page's counts are tied to the committed check counts.
            check_result.check(result, checks[half])
    return page(
        results["confirmation"],
        results["discovery"],
        checks_confirmation=checks["confirmation"],
        checks_discovery=checks["discovery"],
        failed_condition_confirmation=inputs.failed_condition["confirmation"],
        failed_condition_discovery=inputs.failed_condition["discovery"],
        differences_confirmation=differences["confirmation"],
        differences_discovery=differences["discovery"],
        stopped_after_step=inputs.stopped_after_step,
    )


def write_page(out_path: Path, text: str) -> None:
    """Creates the page with mode 0600 and refuses to overwrite an existing file."""
    try:
        fd = os.open(str(out_path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        raise OutputRefused from None
    with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
        _ = handle.write(text)


def main(argv: list[str] | None = None) -> int:
    parser = _ArgumentParser(add_help=False, allow_abbrev=False)
    _ = parser.add_argument("--dir")
    _ = parser.add_argument("--confirmation")
    _ = parser.add_argument("--discovery")
    _ = parser.add_argument("--checks-confirmation", dest="checks_confirmation")
    _ = parser.add_argument("--checks-discovery", dest="checks_discovery")
    _ = parser.add_argument("--out", required=True)
    _ = parser.add_argument("--notice-only", dest="notice_only", action="store_true")
    # The parser converts the two condition numbers, so `_condition_number` takes an integer and
    # nothing else; a value that is not one is `arguments-invalid` from the parser.
    _ = parser.add_argument(
        "--failed-condition-confirmation", dest="failed_condition_confirmation", type=int
    )
    _ = parser.add_argument(
        "--failed-condition-discovery", dest="failed_condition_discovery", type=int
    )
    try:
        args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    except SystemExit:
        return 2

    try:
        inputs = _inputs(args)
    except ArgumentsInvalid:
        print("arguments-invalid", file=sys.stderr)
        return 2
    except FolderRefused:
        print("notice-only-folder", file=sys.stderr)
        return 4

    try:
        text = page_of(inputs)
    except ResultInvalid:
        print("result-invalid", file=sys.stderr)
        return 2
    except check_result.RuleFailed:
        print("result-invalid", file=sys.stderr)
        return 2
    except (KeyError, TypeError):
        print("result-invalid", file=sys.stderr)
        return 2

    try:
        write_page(Path(str(args.out)), text)
    except OutputRefused:
        print("output-exists", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"write: {type(exc).__name__}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
