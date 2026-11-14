"""Validate imported observations, then use the shared balanced-round kernel."""

from __future__ import annotations

import csv
import io
import re
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from fractions import Fraction
from itertools import pairwise
from pathlib import Path
from typing import Any, Literal, cast

import yaml
from pydantic import ValidationError

from arci.hashing import hash_bytes, hash_record
from arci.importers import (
    OutcomeError,
    OutcomeValue,
    ParsedInput,
    Row,
    check_identity,
    loads_json,
    round_label,
)
from arci.outcome_report import text
from arci.outcome_schema import (
    NORMALISATION,
    OUTCOMES_SCHEMA_VERSION,
    OutcomeDecision,
    OutcomeInput,
    OutcomeRoundDigest,
    OutcomeRoundLook,
    OutcomeRule,
    OutcomeTaskCounts,
)
from arci.schema import EXIT_CODES, Verdict
from arci.suite_gate import RoundIncrement, walk_rounds
from arci.suite_schema import SuiteCounts, format_rational, parse_rational
from arci.suite_stats import (
    RunningWealth,
    SuiteRule,
    check_rule_plan,
    default_max_errored_pairs,
    default_max_rounds,
)

Arm = Literal["baseline", "candidate"]
Format = Literal["csv", "jsonl", "junit", "inspect"]
PathLike = str | Path
RoundMap = dict[int, dict[str, OutcomeValue | None]]


class _RuleLoader(yaml.SafeLoader):
    """Refuse duplicate YAML keys, including duplicates introduced by merges."""


def _mapping(loader: _RuleLoader, node: yaml.MappingNode) -> dict[str, Any]:
    loader.flatten_mapping(node)
    result: dict[str, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node)
        if not isinstance(key, str):
            raise ValueError("rule keys must be strings")
        if key in result:
            raise ValueError(f"duplicate key: {key}")
        result[key] = loader.construct_object(value_node)
    return result


_RuleLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping)

# Copy the resolver table: the stricter grammar must not change other YAML readers.
_RuleLoader.yaml_implicit_resolvers = {
    key: [(tag, pattern) for tag, pattern in entries if tag != "tag:yaml.org,2002:int"]
    for key, entries in yaml.SafeLoader.yaml_implicit_resolvers.items()
}
_PLAIN_INTEGER = re.compile(r"[-+]?(0|[1-9][0-9]*)\Z")
_RuleLoader.add_implicit_resolver("tag:yaml.org,2002:int", _PLAIN_INTEGER, list("-+0123456789"))


def _rule_integer(loader: _RuleLoader, node: yaml.ScalarNode) -> int | Decimal:
    spelling = loader.construct_scalar(node)
    if _PLAIN_INTEGER.fullmatch(spelling) is None:
        raise ValueError("expected a plain decimal integer")
    # Oversized values stay non-integers for the ordered field validation below.
    return int(spelling) if len(spelling.lstrip("+-")) <= 9 else Decimal(spelling)


_RuleLoader.add_constructor("tag:yaml.org,2002:int", _rule_integer)


def _signed_rational(value: object) -> str:
    if (
        not isinstance(value, str)
        or re.fullmatch(r"[+-]?[0-9]{1,400}/[1-9][0-9]{0,399}", value) is None
    ):
        raise ValueError("pass_at_least must be a finite rational n/d")
    number = Fraction(value)
    return f"{number.numerator}/{number.denominator}"


def rule_of(rule: OutcomeRule) -> SuiteRule:
    return SuiteRule(
        parse_rational(rule.alpha),
        parse_rational(rule.margin),
        tuple(parse_rational(q) for q in rule.stakes),
        len(rule.tasks),
        rule.max_rounds,
        rule.max_errored_pairs,
    )


def _rule_from_mapping(raw: object) -> OutcomeRule:
    """Validate fields in the ADR's explicit order, before checking the plan."""
    if not isinstance(raw, dict):
        raise ValueError("expected a mapping")
    values = cast(dict[str, Any], raw)

    def field(name: str, default: object = None) -> Any:
        if name in values and values[name] is None:
            raise ValueError(f"{name} must not be null")
        return values.get(name, default)

    if field("schema_version") != OUTCOMES_SCHEMA_VERSION:
        raise ValueError(f"schema_version must be {OUTCOMES_SCHEMA_VERSION}")
    suite_id = field("suite_id")
    if not isinstance(suite_id, str) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", suite_id
    ):
        raise ValueError("suite_id must match SuiteId")
    tasks = field("tasks")
    if (
        not isinstance(tasks, list)
        or not tasks
        or any(not isinstance(task, str) or not task for task in tasks)
    ):
        raise ValueError("tasks must be a non-empty list of non-empty strings")
    if len(set(tasks)) != len(tasks):
        raise ValueError("tasks must be unique")
    try:
        for task in tasks:
            task.encode("utf-8")
    except UnicodeError:
        raise ValueError("tasks must contain valid Unicode strings") from None
    n = len(tasks)

    def rational(name: str, default: str) -> str:
        value = field(name, default)
        if not isinstance(value, str):
            raise ValueError(f"{name} must be a rational string")
        try:
            return format_rational(parse_rational(value))
        except ValueError as exc:
            raise ValueError(f"{name}: {exc}") from None

    alpha = rational("alpha", "1/20")
    if not Fraction(1, 1_000_000) <= parse_rational(alpha) <= Fraction(1, 2):
        raise ValueError("alpha must be in [1/1000000, 1/2]")
    margin = rational("margin", "1/10")
    if not 0 < parse_rational(margin) < 1:
        raise ValueError("margin must be in (0, 1)")
    stakes = field("stakes", ["1/4", "1/2"])
    if not isinstance(stakes, list) or not 1 <= len(stakes) <= 8:
        raise ValueError("stakes must contain 1 to 8 rational strings")
    parsed_stakes: list[Fraction] = []
    for stake in stakes:
        if not isinstance(stake, str):
            raise ValueError("stakes must contain rational strings")
        parsed_stakes.append(parse_rational(stake))
    if any(not 0 < q < 1 for q in parsed_stakes):
        raise ValueError("stakes must be in (0, 1)")
    if any(a >= b for a, b in pairwise(parsed_stakes)):
        raise ValueError("stakes must be strictly increasing")
    rounds = field("max_rounds", default_max_rounds(n))
    if type(rounds) is not int or rounds < 1 or n * rounds > 100_000:
        raise ValueError("max_rounds must be a positive integer with at most 100000 pairs")
    tolerance = field("max_errored_pairs", default_max_errored_pairs(n, rounds))
    if type(tolerance) is not int or not 0 <= tolerance <= n * rounds:
        raise ValueError("max_errored_pairs must be an integer within the registered budget")
    score = field("score")
    if score is not None and (not isinstance(score, str) or not score):
        raise ValueError("score must be a non-empty string")
    if score is not None:
        try:
            score.encode("utf-8")
        except UnicodeError:
            raise ValueError("score must be a valid Unicode string") from None
    threshold = field("pass_at_least")
    if threshold is not None:
        threshold = _signed_rational(threshold)
    declaration = field("fixed_before_runs")
    if type(declaration) is not bool:
        raise ValueError("fixed_before_runs must be a boolean")
    unknown = set(values) - set(OutcomeRule.model_fields)
    if unknown:
        raise ValueError(f"unknown rule fields: {', '.join(sorted(str(k) for k in unknown))}")
    rule = OutcomeRule(
        schema_version=OUTCOMES_SCHEMA_VERSION,
        suite_id=suite_id,
        fixed_before_runs=declaration,
        tasks=tuple(sorted(tasks)),
        alpha=alpha,
        margin=margin,
        stakes=tuple(format_rational(q) for q in parsed_stakes),
        max_rounds=rounds,
        max_errored_pairs=tolerance,
        score=score,
        pass_at_least=threshold,
    )
    check_rule_plan(rule_of(rule))
    return rule


def load_rule(path: PathLike) -> OutcomeRule:
    try:
        raw: object = yaml.load(Path(path).read_text(encoding="utf-8-sig"), Loader=_RuleLoader)
        return _rule_from_mapping(raw)
    except Exception as exc:
        reason = str(exc).splitlines()[0] if str(exc) else type(exc).__name__
        raise OutcomeError(text("E15", reason=reason)) from None


def rule_sha256(rule: OutcomeRule) -> str:
    return hash_record(rule.model_dump(mode="json", exclude_none=True))


def round_outcomes_sha256(
    tasks: Sequence[str],
    baseline: Mapping[str, OutcomeValue | None],
    candidate: Mapping[str, OutcomeValue | None],
) -> str:
    return hash_record(
        {
            "normalisation": NORMALISATION,
            "outcomes": [
                [arm, task, outcomes.get(task)]
                for arm, outcomes in (("baseline", baseline), ("candidate", candidate))
                for task in sorted(tasks)
            ],
        }
    )


def _format(path: str, fmt: str) -> Format:
    # .eval is always refused, including an explicit format override.
    extension = Path(path).suffix
    if extension == ".eval":
        raise OutcomeError(text("E7"))
    if fmt == "auto":
        formats: dict[str, Format] = {
            ".csv": "csv",
            ".jsonl": "jsonl",
            ".xml": "junit",
            ".json": "inspect",
        }
        if extension not in formats:
            raise OutcomeError(text("E8", path=path))
        return formats[extension]
    if fmt not in {"csv", "jsonl", "junit", "inspect"}:
        raise OutcomeError(text("E6", path=path))
    return cast(Format, fmt)


def _neutral(
    source: str,
    *,
    fmt: Format,
    path: str,
    arm: str,
    position: int,
    tasks: frozenset[str] | None,
    seen: set[tuple[str, int]],
) -> ParsedInput:
    def records() -> Iterator[dict[str, Any]]:
        if fmt == "csv":
            reader = csv.reader(io.StringIO(source, newline=""), strict=True)
            header = next(reader, None)
            if (
                header is None
                or len(header) != len(set(header))
                or not {"task_id", "outcome"} <= set(header)
            ):
                raise ValueError("invalid header")
            for values in reader:
                if not values:
                    continue
                if len(values) != len(header):
                    raise ValueError("invalid row")
                yield dict(zip(header, values, strict=True))
        else:
            for line in source.split("\n"):
                if not line.strip():
                    continue
                record = loads_json(line)
                if not isinstance(record, dict) or not {"task_id", "outcome"} <= record.keys():
                    raise ValueError("invalid row")
                yield cast(dict[str, Any], record)

    rows: list[Row] = []
    labelled: bool | None = None
    rounds: set[int] = set()
    for record in records():
        task = record["task_id"]
        if not isinstance(task, str):
            raise ValueError("invalid task id")
        has_round = "round" in record
        if fmt == "csv" and has_round and record["round"] == "":
            raise OutcomeError(text("E14", path=path))
        if labelled is not None and has_round != labelled:
            raise OutcomeError(text("E14", path=path))
        labelled = has_round
        r: Any = record.get("round", position)
        if fmt == "csv" and has_round:
            r = round_label(r)
        if type(r) is not int:
            raise ValueError("invalid round")
        r = round_label(r)
        check_identity(task, r, arm=arm, tasks=tasks, seen=seen)
        value = record["outcome"]
        if not isinstance(value, str) or value not in {"pass", "fail", "error"}:
            raise OutcomeError(text("E10", value=value, id=task))
        rows.append(Row(task, r, cast(OutcomeValue, value)))
        rounds.add(r)
    if not rows:
        raise ValueError("input has no records")
    return ParsedInput(tuple(rows), tuple(sorted(rounds)), not bool(labelled))


@dataclass
class _InputFile:
    path: str
    sha256: str
    arm: Arm
    format: Format
    rounds: tuple[int, ...] | range


@dataclass
class _Inputs:
    inputs: tuple[_InputFile, ...]
    baseline: RoundMap
    candidate: RoundMap
    assigned: bool


def _read_inputs(
    baseline: Sequence[PathLike],
    candidate: Sequence[PathLike],
    *,
    fmt: str,
    tasks: frozenset[str] | None,
    score: str | None,
    pass_at_least: str | None,
    discovery: bool = False,
) -> _Inputs:
    from arci.importers import inspect_log, junit

    inputs: list[_InputFile] = []
    arms: dict[Arm, RoundMap] = {"baseline": {}, "candidate": {}}
    assigned = False
    id_types: dict[str, str] = {}
    selected_score = score
    for arm, paths in (("baseline", baseline), ("candidate", candidate)):
        arm = cast(Arm, arm)
        seen: set[tuple[str, int]] = set()
        inspect_count = 0
        for position, input_path in enumerate(paths, 1):
            path = str(input_path)
            try:
                path.encode("utf-8")
                parser = _format(path, fmt)
                if parser == "inspect":
                    inspect_count += 1
                    if inspect_count > 1 and not discovery:
                        raise OutcomeError(text("E9", arm=arm))
                data = Path(input_path).read_bytes()
                source = data.decode("utf-8-sig")
                # Discovery deduplicates between files, never within one file.
                file_seen = set[tuple[str, int]]() if discovery else seen
                if parser in {"csv", "jsonl"}:
                    parsed = _neutral(
                        source,
                        fmt=parser,
                        path=path,
                        arm=arm,
                        position=position,
                        tasks=tasks,
                        seen=file_seen,
                    )
                else:
                    kwargs: dict[str, Any] = dict(
                        path=path,
                        arm=arm,
                        position=position,
                        tasks=tasks,
                        seen=file_seen,
                        score=score,
                        pass_at_least=Fraction(pass_at_least)
                        if pass_at_least is not None
                        else None,
                    )
                    if parser == "junit":
                        parsed = junit.read(source, **kwargs)
                    else:
                        parsed = inspect_log.read(
                            source, **kwargs, expected_score=selected_score, known_id_types=id_types
                        )
                if parser == "inspect":
                    selected_score = parsed.score
                    for task, kind in parsed.id_types:
                        if task in id_types and id_types[task] != kind:
                            raise OutcomeError(text("E13", id=task))
                        id_types[task] = kind
                for row in parsed.rows:
                    arms[arm].setdefault(row.round, {})[row.task_id] = row.outcome
                if discovery:
                    for task, _ in parsed.id_types:
                        arms[arm].setdefault(1, {}).setdefault(task, None)
                inputs.append(
                    _InputFile(
                        path=path,
                        sha256=hash_bytes(data),
                        arm=arm,
                        format=parser,
                        rounds=parsed.rounds,
                    )
                )
                assigned |= parsed.assigned
            except OutcomeError:
                raise
            except Exception:
                raise OutcomeError(text("E6", path=path)) from None
    return _Inputs(tuple(inputs), arms["baseline"], arms["candidate"], assigned)


def _validate_rounds(data: _Inputs, rule: OutcomeRule) -> int:
    # E3 follows input order; E4 and E5 follow only after all labels are in range.
    for item in data.inputs:
        for r in item.rounds:
            if not 1 <= r <= rule.max_rounds:
                raise OutcomeError(text("E3", n=r, max_rounds=rule.max_rounds))
    for item in data.inputs:
        arm_rounds = data.baseline if item.arm == "baseline" else data.candidate
        for r in item.rounds:
            arm_rounds.setdefault(r, {})
    a, b = sorted(data.baseline), sorted(data.candidate)
    if any(rounds != list(range(1, len(rounds) + 1)) for rounds in (a, b)):
        raise OutcomeError(text("E4"))
    if a != b:
        raise OutcomeError(text("E5", baseline=a, candidate=b))
    if not a:
        raise OutcomeError(text("E16", arm="baseline"))
    return len(a)


def empty_decision(
    reason: str, rule: OutcomeRule | None = None, *, validated_rounds: int | None = None
) -> OutcomeDecision:
    """Return the fixed template, independent of any validated input prefix."""
    return OutcomeDecision.create(
        schema_version=OUTCOMES_SCHEMA_VERSION,
        rule=rule,
        rule_sha256=None if rule is None else rule_sha256(rule),
        normalisation=NORMALISATION,
        inputs=(),
        rounds_registered=0,
        rounds_supplied=0,
        last_round_evaluated=0,
        round_digests=(),
        history=(),
        tasks=(),
        stopped_at_round=0,
        verdict=Verdict.ERROR,
        exit_code=3,
        reasons=(reason,),
        statements=(text("F2"),),
        notices=(),
        previous_sha256=None,
    )


def _previous(path: PathLike) -> OutcomeDecision:
    try:
        raw = loads_json(Path(path).read_text(encoding="utf-8-sig"))
        # Bound the embedded rational before the record model converts it to Fraction.
        if isinstance(raw, dict) and isinstance(raw.get("rule"), dict):
            threshold = raw["rule"].get("pass_at_least")
            if threshold is not None:
                _signed_rational(threshold)
        previous = OutcomeDecision.model_validate(raw)
        if not previous.validate_seal():
            raise ValueError("seal invalid")
        rule = previous.rule
        if previous.verdict is Verdict.ERROR and previous.last_round_evaluated == 0:
            if (
                previous.inputs
                or previous.round_digests
                or previous.history
                or previous.tasks
                or previous.rounds_registered
                or previous.rounds_supplied
                or previous.stopped_at_round
                or previous.exit_code != 3
                or previous.previous_sha256 is not None
                or previous.notices
                or len(previous.reasons) != 1
                or (rule is None) != (previous.rule_sha256 is None)
                or (rule is not None and previous.rule_sha256 != rule_sha256(rule))
            ):
                raise ValueError("empty ERROR template inconsistent")
            if rule is not None:
                _rule_from_mapping(rule.model_dump(mode="json", exclude_none=True))
            return previous
        if rule is None or previous.rule_sha256 != rule_sha256(rule):
            raise ValueError("embedded rule digest mismatch")
        # Reapply full rule validation, including plan constraints, to the embedded rule.
        _rule_from_mapping(rule.model_dump(mode="json", exclude_none=True))
        k = previous.rounds_supplied
        last = previous.last_round_evaluated
        if not 1 <= last <= k <= rule.max_rounds:
            raise ValueError("round counts inconsistent")
        stopped = 0 if previous.verdict is Verdict.ERROR else last
        if previous.rounds_registered != rule.max_rounds or previous.stopped_at_round != stopped:
            raise ValueError("stopping round inconsistent")
        if previous.exit_code != EXIT_CODES[previous.verdict]:
            raise ValueError("exit code inconsistent")
        if [d.round for d in previous.round_digests] != list(range(1, k + 1)):
            raise ValueError("round digests must cover every supplied round")
        if [h.round for h in previous.history] != list(range(1, last + 1)):
            raise ValueError("history must cover every evaluated round")
        if previous.history[-1].verdict is not previous.verdict:
            raise ValueError("history verdict inconsistent")
        if previous.history[-1].reasons != previous.reasons:
            raise ValueError("history reasons inconsistent")
        if any(h.verdict is not Verdict.INCONCLUSIVE for h in previous.history[:-1]):
            raise ValueError("history continued after a decision")
        if previous.verdict is Verdict.INCONCLUSIVE and last != k:
            raise ValueError("inconclusive history incomplete")
        if tuple(t.task_id for t in previous.tasks) != rule.tasks:
            raise ValueError("task inventory inconsistent")
        for arm in ("baseline", "candidate"):
            rounds = {r for item in previous.inputs if item.arm == arm for r in item.rounds}
            if rounds != set(range(1, k + 1)):
                raise ValueError("input rounds inconsistent")
        for item in previous.inputs:
            if not item.rounds or tuple(sorted(set(item.rounds))) != item.rounds:
                raise ValueError("input rounds inconsistent")
        counts = previous.history[-1].counts
        for name in ("minus", "zero", "plus", "errored"):
            if sum(getattr(t.counts, name) for t in previous.tasks) != getattr(counts, name):
                raise ValueError("task counts inconsistent")
        for task in previous.tasks:
            if task.pairs != last or sum(task.counts.model_dump().values()) != last:
                raise ValueError("task pairs inconsistent")
            if max(task.baseline_successes, task.candidate_successes) > last:
                raise ValueError("task successes inconsistent")
            difference = task.candidate_successes - task.baseline_successes
            observed_difference = task.counts.plus - task.counts.minus
            if abs(difference - observed_difference) > task.counts.errored:
                raise ValueError("task successes inconsistent")
        before = SuiteCounts(minus=0, zero=0, plus=0, errored=0)
        increments: list[RoundIncrement] = []
        for look in previous.history:
            changes = [
                getattr(look.counts, key) - getattr(before, key)
                for key in ("minus", "zero", "plus", "errored")
            ]
            if min(changes) < 0 or sum(changes) != len(rule.tasks):
                raise ValueError("history counts inconsistent")
            increments.append(RoundIncrement(changes[0], changes[1], changes[2], changes[3], 0))
            before = look.counts
        expected = walk_rounds(rule_of(rule), increments)
        if len(expected) != last:
            raise ValueError("history continued after a decision")
        for actual, look in zip(previous.history, expected, strict=True):
            if (
                actual.pairs,
                actual.pass_wealth,
                actual.block_wealth,
                actual.pass_crossed,
                actual.block_crossed,
                actual.verdict,
            ) != (
                look.pairs,
                look.pass_wealth,
                look.block_wealth,
                look.pass_crossed,
                look.block_crossed,
                look.verdict,
            ):
                raise ValueError("history inference inconsistent")
            if actual.reasons != _reasons(look.reasons, rule):
                raise ValueError("history inference reasons inconsistent")
        return previous
    except Exception as exc:
        reason = "invalid record" if isinstance(exc, ValidationError) else str(exc).splitlines()[0]
        raise OutcomeError(text("E24", reason=reason)) from None


@dataclass
class _Counts:
    minus: int = 0
    zero: int = 0
    plus: int = 0
    errored: int = 0
    baseline_successes: int = 0
    candidate_successes: int = 0

    def add(self, a: OutcomeValue | None, b: OutcomeValue | None) -> None:
        self.baseline_successes += a == "pass"
        self.candidate_successes += b == "pass"
        if a in (None, "error") or b in (None, "error"):
            self.errored += 1
        else:
            difference = int(b == "pass") - int(a == "pass")
            self.minus += difference == -1
            self.zero += difference == 0
            self.plus += difference == 1

    def model(self) -> SuiteCounts:
        return SuiteCounts(minus=self.minus, zero=self.zero, plus=self.plus, errored=self.errored)


def _reasons(reasons: tuple[str, ...], rule: OutcomeRule) -> tuple[str, ...]:
    if rule.fixed_before_runs:
        return reasons
    replacements = {
        "non-inferiority established": text("F15"),
        "regression established": text("F16"),
    }
    return tuple(replacements.get(reason, reason) for reason in reasons)


def _infer(
    rule: OutcomeRule,
    data: _Inputs,
    k: int,
    digests: tuple[OutcomeRoundDigest, ...],
    previous: OutcomeDecision | None,
) -> OutcomeDecision:
    counts = {task: _Counts() for task in rule.tasks}

    def increments() -> Iterator[RoundIncrement]:
        for r in range(1, k + 1):
            current = _Counts()
            for task in rule.tasks:
                a, b = data.baseline[r].get(task), data.candidate[r].get(task)
                current.add(a, b)
                counts[task].add(a, b)
            yield RoundIncrement(current.minus, current.zero, current.plus, current.errored, 0)

    stats_rule = rule_of(rule)
    looks = walk_rounds(stats_rule, increments())
    last = looks[-1]
    history = tuple(
        OutcomeRoundLook(
            round=look.round,
            pairs=look.pairs,
            counts=look.counts,
            pass_wealth=look.pass_wealth,
            block_wealth=look.block_wealth,
            pass_crossed=look.pass_crossed,
            block_crossed=look.block_crossed,
            verdict=look.verdict,
            reasons=_reasons(look.reasons, rule),
        )
        for look in looks
    )
    statements = ([] if rule.fixed_before_runs else [text("F1")]) + [
        text("F2"),
        text("F3"),
        text("F4", k=k),
    ]
    if rule.fixed_before_runs:
        statements.extend(
            [text("F5"), text("F6", alpha=rule.alpha, bound=format_rational(stats_rule.alpha / 2))]
        )
    notices = list(check_rule_plan(stats_rule))
    if data.assigned:
        notices.append(text("F12"))
    notices.append(text("F7", k=k, N=rule.max_rounds))
    if last.verdict is Verdict.INCONCLUSIVE:
        # Positive tie factors make this crossing monotone. Binary search uses the same
        # exact integer wealth implementation; displayed wealth strings never decide.
        def reaches(extra_rounds: int) -> bool:
            passed = RunningWealth(stats_rule, 1)
            c = last.counts
            passed.advance(c.minus, c.zero + extra_rounds * len(rule.tasks), c.plus, c.errored)
            return passed.crossed()

        remaining = rule.max_rounds - last.round
        if remaining and reaches(remaining):
            low, high = 1, remaining
            while low < high:
                mid = (low + high) // 2
                if reaches(mid):
                    high = mid
                else:
                    low = mid + 1
            notices.append(text("F8", r=low, p=low * len(rule.tasks)))
        else:
            notices.append(text("F9"))
    if k > last.round:
        notices.append(text("F10", n=k - last.round))
    return OutcomeDecision.create(
        schema_version=OUTCOMES_SCHEMA_VERSION,
        rule=rule,
        rule_sha256=rule_sha256(rule),
        normalisation=NORMALISATION,
        inputs=tuple(
            OutcomeInput(
                path=item.path,
                sha256=item.sha256,
                arm=item.arm,
                format=item.format,
                rounds=tuple(item.rounds),
            )
            for item in data.inputs
        ),
        rounds_registered=rule.max_rounds,
        rounds_supplied=k,
        last_round_evaluated=last.round,
        round_digests=digests,
        history=history,
        tasks=tuple(
            OutcomeTaskCounts(
                task_id=task,
                pairs=last.round,
                baseline_successes=c.baseline_successes,
                candidate_successes=c.candidate_successes,
                counts=c.model(),
            )
            for task, c in counts.items()
        ),
        stopped_at_round=0 if last.verdict is Verdict.ERROR else last.round,
        verdict=last.verdict,
        exit_code=EXIT_CODES[last.verdict],
        reasons=_reasons(last.reasons, rule),
        statements=tuple(statements),
        notices=tuple(notices),
        previous_sha256=previous.record_sha256 if previous is not None else None,
    )


def decide_outcomes(
    rule_path: PathLike,
    baseline: Sequence[PathLike],
    candidate: Sequence[PathLike],
    *,
    fmt: str = "auto",
    previous: PathLike | None = None,
) -> OutcomeDecision:
    """Never raise: malformed inputs produce the fixed sealed ERROR template."""
    rule: OutcomeRule | None = None
    validated: int | None = None
    try:
        for arm, paths in (("baseline", baseline), ("candidate", candidate)):
            if not paths:
                raise OutcomeError(text("E16", arm=arm))
        rule = load_rule(rule_path)
        predecessor = _previous(previous) if previous is not None else None
        if predecessor is not None:
            if predecessor.verdict is Verdict.ERROR:
                raise OutcomeError(text("E25", path=previous))
            if predecessor.normalisation != NORMALISATION:
                raise OutcomeError(text("E27", v=predecessor.normalisation, w=NORMALISATION))
        data = _read_inputs(
            baseline,
            candidate,
            fmt=fmt,
            tasks=frozenset(rule.tasks),
            score=rule.score,
            pass_at_least=rule.pass_at_least,
        )
        k = _validate_rounds(data, rule)
        validated = k
        digests = tuple(
            OutcomeRoundDigest(
                round=r,
                outcomes_sha256=round_outcomes_sha256(
                    rule.tasks, data.baseline[r], data.candidate[r]
                ),
            )
            for r in range(1, k + 1)
        )
        if predecessor is not None:
            if predecessor.rounds_supplied > k:
                raise OutcomeError(text("E26", k=predecessor.rounds_supplied, j=k))
            if predecessor.rule is None or rule_sha256(predecessor.rule) != rule_sha256(rule):
                raise OutcomeError(text("E23", digest=predecessor.rule_sha256))
            for old, new in zip(predecessor.round_digests, digests, strict=False):
                if old.outcomes_sha256 != new.outcomes_sha256:
                    raise OutcomeError(text("E28", n=old.round))
        return _infer(rule, data, k, digests, predecessor)
    except OutcomeError as exc:
        return empty_decision(exc.reason, rule, validated_rounds=validated)
    except Exception:
        # Non-path caller misuse and unexpected malformed values remain non-green.
        return empty_decision(text("E6", path=rule_path), rule, validated_rounds=validated)


def discover_rule(
    paths: Sequence[PathLike], *, fmt: str = "auto", **options: object
) -> OutcomeRule:
    """Extract an inventory without imposing a run's round budget."""
    if not paths:
        raise OutcomeError(text("E16", arm="tasks"))
    score = options.get("score")
    threshold = options.get("pass_at_least")
    try:
        if score is not None and (not isinstance(score, str) or not score):
            raise ValueError("score must be a non-empty string")
        threshold = _signed_rational(threshold) if threshold is not None else None
    except ValueError as exc:
        raise OutcomeError(text("E15", reason=str(exc))) from None
    data = _read_inputs(
        paths, (), fmt=fmt, tasks=None, score=score, pass_at_least=threshold, discovery=True
    )
    tasks = sorted({task for values in data.baseline.values() for task in values})
    values: dict[str, object] = {
        "schema_version": OUTCOMES_SCHEMA_VERSION,
        "suite_id": "imported-outcomes",
        **options,
        "tasks": tasks,
        "fixed_before_runs": False,
    }
    try:
        return _rule_from_mapping(values)
    except Exception as exc:
        raise OutcomeError(text("E15", reason=str(exc).splitlines()[0])) from None
