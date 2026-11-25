"""Fail the neutral rehearsal if any kept evidence contains the operator's HOME."""

from __future__ import annotations

import os
import sys
from collections import Counter
from pathlib import Path

from harness.clean_row import safe_bytes


def scan(root: Path) -> Counter[str]:
    home = os.environ["HOME"]
    if not home or home == "/":
        raise ValueError("expected the operator's HOME")
    counts: Counter[str] = Counter()
    for path in sorted(root.rglob("*")):
        # Package copies and the staged node executable are inputs, never traverse
        # linked dependency directories. Include every file of each output store.
        rel = path.relative_to(root)
        if not path.is_file() or path.is_symlink():
            continue
        if path.suffix in (".yaml", ".yml"):
            group = "descriptors"
        elif "stores" in rel.parts:
            group = "store files"
        elif "receipts" in rel.parts or path.name in ("ledger.jsonl", "receipts.jsonl"):
            group = "receipts and ledgers"
        elif path.suffix == ".log":
            group = "logs"
        elif rel.parts[0] != "bin" and "edited" not in rel.parts:
            group = "other evidence"
        else:
            continue
        try:
            safe_bytes(path.read_bytes(), {home.casefold()})
        except ValueError as exc:
            raise ValueError(f"privacy check failed in {rel}: {exc}") from exc
        counts[group] += 1
    if not all(counts[k] for k in ("descriptors", "store files", "receipts and ledgers")):
        raise ValueError("privacy check missing an evidence class")
    return counts


if __name__ == "__main__":
    counts = scan(Path(sys.argv[1]))
    if not counts["logs"]:
        raise ValueError("privacy check missing run logs")
    print("HOME scan clean:", ", ".join(f"{n} {k}" for k, n in sorted(counts.items())))
