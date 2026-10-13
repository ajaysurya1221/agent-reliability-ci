#!/usr/bin/env bash
# Track B stopwatch (docs/measurement/ttfv-protocol.md section 4) on the python_agent sample tree,
# maintainer/AI-labelled run. Deviation: the harness denies the README's `uv tool` install route,
# so the install step is `uv venv` + `uv pip install <spec>` and `arci` comes from that venv's bin.
# usage: ttfv_track_b.sh <package spec> <sample tree dir> <out.json>
set -u
SPEC=$1; TREE=$2; OUT=$3
stamp() { date -u +%Y-%m-%dT%H:%M:%SZ; }
WORK=$(mktemp -d -t ttfv-b); cd "$WORK" || exit 1
export UV_NO_PROGRESS=1
cp -R "$TREE" checkout && cd checkout || exit 1
[ -f arci.yaml ] && mv arci.yaml arci.yaml.shipped
T_README=$(stamp)
T_INSTALL_START=$(stamp)
uv venv -q "$WORK/venv" && uv pip install -q --python "$WORK/venv/bin/python" "$SPEC" || { echo "install failed"; exit 1; }
export PATH="$WORK/venv/bin:$PATH"
command -v arci >/dev/null || { echo "arci not on PATH"; exit 1; }
T_INSTALL_DONE=$(stamp)
T_SCAFFOLD_START=$(stamp)
arci init checkout-retry --baseline app.v1:run --candidate app.v2:run --toolset tests.world:make_world --oracle tests.world:passed --task '{"order_id": "order-7"}' --fault tool_timeout:reserve:0 > init.out 2> init.err; INIT_EXIT=$?
T_DESCRIPTOR=$(stamp)
[ $INIT_EXIT -eq 0 ] && [ -f arci.yaml ] || { echo "init failed ($INIT_EXIT)"; cat init.err; exit 1; }
T_RUN_START=$(stamp)
arci run arci.yaml > run.out 2> run.err; RUN_EXIT=$?
T_VERDICT=$(stamp)
VERDICT_LINE=$(grep -m1 '^VERDICT: ' run.out)
STORE=runs/checkout-retry
ls "$STORE" > store.ls 2>&1; SHA1=$(shasum -a 256 "$STORE/decision.json" | cut -d' ' -f1)
# No pipeline here: `arci gate | grep` would leave the gate's exit status in `${PIPESTATUS[0]}`,
# which is bash-only (unset under zsh). Redirect to a file and read `$?` directly instead; protocol
# 4.3 needs the gate's exit code to equal the run's.
arci gate "$STORE" > gate.out 2> gate.err; GATE_EXIT=$?
GATE_LINE=$(grep -m1 '^VERDICT: ' gate.out)
SHA2=$(shasum -a 256 "$STORE/decision.json" | cut -d' ' -f1)
T_STORE=$(stamp)
AGENT_EXEC=$(python3 -c "import json,sys; print(sum(json.loads(l)['usage']['wall_seconds'] for l in open(sys.argv[1]) if l.strip()))" "$STORE/trials.jsonl" 2>/dev/null || echo null)
python3 - "$OUT" "$T_README" "$T_INSTALL_START" "$T_INSTALL_DONE" "$T_SCAFFOLD_START" "$T_DESCRIPTOR" "$T_RUN_START" "$T_VERDICT" "$T_STORE" "$RUN_EXIT" "$VERDICT_LINE" "$GATE_LINE" "$SHA1" "$SHA2" "$AGENT_EXEC" "$SPEC" "$WORK" "$GATE_EXIT" <<'PY'
import json, sys, datetime as dt, os
(out, readme, i0, i1, s0, s1, r0, r1, st, run_exit, vline, gline, sha1, sha2, agent_exec, spec, work, gate_exit) = sys.argv[1:]
p = lambda s: dt.datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ")
d = lambda a, b: (p(b) - p(a)).total_seconds()
store = os.path.join(work, "checkout", "runs", "checkout-retry")
files_ok = all(os.path.exists(os.path.join(store, f)) for f in ("manifest.json", "trials.jsonl", "decision.json"))
validated = bool(vline) and vline == gline and gate_exit == run_exit and sha1 == sha2 and files_ok and "ERROR" not in vline
rec = {"track": "B", "label": "maintainer/AI run (orchestrator); not a cold reader", "package": spec,
       "project": "sample (examples/recipes/python_agent)",
       "install_method": "uv venv + uv pip install (the uv tool route is denied in this harness)",
       "timestamps": {"readme_opened": readme, "install_start": i0, "install_done": i1, "scaffold_start": s0,
                      "descriptor_written": s1, "run_start": r0, "verdict_printed": r1, "store_validated": st},
       "durations_seconds": {"install": d(i0, i1), "scaffold": d(s0, s1), "run": d(r0, r1),
                             "total_to_store_validated": d(readme, st),
                             "agent_execution": None if agent_exec == "null" else float(agent_exec)},
       "outcome": {"verdict_line": vline, "run_exit": int(run_exit), "gate_line": gline, "decision_sha256": sha1,
                   "store_validated": validated,
                   "trials_started": os.path.getsize(os.path.join(store, "trials.jsonl")) > 0 if files_ok else False},
       "workdir": work}
json.dump(rec, open(out, "w"), indent=1)
print(json.dumps(rec["durations_seconds"]), vline, "validated" if validated else "NOT validated")
PY
