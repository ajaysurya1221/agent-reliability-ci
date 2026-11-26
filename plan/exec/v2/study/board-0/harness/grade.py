"""Board-0 final text scoring against a seeded desk snapshot."""

import re
from collections.abc import Iterator
from decimal import Decimal

NUMBER = re.compile(r"(?<![\d.,])(?:\d{1,3}(?:,\d{3})+|\d+)(?![\d]|[.,]\d)")


def scalars(node: object) -> Iterator[int | str]:
    if isinstance(node, dict):
        for value in node.values():
            yield from scalars(value)
    elif isinstance(node, list):
        for value in node:
            yield from scalars(value)
    elif type(node) is int or isinstance(node, str):
        yield node


def grade(text: str | None, key: int | str, snapshot: object, row_id: str) -> tuple[bool, bool]:
    """Return the trial grade and the display-only exact match."""
    if not text:
        return False, False
    exact = text.strip().removesuffix(".") == str(key)
    answer = text.replace(row_id, "") if row_id else text
    candidates = {v for v in scalars(snapshot) if type(v) is type(key)} | {key}
    if isinstance(key, int):
        # Decimal preserves arbitrarily long digit tokens and accepts Unicode decimal digits.
        values = {Decimal(m[0].replace(",", "")) for m in NUMBER.finditer(answer)}
        return candidates.intersection(values) == {key}, exact

    words = sorted((s for s in candidates if isinstance(s, str) and s), key=len, reverse=True)
    # [^\W_] is Python's Unicode alphanumeric class.
    pattern = r"(?<![^\W_])(?:" + "|".join(map(re.escape, words)) + r")(?![^\W_])"
    return set(re.findall(pattern, answer)) == {key}, exact
