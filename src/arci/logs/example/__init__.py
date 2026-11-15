"""Locate the installed, generated example without writing or extracting files."""

from datetime import datetime
from pathlib import Path


def load() -> tuple[Path, Path, datetime]:
    root = Path(__file__).parent
    return (
        root / "claude",
        root / "codex",
        datetime.fromisoformat((root / "now.txt").read_text(encoding="utf-8").strip()),
    )
