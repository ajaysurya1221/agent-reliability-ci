"""Compare the newest published client versions against the ones the readers were checked
against.

Takes no network access itself: it reads the two latest published versions from the
command line and the checked versions from `docs/LOG_FORMATS.md`, then prints the body for
the tracking issue (or nothing). The workflow (`.github/workflows/client-versions.yml`)
supplies the two arguments from `npm view`, and uses the printed text (or its absence) to
decide whether to create or update the issue. This lets the comparison be tested without a
network.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

CLAUDE_CODE = "Claude Code"
CODEX = "Codex CLI"

_SENTENCE = re.compile(
    r"checked against Claude Code client versions(?P<claude>.*?)"
    r"and Codex CLI versions(?P<codex>.*?) on one machine",
    re.DOTALL,
)
_VERSION = re.compile(r"[0-9]+(?:\.[0-9]+)*")


def version_tuple(raw: str) -> tuple[int, ...]:
    """Parse a dotted version string into a tuple compared numerically, part by part."""
    parts: list[int] = []
    for part in raw.split("."):
        match = re.match(r"[0-9]+", part)
        parts.append(int(match.group()) if match is not None else 0)
    return tuple(parts)


def highest_checked(text: str) -> tuple[str, str]:
    """Return the highest Claude Code and Codex CLI versions docs/LOG_FORMATS.md names."""
    match = _SENTENCE.search(text)
    if match is None:
        raise ValueError("docs/LOG_FORMATS.md: could not find the checked-versions sentence")
    claude_versions = _VERSION.findall(match["claude"])
    codex_versions = _VERSION.findall(match["codex"])
    if not claude_versions or not codex_versions:
        raise ValueError("docs/LOG_FORMATS.md: found no version numbers in the checked sentence")
    return (
        max(claude_versions, key=version_tuple),
        max(codex_versions, key=version_tuple),
    )


def issue_body(
    checked_claude_code: str, checked_codex: str, latest_claude_code: str, latest_codex: str
) -> str:
    return (
        "A newer client version was published than the one the session-log readers were\n"
        "checked against. For each line below, run the format tests against a session of\n"
        "the new client version, then add that version to docs/LOG_FORMATS.md.\n"
        "\n"
        f"- {CLAUDE_CODE}: checked up to {checked_claude_code}, latest published "
        f"{latest_claude_code}\n"
        f"- {CODEX}: checked up to {checked_codex}, latest published {latest_codex}\n"
    )


def log_formats_path() -> Path:
    return Path(__file__).resolve().parents[2] / "docs" / "LOG_FORMATS.md"


def compare(latest_claude_code: str, latest_codex: str, log_formats_text: str) -> str:
    """Return the issue body when either client has a version newer than checked, else ""."""
    checked_claude_code, checked_codex = highest_checked(log_formats_text)
    newer = version_tuple(latest_claude_code) > version_tuple(checked_claude_code) or (
        version_tuple(latest_codex) > version_tuple(checked_codex)
    )
    return (
        issue_body(checked_claude_code, checked_codex, latest_claude_code, latest_codex)
        if newer
        else ""
    )


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: client_versions.py LATEST_CLAUDE_CODE LATEST_CODEX", file=sys.stderr)
        return 2
    latest_claude_code, latest_codex = argv
    # The values come from a registry; only a plain version may reach the issue body.
    for value in argv:
        if re.fullmatch(r"[0-9]{1,6}(?:\.[0-9]{1,6}){1,3}(?:-[0-9A-Za-z.]{1,40})?", value) is None:
            print("client_versions.py: not a version string", file=sys.stderr)
            return 2
    body = compare(latest_claude_code, latest_codex, log_formats_path().read_text(encoding="utf-8"))
    sys.stdout.write(body)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
