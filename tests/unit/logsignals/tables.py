"""Synthetic private tables for the log-signals tests.

Every path, repository key, user key and model name carries a token that no output of the study
may hold. No real file is ever opened by these helpers.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from fractions import Fraction
from pathlib import Path

from bench.logsignals import analyze

CANARY = "CANARY"
SIGNAL_HEADER = (
    "path\trepo_key\thalf\tmonth\tuser_key\tmodel\td\tfirst_time\tzero\ttokens_num\ttokens_den"
)
OUTCOME_HEADER = "path\tagent_percentage"

MONTHS: tuple[str, ...] = ("2026-04", "2026-05", "2026-06", "2026-07")
BASE_TIME = datetime(2026, 5, 3, 14, 7, 9, tzinfo=UTC)


def canary_path(token: int) -> str:
    return f"transcripts0/{CANARY}-session-{token:06d}.jsonl"


def canary_key(token: int) -> str:
    """A 16 hex digit key that is unique to this token (the canary of a key is its value)."""
    return format(0xC0DE000000000000 + token, "016x")


def canary_model(token: int) -> str:
    """A model name the shipped reader would render, carrying a unique number."""
    return f"gpt-6-astra-{token % 100:02d}"


@dataclass(frozen=True, slots=True)
class Session:
    path: str
    repo_key: str
    half: str
    month: str
    user_key: str
    model: str
    d: int
    first_time: str
    zero: int
    tokens_num: int
    tokens_den: int
    outcome: str

    def signal_row(self) -> str:
        return "\t".join(
            [
                self.path,
                self.repo_key,
                self.half,
                self.month,
                self.user_key,
                self.model,
                str(self.d),
                self.first_time,
                str(self.zero),
                str(self.tokens_num),
                str(self.tokens_den),
            ]
        )

    def outcome_row(self) -> str:
        return f"{self.path}\t{self.outcome}"


def signal_text(sessions: Sequence[Session]) -> str:
    return SIGNAL_HEADER + "\n" + "".join(s.signal_row() + "\n" for s in sessions)


def outcome_text(sessions: Sequence[Session]) -> str:
    return OUTCOME_HEADER + "\n" + "".join(s.outcome_row() + "\n" for s in sessions)


def other_half_filler(half: str, *, start: int = 800000) -> list[Session]:
    """A few sessions of the other half, carrying no user id.

    `signal.tsv` holds the eligible sessions "of either half" and `describe` refuses a table
    without the other half, since the number without shared users would then exclude nothing.
    These rows carry no user id, so they exclude nothing either and move no number of this half.
    """
    other = "discovery" if half == "confirmation" else "confirmation"
    return make_sessions(repositories=2, per_repository=3, half=other, start=start)


def write_tables(
    directory: Path,
    signal_sessions: Sequence[Session],
    outcome_sessions: Sequence[Session] | None = None,
    *,
    fill_other_half: bool = True,
) -> tuple[Path, Path]:
    """Writes the two tables. By default the half that is missing is given a few filler rows."""
    filler: list[Session] = []
    halves = {session.half for session in signal_sessions}
    if fill_other_half and len(halves) == 1:
        filler = other_half_filler(next(iter(halves)))
    rows = list(signal_sessions) + filler
    values = list(signal_sessions if outcome_sessions is None else outcome_sessions) + filler
    directory.mkdir(parents=True, exist_ok=True)
    signal = directory / "signal.tsv"
    outcome = directory / "outcome.tsv"
    _ = signal.write_text(signal_text(rows), encoding="utf-8")
    _ = outcome.write_text(outcome_text(values), encoding="utf-8")
    return signal, outcome


def make_sessions(
    *,
    repositories: int,
    per_repository: int,
    half: str = "confirmation",
    start: int = 0,
    months: Sequence[str] = MONTHS,
    models: int = 2,
    user_keys: int = 0,
) -> list[Session]:
    """A block of sessions with values that are distinct inside every block of every definition.

    `user_keys` gives the first `user_keys` repositories one shared user key each; the rest carry
    none.
    """
    sessions: list[Session] = []
    token = start
    for repository in range(repositories):
        repo_key = canary_key(start + 1000 + repository)
        for _index in range(per_repository):
            token += 1
            sessions.append(
                Session(
                    path=canary_path(token),
                    repo_key=repo_key,
                    half=half,
                    month=months[token % len(months)] if months else "",
                    user_key=(
                        canary_key(start + 2000 + repository) if repository < user_keys else ""
                    ),
                    model=canary_model(start + 3000 + (token % models)),
                    d=20 + (token % 5),
                    first_time=(BASE_TIME + timedelta(seconds=token)).isoformat(),
                    zero=(token * 3) % 13,
                    tokens_num=10 + (token * 5) % 23,
                    tokens_den=1 + (token % 2),
                    outcome=repr(float((token * 37) % 101)),
                )
            )
    return sessions


def with_outcome(session: Session, outcome: str) -> Session:
    return replace(session, outcome=outcome)


def with_user(session: Session, user_key: str) -> Session:
    return replace(session, user_key=user_key)


def with_model(session: Session, model: str) -> Session:
    return replace(session, model=model)


def with_month(session: Session, month: str) -> Session:
    return replace(session, month=month)


def with_tokens(session: Session, num: int, den: int) -> Session:
    """The second measure of one session, as the exact fraction `num / den`."""
    return replace(session, tokens_num=num, tokens_den=den)


def with_repository(session: Session, repo_key: str) -> Session:
    return replace(session, repo_key=repo_key)


def _interleave(counts: dict[str, int]) -> list[str]:
    """The given labels spread evenly over their total, deterministically."""
    items: list[tuple[Fraction, str, int]] = []
    for name, count in sorted(counts.items()):
        for index in range(count):
            items.append((Fraction(2 * index + 1, 2 * count), name, index))
    items.sort()
    return [name for _key, name, _index in items]


def registered_sessions(
    half: str, *, start: int = 0, shared_repositories: int = 0
) -> list[Session]:
    """A half whose every stage 1 check count is the figure the registration fixes for it.

    The figures are taken from `analyze.REGISTERED_CHECKS`, so this builder cannot drift from
    them. The values themselves are arbitrary: only the counts are the registration's.
    """
    figures = dict(analyze.REGISTERED_CHECKS[half])
    total = figures["sessions"]
    repositories = figures["repositories"]
    outcome_classes = _interleave(
        {
            "at_0": figures["outcome_at_0"],
            "at_100": figures["outcome_at_100"],
            "between": figures["outcome_between"],
        }
    )
    month_labels = _interleave(
        {month: figures[f"month_{month}"] for month in analyze.REGISTERED_MONTHS}
    )
    zero_flags = _interleave(
        {
            "zero": figures["first_measure_exactly_0"],
            "other": total - figures["first_measure_exactly_0"],
        }
    )
    assert len(outcome_classes) == total
    assert len(month_labels) == total
    assert len(zero_flags) == total

    base, extra = divmod(total, repositories)
    sizes = [base + 1] * extra + [base] * (repositories - extra)

    sessions: list[Session] = []
    index = 0
    for repository, size in enumerate(sizes):
        repo_key = canary_key(start + 1000 + repository)
        user_key = canary_key(start + 2000 + repository) if repository < shared_repositories else ""
        for _ in range(size):
            token = start + index + 1
            outcome_class = outcome_classes[index]
            if outcome_class == "at_0":
                outcome = repr(0.0)
            elif outcome_class == "at_100":
                outcome = repr(100.0)
            else:
                outcome = repr(1.0 + (index % 97) + 0.25)
            sessions.append(
                Session(
                    path=canary_path(token),
                    repo_key=repo_key,
                    half=half,
                    month=month_labels[index],
                    user_key=user_key,
                    model=canary_model(start + 3000 + (index % 2)),
                    d=20 + (index % 5),
                    first_time=(BASE_TIME + timedelta(seconds=token)).isoformat(),
                    zero=0 if zero_flags[index] == "zero" else 1 + (index % 11),
                    tokens_num=10 + (index * 5) % 23,
                    tokens_den=1 + (index % 2),
                    outcome=outcome,
                )
            )
            index += 1
    assert len(sessions) == total
    return sessions


def both_halves_short(half: str = "confirmation", *, missing: int = 1) -> list[Session]:
    """Both halves with `missing` sessions dropped from one of them.

    That half's stage 1 check counts then differ, while the other half stays the registered one.
    """
    rows = both_halves()
    mine = [session for session in rows if session.half == half]
    others = [session for session in rows if session.half != half]
    return others + mine[: len(mine) - missing]


def both_halves(*, shared_repositories: int = 2) -> list[Session]:
    """The two halves in one signal table, sharing `shared_repositories` user keys."""
    first = registered_sessions("confirmation", start=0, shared_repositories=shared_repositories)
    second = registered_sessions("discovery", start=100000, shared_repositories=0)
    shared = [canary_key(2000 + repository) for repository in range(shared_repositories)]
    if not shared:
        return first + second
    adjusted = [
        replace(session, user_key=shared[index % len(shared)]) if index < 40 else session
        for index, session in enumerate(second)
    ]
    return first + adjusted
