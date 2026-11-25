#!/bin/sh
# Run DESIGN section 12.1-6 offline. Each invocation keeps a fresh evidence directory.
set -eu
umask 077
exec </dev/null
cd -P "$(dirname "$0")/.."
repo=$(cd ../../../../.. && pwd -P)
envdir=${REPLY0_ENV:-/Users/Shared/arci-reply0/env}
py="$envdir/py/bin/python"
out=$(mktemp -d "$PWD/.offline-proof-XXXXXXXX")
export TMPDIR="$out/tmp" PYTHONDONTWRITEBYTECODE=1 GIT_OPTIONAL_LOCKS=0
export PYTHONPATH="$PWD/harness:$PWD" REPLY0_ENV="$envdir"
mkdir "$TMPDIR"
"$py" -B -c 'from pathlib import Path; import sys; from harness.wiring_check import registered_node; registered_node(Path(sys.argv[1]))' "$envdir"
unset REPLY0_CHECK_TRANSPORT
case "${REPLY0_REHEARSAL_TRANSPORT:-fifo}" in
    fifo) transport=--pipes ;;
    native) transport= ;;
    *) echo 'Expected fifo or native transport' >&2; exit 2 ;;
esac

logged() {
    log="$1"
    shift
    if "$@" >"$out/$log.log" 2>&1; then
        tail -n 3 "$out/$log.log"
    else
        tail -n 15 "$out/$log.log" >&2
        return 1
    fi
}

echo "Offline evidence ${out##*/}"
echo '1. Rule, opening, receipt and oracle tests'
logged unit "$py" -B -m unittest discover -s harness/tests/core -p test_core.py
echo '2. Seven stub cases and hidden-tool refusal'
logged stub "$py" -B -m unittest discover -s harness/tests/core -p test_stub.py
echo '3. C0 released fault, ledger and first request'
"$py" -B harness/rehearse.py C0 "$out" --pair --checks tasks/check $transport
echo '4. Task matrix, edited packages and protected paths'
if [ "$transport" = --pipes ]; then
    logged tasks "$py" -B harness/tests/core/offline_run.py matrix "$envdir" "$out/checks"
else
    logged tasks "$py" -B harness/tests/core/offline_run.py native-matrix "$envdir" "$out/checks"
fi
echo '5. Directional, equal and swapped stand-ins for each server'
for cell in F1 G1 C0; do
    "$py" -B harness/rehearse.py "$cell" "$out" --checks "$out/checks" $transport
done
"$py" -B harness/rehearse.py F1 "$out" --pair --checks "$out/checks" $transport
logged combined "$py" -B -m unittest harness/tests/core/test_*.py \
    harness/tests/ops/test_*.py harness/tests/blind/test_*.py
echo '6. Format, lint, types and input digests'
"$repo/.venv/bin/ruff" format --check --no-cache harness
"$repo/.venv/bin/ruff" check --no-cache harness
"$repo/.venv/bin/basedpyright" --project harness/pyrightconfig.json --pythonpath "$py" harness
# A rehearsal computes a candidate list in its evidence directory. The orchestrator freezes it.
"$py" -B harness/make_digests.py --out "$out/reply0-digests.sha256"
logged hashes /usr/bin/shasum -a 256 -c "$out/reply0-digests.sha256"
cmp tasks/check/tasks.check.json "$out/checks/tasks.check.json"
if [ "$envdir" = /Users/Shared/arci-reply0/env ]; then
    "$py" -B harness/tests/core/check_privacy.py "$out"
fi
echo 'PASS checks 1-6'
