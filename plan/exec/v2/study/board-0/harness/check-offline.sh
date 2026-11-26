#!/bin/sh
set -eu
umask 077
exec </dev/null
study=$(cd -P "$(dirname "$0")/.." && pwd)
repo=$(cd -P "$study/../../../../.." && pwd)
cd "$repo"
py="$repo/.venv/bin/python"
# The checkout interpreter uses the already installed release, with no dependency installation.
envdir=${BOARD0_ENV:-/Users/Shared/arci-reply0/env}
site=$("$py" -IB - "$envdir" <<'PY'
from pathlib import Path
import sys
base=Path(sys.argv[1])/"py/lib"/f"python{sys.version_info.major}.{sys.version_info.minor}"/"site-packages"
if not (base/"agent_reliability_ci-2.4.1.dist-info").is_dir():
    raise SystemExit("set BOARD0_ENV to an installed ARCI 2.4.1 environment")
print(base)
PY
)
out=$(mktemp -d /private/tmp/board0-offline-XXXXXXXX)
trap 'rm -rf "$out"' EXIT
mkdir "$out/tmp" "$out/harness" "$out/calendardesk"
cp -R "$study/harness/." "$out/harness/"
cp -R "$study/tasks" "$study/orderdesk" "$study/projections" "$out/"
for name in calendar_world.py tasks.json key.py; do
    cp "$study/calendardesk/$name" "$out/calendardesk/$name"
done
cp "$study/models.example.json" "$study/PREREGISTRATION-board-0.draft.md" "$out/"
export BOARD0_NO_SANDBOX=1 PYTHONDONTWRITEBYTECODE=1 GIT_OPTIONAL_LOCKS=0
export PYTHONPATH="$site:$out/harness" TMPDIR="$out/tmp" PATH="$repo/.venv/bin:$PATH"
"$py" -PB "$out/tasks/make_tasks.py"
cmp "$study/tasks/tasks.json" "$out/tasks/tasks.json"
"$py" -PB "$out/harness/tests/rehearsal.py"

