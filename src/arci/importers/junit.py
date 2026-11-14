"""Read JUnit XML as one logical round, preserving every test case."""

from __future__ import annotations

import re
from fractions import Fraction
from xml.etree import ElementTree

from arci.importers import OutcomeError, OutcomeValue, ParsedInput, Row, check_identity
from arci.outcome_report import text as fixed_text


def read(
    text: str,
    *,
    path: str,
    arm: str,
    position: int,
    tasks: frozenset[str] | None,
    seen: set[tuple[str, int]],
    score: str | None = None,
    pass_at_least: Fraction | None = None,
) -> ParsedInput:
    """The caller decodes UTF-8 before this parser examines declarations."""
    source = text.removeprefix("\ufeff")
    if re.search(r"<!DOCTYPE|<!ENTITY", source, re.IGNORECASE):
        raise OutcomeError(fixed_text("E6", path=path))
    declaration = re.match(r"<\?xml\b(.*?)\?>", source, re.DOTALL)
    if declaration is not None:
        encoding = re.search(r"\bencoding\s*=\s*(['\"])(.*?)\1", declaration[1])
        if encoding is not None and encoding[2].lower() not in {"utf-8", "utf8"}:
            raise OutcomeError(fixed_text("E6", path=path))
    try:
        root = ElementTree.fromstring(source)
    except (ElementTree.ParseError, ValueError) as error:
        raise OutcomeError(fixed_text("E6", path=path)) from error
    if root.tag not in {"testsuite", "testsuites"}:
        raise OutcomeError(fixed_text("E6", path=path))
    rows: list[Row] = []
    for case in root.iter("testcase"):
        classname, name = case.get("classname"), case.get("name")
        if not classname or not name:
            raise OutcomeError(fixed_text("E29", path=path))
        task_id = f"{classname}::{name}"
        check_identity(task_id, position, arm=arm, tasks=tasks, seen=seen)
        statuses = {child.tag for child in case}
        outcome: OutcomeValue = (
            "error"
            if statuses & {"error", "skipped"}
            else "fail"
            if "failure" in statuses
            else "pass"
        )
        rows.append(Row(task_id, position, outcome))
    return ParsedInput(tuple(rows), (position,), assigned=True)
