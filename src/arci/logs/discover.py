"""Locate log files without reading their contents or rendering paths."""

import os
from collections.abc import Mapping
from pathlib import Path


def claude_root(env: Mapping[str, str], home: Path) -> Path:
    config = env.get("CLAUDE_CONFIG_DIR")
    return (Path(config) if config else home / ".claude") / "projects"


def codex_root(env: Mapping[str, str], home: Path) -> Path:
    config = env.get("CODEX_HOME")
    return Path(config) if config else home / ".codex"


def claude_files(root: Path) -> list[Path]:
    found: list[Path] = []
    try:
        for directory, _, names in os.walk(root):
            found.extend(
                Path(directory) / name
                for name in names
                if name.endswith(".jsonl")
                and name != "journal.jsonl"
                and (Path(directory) / name).is_file()
            )
    except (OSError, ValueError):
        pass
    return sorted(found, key=lambda path: path.relative_to(root).as_posix())


def codex_files(root: Path) -> list[Path]:
    found: list[Path] = []
    for folder in ("sessions", "archived_sessions"):
        try:
            for directory, _, names in os.walk(root / folder):
                found.extend(
                    Path(directory) / name
                    for name in names
                    if name.startswith("rollout-")
                    and name.endswith((".jsonl", ".jsonl.zst"))
                    and (Path(directory) / name).is_file()
                )
        except (OSError, ValueError):
            pass
    return sorted(found, key=lambda path: path.relative_to(root).as_posix())
