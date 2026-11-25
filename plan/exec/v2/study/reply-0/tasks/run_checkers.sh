#!/bin/sh
# Reply-0: feed the replies to the REGISTERED bad calls (tasks/check/registered-*.replies.json,
# written by check_tasks.py) to the two rule-based checkers. No model, no server. Both checkers
# run with the network denied and an empty HOME, through the feeder scripts of ../checkers/
# (read and judged safe on day 1, task D). The successful replies are fed a second time without
# mcp-linter's excuse for a success on an "unknown value" call.
set -eu
HERE=$(cd "$(dirname "$0")" && pwd)
CHK=$HERE/../checkers
ENVDIR=${1:-${REPLY0_ENV:?give ENV_DIR or set REPLY0_ENV}}
OUT=${2:-$HERE/check}
PKG=$ENVDIR/checkers
PY=$ENVDIR/py/bin/python
NODE=${NODE:-$(command -v node)}
DENY='(version 1)(allow default)(deny network*)'
exec </dev/null
isolated() {
  if [ "${REPLY0_NO_SANDBOX:-0}" = 1 ]; then
    "$@"
  else
    sandbox-exec -p "$DENY" "$@"
  fi
}
export PYTHONDONTWRITEBYTECODE=1
"$PY" -I -B - "$OUT" <<'PYEOF'
import json, sys
from pathlib import Path
root = Path(sys.argv[1])
for server in ("filesystem", "git"):
    data = json.loads((root / f"registered-{server}.replies.json").read_text("utf-8"))
    strict = [{**r, "id": r["id"] + "#not-excused", "bad_call": "unknown_value_not_excused"}
              for r in data["replies"] if r["bad_call"] == "unknown_value" and not r["is_error"]]
    (root / f"registered-{server}.not-excused.replies.json").write_text(
        json.dumps({"tools": data["tools"], "replies": strict}, indent=1) + "\n", encoding="utf-8")
PYEOF
for name in filesystem git filesystem.not-excused git.not-excused; do
  in="$OUT/registered-$name.replies.json"
  isolated env -i HOME="$ENVDIR/home" LC_ALL=C PYTHONDONTWRITEBYTECODE=1 \
    "$PY" -I -B "$CHK/feed_mcp_linter.py" "$PKG/mcp-linter-pypi/src" "$in" \
    > "$OUT/registered-$name.mcp-linter.json"
  case "$name" in
    *.not-excused) ;;
    *)
      isolated env -i HOME="$ENVDIR/home" LC_ALL=C \
        "$NODE" "$CHK/feed_mcp_lint.mjs" "$PKG/mcp-lint-npm/src/package" "$in" \
        > "$OUT/registered-$name.mcp-lint.json"
      ;;
  esac
done
