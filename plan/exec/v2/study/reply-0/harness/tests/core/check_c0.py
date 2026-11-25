"""Section 12.3. Run a registered C0 pair and check the ledger, recording and receipt."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from harness.make_suites import FX, register  # noqa: E402
from tasks.check_tasks import check_control, exercise  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--stdio", action="store_true", help="component test without a sealed store"
    )
    args = parser.parse_args()
    env = Path(sys.executable).parent.parent.parent
    doc = register()
    cell = doc["cells"]["C0"]
    task = cell["main"][0]
    with TemporaryDirectory() as folder, TemporaryDirectory() as world:
        ref = check_control(env, Path(world), task, cell)
        exercise(env, FX, Path(folder), doc, "C0", task, ref, "corrected", pipes=args.stdio)
    mode = "stdio boundary components" if args.stdio else "sealed arci run"
    print(f"C0 {mode}: both seeded lookups, injections, first requests and corrected answers match")


if __name__ == "__main__":
    main()
