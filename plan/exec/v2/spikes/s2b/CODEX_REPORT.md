Open [FINDINGS.md](/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/spikes/s2b/FINDINGS.md): **implementation complete; acceptance FAIL.** Final runs both produced **17 OK, 1 FAIL**, with identical check verdicts and **53 matching sealed trial hashes**.

Created only under `plan/exec/v2/spikes/s2b/`: the six requested deliverables, `probe_app.py`, `scripted_model.py`, and scope/verification artifacts in `out/`, `quality/`, and `.evalopt/`.

| Check | Result |
|---|---|
| 1. Native parity | **FAIL:** native/injected body counts differ; `ValueError` becomes `ToolFault`. |
| 2. Exactly once | OK, including injected and real-error retries. |
| 3. Argument validation | OK; identical native feedback across all three middleware configurations. |
| 4. Built-in faults | OK; all three verified in recorded events. |
| 5. Budget | OK; FAIL/budget, with completed snapshots proving no deadlock. |
| 6. Multiple calls | OK; 20 identical ordered repetitions; replay REPRODUCED. |
| 7. Unsupported shapes | Live ERROR verified. Async replay still FAIL/crash; missing kernel support documented. |
| 8. Message shapes | OK; byte-identical string/dict observations and list-block answer capture. |
| 9. Replay answer | Limitation demonstrated: altered answers still report REPRODUCED. |
| 10. Cost | Final median **0.9998 s**, 12 graded trials; substantial variation across runs. |
| 11. User burden | `user_app.py`: 44 lines; `user_check.py`: 7. |
| 12. Scope/repeatability | 54 frozen hashes pass; 735 inventoried outside-plan files unchanged; final runs match. |

Exact commands and final lines:

```sh
PYTHONDONTWRITEBYTECODE=1 LANGSMITH_TRACING=false PYTHONPATH=src:plan/exec/v2/spikes/s2b /Users/ajay/Developer/.arci-worktrees/v2-spike-venv/bin/python -B plan/exec/v2/spikes/s2b/run_spike.py
# Both final runs: RESULT: 17 OK, 1 FAIL; exit 1

.venv/bin/ruff format --no-cache --check plan/exec/v2/spikes/s2b
# 8 files already formatted

.venv/bin/ruff check --no-cache plan/exec/v2/spikes/s2b
# All checks passed!

.venv/bin/basedpyright --pythonpath /Users/ajay/Developer/.arci-worktrees/v2-spike-venv/bin/python plan/exec/v2/spikes/s2b
# 0 errors, 0 warnings, 0 notes

shasum -a 256 -c FROZEN.sha256
# uv.lock: OK
```

The user writes `make_tools` with the real `lookup` body, `build_baseline`, `build_candidate`, the `toolset/baseline/candidate` glue assignment, independent `check`, and `arci.yaml`.

All-green acceptance could not be met without relaxing parity. No assertions were relaxed and no product code changed. Remaining risks include replay answer verification, unsupported replay classification, double validation, and seed-independent replay schemas. The exact proposed unfrozen ToolBox extension is documented in the findings.