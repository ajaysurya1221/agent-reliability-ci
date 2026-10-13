"""Count the words of the README first screen: everything before the first '## ' heading.

    python plan/exec/scripts/first_screen_words.py [README.md]

Exit 1 when the count exceeds 200 (the memo's limit). Code fences, HTML tags and badge lines are
counted as words only where they carry prose; commands count (a reader reads them).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


def first_screen(text: str) -> str:
    out: list[str] = []
    for line in text.splitlines():
        if line.startswith("## "):
            break
        out.append(line)
    return "\n".join(out)


def count_words(text: str) -> int:
    stripped = re.sub(r"<[^>]+>", " ", text)  # html tags
    stripped = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", stripped)  # images
    stripped = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", stripped)  # keep link text
    stripped = stripped.replace("```", " ")
    return len([w for w in stripped.split() if w not in {"#", "**", "bash"}])


def main(argv: list[str]) -> int:
    path = Path(argv[1]) if len(argv) > 1 else Path("README.md")
    screen = first_screen(path.read_text(encoding="utf-8"))
    n = count_words(screen)
    print(f"first screen: {n} words (limit 200)")
    return 0 if n <= 200 else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
