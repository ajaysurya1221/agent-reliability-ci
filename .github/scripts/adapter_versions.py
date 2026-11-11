"""Fail unless the installed adapter packages are exactly the ones a constraints file names."""

from __future__ import annotations

import sys
from importlib.metadata import version
from pathlib import Path


def main(path: str) -> int:
    wanted = dict(
        line.split("==") for line in Path(path).read_text().split() if line and "==" in line
    )
    found = {name: version(name) for name in wanted}
    for name in wanted:
        print(f"{name}: installed {found[name]}, expected {wanted[name]}")
    return 0 if found == wanted and wanted else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
