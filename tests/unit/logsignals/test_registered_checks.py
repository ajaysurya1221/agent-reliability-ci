"""The 24 figures the registration fixes, typed out here and never imported from the module.

The stage 1 fixture builds its sessions from `analyze.REGISTERED_CHECKS`, so no test that uses it
can catch a wrong figure in that constant. This file is the one that can: every number below is
typed from `PREREGISTRATION-2.md` ("Data and population", "What was looked at before writing
this", "Conditions for reading the numbers as an answer").
"""

from __future__ import annotations

from bench.logsignals import analyze

# First reported half: "423 Codex sessions in 33 repositories"; "79 sessions at 0%, 228 at 100%,
# 116 between"; "25 sessions at exactly 0"; "By month, April to September: 102, 76, 109, 104,
# 25, 7".
TYPED_CONFIRMATION: dict[str, int] = {
    "sessions": 423,
    "repositories": 33,
    "outcome_at_0": 79,
    "outcome_at_100": 228,
    "outcome_between": 116,
    "first_measure_exactly_0": 25,
    "month_2026-04": 102,
    "month_2026-05": 76,
    "month_2026-06": 109,
    "month_2026-07": 104,
    "month_2026-08": 25,
    "month_2026-09": 7,
}
# Second reported half: "432 sessions in 32 repositories"; "outcome 107 at 0%, 184 at 100%, 141
# between"; "18 sessions at exactly 0"; "by month 84, 116, 80, 40, 72, 40".
TYPED_DISCOVERY: dict[str, int] = {
    "sessions": 432,
    "repositories": 32,
    "outcome_at_0": 107,
    "outcome_at_100": 184,
    "outcome_between": 141,
    "first_measure_exactly_0": 18,
    "month_2026-04": 84,
    "month_2026-05": 116,
    "month_2026-06": 80,
    "month_2026-07": 40,
    "month_2026-08": 72,
    "month_2026-09": 40,
}
# "All sessions fall between April and September 2026."
TYPED_MONTHS: tuple[str, ...] = (
    "2026-04",
    "2026-05",
    "2026-06",
    "2026-07",
    "2026-08",
    "2026-09",
)


def test_the_module_holds_the_registrations_own_figures() -> None:
    assert analyze.REGISTERED_CHECKS == {
        "confirmation": TYPED_CONFIRMATION,
        "discovery": TYPED_DISCOVERY,
    }
    assert analyze.REGISTERED_MONTHS == TYPED_MONTHS
    assert len(TYPED_CONFIRMATION) + len(TYPED_DISCOVERY) == 24


def test_each_halfs_three_outcome_classes_add_up_to_its_sessions() -> None:
    # The registration's own arithmetic: "none missing" in either half.
    for figures in (TYPED_CONFIRMATION, TYPED_DISCOVERY):
        classes = figures["outcome_at_0"] + figures["outcome_at_100"] + figures["outcome_between"]
        assert classes == figures["sessions"]
        assert sum(figures[f"month_{month}"] for month in TYPED_MONTHS) == figures["sessions"]


def test_the_two_halves_are_the_855_eligible_codex_sessions() -> None:
    # "855 of the 1,444 Codex pool sessions are eligible", in "65 repositories".
    assert TYPED_CONFIRMATION["sessions"] + TYPED_DISCOVERY["sessions"] == 855
    assert TYPED_CONFIRMATION["repositories"] + TYPED_DISCOVERY["repositories"] == 65
