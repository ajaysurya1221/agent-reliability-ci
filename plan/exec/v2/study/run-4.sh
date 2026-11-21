#!/bin/sh
# Run 4 of the order-desk study. One start per mode; it refuses to run twice.
# Smoke mode has been used. Its permanent run-4-smoke.started marker exists.
#
#   RUN4_ENV=/path/to/environment sh run-4.sh smoke    16 trials, another suite id, not evidence
#   RUN4_ENV=/path/to/environment sh run-4.sh check    every guard of the real run; starts nothing
#   RUN4_ENV=/path/to/environment sh run-4.sh real     the registered run
#
# Before any trial it takes a permanent one-start marker (a second start is refused, also a
# simultaneous one), and it refuses to go on unless: the output and audit paths do not
# exist; in real mode, the pre-registration and every registered file are committed
# unchanged in the commit that the published branch points to, and every registered file
# has its registered digest; the installed versions and the model id are the registered
# ones; the registered settings match the environment; and the agent module that will be
# imported is the one in the study folder with the message middleware in both arms. The tool is started through the environment's own Python.
set -eu

MODE=${1:?usage: RUN4_ENV=... sh run-4.sh smoke|check|real}
: "${RUN4_ENV:?set RUN4_ENV to the Python environment folder}"
STUDY=$(cd "$(dirname "$0")" && pwd)
FOLDER=$STUDY/order-desk-control-message
PYTHON=$RUN4_ENV/bin/python
MODEL=qwen3.5:4b-mlx-ctx32k
MODEL_ID=c01efed5a364
MODEL_DIGEST=c01efed5a36459ab6ffffa0b158636a014d8b30b4d5493167cba9916ed558430
MARKER=$STUDY/run-4-$MODE.started

case "$MODE" in
  smoke)
    DESCRIPTOR=$STUDY/order-desk-control-message-smoke/arci.yaml
    OUT=$STUDY/runs-run-4-smoke
    AUDIT=$STUDY/run-4-smoke-audit.jsonl
    LOG=$STUDY/run-4-smoke.log
    ;;
  check)
    DESCRIPTOR=$FOLDER/arci.yaml
    OUT=$STUDY/runs-run-4
    AUDIT=$STUDY/run-4-audit.jsonl
    LOG=$STUDY/run-4-check.log
    for path in "$STUDY/run-4-real.started" "$STUDY/run-4.log"; do
      if [ -e "$path" ] || [ -L "$path" ]; then
        echo "refusing to start: $path already exists" >&2
        exit 65
      fi
    done
    rm -f "$LOG"
    ;;
  real)
    DESCRIPTOR=$FOLDER/arci.yaml
    OUT=$STUDY/runs-run-4
    AUDIT=$STUDY/run-4-audit.jsonl
    LOG=$STUDY/run-4.log
    ;;
  *)
    echo "usage: RUN4_ENV=... sh run-4.sh smoke|check|real" >&2
    exit 64
    ;;
esac

# mkdir is atomic: of two starts at the same moment only one gets the marker. It is never
# removed.
if [ "$MODE" != check ] && ! mkdir "$MARKER" 2>/dev/null; then
  echo "refusing to start: $MARKER exists (this mode was started before)" >&2
  exit 65
fi
for path in "$OUT" "$AUDIT" "$LOG"; do
  if [ -e "$path" ]; then
    echo "refusing to start: $path already exists" >&2
    exit 65
  fi
done

cd "$FOLDER"
unset OLLAMA_HOST PYTHONPATH PYTHONOPTIMIZE
export ARCI_QUICKSTART_BASELINE='ollama:qwen3.5:4b-mlx-ctx32k'
export ARCI_QUICKSTART_CANDIDATE='ollama:qwen3.5:4b-mlx-ctx32k'
export ARCI_QUICKSTART_TEMPERATURE=0.7
export LANGSMITH_TRACING=false
export LANGCHAIN_TRACING_V2=false
export ORDER_DESK_EMPTY_TEXT_AUDIT="$AUDIT"
export PYTHONDONTWRITEBYTECODE=1

{
  echo "mode: $MODE"
  echo "start: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "records commit: $(git -C "$STUDY" rev-parse HEAD)"
  echo "working directory: $(pwd)"
  echo "descriptor: $DESCRIPTOR"
  echo "environment variables:"
  env | grep -E '^(LANGSMITH|LANGCHAIN|OLLAMA|PYTHONPATH|ARCI_|ORDER_DESK)' | sort
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

if [ "$MODE" != smoke ]; then
  # The registration must be committed, unchanged, and published before the first trial.
  REGISTERED="PREREGISTRATION-run-4.md run-4-digests.sha256 $(cut -c67- "$STUDY/run-4-digests.sha256" | tr '\n' ' ')"
  HEAD_COMMIT=$(git -C "$STUDY" rev-parse HEAD)
  PUBLISHED=$(git -C "$STUDY" ls-remote origin refs/heads/v2/phase0 | cut -f1)
  echo "published branch commit: $PUBLISHED" >> "$LOG"
  if [ "$PUBLISHED" != "$HEAD_COMMIT" ]; then
    echo "refusing to start: the published branch is at '$PUBLISHED', this checkout at $HEAD_COMMIT" | tee -a "$LOG" >&2
    exit 67
  fi
  for file in $REGISTERED; do
    if ! git -C "$STUDY" cat-file -e "HEAD:./$file" 2>/dev/null; then
      echo "refusing to start: $file is not in the published commit" | tee -a "$LOG" >&2
      exit 67
    fi
  done
  # shellcheck disable=SC2086
  if ! status=$(cd "$STUDY" && git status --porcelain -- $REGISTERED); then
    echo "refusing to start: git status failed" | tee -a "$LOG" >&2
    exit 67
  fi
  if [ -n "$status" ]; then
    echo "refusing to start: a registered file differs from the published commit" | tee -a "$LOG" >&2
    exit 67
  fi
  echo "registered files: committed, unchanged and published" >> "$LOG"
  echo "digests:" >> "$LOG"
  (cd "$STUDY" && shasum -a 256 -c run-4-digests.sha256) >> "$LOG" 2>&1
fi

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
expected_classes = ["ToolRetryMiddleware", "ReturnToolErrors", "ReplaceEmptyLookup"]
for arm, settings, text in (
    ("baseline", baseline, agent.EXPLICIT_TEXT),
    ("candidate", candidate, agent.NEUTRAL_TEXT),
):
    middleware = settings["middleware"]
    classes = [type(item).__name__ for item in middleware]
    assert classes == expected_classes, (arm, classes)
    replacement = middleware[-1]
    assert type(replacement) is agent.ReplaceEmptyLookup
    assert replacement.arm == arm and replacement.text == text, arm
    print("preflight:", arm, "middleware", classes)
    print("preflight:", arm, "message", repr(replacement.text))
assert agent.EXPLICIT_TEXT != agent.NEUTRAL_TEXT
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
  # Load the model once outside the experiment, so that the first trial is not a cold start.
  echo "warm-up call outside the experiment:" >> "$LOG"
  ollama run "$MODEL" "Reply with the single word ok." >> "$LOG" 2>&1
fi

echo "run start: $(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$LOG"
set +e
caffeinate -dims "$PYTHON" -m arci run "$DESCRIPTOR" --workers 1 --out "$OUT" >> "$LOG" 2>&1
STATUS=$?
set -e
{
  echo "arci exit $STATUS"
  echo "run end: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "ollama ps after:"
  ollama ps 2>&1
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
