Review [FINDINGS.md](/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/spikes/s2/FINDINGS.md): **all nine technical checks pass; full acceptance fails the scope check.**

Created only inside `plan/exec/v2/spikes/s2/`: `adapter_spike.py`, `arci.yaml`, `run_spike.py`, `FINDINGS.md`, initial scope inventories, and evidence under `out/`.

Two consecutive runs produced identical check verdicts and all 12 identical sealed trial hashes. Both exited **1** because concurrent edits appeared in four outside-owned paths. I did not modify those files.

| Question | Result |
|---|---|
| 1. Exactly once | ToolBox alone executes tools; body counts verified. Middleware never calls `handler`. |
| 2. Fault visibility | Error ToolMessages reach the model: baseline 6 PASS, candidate 6 FAIL. ReplayMiss remains ERROR/replay_miss. |
| 3. Fault injection | Each of the three faults fired four times in recorded events. |
| 4. Budget | One-call budget produces FAIL/budget; retry emits no additional tool-start event. |
| 5. Final state | Snapshot controls grading despite contradictory return claims. Erasing captured output causes FAIL. |
| 6. Replay/diff | Failing bundle returns REPRODUCED. Diff identifies retry versus termination after the timeout. |
| 7. Parallel calls | Native LangChain overlaps two tool bodies. Adapter rejects the response before either executes. |
| 8. Unsupported shapes | Command, non-JSON arguments/results, and async invocation produce explicit rejection evidence. |
| 9. Startup cost | Latest median across ten children: **0.7476 seconds** launch/import/exit; **0.6826 seconds** imports. |

Exact verification command, run twice on the final source:

```sh
PYTHONDONTWRITEBYTECODE=1 LANGSMITH_TRACING=false LANGCHAIN_TRACING_V2=false PYTHONPATH=src:plan/exec/v2/spikes/s2 /Users/ajay/Developer/.arci-worktrees/v2-spike-venv/bin/python -B plan/exec/v2/spikes/s2/run_spike.py
```

Last check: `OK repeatability: previous invocation has identical check verdicts and all 12 sealed trial hashes`. Exit **1**, solely from scope.

Quality commands:

```sh
.venv/bin/ruff format --no-cache plan/exec/v2/spikes/s2
.venv/bin/ruff format --no-cache --check plan/exec/v2/spikes/s2
.venv/bin/ruff check --no-cache plan/exec/v2/spikes/s2
.venv/bin/basedpyright --pythonpath /Users/ajay/Developer/.arci-worktrees/v2-spike-venv/bin/python plan/exec/v2/spikes/s2
shasum -a 256 -c FROZEN.sha256
git status --short
```

Results: `3 files left unchanged`; `3 files already formatted`; `All checks passed!`; `0 errors, 0 warnings, 0 notes`; all **54 frozen hashes passed**, ending `uv.lock: OK`. Git status retains pre-existing untracked files. Exact outputs are preserved in [validation.json](/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/spikes/s2/out/validation.json).

Risks: scripted-model evidence does not establish hosted-model replay; the proposed product API still needs explicit session binding and tool-schema validation. The full product suite was not run.

Next: inspect the four concurrent changes in [scope-differences.json](/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/spikes/s2/out/run-0004/scope-differences.json).