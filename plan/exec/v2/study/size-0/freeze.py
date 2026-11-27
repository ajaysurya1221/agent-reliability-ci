"""Local freeze for both days and the released compiler's manifest identities."""

import hashlib
import os
import re
import subprocess
import sys
from importlib.metadata import version
from pathlib import Path
from tempfile import TemporaryDirectory

from assignments import assignments
from claims import claims_dir
from descriptors import REG, RUNS, Row, descriptor, encoded, models, read
from records import require

from arci.descriptor import compile_run_descriptor
from arci.suite_schema import SuiteManifest

VERSIONS = {
    "agent-reliability-ci": "2.4.1",
    "langchain": "1.4.10",
    "langchain-core": "1.7.7",
    "langgraph": "1.2.20",
    "langgraph-prebuilt": "1.1.1",
    "langchain-ollama": "1.1.0",
    "ollama": "0.6.3",
    "pydantic": "2.14.3",
}


def versions() -> None:
    require(sys.version_info[:3] == (3, 13, 12), "Run 6 requires Python 3.13.12")
    for name, expected in VERSIONS.items():
        require(version(name) == expected, f"{name} version differs")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sources(root: Path) -> dict[str, str]:
    files = [
        root / name
        for name in (
            REG,
            "models.json",
            "slots.json",
            ".gitignore",
            "pyrightconfig.json",
            "request-template.json",
        )
    ]
    for pattern in (
        "*.py",
        "*.sh",
        "*.md",
        "*.example.json",
        "agent/*",
        "tests/*.py",
        "tests/*.sh",
    ):
        files.extend(p for p in root.glob(pattern) if p.is_file())
    return {str(p.relative_to(root)): sha(p.read_bytes()) for p in sorted(set(files))}


def prepare(root: Path) -> None:
    roster = models(root)
    require(not any((claims_dir() / r).exists() for r in RUNS), "claims already exist")
    with TemporaryDirectory(dir=root) as staging:
        stage = Path(staging)
        pins: Row = {}
        all_seeds: set[int] = set()
        for run in RUNS:
            path = stage / (run + ".yaml")
            path.write_bytes(encoded(descriptor(root, run, roster[run.split("-")[2]])))
            manifest = compile_run_descriptor(path)
            assert isinstance(manifest, SuiteManifest)
            rows = assignments(root, run, roster[run.split("-")[2]], manifest)
            seeds = {r["seed"] for r in rows}
            require(all_seeds.isdisjoint(seeds), "scenario seeds overlap")
            all_seeds.update(seeds)
            binding = stage / (run + ".assignments.json")
            binding.write_bytes(encoded(rows))
            pins[path.name] = {
                "sha256": sha(path.read_bytes()),
                "manifest": manifest.record_sha256,
                "experiment": manifest.experiment_id,
                "assignments": sha(binding.read_bytes()),
            }
        (stage / "descriptors.json").write_bytes(encoded(pins))
        (stage / "inputs.json").write_bytes(encoded(sources(root)))
        dest = root / "prepared"
        if dest.exists():
            verify(root)
            require(
                all((dest / p.name).read_bytes() == p.read_bytes() for p in stage.iterdir()),
                "prepared freeze differs",
            )
        else:
            stage.rename(dest)


def verify(root: Path) -> None:
    prepared = root / "prepared"
    require(read(prepared / "inputs.json") == sources(root), "input digest list differs")
    roster = models(root)
    pins = read(prepared / "descriptors.json")
    names = {r + ".yaml" for r in RUNS}
    require(
        set(pins) == names
        and {p.name for p in prepared.iterdir()}
        == names | {r + ".assignments.json" for r in RUNS} | {"inputs.json", "descriptors.json"},
        "descriptor inventory differs",
    )
    for name in sorted(names):
        p = prepared / name
        require(
            not p.is_symlink() and sha(p.read_bytes()) == pins[name]["sha256"],
            f"descriptor digest differs: {name}",
        )

        run = p.stem
        row = roster[run.split("-")[2]]
        require(
            p.read_bytes() == encoded(descriptor(root, run, row)),
            f"regenerated descriptor differs: {name}",
        )
        compiled = compile_run_descriptor(p)
        assert isinstance(compiled, SuiteManifest)
        bindings = prepared / (run + ".assignments.json")
        require(
            pins[name]
            == {
                "sha256": sha(p.read_bytes()),
                "manifest": compiled.record_sha256,
                "experiment": compiled.experiment_id,
                "assignments": sha(bindings.read_bytes()),
            }
            and bindings.read_bytes() == encoded(assignments(root, run, row, compiled)),
            f"compiled freeze differs: {name}",
        )


def published(root: Path, *, checkout: Path | None = None) -> str:
    source = checkout or root

    def git(*args: str) -> bytes:
        return subprocess.check_output(
            ["git", "--no-optional-locks", *args],
            cwd=source,
            stdin=subprocess.DEVNULL,
            env=os.environ | {"GIT_NO_LAZY_FETCH": "1"},
            timeout=15,
        )

    # Keep permanent claims at one checkout across branches and linked worktrees.
    common = Path(git("rev-parse", "--path-format=absolute", "--git-common-dir").decode().strip())
    repo = Path(git("rev-parse", "--show-toplevel").decode().strip())
    require(common.parent == repo and not root.is_symlink(), "real requires primary checkout")
    require(not any(root.rglob("__pycache__")), "bytecode cache in study")
    receipt = (claims_dir() / "push-receipt.txt").read_text()
    match = re.fullmatch(r"([0-9a-f]{40}) refs/heads/v2/phase0\n?", receipt)
    require(match, "invalid push receipt")
    assert match
    commit = match[1]
    require(
        git("merge-base", commit, "refs/remotes/origin/v2/phase0").decode().strip() == commit,
        "unpublished registration",
    )
    for path in [*(root / n for n in sources(root)), *(root / "prepared").iterdir()]:
        require(path == path.resolve(), f"linked input {path.name}")
        require(
            git(
                "cat-file",
                "blob",
                f"{commit}:{(source / path.relative_to(root)).relative_to(repo)}",
            )
            == path.read_bytes(),
            f"upstream input differs: {path.name}",
        )
    reg = (root / REG).read_text().strip()
    require(reg and "PLACEHOLDER" not in reg, "placeholder registration")
    return commit
