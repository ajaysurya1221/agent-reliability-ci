"""T12: move the README's release pins to v0.8.0 in place (run on main after sprint/readme merges).

    python plan/exec/scripts/readme_release_pins.py [README.md]

Idempotent: prints what it changed; exits 1 if a pin it expects is missing.
"""

from __future__ import annotations

import sys
from pathlib import Path

PINS = [
    ("releases/tag/v0.7.0)", "releases/tag/v0.8.0)"),
    ("- uses: ajaysurya1221/agent-reliability-ci@v0.7.0", "- uses: ajaysurya1221/agent-reliability-ci@v0.8.0"),
    (
        "This example pins `v0.7.0`, the released feature set. The planner (`arci plan`), opt-in pass^k\n"
        "reporting (`arci report --pass-k`) and the later portability fixes are not in that tag; see the\n"
        "Unreleased section of [CHANGELOG.md](https://github.com/ajaysurya1221/agent-reliability-ci/blob/main/CHANGELOG.md).",
        "This example pins `v0.8.0`, the released feature set (the Action installs that tag's source; the\n"
        "same code is on PyPI as `agent-reliability-ci==0.8.0`). See\n"
        "[CHANGELOG.md](https://github.com/ajaysurya1221/agent-reliability-ci/blob/main/CHANGELOG.md).",
    ),
    (
        "**Availability:** main adds the packaged demo (`arci demo`), the descriptor (`arci.yaml`, `arci schema`),\n"
        "`arci init`, the planner (`arci plan`), opt-in pass^k reporting (`arci report --pass-k`) and portability\n"
        "fixes beyond v0.7.0; the v0.8.0 release and the PyPI package follow this sprint.",
        "**Availability:** v0.8.0 is on PyPI as `agent-reliability-ci` and as the Action tag `v0.8.0`; it adds the\n"
        "packaged demo (`arci demo`), the descriptor (`arci.yaml`, `arci schema`), `arci init`, the planner\n"
        "(`arci plan`), opt-in pass^k reporting (`arci report --pass-k`) and portability fixes over v0.7.0.",
    ),
]


def main(argv: list[str]) -> int:
    path = Path(argv[1]) if len(argv) > 1 else Path("README.md")
    text = path.read_text(encoding="utf-8")
    missing = [old for old, new in PINS if old not in text and new not in text]
    if missing:
        for old in missing:
            print("missing pin:", old.splitlines()[0])
        return 1
    changed = 0
    for old, new in PINS:
        if old in text:
            text = text.replace(old, new)
            changed += 1
    path.write_text(text, encoding="utf-8")
    print(f"pins updated: {changed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
