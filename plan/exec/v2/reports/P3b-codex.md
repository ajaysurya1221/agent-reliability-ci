**Authorize the init-specific edit to `src/arci/cli.py` to finish P3b.** The brief names `init.py`, while [AGENTS.md](/Users/ajay/Developer/.arci-worktrees/wt-v2-integration/AGENTS.md) requires: “Edit only the files your brief says you own.” CLI wiring remains pending.

Implemented files:

- `examples/langchain_quickstart/`: `agent.py`, `tools.py`, `offline_model.py`, `check.py`, `tasks.jsonl`, `arci.yaml`, `README.md`.
- `src/arci/init.py`, `pyrightconfig.adapters.json`, `docs/recipes/langchain.md`.
- `tests/unit/adapters/test_quickstart.py`, `tests/unit/examples/test_langchain_quickstart.py`, `tests/unit/init/test_init_langchain.py`.

**Verified outcome:** example and generated scaffold both produce **BLOCK, round 1**, with successful gate recomputation. Latest wall times: **50.70 s** and **52.02 s**.

Checks:

| Command | Result |
|---|---|
| New tests, excluding pending CLI test | **18 passed** |
| `.venv/bin/pytest tests/unit/adapters tests/unit/examples tests/unit/init tests/unit/recipes -q` | **4 failures**; [log](/tmp/p3b-focused.log) |
| `.venv/bin/pytest -q` | **66 failures**, including sandbox socket/process restrictions and unwired CLI; [log](/tmp/p3b-full.log) |
| Ruff format/check; core and adapter basedpyright | Clean; both type checks: `0 errors, 0 warnings, 0 notes` |
| `shasum -a 256 -c FROZEN.sha256` | **64 OK** |

Python code lines, excluding blanks/comments and including docstrings: `agent.py` **46**, `tools.py` **52**, `offline_model.py` **71**, `check.py` **18**.

The orchestrator must add `"examples/langchain_quickstart"` to frozen `pyproject.toml`’s `[tool.basedpyright].exclude`. No frozen files were changed. Core checking without LangChain and real-model execution remain unverified; acceptance is **not clean**.

Next: authorize the init-specific `src/arci/cli.py` edit.