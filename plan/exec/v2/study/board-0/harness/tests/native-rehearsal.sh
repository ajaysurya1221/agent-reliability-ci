#!/bin/sh
set -eu
exec "${BOARD0_ENV:-/Users/Shared/arci-reply0/env}/py/bin/python" -IB "$(dirname "$0")/native_rehearsal.py"
