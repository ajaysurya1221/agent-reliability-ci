#!/usr/bin/env bash
# Smoke-test a built arci wheel and an optional realornoise wheel on Python 3.11 onward.
# Use a fresh venv with only the wheels and their declared dependencies, then run the CLI
# from a fresh empty directory.
#
#   PYTHON=python3 bash .github/scripts/wheel_smoke.sh dist/agent_reliability_ci-X.Y.Z-py3-none-any.whl
#
# Shared by release.yml (smoke job) and ci.yml (wheel-smoke job). POSIX hosts only (Linux, macOS):
# no GNU-only flags, no `timeout`, nothing beyond bash 3.2.
set -euo pipefail

if [ "$#" -lt 1 ] || [ "$#" -gt 2 ]; then
  echo "usage: PYTHON=python3 $0 WHEEL [REALORNOISE_WHEEL] (got $# arguments)" >&2
  exit 64
fi
if [ ! -f "$1" ]; then
  echo "wheel_smoke: no such wheel: $1" >&2
  exit 64
fi
# Absolute, so a relative $PYTHON (.venv/bin/python) still resolves after the cd below.
python="$("${PYTHON:-python3}" -c 'import sys; print(sys.executable)')"
wheel="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
second_wheel=""
if [ "$#" -eq 2 ]; then
  [ -f "$2" ] || { echo "wheel_smoke: no such wheel: $2" >&2; exit 64; }
  second_wheel="$(cd "$(dirname "$2")" && pwd)/$(basename "$2")"
fi
trace_smoke="$(cd "$(dirname "$0")" && pwd)/trace_check_smoke.py"
triage_smoke="$(cd "$(dirname "$0")" && pwd)/triage_smoke.py"

# No inherited checkout import paths may satisfy this installed-wheel test.
unset PYTHONPATH
export PYTHONSAFEPATH=1

tmpbase=${TMPDIR:-/tmp}
root="$(mktemp -d "${tmpbase%/}/arci-wheel-smoke.XXXXXX")"
root="$(cd "$root" && pwd -P)"
trap 'rm -rf "$root"' EXIT
venv="$root/venv"
work="$root/empty"
mkdir "$work" "$root/tmp"
: >"$root/timings"

now() {
  "$python" -c 'import time; print(f"{time.time():.3f}")'
}

fail() {
  echo "wheel_smoke: FAILED: $*" >&2
  exit 1
}

record() { # record LABEL START END
  awk -v l="$1" -v s="$2" -v e="$3" 'BEGIN { printf "%8.2fs  %s\n", e - s, l }' >>"$root/timings"
}

# timed LABEL COMMAND...: run one external command; fail naming LABEL if it exits non-zero.
timed() {
  local label=$1 start
  shift
  echo "wheel_smoke: $label"
  start=$(now)
  "$@" || fail "$label (exit $?)"
  record "$label" "$start" "$(now)"
}

# The synthetic example deliberately reports a drop. Both status and output must agree.
example() { # example LABEL COMMAND...
  local label=$1 start status=0
  shift
  echo "wheel_smoke: $label"
  start=$(now)
  "$@" >"$root/example.log" || status=$?
  cat "$root/example.log"
  [ "$status" -eq 1 ] || fail "$label (expected exit 1, got $status)"
  grep -qx 'RESULT: REAL DROP' "$root/example.log" || fail "$label did not report REAL DROP"
  record "$label" "$start" "$(now)"
}

echo "wheel_smoke: wheel $wheel"
echo "wheel_smoke: python $python $("$python" -c 'import sys; print(sys.version.split()[0])')"

timed "create a fresh venv" "$python" -m venv "$venv"
if [ -n "$second_wheel" ]; then
  timed "pip install both wheels" "$venv/bin/python" -m pip install \
    --disable-pip-version-check --no-input --quiet "$wheel" "$second_wheel"
else
  timed "pip install the wheel" "$venv/bin/python" -m pip install \
    --disable-pip-version-check --no-input --quiet "$wheel"
fi

cd "$work"
PATH="$venv/bin:$PATH"
export PATH

[ "$(command -v arci)" = "$venv/bin/arci" ] || fail "arci resolves to $(command -v arci), not the venv"
located="$(python -c 'import arci, os; print(os.path.realpath(arci.__file__))')"
case "$located" in
  "$venv"/*) echo "wheel_smoke: arci $(python -c 'import arci; print(arci.__version__)') imported from $located" ;;
  *) fail "arci imported from $located, not from the installed wheel" ;;
esac

timed "arci --help" arci --help
timed "python -m arci --help" python -m arci --help

example "arci logs --example" arci logs --example
if [ -n "$second_wheel" ]; then
  [ "$(command -v realornoise)" = "$venv/bin/realornoise" ] || fail "realornoise is not from the venv"
  example "realornoise --example" realornoise --example
fi

# The demo's run stores go to a temp dir under $root (removed on exit), never to the cwd.
echo "wheel_smoke: arci demo --workers 4 --keep DEMO_DIR"
start=$(now)
if ! TMPDIR="$root/tmp" arci demo --workers 4 --keep "$root/demo" | tee "$root/demo.log"; then
  fail "arci demo --workers 4 exited non-zero"
fi
record "arci demo --workers 4" "$start" "$(now)"
grep -qx 'All six steps held.' "$root/demo.log" || fail "arci demo did not print 'All six steps held.'"

timed "installed trace-check statuses and read-only stores" \
  "$venv/bin/python" -P "$trace_smoke" "$root/demo"

timed "installed triage gate exits, JSON contract and read-only stores" \
  "$venv/bin/python" -P "$triage_smoke" "$root/demo"

leftover="$(ls -A "$work")"
[ -z "$leftover" ] || fail "the working directory is not empty after the demo: $leftover"

# The packaged JSON Schema prints and parses (written into the empty directory, removed on exit).
echo "wheel_smoke: arci schema"
start=$(now)
arci schema >schema.json || fail "arci schema exited non-zero"
python3 -c "import json; json.load(open('schema.json'))" || fail "arci schema did not print JSON"
record "arci schema" "$start" "$(now)"

echo "wheel_smoke: timings"
cat "$root/timings"
echo "wheel_smoke: OK"
