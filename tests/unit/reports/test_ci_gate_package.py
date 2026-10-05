"""Fast guard for the ci-gate-2026-10-06 evidence package (no subprocess, no network).

It re-implements, independently of `reproduce.py`, three properties of
`docs/reports/ci-gate-2026-10-06/`:

1. `evidence-index.json` lists every package file except `reproduce.py`, the index and
   `SHA256SUMS` (Python/OS caches ignored), and its hashes and sizes are current;
2. `SHA256SUMS` lists the same set and every digest matches;
3. `REPORT.md` holds no `<<...>>` placeholder outside the families the orchestrator still fills
   (`REPRO`, `WP3`, `PLANNER`); the tolerated ones are printed (`pytest -s` shows them).

Release mode: set `ARCI_REPORT_STRICT=1` and no placeholder at all is tolerated. The same rule is
`reproduce.py --check --strict`. After any edit to a package file, re-run
`.venv/bin/python docs/reports/ci-gate-2026-10-06/reproduce.py --index`.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import cast

PACKAGE = Path(__file__).resolve().parents[3] / "docs" / "reports" / "ci-gate-2026-10-06"
INDEX = PACKAGE / "evidence-index.json"
SUMS = PACKAGE / "SHA256SUMS"
NOT_INDEXED = {"reproduce.py", "evidence-index.json", "SHA256SUMS"}
IGNORED = {"__pycache__", ".DS_Store"}
ALLOWED_FAMILIES = {"REPRO", "WP3", "PLANNER"}
STRICT_ENV = "ARCI_REPORT_STRICT"


def _package_files() -> set[str]:
    return {
        path.relative_to(PACKAGE).as_posix()
        for path in PACKAGE.rglob("*")
        if path.is_file()
        and not IGNORED.intersection(path.relative_to(PACKAGE).parts)
        and path.relative_to(PACKAGE).as_posix() not in NOT_INDEXED
    }


def _sha256(name: str) -> str:
    return hashlib.sha256((PACKAGE / name).read_bytes()).hexdigest()


def _sums() -> dict[str, str]:
    listed: dict[str, str] = {}
    for line in SUMS.read_text("utf-8").splitlines():
        match = re.fullmatch(r"([0-9a-f]{64}) [ *](.+)", line)
        assert match is not None, f"not sha256sum format: {line!r}"
        assert match.group(2) not in listed, f"listed twice: {match.group(2)}"
        listed[match.group(2)] = match.group(1)
    return listed


def _family(placeholder: str) -> str | None:
    match = re.match(r"\s*([A-Z][A-Z0-9_]*)\s*:", placeholder[2:-2])
    return match.group(1) if match else None


def test_index_covers_every_package_file() -> None:
    index = cast(dict[str, object], json.loads(INDEX.read_text("utf-8")))
    entries = cast(list[dict[str, object]], index["files"])
    paths = [str(entry["path"]) for entry in entries]
    assert paths == sorted(paths), "index order is not deterministic"
    assert set(paths) == _package_files()
    for entry in entries:
        name = str(entry["path"])
        assert entry["sha256"] == _sha256(name), f"stale index entry: {name}"
        assert entry["size"] == (PACKAGE / name).stat().st_size, f"stale size: {name}"
        assert entry["what"] and entry["proves"], f"undescribed: {name}"
    assert re.fullmatch(r"[0-9a-f]{40}", str(index["source_commit"]))


def test_sha256sums_match_the_files() -> None:
    listed = _sums()
    assert set(listed) == _package_files()
    stale = sorted(name for name, digest in listed.items() if _sha256(name) != digest)
    assert not stale, f"sha256 differs: {stale}"


def test_report_placeholders_are_only_the_tolerated_families() -> None:
    text = (PACKAGE / "REPORT.md").read_text("utf-8")
    found = [match.group(0) for match in re.finditer(r"<<(.*?)>>", text, re.DOTALL)]
    for placeholder in found:
        print(f"REPORT.md placeholder: {placeholder}")
    if os.environ.get(STRICT_ENV) == "1":
        assert not found, f"{STRICT_ENV}=1: {len(found)} placeholders left in REPORT.md"
    unknown = [item for item in found if _family(item) not in ALLOWED_FAMILIES]
    assert not unknown, f"placeholders outside {sorted(ALLOWED_FAMILIES)}: {unknown}"
