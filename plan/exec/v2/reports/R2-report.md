R2 implemented. Different model IDs retain one retry in both arms; equal IDs preserve the retry-change demo.

Changed files:

- `examples/langchain_quickstart/{agent.py,register.py,README.md}`
- `src/arci/init.py`
- [model-swap.md](/Users/ajay/Developer/.arci-worktrees/wt-v2.1/docs/recipes/model-swap.md)
- `tests/unit/examples/{test_model_swap_registration.py,test_model_swap_adapter.py}`

Labels use full model IDs unchanged—the schema permits them—and restore `retry` / `no-retry` for equal IDs. Templates remain byte-synchronized. Existing tests were unchanged.

| Command | Result / final output |
|---|---|
| `.venv/bin/pytest tests/unit/examples tests/unit/init tests/unit/docs -q` | 192 passed; guardrail test failed with `PermissionError`. [Log](/tmp/arci-r2-focused.log) |
| `LANGSMITH_TRACING=false .venv/bin/pytest -q` | 2,802 passed, 65 failures; final failure: `test_diff_minimize_bundle_and_replay`. [Log](/tmp/arci-r2-full.log) |
| Adapter-env `pytest tests/unit/examples tests/unit/init tests/unit/adapters -q` | 520 passed; same guardrail permission failure. [Log](/tmp/arci-r2-adapter.log) |
| `.venv/bin/ruff format --check . && .venv/bin/ruff check . && .venv/bin/basedpyright` | `557 files already formatted`; `All checks passed!`; `0 errors, 0 warnings, 0 notes` |
| `shasum -a 256 -c FROZEN.sha256` | All 65 OK; last line: `uv.lock: OK` |

All nine new regressions passed. Both offline end-to-end tests preserved **BLOCK: baseline 96/96, candidate 48/96**.

Remaining limit: the 65 failures match the known socket/`ps` sandbox restrictions; no additional failure category identified. Real-provider behavior remains untested.

Next: the orchestrator reruns acceptance outside the sandbox.