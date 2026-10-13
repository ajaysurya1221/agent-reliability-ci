#!/usr/bin/env bash
# Track A stopwatch (docs/measurement/ttfv-protocol.md section 3), maintainer/AI-labelled run.
# usage: ttfv_track_a.sh <package spec: agent-reliability-ci==0.8.0 or /path/to/x.whl> <out.json> [uv cache dir]
set -u
SPEC=$1; OUT=$2; CACHE=${3:-}
stamp() { date -u +%Y-%m-%dT%H:%M:%SZ; }
WORK=$(mktemp -d -t ttfv-a); cd "$WORK" || exit 1
export UV_NO_PROGRESS=1
[ -n "$CACHE" ] && export UV_CACHE_DIR="$CACHE"
T_README=$(stamp)                     # README on screen: the facilitator (this script) starts
T_CMD=$(stamp)
LOG="$WORK/demo.log"
# Exit status of `arci demo`, not of the stamping loop. `${PIPESTATUS[0]}` is bash-only: under zsh
# (the shell the v0.8.0 cohort's wrapper ran in, or `zsh ttfv_track_a.sh`) it is unset, which
# aborts under `set -u` or records nothing. Writing the status to a file from inside the brace
# group is portable to bash, zsh and sh, and the stamping loop cannot overwrite it.
EXIT_FILE="$WORK/demo.exit"
{ uvx --from "$SPEC" arci demo 2>&1; echo $? > "$EXIT_FILE"; } | while IFS= read -r line; do printf '%s %s\n' "$(stamp)" "$line"; done > "$LOG"
EXIT=$(cat "$EXIT_FILE" 2>/dev/null)
EXIT=${EXIT:-127}
T_BANNER=$(grep -m1 ' arci demo: ' "$LOG" | cut -d' ' -f1)
T_VERDICT=$(grep -m1 ' VERDICT: ' "$LOG" | cut -d' ' -f1)
T_HELD=$(grep -m1 'All six steps held' "$LOG" | cut -d' ' -f1)
python3 - "$OUT" "$T_README" "$T_CMD" "${T_BANNER:-}" "${T_VERDICT:-}" "${T_HELD:-}" "$EXIT" "$SPEC" "$LOG" <<'PY'
import json, sys, datetime as dt
out, readme, cmd, banner, verdict, held, exit_, spec, log = sys.argv[1:]
p = lambda s: dt.datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ") if s else None
d = lambda a, b: (p(b) - p(a)).total_seconds() if a and b else None
rec = {"track": "A", "label": "maintainer/AI run (orchestrator); not a cold reader", "package": spec, "exit": int(exit_),
       "timestamps": {"readme_opened": readme, "command_start": cmd, "demo_banner": banner or None,
                      "demo_verdict": verdict or None, "all_steps_held": held or None},
       "durations_seconds": {"install": d(cmd, banner), "run": d(banner, held), "total": d(readme, held)}, "log": log}
json.dump(rec, open(out, "w"), indent=1)
print(json.dumps(rec["durations_seconds"]), "exit", exit_)
PY
