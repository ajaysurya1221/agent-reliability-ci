#!/bin/sh
# Run from a neutral checkout, with REPLY0_ENV pointing at the registered environment.
# list prints canonical RUNs. A clean/unscripted RUN without its final task ID runs
# one model/cell serially. All invocations share the suite lock.
# digests > reply0-digests.sha256 prepares the initial list before registration.
# prepare > descriptor-digests.sha256 follows the completed clean row.
# check verifies pushed inputs without issuing any request.
# real reply0-wiring-4B / real reply0-clean-4B-F1 / real reply0-main-4B-F1
# report prints the status of each scheduled slot and unscripted exposure denominators.
# assemble DIRECTORY builds the registration's allowlisted publication tree.
exec </dev/null
set -eu
umask 077
cd -P "$(dirname "$0")/.."
: "${REPLY0_ENV:?set REPLY0_ENV to the registered environment directory}"
export PYTHONDONTWRITEBYTECODE=1 GIT_OPTIONAL_LOCKS=0
unset PYTHONPATH PYTHONHOME PYTHONOPTIMIZE OLLAMA_HOST
case "${1:-}" in
    real|check)
        # Verify launcher code against the published tree before importing study modules.
        "$REPLY0_ENV/py/bin/python" -IB - <<'PYCODE' || exit 67
from pathlib import Path
import subprocess
import sys
for name in ("harness/run-reply0.sh", "harness/clean_row.py", "harness/wiring_check.py"):
    try:
        pushed = subprocess.check_output(
            ["/opt/homebrew/bin/git", "--no-optional-locks", "cat-file", "blob",
             "refs/remotes/origin/v2/phase0:./" + name],
            stdin=subprocess.DEVNULL, timeout=15,
        )
        if pushed == Path(name).read_bytes():
            continue
    except (OSError, subprocess.SubprocessError):
        pass
    sys.exit("Reply-0: no matching pushed " + name)
PYCODE
        ;;
esac
if [ "${1:-}" = real ]; then
    exec /usr/bin/caffeinate -dims "$REPLY0_ENV/py/bin/python" -IB harness/clean_row.py "$@"
fi
exec "$REPLY0_ENV/py/bin/python" -IB harness/clean_row.py "$@"
