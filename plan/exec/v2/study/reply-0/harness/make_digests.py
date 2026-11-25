"""Hash exactly the inputs the Reply-0 launch preflight requires, including its fixture."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from tempfile import NamedTemporaryFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from harness.wiring_check import LIST, digest_list  # noqa: E402


def main() -> None:
    if not any((ROOT / "harness/tests/blind").rglob("*.py")):
        raise ValueError("missing independent counter tests")
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=ROOT / LIST)
    output = parser.parse_args().out
    data = digest_list().encode("utf-8")
    with NamedTemporaryFile(dir=output.parent, delete=False) as tmp:
        tmp.write(data)
    os.replace(tmp.name, output)
    print(f"Wrote {len(data.splitlines())} entries to {output.name}")


if __name__ == "__main__":
    main()
