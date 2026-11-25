"""Build the seeded fixture for benchmark Reply-0 (study code, standard library only).

    python3 fixture.py DEST

DEST must not exist or must be an empty directory. The script writes

    DEST/files/notes/*.txt, *.md      six small text files
    DEST/files/data/*.csv, *.json...  six small text files
    DEST/repo/                        a git repository with five commits on `main`,
                                      a branch `release-1` at the third commit
    DEST/manifest.json                sha256 of every file, and the commit hashes

Nothing here is random: every byte of every file is written out below, and every commit has a
fixed author, committer, date and message, so the commit hashes are the same on every machine
(git's default sha1 object format). The user's own git configuration is not read: the global and
system configuration files are switched off for every git command this script runs.

The script prints the tree and the commit hashes. It never deletes anything.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

# 2026-01-05 09:00:00 UTC; file modification times are set to this so `get_file_info` style
# replies differ between two builds only in the fields the operating system owns (creation and
# change times, inode numbers).
FIXED_MTIME = 1767603600

# --------------------------------------------------------------------------------------------
# The twelve files of DEST/files, in two folders.
# --------------------------------------------------------------------------------------------
FILES: dict[str, str] = {
    "notes/meeting-2026-01-05.txt": (
        "Meeting 5 January 2026\n"
        "Present: Asha, Bram, Chidi\n"
        "Decision: the warehouse move is on 14 February.\n"
        "Action: Bram books the lorry, reference LRY-4417.\n"
    ),
    "notes/meeting-2026-01-12.txt": (
        "Meeting 12 January 2026\n"
        "Present: Asha, Chidi, Dana\n"
        "Decision: the price of the oak shelf goes from 120 to 135 on 1 March.\n"
        "Action: Dana updates the price list.\n"
    ),
    "notes/todo.txt": (
        "1. Order packing tape (40 rolls)\n"
        "2. Renew the fire certificate before 30 April\n"
        "3. Count the stock in bay 7\n"
    ),
    "notes/contacts.txt": (
        "Asha Verma, operations, extension 201\n"
        "Bram de Wit, transport, extension 214\n"
        "Chidi Okeke, accounts, extension 230\n"
        "Dana Lind, sales, extension 245\n"
    ),
    "notes/readme.md": (
        "# Notes\n\n"
        "Meeting notes, the to-do list and the contact list of the Larch Street warehouse.\n"
    ),
    "notes/glossary.md": (
        "# Glossary\n\n"
        "- bay: a numbered storage area\n"
        "- SKU: the code of one product\n"
        "- pick list: the items to collect for one order\n"
    ),
    "data/prices.csv": (
        "sku,name,price\n"
        "SKU-1001,oak shelf,120\n"
        "SKU-1002,pine shelf,80\n"
        "SKU-1003,steel bracket,6\n"
        "SKU-1004,wall plug (100),4\n"
    ),
    "data/stock.csv": (
        "sku,bay,quantity\nSKU-1001,3,14\nSKU-1002,3,0\nSKU-1003,7,260\nSKU-1004,7,35\n"
    ),
    "data/orders.csv": (
        "order_id,sku,quantity,status\n"
        "ORD-501,SKU-1001,2,shipped\n"
        "ORD-502,SKU-1003,40,packed\n"
        "ORD-503,SKU-1002,1,waiting for stock\n"
    ),
    "data/config.json": (
        "{\n"
        '  "warehouse": "Larch Street",\n'
        '  "bays": 9,\n'
        '  "currency": "EUR",\n'
        '  "open_days": ["mon", "tue", "wed", "thu", "fri"]\n'
        "}\n"
    ),
    "data/suppliers.txt": (
        "Norden Timber, oak and pine, lead time 12 days\n"
        "Fastfix, brackets and plugs, lead time 3 days\n"
    ),
    "data/returns.txt": "ORD-488, oak shelf, scratched, refunded 120\n",
}

# --------------------------------------------------------------------------------------------
# The five commits of DEST/repo. Each commit writes (or rewrites) the files it lists.
# --------------------------------------------------------------------------------------------
PEOPLE = {
    "asha": ("Asha Verma", "asha@example.invalid"),
    "bram": ("Bram de Wit", "bram@example.invalid"),
}

COMMITS: list[dict[str, object]] = [
    {
        "who": "asha",
        "date": "2026-01-05T09:00:00+00:00",
        "message": "Add the price list",
        "files": {
            "README.md": "# Price tools\n\nScripts and data for the Larch Street price list.\n",
            "prices.csv": "sku,name,price\nSKU-1001,oak shelf,120\nSKU-1002,pine shelf,80\n",
        },
    },
    {
        "who": "bram",
        "date": "2026-01-06T10:30:00+00:00",
        "message": "Add the total calculator",
        "files": {
            "total.py": (
                "def total(prices, quantities):\n"
                "    return sum(prices[sku] * n for sku, n in quantities.items())\n"
            ),
        },
    },
    {
        "who": "asha",
        "date": "2026-01-12T14:15:00+00:00",
        "message": "Add brackets and wall plugs to the price list",
        "files": {
            "prices.csv": (
                "sku,name,price\n"
                "SKU-1001,oak shelf,120\n"
                "SKU-1002,pine shelf,80\n"
                "SKU-1003,steel bracket,6\n"
                "SKU-1004,wall plug (100),4\n"
            ),
        },
        "branch_here": "release-1",
    },
    {
        "who": "bram",
        "date": "2026-02-02T08:45:00+00:00",
        "message": "Round totals to whole cents",
        "files": {
            "total.py": (
                "def total(prices, quantities):\n"
                "    raw = sum(prices[sku] * n for sku, n in quantities.items())\n"
                "    return round(raw, 2)\n"
            ),
        },
    },
    {
        "who": "asha",
        "date": "2026-03-01T07:00:00+00:00",
        "message": "Raise the oak shelf to 135",
        "files": {
            "prices.csv": (
                "sku,name,price\n"
                "SKU-1001,oak shelf,135\n"
                "SKU-1002,pine shelf,80\n"
                "SKU-1003,steel bracket,6\n"
                "SKU-1004,wall plug (100),4\n"
            ),
            "CHANGELOG.md": "# Changes\n\n- 1 March 2026: oak shelf 120 -> 135\n",
        },
    },
]


def _git(repo: Path, *args: str, env_extra: dict[str, str] | None = None) -> str:
    """Run git in `repo` without the user's or the system's configuration."""
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(repo),  # no ~/.gitconfig is read
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_TERMINAL_PROMPT": "0",
        "LC_ALL": "C",
        "TZ": "UTC",
    }
    if env_extra:
        env.update(env_extra)
    fixed = [
        "-c", "commit.gpgsign=false",
        "-c", "core.autocrlf=false",
        "-c", "core.fileMode=true",
        "-c", "init.defaultBranch=main",
        "-c", "init.defaultObjectFormat=sha1",
        "-c", "core.hooksPath=" + os.devnull,
    ]  # fmt: skip
    done = subprocess.run(
        ["git", *fixed, *args], cwd=repo, env=env, capture_output=True, text=True, check=False
    )
    if done.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} failed: {done.stderr.strip()}")
    return done.stdout.strip()


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))
    os.chmod(path, 0o644)


def build(dest: Path) -> dict[str, object]:
    if dest.exists() and (not dest.is_dir() or any(dest.iterdir())):
        raise SystemExit(f"refusing to build into {dest}: it exists and is not an empty directory")
    dest.mkdir(parents=True, exist_ok=True)

    files_root = dest / "files"
    for relative, text in FILES.items():
        _write(files_root / relative, text)
    for path in sorted(files_root.rglob("*")):
        if path.is_file():
            os.utime(path, (FIXED_MTIME, FIXED_MTIME))

    repo = dest / "repo"
    repo.mkdir()
    _git(repo, "init", "--quiet", "--initial-branch=main")
    commits: list[dict[str, str]] = []
    branches: dict[str, str] = {}
    for commit in COMMITS:
        files = commit["files"]
        assert isinstance(files, dict)
        for relative, text in files.items():
            _write(repo / relative, text)
            _git(repo, "add", "--", relative)
        name, email = PEOPLE[str(commit["who"])]
        date = str(commit["date"])
        stamp = {
            "GIT_AUTHOR_NAME": name,
            "GIT_AUTHOR_EMAIL": email,
            "GIT_AUTHOR_DATE": date,
            "GIT_COMMITTER_NAME": name,
            "GIT_COMMITTER_EMAIL": email,
            "GIT_COMMITTER_DATE": date,
        }
        _git(
            repo, "commit", "--quiet", "--no-verify", "-m", str(commit["message"]), env_extra=stamp
        )
        sha = _git(repo, "rev-parse", "HEAD")
        commits.append(
            {"sha": sha, "author": name, "date": date, "message": str(commit["message"])}
        )
        branch = commit.get("branch_here")
        if isinstance(branch, str):
            _git(repo, "branch", branch, sha)
            branches[branch] = sha
    branches["main"] = commits[-1]["sha"]

    manifest: dict[str, object] = {
        "files": {
            relative: hashlib.sha256(text.encode("utf-8")).hexdigest()
            for relative, text in sorted(FILES.items())
        },
        "repo": {
            "commits": commits,
            "branches": dict(sorted(branches.items())),
            "tracked_files": _git(repo, "ls-files").splitlines(),
        },
    }
    (dest / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest


def _tree(root: Path) -> list[str]:
    lines: list[str] = []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if ".git" in relative.parts:
            continue
        if path.is_dir():
            lines.append(f"{relative}/")
        else:
            lines.append(f"{relative}  ({path.stat().st_size} bytes)")
    return lines


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    dest = Path(argv[1]).resolve()
    manifest = build(dest)
    print(f"fixture built at {dest}")
    print("tree (the repository's .git directory is left out):")
    for line in _tree(dest):
        print(f"  {line}")
    repo = manifest["repo"]
    assert isinstance(repo, dict)
    print("commits on main, oldest first:")
    for commit in repo["commits"]:
        print(f"  {commit['sha']}  {commit['date']}  {commit['author']}: {commit['message']}")
    print("branches:")
    for name, sha in repo["branches"].items():
        print(f"  {name} -> {sha}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
