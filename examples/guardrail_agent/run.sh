#!/usr/bin/env bash
# The guardrail experiment against the live System One endpoint (README.md, "Pre-registered").
#
#   TYPESAFE_API_KEY=... examples/guardrail_agent/run.sh [--base-url URL] [--model ID] [--rpm N] \
#       [--workers N] [--out DIR] [--force]
#
# Runs, in order: preflight; the clean pair (N=1); A vs B under decision_unavailable, A vs B under
# decision_low_confidence and A vs C clean, each at N=50 on the `ask` population; A vs B under
# decision_unavailable at N=200 listing the N=50 runs as prior runs, with one B failure minimised
# and replayed; then the secondary N=200 on the `all` population. Every run gets a gate report
# (Markdown + JUnit). A run whose decision.json exists is skipped unless --force. The key is read
# by `arci` from the environment and never printed; the script refuses to finish if the key
# appears in any output.
set -euo pipefail

ARCI=${ARCI:-.venv/bin/arci}
PY=${PY:-.venv/bin/python}
BASE_URL=${TYPESAFE_BASE_URL:-https://api.typesafe.ai}
MODEL=jev-1.13.0
RPM=200
WORKERS=4
OUT="runs/guardrail-$(date -u +%F)"
FORCE=0
while [ $# -gt 0 ]; do
  case "$1" in
    --base-url) BASE_URL=$2; shift 2 ;;
    --model) MODEL=$2; shift 2 ;;
    --rpm) RPM=$2; shift 2 ;;
    --workers) WORKERS=$2; shift 2 ;;
    --out) OUT=$2; shift 2 ;;
    --force) FORCE=1; shift ;;
    *) echo "unknown argument: $1" >&2; exit 64 ;;
  esac
done
if [ -z "${TYPESAFE_API_KEY:-}" ]; then
  echo "TYPESAFE_API_KEY is not set in this environment" >&2
  exit 3
fi
if [ ! -f pyproject.toml ] || [ ! -d examples/guardrail_agent ]; then
  echo "run this script from the repository root" >&2
  exit 64
fi
# The manifests name the agent and the toolset server as `examples.guardrail_agent.*` modules;
# the `arci` console script's sys.path does not include the repository root.
export PYTHONPATH="$PWD${PYTHONPATH:+:$PYTHONPATH}"
mkdir -p "$OUT/manifests"
SUMMARY="$OUT/summary.tsv"
: > "$SUMMARY"

manifest() {  # candidate n condition population [prior-run ...] -> prints manifest path
  local candidate=$1 n=$2 condition=$3 population=$4; shift 4
  local args=()
  for prior in "$@"; do args+=(--prior-run "$prior"); done
  local path="$OUT/manifests/$candidate-$population-$condition-$n.json"
  "$PY" -m examples.guardrail_agent.experiment --candidate "$candidate" --n-per-arm "$n" \
    --condition "$condition" --population "$population" --base-url "$BASE_URL" \
    --model "$MODEL" --rpm "$RPM" "${args[@]}" --out "$path" >/dev/null
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

minimise_one() {  # experiment-id -> diff, minimise and replay the first candidate FAIL with a passing pair
  local id=$1 failing passing
  failing=$("$PY" - "$OUT/$id/trials.jsonl" <<'PYEOF'
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
  if [ -n "$failing" ]; then
    passing="${failing%:*}:baseline"
    "$ARCI" diff "$OUT/$id" "$passing" "$failing" | tee "$OUT/$id/divergence.txt"
    "$ARCI" minimize "$OUT/$id" "$failing" --out "$OUT/$id/min-bundle.json" | tee "$OUT/$id/minimize.txt"
    set +e
    "$ARCI" replay "$OUT/$id/min-bundle.json" | tee "$OUT/$id/replay.txt"
    echo "   replay exit $?"
    set -e
  else
    echo "no candidate FAIL with a passing baseline pair in $id; nothing to minimise" | tee "$OUT/$id/minimize.txt"
  fi
}

echo "## preflight ($BASE_URL, model $MODEL)"
PRE_MANIFEST=$(manifest b 50 clean ask)
set +e
"$ARCI" preflight --allow-unlisted-model "$PRE_MANIFEST" > "$OUT/preflight.txt" 2>&1
PRE=$?
set -e
cat "$OUT/preflight.txt"
case "$PRE" in
  0) grep -E '^\{"preflight"' "$OUT/preflight.txt" > "$OUT/preflight.receipt.json" || true ;;
  2) echo "preflight: the pinned model is neither listed nor reported by the smoke request; pick one of the ids above with --model" >&2; exit 2 ;;
  *) echo "preflight failed (exit $PRE); nothing was run" >&2; exit "$PRE" ;;
esac

echo "## clean pair (N=1)"
run_one "$(manifest b 1 clean ask)"
"$PY" - "$OUT/guardrail-live-b-ask-clean-1/trials.jsonl" <<'PYEOF'
import json, sys
trials = [json.loads(line) for line in open(sys.argv[1], encoding="utf-8") if line.strip()]
bad = [t for t in trials if t["outcome"] != "PASS"]
if len(trials) != 2 or bad:
    for t in bad:
        print(f"clean pair: {t['trial_id']} {t['outcome']} ({t['termination']}): {t['failure_detail']}", file=sys.stderr)
    print("the harness could not complete a clean trial; nothing below would measure the guard", file=sys.stderr)
    sys.exit(4)
PYEOF

echo "## the trio at N=50 on the ask population"
run_one "$(manifest b 50 unavailable ask)"
run_one "$(manifest b 50 low_confidence ask)"
run_one "$(manifest c 50 clean ask)"

echo "## pre-registered N=200, A vs B under decision_unavailable, listing the runs above as prior runs"
PRIORS=(guardrail-live-b-ask-clean-1 guardrail-live-b-ask-provider_down-50 guardrail-live-b-ask-low_confidence-50 guardrail-live-c-ask-clean-50)
BIG=$(manifest b 200 unavailable ask "${PRIORS[@]}")
run_one "$BIG"
BIG_ID=$(experiment_id "$BIG")
echo "## minimise and replay one B failure from $BIG_ID"
minimise_one "$BIG_ID"

echo "## secondary N=200 on the whole labelled set"
run_one "$(manifest b 200 unavailable all "${PRIORS[@]}" "$BIG_ID")"

echo "## secret scan"
if grep -rqF -- "$TYPESAFE_API_KEY" "$OUT"; then
  echo "the API key appears somewhere under $OUT; do not commit it" >&2
  exit 9
fi
echo "no key material under $OUT"

echo "## summary"
column -t -s $'\t' "$SUMMARY" 2>/dev/null || cat "$SUMMARY"
