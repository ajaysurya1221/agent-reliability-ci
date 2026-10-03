#!/usr/bin/env bash
# Day one against the live System One endpoint (docs/design/0004-day-one.md).
#
#   TYPESAFE_API_KEY=... examples/jev_triage_agent/day_one.sh [--base-url URL] [--model ID] \
#       [--rpm N] [--workers N] [--out DIR] [--skip-node] [--force]
#
# Runs, in order: preflight; the clean pair (N=1); A vs B, A vs A, A vs C under
# decision_low_confidence at N=50; A vs B at N=50 through the Node agent (official JS SDK,
# unchanged); A vs B at N=200 listing the N=50 runs as prior runs; then minimise and replay one
# B failure from the N=200 run. Every run gets a gate report (Markdown + JUnit). A run whose
# decision.json already exists is skipped unless --force. The key is read by `arci` from the
# environment and never printed; the script refuses to finish if the key appears in any output.
set -euo pipefail

ARCI=${ARCI:-.venv/bin/arci}
PY=${PY:-.venv/bin/python}
BASE_URL=${TYPESAFE_BASE_URL:-https://api.typesafe.ai}
MODEL=jev-1.13.0
RPM=200
WORKERS=4
OUT="runs/jev-$(date -u +%F)"
SKIP_NODE=0
FORCE=0
while [ $# -gt 0 ]; do
  case "$1" in
    --base-url) BASE_URL=$2; shift 2 ;;
    --model) MODEL=$2; shift 2 ;;
    --rpm) RPM=$2; shift 2 ;;
    --workers) WORKERS=$2; shift 2 ;;
    --out) OUT=$2; shift 2 ;;
    --skip-node) SKIP_NODE=1; shift ;;
    --force) FORCE=1; shift ;;
    *) echo "unknown argument: $1" >&2; exit 64 ;;
  esac
done
if [ -z "${TYPESAFE_API_KEY:-}" ]; then
  echo "TYPESAFE_API_KEY is not set in this environment" >&2
  exit 3
fi
if [ "$SKIP_NODE" -eq 0 ] && ! command -v node >/dev/null 2>&1; then
  echo "node not found; skipping the Node agent run (pass --skip-node to silence this)" >&2
  SKIP_NODE=1
fi
mkdir -p "$OUT/manifests"
SUMMARY="$OUT/summary.tsv"
: > "$SUMMARY"

manifest() {  # candidate n condition runtime [prior-run ...] -> prints manifest path
  local candidate=$1 n=$2 condition=$3 runtime=$4; shift 4
  local args=()
  for prior in "$@"; do args+=(--prior-run "$prior"); done
  local path="$OUT/manifests/$candidate-$condition-$n-$runtime.json"
  "$PY" -m examples.jev_triage_agent.experiment --candidate "$candidate" --n-per-arm "$n" \
    --condition "$condition" --runtime "$runtime" --base-url "$BASE_URL" --model "$MODEL" \
    --rpm "$RPM" "${args[@]}" --out "$path" >/dev/null
  echo "$path"
}

experiment_id() { "$PY" -c 'import json,sys; print(json.load(open(sys.argv[1]))["experiment_id"])' "$1"; }

run_one() {  # manifest-path -> runs, gates, records; never aborts the sequence
  local path=$1 id code
  id=$(experiment_id "$path")
  if [ "$FORCE" -eq 0 ] && [ -f "$OUT/$id/decision.json" ]; then
    echo "== $id: already run, skipping (use --force to re-run)"
  else
    echo "== $id"
    set +e
    "$ARCI" run "$path" --out "$OUT" --workers "$WORKERS" > "$OUT/$id.run.txt" 2>&1
    code=$?
    set -e
    tail -n 12 "$OUT/$id.run.txt"
    echo "   exit $code"
    "$ARCI" gate "$OUT/$id" --markdown "$OUT/$id/report.md" --junit "$OUT/$id/junit.xml" \
      > "$OUT/$id.gate.txt" 2>&1 || true
  fi
  local verdict
  verdict=$("$PY" -c 'import json,sys; d=json.load(open(sys.argv[1])); print(d["verdict"], d["exit_code"])' "$OUT/$id/decision.json" 2>/dev/null || echo "missing -")
  printf '%s\t%s\n' "$id" "$verdict" >> "$SUMMARY"
}

echo "## preflight ($BASE_URL, model $MODEL)"
PRE_MANIFEST=$(manifest b 50 low_confidence python)
set +e
"$ARCI" preflight "$PRE_MANIFEST" > "$OUT/preflight.txt" 2>&1
PRE=$?
set -e
cat "$OUT/preflight.txt"
case "$PRE" in
  0) grep -E '^\{"preflight"' "$OUT/preflight.txt" > "$OUT/preflight.receipt.json" || true ;;
  2) echo "preflight: the pinned model is not on this account; pick one of the ids above with --model" >&2; exit 2 ;;
  *) echo "preflight failed (exit $PRE); nothing was run" >&2; exit "$PRE" ;;
esac

echo "## clean pair (N=1)"
run_one "$(manifest b 1 clean python)"

echo "## hero trio at N=50"
run_one "$(manifest b 50 low_confidence python)"
run_one "$(manifest a 50 low_confidence python)"
run_one "$(manifest c 50 low_confidence python)"

if [ "$SKIP_NODE" -eq 0 ]; then
  echo "## official JavaScript SDK, unchanged, at N=50"
  ( cd examples/jev_triage_agent && npm ci --silent >/dev/null 2>&1 ) || echo "npm ci failed; the Node run will show it" >&2
  run_one "$(manifest b 50 low_confidence node)"
fi

echo "## pre-registered N=200, listing the N=50 runs as prior runs"
PRIORS=(jev-live-b-clean-1 jev-live-b-low_confidence-50 jev-live-a-low_confidence-50 jev-live-c-low_confidence-50)
[ "$SKIP_NODE" -eq 0 ] && PRIORS+=(jev-live-b-low_confidence-50-node)
BIG=$(manifest b 200 low_confidence python "${PRIORS[@]}")
run_one "$BIG"
BIG_ID=$(experiment_id "$BIG")

echo "## minimise and replay one B failure from $BIG_ID"
FAILING=$("$PY" - "$OUT/$BIG_ID/trials.jsonl" <<'PYEOF'
import json, sys
trials = [json.loads(line) for line in open(sys.argv[1], encoding="utf-8") if line.strip()]
by_id = {t["trial_id"]: t for t in trials}
for t in trials:
    if t["arm"] == "candidate" and t["outcome"] == "FAIL":
        base = by_id.get(t["pair_id"] + ":baseline")
        if base is not None and base["outcome"] == "PASS":
            print(t["trial_id"]); break
PYEOF
)
if [ -n "$FAILING" ]; then
  PASSING="${FAILING%:*}:baseline"
  "$ARCI" diff "$OUT/$BIG_ID" "$PASSING" "$FAILING" | tee "$OUT/$BIG_ID/divergence.txt"
  "$ARCI" minimize "$OUT/$BIG_ID" "$FAILING" --out "$OUT/$BIG_ID/min-bundle.json" | tee "$OUT/$BIG_ID/minimize.txt"
  set +e
  "$ARCI" replay "$OUT/$BIG_ID/min-bundle.json" | tee "$OUT/$BIG_ID/replay.txt"
  echo "   replay exit $?"
  set -e
else
  echo "no candidate FAIL with a passing baseline pair in $BIG_ID; nothing to minimise" | tee "$OUT/$BIG_ID/minimize.txt"
fi

echo "## secret scan"
if grep -rqF -- "$TYPESAFE_API_KEY" "$OUT"; then
  echo "the API key appears somewhere under $OUT; do not commit it" >&2
  exit 9
fi
echo "no key material under $OUT"

echo "## summary"
column -t -s $'\t' "$SUMMARY" 2>/dev/null || cat "$SUMMARY"
