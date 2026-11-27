#!/bin/sh
set -eu
exec </dev/null
umask 077
cd -P "$(dirname "$0")"
export PYTHONDONTWRITEBYTECODE=1 GIT_NO_LAZY_FETCH=1
unset PYTHONHOME PYTHONPATH PYTHONOPTIMIZE
py=../../../../../../.arci-worktrees/run4-env/bin/python
case " $* " in
  *' --rehearsal '*) rehearsal=yes ;;
  *) rehearsal=no ;;
esac
case "${1:-}" in
  real) unset SIZE0_CLAIMS SIZE0_DATE SIZE0_REHEARSAL_ROOT; rehearsal=no ;;
esac
case "${1:-}:$rehearsal" in
  real:no|check:no|preflight:no)
    unset SIZE0_CLAIMS SIZE0_DATE SIZE0_REHEARSAL_ROOT
    "$py" -IB - <<'PY'
import hashlib
import json
import re
import subprocess
from pathlib import Path

def git(*args):
    return subprocess.check_output(["git", "--no-optional-locks", *args], stdin=subprocess.DEVNULL)

root = Path.cwd()
if any(root.rglob("__pycache__")):
    raise SystemExit("bytecode cache in study")
receipt = Path("/private/var/tmp/arci-size0-claims/push-receipt.txt").read_text()
match = re.fullmatch(r"([0-9a-f]{40}) refs/heads/v2/phase0\n?", receipt)
if not match or git("merge-base", match[1], "refs/remotes/origin/v2/phase0").decode().strip() != match[1]:
    raise SystemExit("missing or unpublished registration receipt")
ref = match[1]
listing = "prepared/inputs.json"
pins = git("cat-file", "blob", f"{ref}:./{listing}")
if pins != Path(listing).read_bytes():
    raise SystemExit("pushed input list differs")
entries = json.loads(pins)
for name, expected in entries.items():
    path = root / name
    if (path != path.resolve() or not path.is_relative_to(root)
            or hashlib.sha256(path.read_bytes()).hexdigest() != expected
            or path.read_bytes() != git("cat-file","blob",f"{ref}:./{name}")):
        raise SystemExit(f"changed registered input: {name}")
for folder in (root, root / "agent"):
    for path in folder.iterdir():
        if path.is_file() and path.suffix in (".py", ".pyc", ".so"):
            if str(path.relative_to(root)) not in entries:
                raise SystemExit(f"unregistered module: {path.name}")
        if path.is_dir() and (path / "__init__.py").exists():
            raise SystemExit(f"unregistered package: {path.name}")
PY
    ;;
esac
exec "$py" -EsB launcher.py "$@"
