#!/bin/sh
# Run 3 of the order-desk study. One start per mode; it refuses to run twice.
#
#   RUN3_ENV=/path/to/environment sh run-3.sh smoke    16 trials, another suite id, not evidence
#   RUN3_ENV=/path/to/environment sh run-3.sh check    every guard of the real run; starts nothing
#   RUN3_ENV=/path/to/environment sh run-3.sh real     the registered run
#
# Before any trial it takes a permanent one-start marker (a second start is refused, also a
# simultaneous one), and it refuses to go on unless: the output and audit paths do not
# exist; in real mode, the pre-registration and every registered file are committed
# unchanged in the commit that the published branch points to, and every registered file
# has its registered digest; the installed versions and the model id are the registered
# ones; the registered settings match the environment; and the agent module that will be
# imported is the one in the study folder with the message middleware in the baseline arm
# only. The tool is started through the environment's own Python.
set -eu

MODE=${1:?usage: RUN3_ENV=... sh run-3.sh smoke|check|real}
: "${RUN3_ENV:?set RUN3_ENV to the Python environment folder}"
STUDY=$(cd "$(dirname "$0")" && pwd)
FOLDER=$STUDY/order-desk-empty-message
PYTHON=$RUN3_ENV/bin/python
MODEL=qwen3.5:4b-mlx-ctx32k
MODEL_ID=c01efed5a364
MARKER=$STUDY/run-3-$MODE.started

case "$MODE" in
  smoke)
    DESCRIPTOR=$STUDY/order-desk-empty-message-smoke/arci.yaml
    OUT=$STUDY/runs-run-3-smoke
    AUDIT=$STUDY/run-3-smoke-audit.jsonl
    LOG=$STUDY/run-3-smoke.log
    ;;
  check)
    DESCRIPTOR=$FOLDER/arci.yaml
    OUT=$STUDY/runs-run-3
    AUDIT=$STUDY/run-3-audit.jsonl
    LOG=$STUDY/run-3-check.log
    rm -f "$LOG"
    ;;
  real)
    DESCRIPTOR=$FOLDER/arci.yaml
    OUT=$STUDY/runs-run-3
    AUDIT=$STUDY/run-3-audit.jsonl
    LOG=$STUDY/run-3.log
    ;;
  *)
    echo "usage: RUN3_ENV=... sh run-3.sh smoke|check|real" >&2
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
unset OLLAMA_HOST PYTHONPATH
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

if [ "$MODE" != smoke ]; then
  # The registration must be committed, unchanged, and published before the first trial.
  REGISTERED="PREREGISTRATION-run-3.md run-3-digests.sha256 $(cut -c67- "$STUDY/run-3-digests.sha256" | tr '\n' ' ')"
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
  if [ -n "$(cd "$STUDY" && git status --porcelain -- $REGISTERED)" ]; then
    echo "refusing to start: a registered file differs from the published commit" | tee -a "$LOG" >&2
    exit 67
  fi
  echo "registered files: committed, unchanged and published" >> "$LOG"
  echo "digests:" >> "$LOG"
  (cd "$STUDY" && shasum -a 256 -c run-3-digests.sha256) >> "$LOG" 2>&1
fi

"$PYTHON" - "$FOLDER" >> "$LOG" 2>&1 <<'PREFLIGHT'
import importlib.metadata as metadata
import json
import sys
from pathlib import Path

folder = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(folder))
import agent  # noqa: E402
import configuration  # noqa: E402

assert Path(agent.__file__).resolve().parent == folder, agent.__file__
for line in (folder / "tasks.jsonl").read_text().splitlines():
    configuration.validate_registration(json.loads(line))
baseline = [type(item).__name__ for item in agent.settings(False)["middleware"]]
candidate = [type(item).__name__ for item in agent.settings(True)["middleware"]]
assert baseline[-1] == "ExplainEmptyLookup" and baseline.count("ExplainEmptyLookup") == 1, baseline
assert "ExplainEmptyLookup" not in candidate and baseline[:-1] == candidate, (baseline, candidate)
print("preflight: agent module", agent.__file__)
print("preflight: baseline middleware", baseline)
print("preflight: candidate middleware", candidate)
print("preflight: message", repr(agent.EMPTY_LOOKUP_TEXT))
registered = {
    "agent-reliability-ci": "2.4.0", "langchain": "1.4.10", "langchain-core": "1.7.7",
    "langgraph": "1.2.20", "langgraph-prebuilt": "1.1.1", "langchain-ollama": "1.1.0",
    "ollama": "0.6.3", "pydantic": "2.14.3",
}
for name, version in registered.items():
    found = metadata.version(name)
    print("preflight:", name, found)
    assert found == version, (name, found, version)
import arci  # noqa: E402

assert arci.__version__ == "2.4.0", arci.__version__
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
    echo "audit sha256: $(shasum -a 256 "$AUDIT" | cut -d' ' -f1)"
  else
    echo "audit lines: no audit file"
  fi
  echo "power: $(pmset -g batt 2>/dev/null | head -1)"
} >> "$LOG"
exit "$STATUS"
