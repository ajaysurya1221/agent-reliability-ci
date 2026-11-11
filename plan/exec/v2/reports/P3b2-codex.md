Review the [verification report](/private/tmp/p3b2-verification.md): **P3b2 is complete within the permitted sandbox exceptions.**

Example: **BLOCK, round 1, 192 trials, 49.13 seconds**. CLI scaffold: **54.68 seconds**, same verdict. README now states the first-run timing.

| Check | Result |
|---|---|
| Focused pytest | `473 passed, 3 failed, 1 warning` |
| Full pytest | 2,823 passed; 65 failed; 2 skipped |
| Ruff format/check | `517 files already formatted`; `All checks passed!` |
| Core and adapter basedpyright | Both: `0 errors, 0 warnings, 0 notes` |
| Frozen hashes | All 64 OK; tail: `uv.lock: OK` |

All quickstart tests pass. Remaining failures are existing socket/`ps` restrictions; [every failing test is named here](/private/tmp/p3b2-failures.txt). Exact commands and tails are in the report.

Final P3b file list:

- `src/arci/cli.py`, `src/arci/init.py`, `pyrightconfig.adapters.json`
- `docs/recipes/langchain.md`
- `examples/langchain_quickstart/`: `README.md`, `agent.py`, `tools.py`, `check.py`, `offline_model.py`, `tasks.jsonl`, `arci.yaml`
- `tests/unit/adapters/test_quickstart.py`, `tests/unit/examples/test_langchain_quickstart.py`, `tests/unit/init/test_init_langchain.py`

This pass changed only the CLI, README, and init tests. Frozen files and orchestrator edits were preserved. Example Python line counts, including blanks: agent 63, tools 64, check 22, offline model 80.

Next: the orchestrator reruns acceptance outside the sandbox and in the core-only environment.
