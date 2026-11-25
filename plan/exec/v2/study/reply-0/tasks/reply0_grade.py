"""Reply-0 answer-only grading. The same rule covers a scalar and one key per set line."""

from __future__ import annotations

import re
import unicodedata

MAX_CHARS = 600
WRAPPERS = """ \"'`“”‘’()[]{}"""  # noqa: RUF001 (registered quotation marks)


def normalise(text: str) -> str:
    value = " ".join(unicodedata.normalize("NFKC", text).casefold().split())
    # A leading dot or sign can change a number. Only a terminal sentence mark is removed.
    value = value.strip(WRAPPERS).removesuffix(".").strip(WRAPPERS)
    if re.fullmatch(r"[0-9]{1,3}(?:,[0-9]{3})+", value):
        return value.replace(",", "")
    return value


def passes(answer: object, expect: list[str], decoys: list[str]) -> bool:
    """Compare complete normalised lines; duplicates, commentary and alternatives fail."""
    if not isinstance(answer, str) or len(answer) > MAX_CHARS or not expect:
        return False
    lines = sorted(normalise(line) for line in answer.strip().splitlines())
    keys = sorted(normalise(key) for key in expect)
    return lines == keys and not set(lines).intersection(map(normalise, decoys))
