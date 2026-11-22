#!/bin/sh
# Run 6 of the order-desk study. The registered run has one start.
#
#   RUN6_ENV=/path/to/environment sh run-6b.sh check    every guard of the real run; starts nothing
#   RUN6_ENV=/path/to/environment sh run-6b.sh real     the registered run
#
# One start means one real invocation past the guards. A failed guard leaves no new marker
# or run-6b.log, so a corrected start is possible. Before warm-up, the wrapper claims the
# permanent marker atomically and moves the preflight log to run-6b.log.
# Guards check fresh paths, published HEAD, registered files and digests, versions,
# model identity, arm settings and the imported study module. ARCI uses RUN6_ENV's Python.
set -eu

MODE=${1:?usage: RUN6_ENV=... sh run-6b.sh check|real}
: "${RUN6_ENV:?set RUN6_ENV to the Python environment folder}"
case "$RUN6_ENV" in
  /*) ;;
  *) RUN6_ENV="$(pwd -P)/$RUN6_ENV" ;;
esac
STUDY=$(cd "$(dirname "$0")" && pwd)
FOLDER=$STUDY/order-desk-compound
PYTHON=$RUN6_ENV/bin/python
MODEL=qwen3.5:4b-mlx-ctx32k
MODEL_ID=c01efed5a364
MODEL_DIGEST=c01efed5a36459ab6ffffa0b158636a014d8b30b4d5493167cba9916ed558430
MARKER=$STUDY/run-6b-$MODE.started
EXPOSURE=$STUDY/run-6-first-exchanges.jsonl

require_fresh() {
  for path do
    if [ -e "$path" ] || [ -L "$path" ]; then
      echo "refusing to start: $path already exists" >&2
      return 65
    fi
  done
}

case "$MODE" in
  check)
    DESCRIPTOR=$FOLDER/arci.yaml
    OUT=$STUDY/runs-run-6
    AUDIT=$STUDY/run-6-audit.jsonl
    LOG=$STUDY/run-6b-check.log
    require_fresh "$STUDY/run-6b-real.started" "$STUDY/run-6b.log" "$OUT" "$AUDIT" "$EXPOSURE"
    if [ ! -L "$LOG" ]; then rm -f "$LOG"; fi
    require_fresh "$LOG"
    ;;
  real)
    DESCRIPTOR=$FOLDER/arci.yaml
    OUT=$STUDY/runs-run-6
    AUDIT=$STUDY/run-6-audit.jsonl
    preflight_log=$(mktemp "$STUDY/.run-6-preflight.XXXXXX")
    trap 'cat "$preflight_log" >&2; rm -f "$preflight_log"' 0
    trap 'exit 1' HUP INT TERM
    LOG=$preflight_log
    require_fresh "$MARKER" "$STUDY/run-6b.log" "$OUT" "$AUDIT" "$EXPOSURE" 2>>"$LOG" || exit 65
    ;;
  *)
    echo "usage: RUN6_ENV=... sh run-6b.sh check|real" >&2
    exit 64
    ;;
esac

cd "$FOLDER"
unset OLLAMA_HOST PYTHONPATH PYTHONOPTIMIZE
export ARCI_QUICKSTART_BASELINE='ollama:qwen3.5:4b-mlx-ctx32k'
export ARCI_QUICKSTART_CANDIDATE='ollama:qwen3.5:4b-mlx-ctx32k'
export ARCI_QUICKSTART_TEMPERATURE=0.7
export LANGSMITH_TRACING=false
export LANGCHAIN_TRACING_V2=false
export ORDER_DESK_EMPTY_TEXT_AUDIT="$AUDIT"
export ORDER_DESK_FIRST_EXCHANGE_AUDIT="$EXPOSURE"
export NO_PROXY=127.0.0.1,localhost no_proxy=127.0.0.1,localhost
export PYTHONDONTWRITEBYTECODE=1

{
  echo "mode: $MODE"
  echo "start: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "working directory: $(pwd)"
  echo "descriptor: $DESCRIPTOR"
  echo "environment variables:"
  for name in ARCI_QUICKSTART_BASELINE ARCI_QUICKSTART_CANDIDATE ARCI_QUICKSTART_TEMPERATURE \
    LANGSMITH_TRACING LANGCHAIN_TRACING_V2 ORDER_DESK_EMPTY_TEXT_AUDIT ORDER_DESK_FIRST_EXCHANGE_AUDIT NO_PROXY; do
    printf '%s=' "$name"
    printenv "$name"
  done
  echo "ollama: $(ollama --version 2>&1 | head -1)"
  # Read the version and the named model's full digest from the running local server.
  if ! "$PYTHON" - "$MODEL" "$MODEL_DIGEST" 2>&1 <<'SERVER'
import json
import sys
from urllib.request import ProxyHandler, build_opener

opener = build_opener(ProxyHandler({}))
with opener.open("http://127.0.0.1:11434/api/version", timeout=5) as response:
    version = json.load(response)["version"]
print("ollama server version:", version)
if version != "0.32.14":
    sys.exit("expected Ollama server 0.32.14")
with opener.open("http://127.0.0.1:11434/api/tags", timeout=5) as response:
    models = json.load(response)["models"]
name, expected = sys.argv[1:]
digests = [model["digest"] for model in models if model["name"] == name]
print("server model digest:", name, *digests)
if digests != [expected]:
    sys.exit(f"expected {name} with digest {expected}")
SERVER
  then
    echo "refusing to start: server version or model digest check failed" | tee -a "$LOG" >&2
    exit 66
  fi
  echo "ollama ps before:"
  ollama ps 2>&1
  echo "power: $(pmset -g batt 2>/dev/null | head -1)"
} > "$LOG"

LISTED=$(ollama list 2>/dev/null | awk -v name="$MODEL" '$1 == name {print $2}')
echo "model id as listed: $MODEL $LISTED" >> "$LOG"
if [ "$LISTED" != "$MODEL_ID" ]; then
  echo "refusing to start: $MODEL has id '$LISTED', registered $MODEL_ID" | tee -a "$LOG" >&2
  exit 66
fi

# Independently hash the local tag manifest file.
models=${OLLAMA_MODELS:-"$HOME/.ollama/models"}
manifest=$models/manifests/registry.ollama.ai/library/${MODEL%:*}/${MODEL#*:}
if [ -r "$manifest" ]; then
  digest=$(shasum -a 256 < "$manifest")
  digest=${digest%% *}
  echo "model manifest sha256: $digest" >> "$LOG"
  if [ "$digest" != "$MODEL_DIGEST" ]; then
    echo "refusing to start: model manifest differs from $MODEL_DIGEST" | tee -a "$LOG" >&2
    exit 66
  fi
else
  echo "refusing to start: model manifest is unreadable: $manifest" | tee -a "$LOG" >&2
  exit 66
fi

# The registration must be committed, unchanged, and published before the first trial.
REGISTERED="PREREGISTRATION-run-6.md PREREGISTRATION-run-6-second-start.md run-6b-digests.sha256 $(cut -c67- "$STUDY/run-6b-digests.sha256" | tr '\n' ' ')"
HEAD_COMMIT=$(git -C "$STUDY" rev-parse HEAD)
echo "records commit (HEAD): $HEAD_COMMIT" >> "$LOG"
published_ancestor() (
  # The published history may be ahead of this checkout or its shallow boundary.
  scratch=$(mktemp -d) || exit 1
  trap 'rm -rf "$scratch"' 0
  remote=$(git -C "$STUDY" remote get-url origin) || exit 1
  git -C "$STUDY" clone --quiet --bare --single-branch --branch v2/phase0 --no-tags \
    --filter=blob:none -- "$remote" "$scratch/history" || exit 1
  tip=$(git -C "$scratch/history" rev-parse --verify 'refs/heads/v2/phase0^{commit}') || exit 1
  echo "published branch commit: $tip"
  git -C "$scratch/history" cat-file -e "$HEAD_COMMIT^{commit}" &&
    git -C "$scratch/history" merge-base --is-ancestor "$HEAD_COMMIT" "$tip"
)
if ! published_ancestor >> "$LOG" 2>&1; then
  echo "refusing to start: cannot verify HEAD is at or before the published branch tip" | tee -a "$LOG" >&2
  exit 67
fi
for file in $REGISTERED; do
  if ! git -C "$STUDY" cat-file -e "HEAD:./$file" 2>/dev/null; then
    echo "refusing to start: $file is not in HEAD" | tee -a "$LOG" >&2
    exit 67
  fi
done
# shellcheck disable=SC2086
if ! git -C "$STUDY" diff --quiet HEAD -- $REGISTERED; then
  echo "refusing to start: cannot verify registered files match HEAD" | tee -a "$LOG" >&2
  exit 67
fi
if grep -Fq '[[PREDICTIONS]]' "$STUDY/PREREGISTRATION-run-6.md"; then
  echo "refusing to start: final registration still contains [[PREDICTIONS]]" | tee -a "$LOG" >&2
  exit 67
else
  [ "$?" -eq 1 ] || exit 67
fi
echo "registered files: committed, unchanged and published" >> "$LOG"
echo "digests:" >> "$LOG"
(cd "$STUDY" && shasum -a 256 -c run-6b-digests.sha256) >> "$LOG" 2>&1

"$PYTHON" - "$FOLDER" >> "$LOG" 2>&1 <<'PREFLIGHT'
import importlib.metadata as metadata
import json
import sys
from pathlib import Path

if sys.flags.optimize != 0:
    sys.exit("refusing to start: Python optimization disables preflight assertions")

folder = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(folder))
import agent  # noqa: E402
import configuration  # noqa: E402

assert Path(agent.__file__).resolve() == folder / "agent.py", agent.__file__
for line in (folder / "tasks.jsonl").read_text().splitlines():
    configuration.validate_registration(json.loads(line))
baseline = agent.settings(False)
candidate = agent.settings(True)
assert baseline["system_prompt"] == candidate["system_prompt"]
print("preflight: agent module", agent.__file__)
expected_text = "The previous tool call returned an empty result. Repeat that call with the same input."
for arm, settings in (("baseline", baseline), ("candidate", candidate)):
    middleware = settings["middleware"]
    classes = [type(item).__name__ for item in middleware]
    expected = ["ScriptedOpening", "ToolRetryMiddleware", "ReturnToolErrors"]
    if arm == "baseline":
        expected.append("ReplaceEmptyLookup")
    assert classes == expected and type(middleware[0]) is agent.ScriptedOpening, (arm, classes)
    if arm == "baseline":
        replacement = middleware[-1]
        assert type(replacement) is agent.ReplaceEmptyLookup
        assert replacement.arm == arm and replacement.text == expected_text
    else:
        assert not any(isinstance(item, agent.ReplaceEmptyLookup) for item in middleware)
    print("preflight:", arm, "middleware", classes)
    print("preflight:", arm, "opening check_stock(order_id as sku), lookup_order(order_id)")
    print("preflight:", arm, "lookup reply", repr(expected_text if arm == "baseline" else "null"))
registered = {
    "agent-reliability-ci": "2.4.1", "langchain": "1.4.10", "langchain-core": "1.7.7",
    "langgraph": "1.2.20", "langgraph-prebuilt": "1.1.1", "langchain-ollama": "1.1.0",
    "ollama": "0.6.3", "pydantic": "2.14.3",
}
for name, version in registered.items():
    found = metadata.version(name)
    print("preflight:", name, found)
    assert found == version, (name, found, version)
import arci  # noqa: E402

assert arci.__version__ == "2.4.1", arci.__version__
assert Path(arci.__file__).resolve().is_relative_to(Path(sys.prefix).resolve()), arci.__file__
print("preflight: arci module", arci.__file__)
print("preflight: python", sys.version.split()[0])
assert sys.version.split()[0] == "3.13.12", sys.version
PREFLIGHT

if [ "$MODE" = check ]; then
  echo "check: every guard passed; nothing was started" | tee -a "$LOG"
  exit 0
fi

if [ "$MODE" = real ]; then
  if ! mkdir "$MARKER"; then
    echo "refusing to start: cannot claim $MARKER" >&2
    exit 65
  fi
  LOG=$STUDY/run-6b.log
  mv "$preflight_log" "$LOG"
  trap - 0 HUP INT TERM
  # Load the model once outside the experiment, so that the first trial is not a cold start.
  echo "warm-up call outside the experiment:" >> "$LOG"
  ollama run "$MODEL" "Reply with the single word ok." < /dev/null >> "$LOG" 2>&1
fi

echo "run start: $(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$LOG"
set +e
caffeinate -dims "$PYTHON" -m arci run "$DESCRIPTOR" --workers 1 --out "$OUT" < /dev/null >> "$LOG" 2>&1
STATUS=$?
set -e
{
  echo "arci exit $STATUS"
  echo "run end: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  if [ -f "$EXPOSURE" ]; then
    echo "first exchanges sha256: $(shasum -a 256 "$EXPOSURE" | cut -d' ' -f1)"
  fi
  "$PYTHON" "$FOLDER/exposure.py" "$OUT"/*/trials.jsonl "$EXPOSURE" ||
    echo "reading condition 2 failed: live exposure unverified"
  echo "ollama ps after:"
  ollama ps 2>&1 || echo "ollama ps failed; active context unverified"
  if [ -f "$AUDIT" ]; then
    echo "audit lines: $(grep -c . "$AUDIT")"
    "$PYTHON" - "$AUDIT" <<'AUDIT_COUNTS' || echo "audit counts per arm: unavailable"
import json
import sys

counts = {"baseline": 0, "candidate": 0}
with open(sys.argv[1], encoding="utf-8") as stream:
    for line in stream:
        if line.strip():
            counts[json.loads(line)["arm"]] += 1
for arm, count in counts.items():
    print(f"{arm} audit lines: {count}")
AUDIT_COUNTS
    echo "audit sha256: $(shasum -a 256 "$AUDIT" | cut -d' ' -f1)"
  else
    echo "audit lines: no audit file"
    echo "baseline audit lines: 0"
    echo "candidate audit lines: 0"
  fi
  echo "power: $(pmset -g batt 2>/dev/null | head -1)"
} >> "$LOG"
exit "$STATUS"
