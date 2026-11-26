#!/bin/sh
set -eu
umask 077
exec </dev/null
dest=
case "${1:-}" in
    assemble|pack) case "$2" in /*) dest=$2 ;; *) dest=$PWD/$2 ;; esac ;;
esac
cd -P "$(dirname "$0")/.."
: "${BOARD0_ENV:?set BOARD0_ENV to the pinned environment}"
py="$BOARD0_ENV/py/bin/python"
export PYTHONDONTWRITEBYTECODE=1 GIT_OPTIONAL_LOCKS=0
unset PYTHONHOME PYTHONOPTIMIZE OLLAMA_HOST BOARD0_CLAIMS
export PATH="$BOARD0_ENV/py/bin:/usr/bin:/bin"
export PYTHONPATH="$PWD/harness"
case "${1:-}" in
    check|real)
        # Check the active launcher and every importable study input before importing it.
        "$py" -IB - <<'PY'
from pathlib import Path
from hashlib import sha256
import subprocess
def git(*args):
    return subprocess.check_output(["git","--no-optional-locks",*args],timeout=15)
commit=git("rev-parse","refs/remotes/origin/v2/phase0").decode().strip()
pins=git("cat-file","blob",commit+":./board0-digests.sha256")
if pins != Path("board0-digests.sha256").read_bytes():
    raise SystemExit("unregistered inputs")
pinned=set()
for line in pins.decode().splitlines():
    h,n=line.split("  ",1)
    p=Path(n)
    if p.is_absolute() or ".." in p.parts or p.absolute()!=p.resolve() or sha256(p.read_bytes()).hexdigest()!=h:
        raise SystemExit("changed pinned input: "+n)
    pinned.add(n)
for folder in ("harness","tasks","orderdesk","calendardesk"):
    for p in Path(folder).glob("*.py"):
        if str(p) not in pinned and not p.name.startswith("test_"):
            raise SystemExit("unregistered module: "+str(p))
PY
    ;;
esac
if [ -n "$dest" ]; then
    exec "$py" -PB harness/launcher.py "$1" "$dest"
fi
exec "$py" -PB harness/launcher.py "$@"

