#!/bin/sh
set -eu
exec </dev/null
cd -P "$(dirname "$0")"
unset PYTHONHOME PYTHONPATH PYTHONOPTIMIZE
export PYTHONDONTWRITEBYTECODE=1
SIZE0_REPO_PYTHON="$(cd ../../../../.. && pwd -P)/.venv/bin/python"
export SIZE0_REPO_PYTHON
exec ../../../../../../.arci-worktrees/run4-env/bin/python -IB tests/rehearsal.py
