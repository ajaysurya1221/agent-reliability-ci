"""Build fresh edited server copies and verify exactly one changed file per package."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from tasks.f2_parity import edited_entry  # noqa: E402

CELLS = ("F1", "F2", "G1")


def git_package(env: Path) -> Path:
    (package,) = (env / "py/lib").glob("python*/site-packages/mcp_server_git")
    return package


def hashes(root: Path) -> dict[str, str]:
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def build(env: Path, destination: Path, cell: str) -> Path:
    if cell not in CELLS:
        raise ValueError("unknown edit")
    modules = (env / "node/node_modules").resolve(strict=True)
    source = (
        git_package(env) if cell == "G1" else modules / "@modelcontextprotocol/server-filesystem"
    )
    target = destination.resolve() / cell
    if target.exists() or "node_modules" in target.parts or target.is_relative_to(source.resolve()):
        raise ValueError("edited destination must be fresh and outside installed packages")
    target.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=target.parent) as stage:
        tree = Path(stage) / cell
        copy = tree / (source.name if cell == "G1" else "package")
        before = hashes(source)
        shutil.copytree(source, copy)
        if hashes(copy) != before:
            raise ValueError("package copy differs before editing")
        patch = HERE / "edits" / f"{cell}.diff"
        subprocess.run(
            ["/usr/bin/patch", "-F", "0", "-p1", "-i", str(patch)],
            cwd=copy,
            stdin=subprocess.DEVNULL,
            check=True,
            capture_output=True,
        )
        after = hashes(copy)
        expected = "server.py" if cell == "G1" else "dist/server.js"
        if (
            before.keys() != after.keys()
            or [k for k in before if before[k] != after[k]] != [expected]
            or hashes(source) != before
        ):
            raise ValueError("edit changed unexpected files")
        if cell == "F2":
            reference = Path(stage) / "reference"
            reference.mkdir()
            registry = json.loads((HERE.parent / "tasks/tasks.json").read_bytes())
            expected_entry = edited_entry(env, reference, registry["cells"]["F2"])
            if expected_entry.with_name("server.js").read_bytes() != (copy / expected).read_bytes():
                raise ValueError(
                    "published F2 patch differs from the registered predicate or sentence"
                )
        if cell != "G1":
            (tree / "node_modules").symlink_to(modules, target_is_directory=True)
        (tree / "digests.json").write_text(
            json.dumps(
                {
                    "cell": cell,
                    "patch_sha256": hashlib.sha256(patch.read_bytes()).hexdigest(),
                    "before": before,
                    "after": after,
                },
                sort_keys=True,
                indent=2,
            )
            + "\n"
        )
        tree.rename(target)
    return target


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("env", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--cell", choices=CELLS, action="append")
    args = parser.parse_args()
    for cell in args.cell or CELLS:
        print(build(args.env, args.out or args.env / "edited", cell))


if __name__ == "__main__":
    main()
