#!/bin/sh
set -eu
exec </dev/null
cd -P "$(dirname "$0")/.."
export PYTHONDONTWRITEBYTECODE=1
exec ../../../../../../.arci-worktrees/run4-env/bin/python -IB tests/native_rehearsal.py "$@"
